"""Dashboard — enriched with farm-of-month, heatmap, radar, notifications, trends."""

from flask import Blueprint, render_template
from database.db import query
from datetime import date, timedelta

dashboard_bp = Blueprint('dashboard', __name__)


def _sum(sql, params=()):
    row = query(sql, params, one=True)
    return float(list(row)[0]) if row else 0.0


def _total_expenses(from_date=None):
    p = (from_date,) if from_date else ()
    w = " AND date>=?" if from_date else ""
    return (
        _sum(f"SELECT COALESCE(SUM(labour_cost+materials_cost),0) FROM activities WHERE activity_type!='Harvesting'{w}", p)
      + _sum(f"SELECT COALESCE(SUM(amount),0) FROM farm_expenses{' WHERE date>=?' if from_date else ''}", p)
      + _sum(f"SELECT COALESCE(SUM(harvesting_cost),0) FROM harvests{' WHERE date>=?' if from_date else ''}", p)
      + _sum(f"SELECT COALESCE(SUM(total_cost),0) FROM transport_logs{' WHERE date>=?' if from_date else ''}", p)
      + _sum(f"SELECT COALESCE(SUM(electricity_cost+operator_pay),0) FROM processing_runs{' WHERE date>=?' if from_date else ''}", p)
      + _sum(f"SELECT COALESCE(SUM(amount),0) FROM plant_expenses{' WHERE date>=?' if from_date else ''}", p)
    )


