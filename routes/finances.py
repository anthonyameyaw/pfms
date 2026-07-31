"""Finances — consolidated P&L + harvest analytics."""

from flask import Blueprint, render_template
from database.db import query
from datetime import date

finances_bp = Blueprint('finances', __name__)


def _s(sql, params=()):
    row = query(sql, params, one=True)
    return float(list(row)[0]) if row else 0.0


@finances_bp.route('/')
def index():
    today      = date.today()
    year_start = today.replace(month=1, day=1).isoformat()

    # ── Per-farm P&L ─────────────────────────────────────────────────────────
    farms = query("""
        SELECT f.id, f.name, f.status, f.crop_type,
               COALESCE((SELECT SUM(h.gallons_sold_income)
                         FROM harvests h WHERE h.farm_id=f.id AND h.gallons_sold_income>0),0) AS income,
               COALESCE((SELECT SUM(h.harvesting_cost)
                         FROM harvests h WHERE h.farm_id=f.id),0) AS harv_cost,
               COALESCE((SELECT SUM(h.threshing_cost)
                         FROM harvests h WHERE h.farm_id=f.id),0) AS thresh_cost,
               COALESCE((SELECT SUM(t.total_cost)
                         FROM transport_logs t WHERE t.farm_id=f.id),0) AS transport_cost,
               COALESCE((SELECT SUM(a.labour_cost+a.materials_cost)
                         FROM activities a WHERE a.farm_id=f.id
                           AND a.activity_type!='Harvesting'),0) AS activity_cost,
               COALESCE((SELECT SUM(fe.amount)
                         FROM farm_expenses fe WHERE fe.farm_id=f.id),0) AS other_expenses
        FROM farms f ORDER BY f.crop_type DESC, f.name
    """)

    farm_rows = []
    total_farm_income = 0.0
    total_farm_expenses = 0.0

    for f in farms:
        income   = f['income']
        expenses = (f['harv_cost'] + f['thresh_cost'] + f['transport_cost']
                    + f['activity_cost'] + f['other_expenses'])
        net = income - expenses
        total_farm_income   += income
        total_farm_expenses += expenses
        farm_rows.append({
            'id': f['id'], 'name': f['name'], 'status': f['status'],
            'crop_type': f['crop_type'],
            'income': income, 'expenses': expenses, 'net': net,
            'harv_cost':      f['harv_cost'],
            'thresh_cost':    f['thresh_cost'],
            'transport_cost': f['transport_cost'],
            'activity_cost':  f['activity_cost'],
            'other_expenses': f['other_expenses'],
        })

    # ── Plant P&L ─────────────────────────────────────────────────────────────
    plant = query("""
        SELECT COALESCE(SUM(company_revenue),0)     AS company_revenue,
               COALESCE(SUM(outside_farmer_fees),0) AS outside_fees,
               COALESCE(SUM(gross_revenue),0)        AS gross_revenue,
               COALESCE(SUM(electricity_cost),0)     AS electricity,
               COALESCE(SUM(operator_pay),0)         AS operator_pay,
               COALESCE(SUM(net_revenue),0)          AS net_revenue
        FROM processing_runs
    """, one=True)

    plant_other_exp = _s("SELECT COALESCE(SUM(amount),0) FROM plant_expenses")
    plant_income    = float(plant['gross_revenue'] or 0)
    plant_expenses  = float(plant['electricity'] or 0) + float(plant['operator_pay'] or 0) + plant_other_exp
    plant_net       = plant_income - plant_expenses

    # ── Consolidated ──────────────────────────────────────────────────────────
    total_income   = total_farm_income + plant_income
    total_expenses = total_farm_expenses + plant_expenses
    total_net      = total_income - total_expenses
    net_margin     = round(total_net / total_income * 100, 1) if total_income > 0 else 0

    # ── YTD ───────────────────────────────────────────────────────────────────
    ytd_income = (
        _s("SELECT COALESCE(SUM(gallons_sold_income),0) FROM harvests WHERE date>=? AND gallons_sold_income>0", (year_start,))
      + _s("SELECT COALESCE(SUM(gross_revenue),0) FROM processing_runs WHERE date>=?", (year_start,))
    )
    ytd_exp = (
        _s("SELECT COALESCE(SUM(harvesting_cost),0) FROM harvests WHERE date>=?", (year_start,))
      + _s("SELECT COALESCE(SUM(threshing_cost),0) FROM harvests WHERE date>=?", (year_start,))
      + _s("SELECT COALESCE(SUM(total_cost),0) FROM transport_logs WHERE date>=?", (year_start,))
      + _s("SELECT COALESCE(SUM(electricity_cost+operator_pay),0) FROM processing_runs WHERE date>=?", (year_start,))
      + _s("SELECT COALESCE(SUM(labour_cost+materials_cost),0) FROM activities WHERE date>=? AND activity_type!='Harvesting'", (year_start,))
      + _s("SELECT COALESCE(SUM(amount),0) FROM plant_expenses WHERE date>=?", (year_start,))
    )

    # ── Monthly chart ─────────────────────────────────────────────────────────
    monthly = query("""
        SELECT m AS month, SUM(income) AS income, SUM(exp) AS expenses FROM (
            SELECT strftime('%Y-%m',date) AS m, SUM(gallons_sold_income) AS income, 0 AS exp
            FROM harvests WHERE gallons_sold_income>0
              AND date>=DATE('now','-12 months') GROUP BY m
            UNION ALL
            SELECT strftime('%Y-%m',date), SUM(gross_revenue), 0
            FROM processing_runs WHERE date>=DATE('now','-12 months') GROUP BY strftime('%Y-%m',date)
            UNION ALL
            SELECT strftime('%Y-%m',date), 0, SUM(harvesting_cost)+COALESCE(SUM(threshing_cost),0)
            FROM harvests WHERE date>=DATE('now','-12 months') GROUP BY strftime('%Y-%m',date)
            UNION ALL
            SELECT strftime('%Y-%m',date), 0, SUM(total_cost)
            FROM transport_logs WHERE date>=DATE('now','-12 months') GROUP BY strftime('%Y-%m',date)
            UNION ALL
            SELECT strftime('%Y-%m',date), 0, SUM(electricity_cost+operator_pay)
            FROM processing_runs WHERE date>=DATE('now','-12 months') GROUP BY strftime('%Y-%m',date)
        ) GROUP BY m ORDER BY m
    """)
    monthly_chart = [
        {'month': r['month'],
         'income':   round(r['income'] or 0, 2),
         'expenses': round(r['expenses'] or 0, 2),
         'net':      round((r['income'] or 0) - (r['expenses'] or 0), 2)}
        for r in monthly
    ]

    # ── Harvest analytics (per-harvest metrics) ───────────────────────────────
    harvests_raw = query("""
        SELECT h.id, h.date, f.name AS farm_name,
               h.bunches_harvested,
               h.husks_processed,
               h.gallons_produced,
               h.gallons_sold,
               h.gallons_sold_income,
               h.gallons_sold_price,
               COALESCE(h.harvesting_cost,0)  AS harv_cost,
               COALESCE(h.threshing_cost,0)   AS thresh_cost,
               COALESCE((SELECT SUM(t.total_cost) FROM transport_logs t
                         WHERE t.farm_id=h.farm_id
                           AND t.date=h.date),0) AS transport_cost
        FROM harvests h
        JOIN farms f ON f.id=h.farm_id
        WHERE h.gallons_produced > 0
        ORDER BY h.date DESC
        LIMIT 50
    """)

    harvest_analytics = []
    for h in harvests_raw:
        gal        = float(h['gallons_produced'] or 0)
        income     = float(h['gallons_sold_income'] or 0)
        harv       = float(h['harv_cost'] or 0)
        thresh     = float(h['thresh_cost'] or 0)
        trans      = float(h['transport_cost'] or 0)
        total_lab  = harv + thresh
        total_cost = total_lab + trans
        price      = float(h['gallons_sold_price'] or 0)
        bunches    = float(h['bunches_harvested'] or 0)
        husks      = float(h['husks_processed'] or 0)

        if gal <= 0:
            continue
        # Skip harvests with no income AND no price — cost distribution meaningless
        # but still include them for levelized cost and other metrics

        # Use actual income if available, else estimate from price * gallons
        # If neither available, skip cost distribution (can't calculate %)
        if income > 0:
            gallon_value = income
        elif price > 0 and gal > 0:
            gallon_value = price * gal
        else:
            gallon_value = 0

        # 1. Cost distribution % — only calculate if we have a real income value
        if gallon_value > 0:
            lab_pct   = round(total_lab / gallon_value * 100, 1)
            trans_pct = round(trans / gallon_value * 100, 1)
            # Cap at 100% in case costs exceed income
            total_cost_pct = min(lab_pct + trans_pct, 100)
            net_pct   = max(0, round(100 - total_cost_pct, 1))
        else:
            # No sale recorded yet — show cost breakdown but flag as no income
            lab_pct   = 0
            trans_pct = 0
            net_pct   = 0

        # 2. Husks per gallon (efficiency — lower = better)
        husks_per_gal = round(husks / gal, 2) if gal > 0 else 0

        # 3. Levelized cost (total cost / gallons produced)
        levelized = round(total_cost / gal, 2) if gal > 0 else 0

        # 4. Gross margin per gallon (price - levelized cost)
        margin_per_gal = round(price - levelized, 2) if price > 0 else 0

        # 5. Labour efficiency (income per GHS spent on labour)
        labour_roi = round(income / total_lab, 2) if total_lab > 0 else 0

        harvest_analytics.append({
            'id':            h['id'],
            'date':          h['date'],
            'farm':          h['farm_name'],
            'bunches':       int(bunches),
            'husks':         int(husks),
            'gallons':       gal,
            'income':        round(income, 2),
            'harv_cost':     round(harv, 2),
            'thresh_cost':   round(thresh, 2),
            'total_lab':     round(total_lab, 2),
            'trans_cost':    round(trans, 2),
            'total_cost':    round(total_cost, 2),
            'price':         price,
            'lab_pct':       lab_pct,
            'trans_pct':     trans_pct,
            'net_pct':       net_pct,
            'husks_per_gal': husks_per_gal,
            'levelized':     levelized,
            'margin_per_gal':margin_per_gal,
            'labour_roi':    labour_roi,
        })

    income_distribution = [
        {'label': 'Farm Oil Sales',    'value': round(total_farm_income, 2)},
        {'label': 'Plant Processing',  'value': round(plant_income, 2)},
    ]

    return render_template('finances/index.html',
        today=today,
        farm_rows=farm_rows,
        total_farm_income=total_farm_income,
        total_farm_expenses=total_farm_expenses,
        plant=dict(plant),
        plant_other_exp=plant_other_exp,
        plant_income=plant_income,
        plant_expenses=plant_expenses,
        plant_net=plant_net,
        total_income=total_income,
        total_expenses=total_expenses,
        total_net=total_net,
        net_margin=net_margin,
        ytd_income=ytd_income,
        ytd_exp=ytd_exp,
        ytd_net=ytd_income - ytd_exp,
        monthly_chart=monthly_chart,
        harvest_analytics=harvest_analytics,
        income_distribution=income_distribution,
    )
