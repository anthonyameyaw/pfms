from database.periods import business_today, comparison_periods, shift_month
"""Processing Plant — runs, analytics, expenses, outside farmers."""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from database.db import query, execute, get_all_farms
from datetime import date, timedelta
import math
from decimal import Decimal
from database.validation import money
from database.processing import processing_transaction, parse_contributions, save_contributions
from database.processing_dates import sync_dates
from database.harvest_workflow import validate_stock
from database.financials import financial_summary, monthly_financials, month_start_months_ago

plant_bp = Blueprint('plant', __name__)
EXPENSE_CATEGORIES = ['Maintenance', 'Casual Labour', 'Consumables', 'Other']


def _cash_balance(gross, collected):
    if collected is None:return None
    return money(max(Decimal(0),Decimal(str(gross))-Decimal(str(collected))))


def _calc_run(own_gallons, outside_gallons, outside_fees):
    """
    Input: gallons (user enters gallons; litres = gallons × 25).
    Gross = own-farm processing fees + outside processing fees.
    Electricity on total combined gallons.
    Net = gross - electricity. Split 70/30.
    """
    own_gallons=Decimal(str(own_gallons));outside_gallons=Decimal(str(outside_gallons))
    outside_fees=Decimal(str(outside_fees))
    total_gal=own_gallons+outside_gallons
    gross=own_gallons*40+outside_fees
    electricity=total_gal*6
    net=gross-electricity
    operator=Decimal(str(money(net*Decimal('0.30'))))
    return dict(
        own_farms_gallons=money(own_gallons), own_farms_litres=money(own_gallons*25),
        outside_farmers_gallons=money(outside_gallons), outside_farmers_litres=money(outside_gallons*25),
        total_output_gallons=money(total_gal), total_output_litres=money(total_gal*25),
        own_oil_revenue=money(own_gallons*40), gross_revenue=money(gross),
        electricity_cost=money(electricity), net_revenue=money(net),
        operator_pay=float(operator), company_revenue=money(net-operator),
        outside_farmer_fees=money(outside_fees),
    )


