"""Farms — CRUD, detail views, and analytics."""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from database.db import query, execute, get_all_farms, get_farm
from datetime import date, timedelta

farms_bp = Blueprint('farms', __name__)


@farms_bp.route('/')
def index():
    farms = get_all_farms()
    return render_template('farms/index.html', farms=farms)


@farms_bp.route('/<int:farm_id>')
def detail(farm_id):
    farm = get_farm(farm_id)
    if not farm:
        flash('Farm not found.', 'error')
        return redirect(url_for('farms.index'))

    today      = date.today()
    year_start = today.replace(month=1, day=1).isoformat()
    prev_year  = (today.replace(month=1, day=1) - timedelta(days=1)).replace(month=1, day=1).isoformat()
    last_month_start = (today.replace(day=1) - timedelta(days=1)).replace(day=1).isoformat()
    this_month_start = today.replace(day=1).isoformat()

    # ── Basic lists ──────────────────────────────────────────────────────────
    activities = query(
        "SELECT * FROM activities WHERE farm_id=? ORDER BY date DESC LIMIT 10", (farm_id,)
    )
    harvests = query(
        "SELECT * FROM harvests WHERE farm_id=? ORDER BY date DESC LIMIT 10", (farm_id,)
    )
    current_cycle = query(
        "SELECT * FROM pruning_cycles WHERE farm_id=? AND is_complete=0 ORDER BY id DESC LIMIT 1",
        (farm_id,), one=True
    )

    # ── Tree tracking ─────────────────────────────────────────────────────────
    total_trees = farm['total_trees'] or 0
    active_cycle = query(
        "SELECT * FROM pruning_cycles WHERE farm_id=? AND is_complete=0 ORDER BY id DESC LIMIT 1",
        (farm_id,), one=True
    )
    trees_pruned_this_cycle = active_cycle['total_trees_pruned'] if active_cycle else 0
    completed_total = _sum(
        "SELECT COALESCE(SUM(total_trees_pruned),0) FROM pruning_cycles WHERE farm_id=? AND is_complete=1",
        (farm_id,)
    )
    trees_ever_pruned = int(completed_total + trees_pruned_this_cycle)
    trees_unpruned    = max(0, total_trees - trees_pruned_this_cycle) if total_trees > 0 else None
    last_cycle = query(
        "SELECT * FROM pruning_cycles WHERE farm_id=? AND is_complete=1 ORDER BY cycle_end_date DESC LIMIT 1",
        (farm_id,), one=True
    )

    # ── All-time totals with expense breakdown ────────────────────────────────
    # Income = sum of gallons_sold_income from harvests (sold gallons revenue)
    # plus any manually recorded other income in farm_income
    harvest_sales_income = _sum(
        "SELECT COALESCE(SUM(gallons_sold_income),0) FROM harvests WHERE farm_id=? AND gallons_sold_income > 0",
        (farm_id,)
    )
    other_income = _sum(
        "SELECT COALESCE(SUM(total_amount),0) FROM farm_income WHERE farm_id=? AND income_type='Other'",
        (farm_id,)
    )
    total_income = harvest_sales_income + other_income

    # Labour from activities (non-harvest types — weeding, spraying, etc.)
    activity_labour_total = _sum(
        "SELECT COALESCE(SUM(labour_cost + materials_cost),0) FROM activities WHERE farm_id=? AND activity_type != 'Harvesting'",
        (farm_id,)
    )
    # Manually recorded farm expenses
    manual_exp_total    = _sum("SELECT COALESCE(SUM(amount),0) FROM farm_expenses WHERE farm_id=?", (farm_id,))
    farm_exp_total      = activity_labour_total + manual_exp_total

    # Harvesting labour (harvester + collector pay from harvests table)
    harvest_exp_total   = _sum("SELECT COALESCE(SUM(harvesting_cost),0) FROM harvests WHERE farm_id=?", (farm_id,))

    # Transport (all trips attributed to this farm)
    transport_exp_total = _sum("SELECT COALESCE(SUM(total_cost),0) FROM transport_logs WHERE farm_id=?", (farm_id,))

    total_expenses      = farm_exp_total + harvest_exp_total + transport_exp_total
    total_net           = total_income - total_expenses
    total_bunches       = _sum("SELECT COALESCE(SUM(bunches_harvested),0) FROM harvests WHERE farm_id=?", (farm_id,))

    # ── Gallons tracking ──────────────────────────────────────────────────────
    pending_harvests = query(
        "SELECT id, date, bunches_harvested FROM harvests"
        " WHERE farm_id=? AND (gallons_produced IS NULL OR gallons_produced=0)"
        " AND bunches_harvested > 0 ORDER BY date DESC",
        (farm_id,)
    )
    total_gallons_produced = _sum(
        "SELECT COALESCE(SUM(gallons_produced),0) FROM harvests WHERE farm_id=? AND gallons_produced > 0",
        (farm_id,)
    )
    total_gallons_sold = _sum(
        "SELECT COALESCE(SUM(gallons_sold),0) FROM harvests WHERE farm_id=? AND gallons_sold > 0",
        (farm_id,)
    )
    total_sold_income = _sum(
        "SELECT COALESCE(SUM(gallons_sold_income),0) FROM harvests WHERE farm_id=?",
        (farm_id,)
    )
    added = _sum(
        "SELECT COALESCE(SUM(gallons),0) FROM storage_transactions WHERE farm_id=? AND transaction_type='Addition'",
        (farm_id,)
    )
    removed = _sum(
        "SELECT COALESCE(SUM(gallons),0) FROM storage_transactions WHERE farm_id=? AND transaction_type='Removal'",
        (farm_id,)
    )
    gallons_in_storage = float(query("SELECT COALESCE(SUM(gallons_produced),0)-COALESCE(SUM(gallons_sold),0) AS v FROM harvests WHERE farm_id=? AND gallons_produced>0", (farm_id,), one=True)['v'] or 0)


    # ── This month vs last month ──────────────────────────────────────────────
    this_m_income = _sum("SELECT COALESCE(SUM(gallons_sold_income),0) FROM harvests WHERE farm_id=? AND date>=? AND gallons_sold_income>0", (farm_id, this_month_start))
    last_m_income = _sum("SELECT COALESCE(SUM(gallons_sold_income),0) FROM harvests WHERE farm_id=? AND date>=? AND date<? AND gallons_sold_income>0", (farm_id, last_month_start, this_month_start))
    this_m_exp    = _expenses(farm_id, this_month_start)
    last_m_exp    = _expenses(farm_id, last_month_start, this_month_start)
    this_m_net    = this_m_income - this_m_exp
    last_m_net    = last_m_income - last_m_exp

    # ── YTD vs prior year ────────────────────────────────────────────────────
    ytd_income    = _sum("SELECT COALESCE(SUM(gallons_sold_income),0) FROM harvests WHERE farm_id=? AND date>=? AND gallons_sold_income>0", (farm_id, year_start))
    prior_income  = _sum("SELECT COALESCE(SUM(gallons_sold_income),0) FROM harvests WHERE farm_id=? AND date>=? AND date<? AND gallons_sold_income>0", (farm_id, prev_year, year_start))
    ytd_exp       = _expenses(farm_id, year_start)
    prior_exp     = _expenses(farm_id, prev_year, year_start)

    # ── MoM and YoY changes ──────────────────────────────────────────────────
    mom_income_chg = _pct_change(last_m_income, this_m_income)
    mom_exp_chg    = _pct_change(last_m_exp, this_m_exp)
    mom_net_chg    = _pct_change(last_m_net, this_m_net)
    yoy_income_chg = _pct_change(prior_income, ytd_income)
    yoy_exp_chg    = _pct_change(prior_exp, ytd_exp)

    # ── Monthly time series (last 18 months) ──────────────────────────────────
    monthly_income_rows = query("""
        SELECT strftime('%Y-%m', date) AS month,
               SUM(gallons_sold_income) AS total
        FROM harvests
        WHERE farm_id=? AND date >= DATE('now','-18 months')
          AND gallons_sold_income > 0
        GROUP BY month ORDER BY month
    """, (farm_id,))

    # Monthly expenses = activity labour/materials + manual farm expenses + transport
    monthly_exp_rows = query("""
        SELECT month, SUM(total) AS total FROM (
            SELECT strftime('%Y-%m', date) AS month,
                   SUM(labour_cost + materials_cost) AS total
            FROM activities
            WHERE farm_id=? AND date >= DATE('now','-18 months')
              AND activity_type != 'Harvesting'
            GROUP BY month
            UNION ALL
            SELECT strftime('%Y-%m', date) AS month, SUM(amount) AS total
            FROM farm_expenses
            WHERE farm_id=? AND date >= DATE('now','-18 months')
            GROUP BY month
            UNION ALL
            SELECT strftime('%Y-%m', date) AS month, SUM(total_cost) AS total
            FROM transport_logs
            WHERE farm_id=? AND date >= DATE('now','-18 months')
            GROUP BY month
            UNION ALL
            SELECT strftime('%Y-%m', date) AS month, SUM(harvesting_cost) AS total
            FROM harvests
            WHERE farm_id=? AND date >= DATE('now','-18 months')
            GROUP BY month
        ) GROUP BY month ORDER BY month
    """, (farm_id, farm_id, farm_id, farm_id))

    monthly_harvest_rows = query("""
        SELECT strftime('%Y-%m', date) AS month,
               SUM(bunches_harvested) AS bunches,
               SUM(harvesting_cost) AS cost
        FROM harvests WHERE farm_id=? AND date >= DATE('now','-18 months')
        GROUP BY month ORDER BY month
    """, (farm_id,))

    # Merge into unified month list
    all_months = sorted(set(
        [r['month'] for r in monthly_income_rows] +
        [r['month'] for r in monthly_exp_rows] +
        [r['month'] for r in monthly_harvest_rows]
    ))
    inc_map = {r['month']: r['total']   for r in monthly_income_rows}
    exp_map = {r['month']: r['total']   for r in monthly_exp_rows}
    bun_map = {r['month']: r['bunches'] for r in monthly_harvest_rows}
    hco_map = {r['month']: r['cost']    for r in monthly_harvest_rows}

    monthly_chart = [
        {
            'month'   : m,
            'income'  : round(inc_map.get(m) or 0, 2),
            'expenses': round(exp_map.get(m) or 0, 2),
            'net'     : round((inc_map.get(m) or 0) - (exp_map.get(m) or 0), 2),
            'bunches' : int(bun_map.get(m) or 0),
            'harvest_cost': round(hco_map.get(m) or 0, 2),
        }
        for m in all_months
    ]

    # ── Expense breakdown by category (all sources combined) ─────────────────
    exp_by_cat = query("""
        SELECT category, SUM(total) AS total FROM (
            SELECT activity_type AS category, SUM(labour_cost + materials_cost) AS total
            FROM activities
            WHERE farm_id=? AND activity_type != 'Harvesting' AND (labour_cost > 0 OR materials_cost > 0)
            GROUP BY activity_type
            UNION ALL
            SELECT 'Harvesting Labour' AS category, SUM(harvesting_cost) AS total
            FROM harvests WHERE farm_id=? AND harvesting_cost > 0
            UNION ALL
            SELECT 'Transport' AS category, SUM(total_cost) AS total
            FROM transport_logs WHERE farm_id=? AND total_cost > 0
            UNION ALL
            SELECT category, SUM(amount) AS total
            FROM farm_expenses WHERE farm_id=?
            GROUP BY category
        ) WHERE total > 0
        GROUP BY category ORDER BY total DESC
    """, (farm_id, farm_id, farm_id, farm_id))

    # ── KPIs & recommended actions ───────────────────────────────────────────
    kpis, actions = _build_kpis_and_actions(
        farm, total_income, total_expenses, total_net,
        this_m_income, this_m_exp, this_m_net,
        last_m_income, last_m_exp, last_m_net,
        ytd_income, ytd_exp,
        mom_income_chg, mom_exp_chg, mom_net_chg,
        yoy_income_chg, yoy_exp_chg,
        total_bunches, monthly_chart,
    )

    return render_template('farms/detail.html',
        farm                 = farm,
        activities           = activities,
        harvests             = harvests,
        current_cycle        = active_cycle,
        total_income         = total_income,
        total_expenses       = total_expenses,
        total_net            = total_net,
        total_bunches           = int(total_bunches),
        pending_harvests        = pending_harvests,
        total_gallons_produced  = round(total_gallons_produced, 2),
        total_gallons_sold      = round(total_gallons_sold, 2),
        gallons_in_storage      = round(gallons_in_storage, 2),
        total_sold_income       = round(total_sold_income, 2),
        farm_exp_total       = farm_exp_total,
        harvest_exp_total    = harvest_exp_total,
        transport_exp_total  = transport_exp_total,
        total_trees          = total_trees,
        trees_pruned_this_cycle = trees_pruned_this_cycle,
        trees_ever_pruned    = trees_ever_pruned,
        trees_unpruned       = trees_unpruned,
        last_cycle           = last_cycle,
        this_m_income        = this_m_income,
        this_m_exp           = this_m_exp,
        this_m_net           = this_m_net,
        last_m_income        = last_m_income,
        last_m_exp           = last_m_exp,
        ytd_income           = ytd_income,
        ytd_exp              = ytd_exp,
        mom_income_chg       = mom_income_chg,
        mom_exp_chg          = mom_exp_chg,
        mom_net_chg          = mom_net_chg,
        yoy_income_chg       = yoy_income_chg,
        yoy_exp_chg          = yoy_exp_chg,
        monthly_chart        = monthly_chart,
        exp_by_cat           = [dict(r) for r in exp_by_cat],
        kpis                 = kpis,
        actions              = actions,
        today                = today,
    )


