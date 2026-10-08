from database.periods import business_today, comparison_periods, shift_month
"""Farms — CRUD, detail views, and analytics."""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from database.db import query, execute, get_all_farms, get_farm
from database.financials import financial_summary, monthly_financials, month_start_months_ago
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

    today      = business_today()
    periods = comparison_periods(today)
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

    # One financial source list for cards, charts, farm views and reports.
    summary = financial_summary(farm_id=farm_id)
    total_income, total_expenses, total_net = summary['total_income'], summary['total_exp'], summary['net']
    farm_exp_total = round(summary['act_exp'] + summary['manual_exp'] + summary['internal_processing_exp'], 2)
    harvest_exp_total = round(summary['harv_exp'] + summary['thresh_exp'], 2)
    transport_exp_total = summary['trans_exp']
    total_bunches = _sum("SELECT COALESCE(SUM(bunches_harvested),0) FROM harvests WHERE farm_id=?", (farm_id,))

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
    current = financial_summary(this_month_start, today.isoformat(), farm_id)
    last = financial_summary(last_month_start, (today.replace(day=1)-timedelta(days=1)).isoformat(), farm_id)
    ytd = financial_summary(year_start, today.isoformat(), farm_id)
    prior = financial_summary(periods['previous_year_start'], periods['previous_year_end'], farm_id)
    comparable = financial_summary(periods['previous_month_start'], periods['previous_month_end'], farm_id)
    this_m_income, this_m_exp, this_m_net = current['total_income'], current['total_exp'], current['net']
    last_m_income, last_m_exp, last_m_net = last['total_income'], last['total_exp'], last['net']
    ytd_income, ytd_exp = ytd['total_income'], ytd['total_exp']
    prior_income, prior_exp = prior['total_income'], prior['total_exp']

    # ── MoM and YoY changes ──────────────────────────────────────────────────
    mom_income_chg = _pct_change(comparable['total_income'], this_m_income)
    mom_exp_chg    = _pct_change(comparable['total_exp'], this_m_exp)
    mom_net_chg    = _pct_change(comparable['net'], this_m_net)
    yoy_income_chg = _pct_change(prior_income, ytd_income)
    yoy_exp_chg    = _pct_change(prior_exp, ytd_exp)

    chart_from = month_start_months_ago(today, 17)
    monthly_chart = monthly_financials(chart_from, today.isoformat(), farm_id)
    harvest_months = query("""
        SELECT substr(date,1,7) AS month, SUM(bunches_harvested) AS bunches,
               SUM(COALESCE(harvesting_cost,0)+COALESCE(threshing_cost,0)) AS cost
        FROM harvests WHERE farm_id=? AND date>=? AND date<=? GROUP BY month
    """, (farm_id, chart_from, today.isoformat()))
    production = {r['month']: r for r in harvest_months}
    for m in monthly_chart:
        h = production.get(m['month'])
        m['bunches'] = int(h['bunches'] or 0) if h else 0
        m['harvest_cost'] = round(h['cost'] or 0, 2) if h else 0
    exp_by_cat = [{'category': item['label'], 'total': item['value']}
                  for item in summary['expense_items'] if item['value']]

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
            request.form['name'], request.form.get('location', ''),
            request.form.get('constituency', ''), request.form.get('size_acres') or None,
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
            request.form['name'], request.form.get('location', ''),
            request.form.get('constituency', ''), request.form.get('size_acres') or None,
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
    if total_income > 0 and farm['crop_type'] != 'Oil Palm':
        margin = (total_net / total_income) * 100
        kpis.append({
            'label' : 'Profit Margin (All Time)',
            'value' : f'{margin:.1f}%',
            'status': 'good' if margin >= 0 else 'bad',
            'note'  : 'Recorded net ÷ recorded income',
        })
        if margin < 0:
            actions.append({
                'priority': 'high',
                'action'  : 'Profit margin is critically low. Review your largest expense categories and compare labour rates against your Labour Intel benchmarks.',
            })
    # ── KPI 2: MoM income growth ─────────────────────────────────────────────
    if mom_income_chg is not None and farm['crop_type'] != 'Oil Palm':
        kpis.append({
            'label' : 'Income Growth (MoM)',
            'value' : f'{("+" if mom_income_chg >= 0 else "")}{mom_income_chg}%',
            'status': 'good' if mom_income_chg >= 5 else 'warn' if mom_income_chg >= 0 else 'bad',
            'note'  : 'Same elapsed period last month',
        })
        if mom_income_chg < 0:
            actions.append({
                'priority': 'high',
                'action'  : f'Income dropped {abs(mom_income_chg)}% this month vs the same elapsed period last month. Check if a harvest was delayed or missed.',
            })

    # ── KPI 3: Expense control ───────────────────────────────────────────────
    if mom_exp_chg is not None:
        kpis.append({
            'label' : 'Expense Change (MoM)',
            'value' : f'{("+" if mom_exp_chg >= 0 else "")}{mom_exp_chg}%',
            'status': 'good' if mom_exp_chg <= 0 else 'warn' if mom_exp_chg <= 15 else 'bad',
            'note'  : 'Same elapsed period last month; compare with work performed',
        })
        if mom_exp_chg > 20:
            actions.append({
                'priority': 'medium',
                'action'  : f'Expenses rose {mom_exp_chg}% this month. Review recent materials and labour costs for unusual items.',
            })

    # ── KPI 4: YoY income growth ─────────────────────────────────────────────
    if yoy_income_chg is not None and farm['crop_type'] != 'Oil Palm':
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
            'status': 'warn',
            'note'  : 'Total expenses ÷ bunches harvested',
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
        recent_harvests = [m['bunches'] for m in monthly_chart if m['month'] < business_today().strftime('%Y-%m')][-3:]
        if len(recent_harvests)==3 and all(b == 0 for b in recent_harvests) and farm['status'] == 'Active':
            kpis.append({
                'label' : 'Harvest Activity',
                'value' : '3 Months Without Records',
                'status': 'bad',
                'note'  : 'No bunches logged recently',
            })
            actions.append({
                'priority': 'high',
                'action'  : 'No harvests have been logged for 3+ months on an active farm. Either log missed harvests or investigate why the farm is not producing.',
            })

    # ── No issues found ───────────────────────────────────────────────────────
    if not actions:
        if total_income > 0 and farm['crop_type'] != 'Oil Palm':
            actions.append({
                'priority': 'good',
                'action'  : 'No significant issues detected. Keep logging consistently to maintain accurate financial intelligence.',
            })
        else:
            actions.append({
                'priority': 'medium',
                'action'  : 'Oil sales are pooled. Use the farm cost-per-gallon profile to compare recorded production costs.' if farm['crop_type']=='Oil Palm' else 'No income recorded yet for this farm.',
            })

    return kpis, actions
