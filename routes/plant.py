"""Processing Plant — runs, analytics, expenses, outside farmers."""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from database.db import query, execute, get_all_farms
from datetime import date, timedelta

plant_bp = Blueprint('plant', __name__)
EXPENSE_CATEGORIES = ['Maintenance', 'Casual Labour', 'Consumables', 'Other']


def _calc_run(own_gallons, outside_gallons, outside_fees):
    """
    Input: gallons (user enters gallons; litres = gallons × 25).
    Gross = own oil revenue + outside fees.
    Electricity on total combined gallons.
    Net = gross - electricity. Split 70/30.
    """
    own_lit     = own_gallons * 25.0
    out_lit     = outside_gallons * 25.0
    total_gal   = own_gallons + outside_gallons
    total_lit   = total_gal * 25.0

    own_oil_rev = own_gallons * 40.0
    gross_rev   = own_oil_rev + outside_fees
    electricity = (total_gal / 20.0) * 120.0
    net_rev     = gross_rev - electricity
    operator    = net_rev * 0.30
    company     = net_rev * 0.70

    return dict(
        own_farms_gallons       = round(own_gallons,  2),
        own_farms_litres        = round(own_lit,      2),
        outside_farmers_gallons = round(outside_gallons, 2),
        outside_farmers_litres  = round(out_lit,      2),
        total_output_gallons    = round(total_gal,    2),
        total_output_litres     = round(total_lit,    2),
        own_oil_revenue         = round(own_oil_rev,  2),
        gross_revenue           = round(gross_rev,    2),
        electricity_cost        = round(electricity,   2),
        net_revenue             = round(net_rev,      2),
        operator_pay            = round(operator,     2),
        company_revenue         = round(company,      2),
        outside_farmer_fees     = round(outside_fees,  2),
    )