@plant_bp.route('/')
def index():
    today            = business_today()
    periods = comparison_periods(today)
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

    def finances_for(from_d=None, to_d=None):
        # Existing plant helper uses an exclusive end; shared reports use inclusive.
        end = (date.fromisoformat(to_d)-timedelta(days=1)).isoformat() if to_d else (today.isoformat() if from_d else '')
        return financial_summary(from_d or '', end, scope='plant')

    def totals(from_d=None, to_d=None):
        bounded_end = to_d or ((today+timedelta(days=1)).isoformat() if from_d else None)
        w, p = _where(from_d, bounded_end)
        row = dict(query(f"""
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
                SUM(CASE WHEN cash_collected IS NULL THEN 1 ELSE 0 END) AS unknown_cash_count,
                COALESCE(SUM(CASE WHEN cash_collected IS NULL THEN gross_revenue ELSE 0 END),0) AS unknown_cash_billed,
                COALESCE(SUM(MAX(0,COALESCE(cash_collected,0)-gross_revenue)),0) AS overpaid,
                COUNT(*)                                AS run_count
            FROM processing_runs{w}
        """, p, one=True))
        money = finances_for(from_d, to_d)
        row.update(gross_revenue=money['total_income'], electricity_cost=money['elec_exp'],
                   operator_pay=money['op_exp'])
        return row

    def plant_other_exp(from_d=None, to_d=None):
        return finances_for(from_d, to_d)['plant_other']

    def total_income_from(t):
        # Gross revenue = all plant income (own-farm processing fees + outside farmer fees)
        return t['gross_revenue'] or 0

    def total_expenses_from(t, from_d=None, to_d=None):
        # Costs = electricity + operator pay + other plant expenses
        return (t['electricity_cost'] or 0) + (t['operator_pay'] or 0) + plant_other_exp(from_d, to_d)

    all_t  = totals()
    this_m = totals(this_month_start)
    last_m = totals(last_month_start, this_month_start)
    ytd_t  = totals(year_start)
    prev_t = totals(periods['previous_year_start'], (date.fromisoformat(periods['previous_year_end'])+timedelta(days=1)).isoformat())
    comparable = financial_summary(periods['previous_month_start'],periods['previous_month_end'],scope='plant')

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

    mom_income_chg = _pct_change(comparable['total_income'], this_m_income)
    mom_exp_chg    = _pct_change(comparable['total_exp'], this_m_exp)
    mom_net_chg    = _pct_change(comparable['net'], this_m_net)
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
               SUM(CASE WHEN cash_collected IS NULL THEN 1 ELSE 0 END) AS unknown_cash_count,
               COUNT(*)                     AS run_count
        FROM processing_runs
        WHERE date >= ? AND date <= ?
        GROUP BY month ORDER BY month
    """, (month_start_months_ago(today,17),today.isoformat()))
    monthly_chart = []
    run_map = {r['month']: r for r in monthly_runs}
    money_months = monthly_financials(month_start_months_ago(today, 17), today.isoformat(), scope='plant')
    run_fields = ('own_gallons','gallons','own_litres','out_litres','litres','out_gallons',
                  'gross_revenue','electricity_cost','company_revenue','outside_fees',
                  'operator_pay','cash_collected','cash_outstanding','run_count','unknown_cash_count')
    for money in money_months:
        r = run_map.get(money['month'], dict.fromkeys(run_fields, 0))
        r = dict(r, month=money['month'])
        m   = r['month']
        inc = money['income']
        exp = money['expenses']
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
            'cash_collected'  : round(r['cash_collected'] or 0, 2) if not r['unknown_cash_count'] else None,
            'cash_outstanding': round(r['cash_outstanding'] or 0, 2) if not r['unknown_cash_count'] else None,
            'run_count'       : r['run_count'] or 0,
            'own_farm_pct'    : round((own_g / total_g * 100), 1) if total_g > 0 else None,
            'outside_farm_pct': round((float(r['out_gallons'] or 0) / total_g * 100), 1) if total_g > 0 else None,
        })

    exp_by_cat = query("""
        SELECT category, COALESCE(SUM(amount),0) AS total
        FROM plant_expenses GROUP BY category ORDER BY total DESC
    """)

    first_record=query("SELECT MIN(date) day FROM (SELECT date FROM processing_runs UNION ALL SELECT date FROM plant_expenses)",one=True)['day']
    monthly_chart=[m for m in monthly_chart if first_record and m['month']>=first_record[:7]]

    # All-time own farm %
    all_total_gal = float(all_t['total_gallons'] or 0)
    all_own_gal   = float(all_t['own_gallons'] or 0)
    all_own_pct   = round((all_own_gal / all_total_gal * 100), 1) if all_total_gal > 0 else None

    kpis, actions = _build_kpis_and_actions(
        all_income, all_expenses, all_net,
        this_m_income, this_m_exp, this_m_net,
        last_m_income, last_m_net,
        mom_income_chg, mom_exp_chg, mom_net_chg,
        yoy_income_chg, all_t, monthly_chart,
    )

    other_expenses = query("SELECT COALESCE(SUM(amount),0) AS t FROM plant_expenses", one=True)

    farm_contributions=[dict(row) for row in query("""SELECT f.name,
        COALESCE(SUM(l.gallons_contributed),0) gallons FROM farms f
        LEFT JOIN processing_run_farms l ON l.farm_id=f.id
        WHERE f.crop_type='Oil Palm' GROUP BY f.id ORDER BY f.name""")]
    for row in farm_contributions:
        row['share']=round(row['gallons']/all_total_gal*100,2) if all_total_gal else None
    unallocated_gallons=round(all_own_gal-sum(row['gallons'] for row in farm_contributions),2)
    return render_template('plant/index.html',
        farm_contributions=farm_contributions, unallocated_gallons=unallocated_gallons,
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
        try:
            own_gallons    = float(request.form.get('own_farms_gallons_input') or 0)
            outside_gallons= float(request.form.get('outside_farmers_gallons_input') or 0)
            outside_fees   = float(request.form.get('outside_farmer_fees') or 0)
            own_bunches    = int(request.form.get('own_farms_bunches') or 0)
            out_bunches    = int(request.form.get('outside_farmers_bunches') or 0)
            cash_text = request.form.get('cash_collected','').strip()
            cash_collected = float(cash_text) if cash_text else None
            values = (own_gallons, outside_gallons, outside_fees, cash_collected or 0)
            if not all(math.isfinite(v) and v >= 0 for v in values) or min(own_bunches, out_bunches) < 0:
                raise ValueError('Oil quantities, fees and bunch counts must be non-negative.')
            contributions = parse_contributions(request.form, own_gallons, {f['id'] for f in get_all_farms()})
        except ValueError as exc:
            flash(str(exc), 'error')
            return redirect(request.url)

        c = _calc_run(own_gallons, outside_gallons, outside_fees)

        # Total billed = gross revenue (full factory income — what is owed to the plant)
        total_billed     = c['gross_revenue']
        cash_outstanding = _cash_balance(total_billed, cash_collected)

        try:
            with processing_transaction() as conn:
                run_id = conn.execute("""
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
                )).lastrowid
                save_contributions(conn, run_id, contributions)
                sync_dates(conn)
                validate_stock(conn)

        except ValueError as exc:
            flash(str(exc), 'error')
            return redirect(request.url)

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
        try:
            own_gallons    = float(request.form.get('own_farms_gallons_input') or 0)
            outside_gallons= float(request.form.get('outside_farmers_gallons_input') or 0)
            outside_fees   = float(request.form.get('outside_farmer_fees') or 0)
            own_bunches    = int(request.form.get('own_farms_bunches') or 0)
            out_bunches    = int(request.form.get('outside_farmers_bunches') or 0)
            cash_text = request.form.get('cash_collected','').strip()
            cash_collected = float(cash_text) if cash_text else None
            values = (own_gallons, outside_gallons, outside_fees, cash_collected or 0)
            if not all(math.isfinite(v) and v >= 0 for v in values) or min(own_bunches, out_bunches) < 0:
                raise ValueError('Oil quantities, fees and bunch counts must be non-negative.')
            contributions = parse_contributions(request.form, own_gallons, {f['id'] for f in get_all_farms()})
        except ValueError as exc:
            flash(str(exc), 'error')
            return redirect(request.url)

        c = _calc_run(own_gallons, outside_gallons, outside_fees)

        cash_outstanding = _cash_balance(c['gross_revenue'], cash_collected)

        try:
            with processing_transaction() as conn:
                conn.execute("""
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
                save_contributions(conn, run_id, contributions)
                sync_dates(conn)
                validate_stock(conn)

        except ValueError as exc:
            flash(str(exc), 'error')
            return redirect(request.url)

        flash('Processing run updated.', 'success')
        return redirect(url_for('plant.index'))

    contributing = query('SELECT * FROM processing_run_farms WHERE run_id=? ORDER BY id', (run_id,))
    return render_template('plant/edit_run.html', run=run, farms=get_all_farms(), contributing=contributing)


@plant_bp.route('/run/<int:run_id>/delete', methods=['POST'])
def delete_run(run_id):
    try:
        with processing_transaction() as conn:
            conn.execute('UPDATE harvests SET processing_date=NULL,processing_run_id=NULL WHERE processing_run_id=?',(run_id,))
            conn.execute('DELETE FROM processing_runs WHERE id=?',(run_id,))
            sync_dates(conn)
            validate_stock(conn)
    except ValueError as exc:
        flash(str(exc),'error')
        return redirect(url_for('plant.index'))
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
            'status': 'good' if margin >= 0 else 'bad',
            'note': 'Recorded plant net ÷ gross processing income'})
        if margin < 0:
            actions.append({'priority': 'high',
                'action': f'Margin is {margin:.1f}%. Review recorded processing fees, electricity, operator pay and maintenance costs.'})

    if mom_income_chg is not None:
        kpis.append({'label': 'Income Growth (MoM)', 'value': f'{("+" if mom_income_chg>=0 else "")}{mom_income_chg}%',
            'status': 'good' if mom_income_chg >= 5 else 'warn' if mom_income_chg >= 0 else 'bad',
            'note': 'Same elapsed period last month'})
        if mom_income_chg < -10:
            actions.append({'priority': 'high',
                'action': f'Plant income fell {abs(mom_income_chg)}% this month. Check if fewer runs were done.'})

    if mom_exp_chg is not None:
        kpis.append({'label': 'Expense Change (MoM)', 'value': f'{("+" if mom_exp_chg>=0 else "")}{mom_exp_chg}%',
            'status': 'good' if mom_exp_chg <= 0 else 'warn' if mom_exp_chg <= 15 else 'bad',
            'note': 'Same elapsed period last month; compare with output'})

    if yoy_income_chg is not None:
        kpis.append({'label': 'YTD Income (YoY)', 'value': f'{("+" if yoy_income_chg>=0 else "")}{yoy_income_chg}%',
            'status': 'good' if yoy_income_chg >= 10 else 'warn' if yoy_income_chg >= 0 else 'bad',
            'note': 'Same dates last year'})

    litres = totals['total_litres'] or 0
    elec   = totals['electricity_cost'] or 0
    if litres > 0:
        epl = elec / litres
        kpis.append({'label': 'Electricity Cost / Litre', 'value': f'GHS {epl:.2f}',
            'status': 'warn',
            'note': 'Recorded electricity ÷ litres; configured charge is GHS 6/gallon (GHS 0.24/litre)' })
        if epl > 2.0:
            actions.append({'priority': 'medium',
                'action': 'Recorded electricity differs substantially from the configured proportional charge. Check the entries.'})

    outside_fees = totals['outside_farmer_fees'] or 0
    if all_income > 0:
        out_pct = (outside_fees / all_income) * 100
        kpis.append({'label': 'Outside Farmer Revenue', 'value': f'{out_pct:.1f}%',
            'status': 'warn',
            'note': 'Outside processing fees ÷ gross processing revenue (all recorded dates)' })

    if len(monthly_chart) >= 3:
        completed = [m for m in monthly_chart if m['month'] < business_today().strftime('%Y-%m')][-3:]
        zero = [m for m in completed if m['run_count'] == 0]
        if zero:
            actions.append({'priority': 'high',
                'action': f'{len(zero)} of the last 3 completed months had no runs logged. Check if runs are being recorded.'})

    if not actions:
        actions.append({'priority': 'good' if all_income > 0 else 'medium',
            'action': 'No alerts from these recorded-data checks. Keep logging every run.' if all_income > 0
                      else 'No runs logged yet. Start recording to unlock analytics.'})

    return kpis, actions