@farms_bp.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        execute("""
            INSERT INTO farms (name, location, constituency, size_acres,
                               crop_type, status, total_trees, notes)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            request.form['name'], request.form['location'],
            request.form['constituency'], request.form.get('size_acres') or None,
            request.form['crop_type'], request.form['status'],
            request.form.get('total_trees') or 0, request.form.get('notes', ''),
        ))
        flash('Farm added successfully.', 'success')
        return redirect(url_for('farms.index'))
    return render_template('farms/add.html')


@farms_bp.route('/<int:farm_id>/edit', methods=['GET', 'POST'])
def edit(farm_id):
    farm = get_farm(farm_id)
    if not farm:
        flash('Farm not found.', 'error')
        return redirect(url_for('farms.index'))
    if request.method == 'POST':
        execute("""
            UPDATE farms SET name=?, location=?, constituency=?,
            size_acres=?, crop_type=?, status=?, total_trees=?, notes=?
            WHERE id=?
        """, (
            request.form['name'], request.form['location'],
            request.form['constituency'], request.form.get('size_acres') or None,
            request.form['crop_type'], request.form['status'],
            request.form.get('total_trees') or 0, request.form.get('notes', ''),
            farm_id,
        ))
        flash('Farm updated.', 'success')
        return redirect(url_for('farms.detail', farm_id=farm_id))
    return render_template('farms/edit.html', farm=farm)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _sum(sql, params=()):
    row = query(sql, params, one=True)
    return float(list(row)[0]) if row else 0.0


def _expenses(farm_id, from_date=None, to_date=None):
    """Sum ALL expense sources for a farm, optionally filtered by date range.
    Includes: activity labour/materials (non-harvest), manual farm expenses,
    harvest labour, and transport costs.
    """
    def q(sql, params):
        return _sum(sql, params)

    if from_date and to_date:
        dp2 = (farm_id, from_date, to_date)
        act_exp   = q("SELECT COALESCE(SUM(labour_cost + materials_cost),0) FROM activities WHERE farm_id=? AND date>=? AND date<? AND activity_type != 'Harvesting'", dp2)
        manual_exp= q("SELECT COALESCE(SUM(amount),0) FROM farm_expenses WHERE farm_id=? AND date>=? AND date<?", dp2)
        harv_exp  = q("SELECT COALESCE(SUM(harvesting_cost),0) FROM harvests WHERE farm_id=? AND date>=? AND date<?", dp2)
        trans_exp = q("SELECT COALESCE(SUM(total_cost),0) FROM transport_logs WHERE farm_id=? AND date>=? AND date<?", dp2)
    elif from_date:
        dp1 = (farm_id, from_date)
        act_exp   = q("SELECT COALESCE(SUM(labour_cost + materials_cost),0) FROM activities WHERE farm_id=? AND date>=? AND activity_type != 'Harvesting'", dp1)
        manual_exp= q("SELECT COALESCE(SUM(amount),0) FROM farm_expenses WHERE farm_id=? AND date>=?", dp1)
        harv_exp  = q("SELECT COALESCE(SUM(harvesting_cost),0) FROM harvests WHERE farm_id=? AND date>=?", dp1)
        trans_exp = q("SELECT COALESCE(SUM(total_cost),0) FROM transport_logs WHERE farm_id=? AND date>=?", dp1)
    else:
        dp0 = (farm_id,)
        act_exp   = q("SELECT COALESCE(SUM(labour_cost + materials_cost),0) FROM activities WHERE farm_id=? AND activity_type != 'Harvesting'", dp0)
        manual_exp= q("SELECT COALESCE(SUM(amount),0) FROM farm_expenses WHERE farm_id=?", dp0)
        harv_exp  = q("SELECT COALESCE(SUM(harvesting_cost),0) FROM harvests WHERE farm_id=?", dp0)
        trans_exp = q("SELECT COALESCE(SUM(total_cost),0) FROM transport_logs WHERE farm_id=?", dp0)

    return act_exp + manual_exp + harv_exp + trans_exp


def _pct_change(old, new):
    if old == 0:
        return None  # can't calculate from zero
    return round(((new - old) / abs(old)) * 100, 1)


def _build_kpis_and_actions(
    farm, total_income, total_expenses, total_net,
    this_m_income, this_m_exp, this_m_net,
    last_m_income, last_m_exp, last_m_net,
    ytd_income, ytd_exp,
    mom_income_chg, mom_exp_chg, mom_net_chg,
    yoy_income_chg, yoy_exp_chg,
    total_bunches, monthly_chart,
):
    kpis    = []
    actions = []

    # ── KPI 1: Profitability margin ──────────────────────────────────────────
    if total_income > 0:
        margin = (total_net / total_income) * 100
        kpis.append({
            'label' : 'Profit Margin (All Time)',
            'value' : f'{margin:.1f}%',
            'status': 'good' if margin >= 40 else 'warn' if margin >= 15 else 'bad',
            'note'  : 'Target: ≥ 40%',
        })
        if margin < 15:
            actions.append({
                'priority': 'high',
                'action'  : 'Profit margin is critically low. Review your largest expense categories and compare labour rates against your Labour Intel benchmarks.',
            })
        elif margin < 40:
            actions.append({
                'priority': 'medium',
                'action'  : f'Profit margin is {margin:.1f}% — below the 40% target. Consider reducing input costs or improving harvest yield.',
            })

    # ── KPI 2: MoM income growth ─────────────────────────────────────────────
    if mom_income_chg is not None:
        kpis.append({
            'label' : 'Income Growth (MoM)',
            'value' : f'{("+" if mom_income_chg >= 0 else "")}{mom_income_chg}%',
            'status': 'good' if mom_income_chg >= 5 else 'warn' if mom_income_chg >= 0 else 'bad',
            'note'  : 'Month-on-month vs last month',
        })
        if mom_income_chg < 0:
            actions.append({
                'priority': 'high',
                'action'  : f'Income dropped {abs(mom_income_chg)}% this month vs last month. Check if a harvest was delayed or missed.',
            })

    # ── KPI 3: Expense control ───────────────────────────────────────────────
    if mom_exp_chg is not None:
        kpis.append({
            'label' : 'Expense Change (MoM)',
            'value' : f'{("+" if mom_exp_chg >= 0 else "")}{mom_exp_chg}%',
            'status': 'good' if mom_exp_chg <= 0 else 'warn' if mom_exp_chg <= 15 else 'bad',
            'note'  : 'Lower is better',
        })
        if mom_exp_chg > 20:
            actions.append({
                'priority': 'medium',
                'action'  : f'Expenses rose {mom_exp_chg}% this month. Review recent materials and labour costs for unusual items.',
            })

    # ── KPI 4: YoY income growth ─────────────────────────────────────────────
    if yoy_income_chg is not None:
        kpis.append({
            'label' : 'YTD Income Growth (YoY)',
            'value' : f'{("+" if yoy_income_chg >= 0 else "")}{yoy_income_chg}%',
            'status': 'good' if yoy_income_chg >= 10 else 'warn' if yoy_income_chg >= 0 else 'bad',
            'note'  : 'This year vs same period last year',
        })
        if yoy_income_chg < 0:
            actions.append({
                'priority': 'high',
                'action'  : f'Year-on-year income is down {abs(yoy_income_chg)}%. Investigate whether yield has dropped or prices have fallen.',
            })

    # ── KPI 5: Cost per bunch ────────────────────────────────────────────────
    if total_bunches > 0 and total_expenses > 0:
        cost_per_bunch = total_expenses / total_bunches
        kpis.append({
            'label' : 'Cost Per Bunch (All Time)',
            'value' : f'GHS {cost_per_bunch:.2f}',
            'status': 'good' if cost_per_bunch < 5 else 'warn' if cost_per_bunch < 10 else 'bad',
            'note'  : 'Total expenses ÷ bunches harvested',
        })
        if cost_per_bunch > 10:
            actions.append({
                'priority': 'high',
                'action'  : f'Cost per bunch is GHS {cost_per_bunch:.2f} — very high. Consider if transport or labour costs can be reduced.',
            })

    # ── KPI 6: Farm status flags ─────────────────────────────────────────────
    if farm['status'] == 'Inactive':
        kpis.append({
            'label' : 'Farm Status',
            'value' : 'Inactive',
            'status': 'bad',
            'note'  : 'No production currently',
        })
        actions.append({
            'priority': 'high',
            'action'  : 'This farm is inactive. Consider a revival investment plan — clearing, replanting, or soil assessment.',
        })

    if farm['status'] == 'Development':
        kpis.append({
            'label' : 'Farm Status',
            'value' : 'Development',
            'status': 'warn',
            'note'  : 'Pre-production phase',
        })
        actions.append({
            'priority': 'medium',
            'action'  : 'Track planting progress carefully. Log all development costs now so you have a clear cost basis when this farm starts producing.',
        })

    # ── KPI 7: Harvest consistency ───────────────────────────────────────────
    if len(monthly_chart) >= 3:
        recent_harvests = [m['bunches'] for m in monthly_chart[-3:]]
        if all(b == 0 for b in recent_harvests) and farm['status'] == 'Active':
            kpis.append({
                'label' : 'Harvest Activity',
                'value' : '3 Months No Harvest',
                'status': 'bad',
                'note'  : 'No bunches logged recently',
            })
            actions.append({
                'priority': 'high',
                'action'  : 'No harvests have been logged for 3+ months on an active farm. Either log missed harvests or investigate why the farm is not producing.',
            })

    # ── No issues found ───────────────────────────────────────────────────────
    if not actions:
        if total_income > 0:
            actions.append({
                'priority': 'good',
                'action'  : 'No significant issues detected. Keep logging consistently to maintain accurate financial intelligence.',
            })
        else:
            actions.append({
                'priority': 'medium',
                'action'  : 'No income recorded yet for this farm. Start logging harvests and income to unlock financial analysis.',
            })

    return kpis, actions