@plant_bp.route('/')
def index():
    today            = date.today()
    this_month_start = today.replace(day=1).isoformat()
    last_month_start = (today.replace(day=1) - timedelta(days=1)).replace(day=1).isoformat()
    year_start       = today.replace(month=1, day=1).isoformat()
    prev_year_start  = (today.replace(month=1, day=1) - timedelta(days=1)).replace(month=1, day=1).isoformat()

    date_from = request.args.get('date_from', '')
    date_to   = request.args.get('date_to', '')

    sql    = "SELECT * FROM processing_runs WHERE 1=1"
    params = []
    if date_from:
        sql += " AND date>=?"; params.append(date_from)
    if date_to:
        sql += " AND date<=?"; params.append(date_to)
    sql += " ORDER BY date DESC"
    runs = query(sql, params)

    def totals(from_d=None, to_d=None):
        w, p = _where(from_d, to_d)
        return query(f"""
            SELECT
                COALESCE(SUM(own_farms_litres),0)       AS own_litres,
                COALESCE(SUM(outside_farmers_litres),0) AS out_litres,
                COALESCE(SUM(total_output_litres),0)    AS total_litres,
                COALESCE(SUM(total_output_gallons),0)   AS total_gallons,
                COALESCE(SUM(own_farms_litres),0)       AS own_litres_sum,
                COALESCE(SUM(outside_farmers_litres),0) AS out_litres_sum,
                COALESCE(SUM(own_farms_gallons),0)      AS own_gallons,
                COALESCE(SUM(outside_farmers_gallons),0)AS out_gallons,
                COALESCE(SUM(gross_revenue),0)          AS gross_revenue,
                COALESCE(SUM(electricity_cost),0)       AS electricity_cost,
                COALESCE(SUM(net_revenue),0)            AS net_revenue,
                COALESCE(SUM(operator_pay),0)           AS operator_pay,
                COALESCE(SUM(company_revenue),0)        AS company_revenue,
                COALESCE(SUM(outside_farmer_fees),0)    AS outside_farmer_fees,
                COALESCE(SUM(cash_collected),0)         AS cash_collected,
                COALESCE(SUM(cash_outstanding),0)       AS cash_outstanding,
                COUNT(*)                                AS run_count
            FROM processing_runs{w}
        """, p, one=True)

    def plant_other_exp(from_d=None, to_d=None):
        w, p = _where(from_d, to_d)
        return _sum(f"SELECT COALESCE(SUM(amount),0) FROM plant_expenses{w}", p)

    def total_income_from(t):
        # Gross revenue = all plant income (own oil sales + outside farmer fees)
        return t['gross_revenue'] or 0

    def total_expenses_from(t, from_d=None, to_d=None):
        # Costs = electricity + operator pay + other plant expenses
        return (t['electricity_cost'] or 0) + (t['operator_pay'] or 0) + plant_other_exp(from_d, to_d)

    all_t  = totals()
    this_m = totals(this_month_start)
    last_m = totals(last_month_start, this_month_start)
    ytd_t  = totals(year_start)
    prev_t = totals(prev_year_start, year_start)

    all_income    = total_income_from(all_t)
    all_expenses  = total_expenses_from(all_t)
    all_net       = all_income - all_expenses

    this_m_income = total_income_from(this_m)
    this_m_exp    = total_expenses_from(this_m, this_month_start)
    this_m_net    = this_m_income - this_m_exp
    last_m_income = total_income_from(last_m)
    last_m_exp    = total_expenses_from(last_m, last_month_start, this_month_start)
    last_m_net    = last_m_income - last_m_exp
    ytd_income    = total_income_from(ytd_t)
    ytd_exp       = total_expenses_from(ytd_t, year_start)
    prior_income  = total_income_from(prev_t)

    mom_income_chg = _pct_change(last_m_income, this_m_income)
    mom_exp_chg    = _pct_change(last_m_exp, this_m_exp)
    mom_net_chg    = _pct_change(last_m_net, this_m_net)
    yoy_income_chg = _pct_change(prior_income, ytd_income)

    # Monthly chart
    monthly_runs = query("""
        SELECT strftime('%Y-%m', date) AS month,
               SUM(own_farms_litres)        AS own_litres,
               SUM(outside_farmers_litres)  AS out_litres,
               SUM(total_output_litres)     AS litres,
               SUM(total_output_gallons)    AS gallons,
               SUM(gross_revenue)           AS gross_revenue,
               SUM(electricity_cost)        AS electricity_cost,
               SUM(company_revenue)         AS company_revenue,
               SUM(outside_farmer_fees)     AS outside_fees,
               SUM(operator_pay)            AS operator_pay,
               SUM(own_farms_gallons)       AS own_gallons,
               SUM(outside_farmers_gallons) AS out_gallons,
               SUM(cash_collected)          AS cash_collected,
               SUM(cash_outstanding)        AS cash_outstanding,
               COUNT(*)                     AS run_count
        FROM processing_runs
        WHERE date >= DATE('now','-18 months')
        GROUP BY month ORDER BY month
    """)
    monthly_exp = query("""
        SELECT strftime('%Y-%m', date) AS month, SUM(amount) AS total
        FROM plant_expenses WHERE date >= DATE('now','-18 months')
        GROUP BY month ORDER BY month
    """)
    exp_map = {r['month']: r['total'] for r in monthly_exp}

    monthly_chart = []
    for r in monthly_runs:
        m   = r['month']
        inc = r['gross_revenue'] or 0
        exp = (r['operator_pay'] or 0) + (r['electricity_cost'] or 0) + (exp_map.get(m) or 0)
        own_g   = round(r['own_gallons'] if r['own_gallons'] is not None else 0, 2)
        total_g = round(r['gallons']     if r['gallons']     is not None else 0, 2)
        monthly_chart.append({
            'month'           : m,
            'own_litres'      : round(r['own_litres'] or 0, 1),
            'out_litres'      : round(r['out_litres'] or 0, 1),
            'litres'          : round(r['litres'] or 0, 1),
            'gallons'         : total_g,
            'own_gal'         : own_g,
            'out_gal'         : round(r['out_gallons'] if r['out_gallons'] is not None else 0, 2),
            'gross_revenue'   : round(r['gross_revenue'] or 0, 2),
            'electricity'     : round(r['electricity_cost'] or 0, 2),
            'company_revenue' : round(r['company_revenue'] or 0, 2),
            'outside_fees'    : round(r['outside_fees'] or 0, 2),
            'operator_pay'    : round(r['operator_pay'] or 0, 2),
            'income'          : round(inc, 2),
            'expenses'        : round(exp, 2),
            'net'             : round(inc - exp, 2),
            'cash_collected'  : round(r['cash_collected'] or 0, 2),
            'cash_outstanding': round(r['cash_outstanding'] or 0, 2),
            'run_count'       : r['run_count'] or 0,
            'own_farm_pct'    : round((own_g / total_g * 100), 1) if total_g > 0 else 0,
        })

    exp_by_cat = query("""
        SELECT category, COALESCE(SUM(amount),0) AS total
        FROM plant_expenses GROUP BY category ORDER BY total DESC
    """)

    # Monthly own-farm % contribution
    for m in monthly_chart:
        total_g = m.get('gallons', 0) or 0
        own_g   = m.get('own_gal', 0) or 0
        m['own_farm_pct'] = round((own_g / total_g * 100), 1) if total_g > 0 else 0

    # All-time own farm %
    all_total_gal = float(all_t['total_gallons'] or 0)
    all_own_gal   = float(all_t['own_gallons'] or 0)
    all_own_pct   = round((all_own_gal / all_total_gal * 100), 1) if all_total_gal > 0 else 0

    kpis, actions = _build_kpis_and_actions(
        all_income, all_expenses, all_net,
        this_m_income, this_m_exp, this_m_net,
        last_m_income, last_m_net,
        mom_income_chg, mom_exp_chg, mom_net_chg,
        yoy_income_chg, all_t, monthly_chart,
    )

    other_expenses = query("SELECT COALESCE(SUM(amount),0) AS t FROM plant_expenses", one=True)

    return render_template('plant/index.html',
        runs=runs, totals=all_t, other_expenses=other_expenses,
        filters=dict(date_from=date_from, date_to=date_to),
        all_own_pct=all_own_pct, all_own_gal=all_own_gal, all_total_gal=all_total_gal,
        all_income=all_income, all_expenses=all_expenses, all_net=all_net,
        this_m_income=this_m_income, this_m_exp=this_m_exp, this_m_net=this_m_net,
        last_m_income=last_m_income, last_m_exp=last_m_exp, last_m_net=last_m_net,
        ytd_income=ytd_income, ytd_exp=ytd_exp,
        mom_income_chg=mom_income_chg, mom_exp_chg=mom_exp_chg,
        mom_net_chg=mom_net_chg, yoy_income_chg=yoy_income_chg,
        monthly_chart=monthly_chart,
        exp_by_cat=[dict(r) for r in exp_by_cat],
        kpis=kpis, actions=actions, today=today,
    )