@dashboard_bp.route('/')
def index():
    today       = date.today()
    month_start = today.replace(day=1).isoformat()
    last_month  = (today.replace(day=1) - timedelta(days=1)).replace(day=1).isoformat()
    year_start  = today.replace(month=1, day=1).isoformat()
    prev_year   = (today.replace(month=1, day=1) - timedelta(days=1)).replace(month=1, day=1).isoformat()

    # ── All-time ─────────────────────────────────────────────────────────────
    alltime_farm_income  = _sum("SELECT COALESCE(SUM(gallons_sold_income),0) FROM harvests WHERE gallons_sold_income>0")
    alltime_plant_income = _sum("SELECT COALESCE(SUM(gross_revenue),0) FROM processing_runs")
    alltime_income       = alltime_farm_income + alltime_plant_income
    alltime_expenses     = _total_expenses()
    alltime_net          = alltime_income - alltime_expenses
    net_margin  = round(alltime_net / alltime_income * 100, 1) if alltime_income > 0 else 0
    exp_ratio   = round(alltime_expenses / alltime_income * 100, 1) if alltime_income > 0 else 0
    irr_proxy   = round(alltime_net / alltime_expenses * 100, 1) if alltime_expenses > 0 else 0

    # ── Monthly ───────────────────────────────────────────────────────────────
    def month_income(start, end=None):
        w = "AND date>=? AND date<?" if end else "AND date>=?"
        p = (start, end) if end else (start,)
        return (
            _sum(f"SELECT COALESCE(SUM(gallons_sold_income),0) FROM harvests WHERE gallons_sold_income>0 {w}", p)
          + _sum(f"SELECT COALESCE(SUM(gross_revenue),0) FROM processing_runs WHERE date>=?{' AND date<?' if end else ''}", p)
        )

    monthly_income    = month_income(month_start)
    prev_month_income = month_income(last_month, month_start)
    ytd_income        = month_income(year_start)
    prior_income      = month_income(prev_year, year_start)

    monthly_expenses = _total_expenses(month_start)
    ytd_expenses     = _total_expenses(year_start)
    monthly_net      = monthly_income - monthly_expenses
    ytd_net          = ytd_income - ytd_expenses

    # Trend arrows
    def trend(current, previous):
        if previous == 0: return 'flat', 0
        pct = round(abs(current - previous) / previous * 100, 1)
        return ('up' if current > previous else 'down' if current < previous else 'flat'), pct

    income_trend,   income_pct   = trend(monthly_income, prev_month_income)
    expenses_trend, expenses_pct = trend(monthly_expenses, _total_expenses(last_month))
    net_trend,      net_pct      = trend(monthly_net, prev_month_income - _total_expenses(last_month))

    # ── Last palm oil price ───────────────────────────────────────────────────
    last_price = query("SELECT * FROM price_log ORDER BY date DESC LIMIT 1", one=True)

    # ── Farm of the month ─────────────────────────────────────────────────────
    fotm_candidates = query("""
        SELECT f.id, f.name, f.status,
               COALESCE(SUM(CASE WHEN strftime('%Y-%m',h.date)=strftime('%Y-%m','now')
                                 THEN h.gallons_sold_income ELSE 0 END),0) AS m_income,
               COALESCE(SUM(CASE WHEN strftime('%Y-%m',h.date)=strftime('%Y-%m','now')
                                 THEN h.harvesting_cost ELSE 0 END),0) AS m_harv,
               COALESCE((SELECT SUM(total_cost) FROM transport_logs t
                          WHERE t.farm_id=f.id
                            AND strftime('%Y-%m',t.date)=strftime('%Y-%m','now')),0) AS m_trans,
               COALESCE(SUM(h.gallons_sold_income),0) AS at_income,
               COALESCE(SUM(h.harvesting_cost),0)      AS at_harv,
               COALESCE(SUM(h.bunches_harvested),0)    AS bunches
        FROM farms f LEFT JOIN harvests h ON h.farm_id=f.id
        WHERE f.crop_type='Oil Palm' AND f.status='Active'
        GROUP BY f.id
    """)
    fotm = None
    best = None
    for r in fotm_candidates:
        net = r['m_income'] - r['m_harv'] - r['m_trans']
        if best is None or net > best:
            best = net
            fotm = dict(r)
            fotm['net'] = net
            fotm['alltime'] = r['m_income'] == 0
    # Fall back to all-time if no current month income
    if fotm and fotm['alltime']:
        for r in fotm_candidates:
            at_net = r['at_income'] - r['at_harv']
            if best is None or at_net > (fotm.get('at_net') or 0):
                fotm = dict(r)
                fotm['net'] = at_net
                fotm['at_net'] = at_net
                fotm['alltime'] = True

    # ── Harvest heatmap (last 365 days) ──────────────────────────────────────
    heatmap_rows = query("""
        SELECT date, SUM(bunches_harvested) AS bunches
        FROM harvests WHERE date >= DATE('now','-365 days')
        GROUP BY date ORDER BY date
    """)
    heatmap_data = {r['date']: int(r['bunches']) for r in heatmap_rows}

    # ── Radar chart (farm comparison) ────────────────────────────────────────
    radar_farms = query("""
        SELECT f.id, f.name,
               COALESCE(SUM(h.gallons_sold_income),0) AS income,
               COALESCE(SUM(h.harvesting_cost),0)
                 + COALESCE((SELECT SUM(total_cost) FROM transport_logs t WHERE t.farm_id=f.id),0) AS expenses,
               COALESCE(SUM(h.gallons_produced),0)    AS gallons,
               COALESCE(SUM(h.bunches_harvested),0)   AS bunches
        FROM farms f LEFT JOIN harvests h ON h.farm_id=f.id
        WHERE f.crop_type='Oil Palm' AND f.status='Active'
        GROUP BY f.id
    """)

    def normalise(rows, key):
        vals = [r[key] or 0 for r in rows]
        mx = max(vals) if max(vals) > 0 else 1
        return {r['id']: round((r[key] or 0) / mx * 100, 1) for r in rows}

    n_inc = normalise(radar_farms, 'income')
    n_exp = normalise(radar_farms, 'expenses')
    n_gal = normalise(radar_farms, 'gallons')
    n_bun = normalise(radar_farms, 'bunches')
    radar_data = [
        {'name': r['name'], 'income': n_inc[r['id']], 'expenses': n_exp[r['id']],
         'gallons': n_gal[r['id']], 'bunches': n_bun[r['id']]}
        for r in radar_farms
    ]

    # ── Notifications ─────────────────────────────────────────────────────────
    notif_pending = query("""
        SELECT COUNT(*) AS c FROM harvests h JOIN farms f ON f.id=h.farm_id
        WHERE (h.gallons_produced IS NULL OR h.gallons_produced=0)
          AND h.bunches_harvested>0
          AND h.husks_processed=1
          AND f.crop_type='Oil Palm'
    """, one=True)['c']

    notif_pruning = query("""
        SELECT COUNT(*) AS c FROM pruning_cycles pc
        WHERE pc.next_due_date <= DATE('now','+30 days') AND pc.is_complete=1
    """, one=True)['c']

    notif_count = notif_pending + notif_pruning

    # ── Charts ────────────────────────────────────────────────────────────────
    bunches_per_farm = query("""
        SELECT f.name, COALESCE(SUM(h.bunches_harvested),0) AS bunches
        FROM farms f LEFT JOIN harvests h ON h.farm_id=f.id
        WHERE f.crop_type='Oil Palm'
        GROUP BY f.id ORDER BY bunches DESC
    """)

    monthly_trend = query("""
        SELECT month, SUM(income) AS income, SUM(exp) AS expenses FROM (
            SELECT strftime('%Y-%m',date) AS month, SUM(gallons_sold_income) AS income, 0 AS exp
            FROM harvests WHERE date>=DATE('now','-12 months') AND gallons_sold_income>0 GROUP BY month
            UNION ALL
            SELECT strftime('%Y-%m',date) AS month, SUM(gross_revenue), 0
            FROM processing_runs WHERE date>=DATE('now','-12 months') GROUP BY month
            UNION ALL
            SELECT strftime('%Y-%m',date) AS month, 0, SUM(harvesting_cost)
            FROM harvests WHERE date>=DATE('now','-12 months') GROUP BY month
            UNION ALL
            SELECT strftime('%Y-%m',date) AS month, 0, SUM(total_cost)
            FROM transport_logs WHERE date>=DATE('now','-12 months') GROUP BY month
            UNION ALL
            SELECT strftime('%Y-%m',date) AS month, 0, SUM(electricity_cost+operator_pay)
            FROM processing_runs WHERE date>=DATE('now','-12 months') GROUP BY month
        ) GROUP BY month ORDER BY month
    """)
    monthly_chart = [
        {'month': r['month'], 'income': round(r['income'] or 0, 2),
         'expenses': round(r['expenses'] or 0, 2),
         'net': round((r['income'] or 0) - (r['expenses'] or 0), 2)}
        for r in monthly_trend
    ]

    farm_pl = query("""
        SELECT f.name,
               COALESCE(SUM(h.gallons_sold_income),0) AS income,
               COALESCE(SUM(h.harvesting_cost),0)
                 + COALESCE((SELECT SUM(total_cost) FROM transport_logs t WHERE t.farm_id=f.id),0) AS expenses
        FROM farms f LEFT JOIN harvests h ON h.farm_id=f.id
        WHERE f.crop_type='Oil Palm'
        GROUP BY f.id ORDER BY income DESC
    """)
    farm_pl_chart = [
        {'name': r['name'], 'income': round(r['income'] or 0, 2),
         'expenses': round(r['expenses'] or 0, 2),
         'net': round((r['income'] or 0) - (r['expenses'] or 0), 2)}
        for r in farm_pl
    ]

    plant_monthly = query("""
        SELECT strftime('%Y-%m',date) AS month,
               SUM(total_output_gallons) AS gallons,
               SUM(gross_revenue) AS revenue,
               SUM(electricity_cost) AS electricity
        FROM processing_runs WHERE date>=DATE('now','-12 months')
        GROUP BY month ORDER BY month
    """)

    elec_rows = query("""
        SELECT strftime('%Y-%m',date) AS month, SUM(electricity_cost) AS e, SUM(gross_revenue) AS g
        FROM processing_runs WHERE date>=DATE('now','-12 months') GROUP BY month ORDER BY month
    """)
    maint_rows = query("""
        SELECT strftime('%Y-%m',date) AS month, SUM(amount) AS m
        FROM plant_expenses WHERE date>=DATE('now','-12 months') GROUP BY month ORDER BY month
    """)
    em = {r['month']: {'electricity': r['e'] or 0, 'gross': r['g'] or 0} for r in elec_rows}
    mm = {r['month']: r['m'] or 0 for r in maint_rows}
    all_em = sorted(set(list(em.keys()) + list(mm.keys())))
    monthly_elec_maint = [
        {'month': m, 'electricity': round(em.get(m,{}).get('electricity',0),2),
         'gross_revenue': round(em.get(m,{}).get('gross',0),2),
         'maintenance': round(mm.get(m,0),2),
         'maint_pct': round(mm.get(m,0) / max(em.get(m,{}).get('gross',0)*0.7,1) * 100, 1)}
        for m in all_em
    ]

    income_distribution = [
        {'label': 'Farm Oil Sales', 'value': round(alltime_farm_income, 2)},
        {'label': 'Plant Processing', 'value': round(alltime_plant_income, 2)},
    ]

    return render_template('dashboard.html',
        today=today,
        # All-time
        alltime_income=alltime_income, alltime_expenses=alltime_expenses,
        alltime_net=alltime_net, alltime_farm_income=alltime_farm_income,
        alltime_plant_income=alltime_plant_income,
        net_margin=net_margin, exp_ratio=exp_ratio, irr_proxy=irr_proxy,
        # Monthly
        monthly_income=monthly_income, monthly_expenses=monthly_expenses,
        monthly_net=monthly_net, ytd_income=ytd_income,
        ytd_expenses=ytd_expenses, ytd_net=ytd_net,
        # Trends
        income_trend=income_trend, income_pct=income_pct,
        expenses_trend=expenses_trend, expenses_pct=expenses_pct,
        net_trend=net_trend, net_pct=net_pct,
        # Features
        last_price=last_price, fotm=fotm,
        heatmap_data=heatmap_data, radar_data=radar_data,
        notif_count=notif_count, notif_pending=notif_pending,
        notif_pruning=notif_pruning,
        # Charts
        monthly_chart=monthly_chart, farm_pl_chart=farm_pl_chart,
        bunches_per_farm=[dict(r) for r in bunches_per_farm],
        plant_monthly=[dict(r) for r in plant_monthly],
        monthly_elec_maint=monthly_elec_maint,
        income_distribution=income_distribution,
    )