@plant_bp.route('/run/add', methods=['GET', 'POST'])
def add_run():
    farms = get_all_farms()
    if request.method == 'POST':
        own_gallons    = float(request.form.get('own_farms_gallons_input') or 0)
        outside_gallons= float(request.form.get('outside_farmers_gallons_input') or 0)
        outside_fees   = float(request.form.get('outside_farmer_fees') or 0)
        own_bunches    = int(request.form.get('own_farms_bunches') or 0)
        out_bunches    = int(request.form.get('outside_farmers_bunches') or 0)

        c = _calc_run(own_gallons, outside_gallons, outside_fees)

        cash_collected   = float(request.form.get('cash_collected') or 0)
        # Total billed = gross revenue (full factory income — what is owed to the plant)
        total_billed     = c['gross_revenue']
        cash_outstanding = max(0, total_billed - cash_collected)

        run_id = execute("""
            INSERT INTO processing_runs (
                date,
                own_farms_litres, own_farms_gallons, own_farms_bunches,
                outside_farmers_litres, outside_farmers_gallons, outside_farmers_bunches,
                total_output_litres, total_output_gallons,
                gross_revenue, outside_farmer_fees,
                electricity_cost, net_revenue,
                operator_pay, company_revenue,
                cash_collected, cash_outstanding,
                notes
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            request.form['date'],
            c['own_farms_litres'], c['own_farms_gallons'], own_bunches,
            c['outside_farmers_litres'], c['outside_farmers_gallons'], out_bunches,
            c['total_output_litres'], c['total_output_gallons'],
            c['gross_revenue'], outside_fees,
            c['electricity_cost'], c['net_revenue'],
            c['operator_pay'], c['company_revenue'],
            cash_collected, cash_outstanding,
            request.form.get('notes', ''),
        ))

        # Link contributing own farms
        farm_ids     = request.form.getlist('contributing_farm_ids')
        farm_bunches = request.form.getlist('contributing_bunches')
        for fid, bunches in zip(farm_ids, farm_bunches):
            if fid and bunches:
                execute("""
                    INSERT INTO processing_run_farms (run_id, farm_id, bunches_contributed)
                    VALUES (?,?,?)
                """, (run_id, fid, bunches))

        flash('Processing run logged.', 'success')
        return redirect(url_for('plant.index'))

    farms_list = [dict(f) for f in farms]
    return render_template('plant/add_run.html', farms=farms, farms_json=farms_list)


@plant_bp.route('/run/<int:run_id>')
def run_detail(run_id):
    run = query("SELECT * FROM processing_runs WHERE id=?", (run_id,), one=True)
    if not run:
        flash('Run not found.', 'error')
        return redirect(url_for('plant.index'))
    contributing = query("""
        SELECT prf.*, f.name AS farm_name FROM processing_run_farms prf
        JOIN farms f ON f.id=prf.farm_id WHERE prf.run_id=?
    """, (run_id,))
    return render_template('plant/run_detail.html', run=run, contributing=contributing)


@plant_bp.route('/run/<int:run_id>/edit', methods=['GET', 'POST'])
def edit_run(run_id):
    run = query("SELECT * FROM processing_runs WHERE id=?", (run_id,), one=True)
    if not run:
        flash('Run not found.', 'error')
        return redirect(url_for('plant.index'))

    if request.method == 'POST':
        own_gallons    = float(request.form.get('own_farms_gallons_input') or 0)
        outside_gallons= float(request.form.get('outside_farmers_gallons_input') or 0)
        outside_fees   = float(request.form.get('outside_farmer_fees') or 0)
        own_bunches    = int(request.form.get('own_farms_bunches') or 0)
        out_bunches    = int(request.form.get('outside_farmers_bunches') or 0)

        c = _calc_run(own_gallons, outside_gallons, outside_fees)

        cash_collected   = float(request.form.get('cash_collected') or 0)
        cash_outstanding = max(0, c['gross_revenue'] - cash_collected)

        execute("""
            UPDATE processing_runs SET
                date=?,
                own_farms_litres=?, own_farms_gallons=?, own_farms_bunches=?,
                outside_farmers_litres=?, outside_farmers_gallons=?, outside_farmers_bunches=?,
                total_output_litres=?, total_output_gallons=?,
                gross_revenue=?, outside_farmer_fees=?,
                electricity_cost=?, net_revenue=?,
                operator_pay=?, company_revenue=?,
                cash_collected=?, cash_outstanding=?,
                notes=?
            WHERE id=?
        """, (
            request.form['date'],
            c['own_farms_litres'], c['own_farms_gallons'], own_bunches,
            c['outside_farmers_litres'], c['outside_farmers_gallons'], out_bunches,
            c['total_output_litres'], c['total_output_gallons'],
            c['gross_revenue'], outside_fees,
            c['electricity_cost'], c['net_revenue'],
            c['operator_pay'], c['company_revenue'],
            cash_collected, cash_outstanding,
            request.form.get('notes', ''),
            run_id,
        ))
        flash('Processing run updated.', 'success')
        return redirect(url_for('plant.index'))

    return render_template('plant/edit_run.html', run=run)


@plant_bp.route('/run/<int:run_id>/delete', methods=['POST'])
def delete_run(run_id):
    execute("DELETE FROM processing_runs WHERE id=?", (run_id,))
    flash('Processing run deleted.', 'success')
    return redirect(url_for('plant.index'))


@plant_bp.route('/expenses')
def expenses():
    exp   = query("SELECT * FROM plant_expenses ORDER BY date DESC")
    total = query("SELECT COALESCE(SUM(amount),0) AS t FROM plant_expenses", one=True)['t']
    return render_template('plant/expenses.html',
        expenses=exp, total=total, categories=EXPENSE_CATEGORIES)


@plant_bp.route('/expenses/add', methods=['GET', 'POST'])
def add_expense():
    if request.method == 'POST':
        execute("""
            INSERT INTO plant_expenses (date, category, description, amount, notes)
            VALUES (?,?,?,?,?)
        """, (
            request.form['date'], request.form['category'],
            request.form.get('description', ''), request.form.get('amount') or 0,
            request.form.get('notes', ''),
        ))
        flash('Expense added.', 'success')
        return redirect(url_for('plant.expenses'))
    return render_template('plant/add_expense.html', categories=EXPENSE_CATEGORIES)


@plant_bp.route('/expenses/<int:exp_id>/delete', methods=['POST'])
def delete_expense(exp_id):
    execute("DELETE FROM plant_expenses WHERE id=?", (exp_id,))
    flash('Expense deleted.', 'success')
    return redirect(url_for('plant.expenses'))


@plant_bp.route('/farmers')
def farmers():
    farmers = query("SELECT * FROM outside_farmers ORDER BY name")
    return render_template('plant/farmers.html', farmers=farmers)


@plant_bp.route('/farmers/add', methods=['GET', 'POST'])
def add_farmer():
    if request.method == 'POST':
        execute("INSERT INTO outside_farmers (name, phone, location, notes) VALUES (?,?,?,?)", (
            request.form['name'], request.form.get('phone', ''),
            request.form.get('location', ''), request.form.get('notes', ''),
        ))
        flash('Farmer added.', 'success')
        return redirect(url_for('plant.farmers'))
    return render_template('plant/add_farmer.html')


@plant_bp.route('/farmers/<int:farmer_id>/delete', methods=['POST'])
def delete_farmer(farmer_id):
    execute("DELETE FROM outside_farmers WHERE id=?", (farmer_id,))
    flash('Farmer removed.', 'success')
    return redirect(url_for('plant.farmers'))


# ── Helpers ──────────────────────────────────────────────────────────────────

def _sum(sql, params=()):
    row = query(sql, params, one=True)
    return float(list(row)[0]) if row else 0.0

def _where(from_d=None, to_d=None):
    if from_d and to_d:
        return " WHERE date>=? AND date<?", (from_d, to_d)
    elif from_d:
        return " WHERE date>=?", (from_d,)
    elif to_d:
        return " WHERE date<?", (to_d,)
    return "", ()

def _pct_change(old, new):
    if not old:
        return None
    return round(((new - old) / abs(old)) * 100, 1)

def _build_kpis_and_actions(
    all_income, all_expenses, all_net,
    this_m_income, this_m_exp, this_m_net,
    last_m_income, last_m_net,
    mom_income_chg, mom_exp_chg, mom_net_chg,
    yoy_income_chg, totals, monthly_chart,
):
    kpis, actions = [], []

    if all_income > 0:
        margin = (all_net / all_income) * 100
        kpis.append({'label': 'Profit Margin (All Time)', 'value': f'{margin:.1f}%',
            'status': 'good' if margin >= 50 else 'warn' if margin >= 25 else 'bad',
            'note': 'Target: ≥ 50%'})
        if margin < 25:
            actions.append({'priority': 'high',
                'action': f'Margin is {margin:.1f}%. Small batches raise cost per litre. Process larger volumes per run.'})

    if mom_income_chg is not None:
        kpis.append({'label': 'Income Growth (MoM)', 'value': f'{("+" if mom_income_chg>=0 else "")}{mom_income_chg}%',
            'status': 'good' if mom_income_chg >= 5 else 'warn' if mom_income_chg >= 0 else 'bad',
            'note': 'This month vs last month'})
        if mom_income_chg < -10:
            actions.append({'priority': 'high',
                'action': f'Plant income fell {abs(mom_income_chg)}% this month. Check if fewer runs were done.'})

    if mom_exp_chg is not None:
        kpis.append({'label': 'Expense Change (MoM)', 'value': f'{("+" if mom_exp_chg>=0 else "")}{mom_exp_chg}%',
            'status': 'good' if mom_exp_chg <= 0 else 'warn' if mom_exp_chg <= 15 else 'bad',
            'note': 'Lower is better'})

    if yoy_income_chg is not None:
        kpis.append({'label': 'YTD Income (YoY)', 'value': f'{("+" if yoy_income_chg>=0 else "")}{yoy_income_chg}%',
            'status': 'good' if yoy_income_chg >= 10 else 'warn' if yoy_income_chg >= 0 else 'bad',
            'note': 'This year vs last year'})

    litres = totals['total_litres'] or 0
    elec   = totals['electricity_cost'] or 0
    if litres > 0:
        epl = elec / litres
        kpis.append({'label': 'Electricity Cost / Litre', 'value': f'GHS {epl:.2f}',
            'status': 'good' if epl < 1.0 else 'warn' if epl < 2.0 else 'bad',
            'note': 'Lower = more efficient runs'})
        if epl > 2.0:
            actions.append({'priority': 'medium',
                'action': 'Electricity cost per litre is high. Batch more FFB per run to spread the fixed cost.'})

    outside_fees = totals['outside_farmer_fees'] or 0
    company_rev  = totals['company_revenue'] or 0
    if company_rev > 0:
        out_pct = (outside_fees / (company_rev + outside_fees)) * 100
        kpis.append({'label': 'Outside Farmer Revenue', 'value': f'{out_pct:.1f}%',
            'status': 'good' if out_pct >= 20 else 'warn',
            'note': 'Share of total plant income'})

    if len(monthly_chart) >= 3:
        zero = [m for m in monthly_chart[-3:] if m['run_count'] == 0]
        if zero:
            actions.append({'priority': 'high',
                'action': f'{len(zero)} of the last 3 months had no runs logged. Check if runs are being recorded.'})

    if not actions:
        actions.append({'priority': 'good' if all_income > 0 else 'medium',
            'action': 'No issues detected. Keep logging every run.' if all_income > 0
                      else 'No runs logged yet. Start recording to unlock analytics.'})

    return kpis, actions
