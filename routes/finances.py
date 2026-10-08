from database.periods import business_today
"""Finances — consolidated P&L + harvest analytics."""

from flask import Blueprint, render_template, request, abort
from database.db import query
from database.oil_costs import cost_profile, harvest_costs
from database.financials import financial_summary, monthly_financials, farm_financials, month_start_months_ago
from datetime import date

finances_bp = Blueprint('finances', __name__)


@finances_bp.route('/')
def index():
    today      = business_today()
    year_start = today.replace(month=1, day=1).isoformat()

    summary = financial_summary()
    farm_rows = farm_financials()
    total_farm_income = round(sum(f['income'] for f in farm_rows), 2)
    total_farm_expenses = financial_summary(scope='farms')['total_exp']
    plant = dict(electricity=summary['elec_exp'], operator_pay=summary['op_exp'])
    plant_other_exp = summary['plant_other']
    plant_income = financial_summary(scope='plant')['total_income']
    plant_expenses = round(summary['elec_exp'] + summary['op_exp'] + plant_other_exp, 2)
    plant_net = round(plant_income - plant_expenses, 2)
    total_income, total_expenses, total_net = summary['total_income'], summary['total_exp'], summary['net']
    net_margin = round(total_net / total_income * 100, 1) if total_income > 0 else 0
    ytd = financial_summary(year_start, today.isoformat())
    ytd_income, ytd_exp = ytd['total_income'], ytd['total_exp']
    monthly_chart = monthly_financials(month_start_months_ago(today, 11), today.isoformat())

    # ── Harvest analytics (per-harvest metrics) ───────────────────────────────
    harvest_analytics = harvest_costs('',today.isoformat())

    income_distribution = summary['income_items']

    return render_template('finances/index.html',
        cost_cards=cost_profile('',today.isoformat()), cost_period='Beginning of records through '+today.isoformat(),
        today=today,
        summary=summary,
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


@finances_bp.route('/oil-costs')
def oil_costs():
    from database.oil_costs import cost_profile, CATEGORIES
    today=business_today().isoformat()
    start=request.args.get('date_from','')
    end=request.args.get('date_to') or today
    try:
        if start:date.fromisoformat(start)
        date.fromisoformat(end)
        if start and start>end:raise ValueError()
        if end>today:raise ValueError()
    except ValueError:
        abort(400,description='Use a valid date range ending today or earlier.')
    profile=cost_profile(start,end)
    if request.args.get('download')=='csv':
        from routes.reports import _csv
        rows=[[r['name'],start or 'Beginning',end,r['gallons'],*[c['cost'] for c in r['components']],r['cost'],r['unit_cost'],r['pending'],r['unknown_dates']] for r in profile['rows']]
        return _csv('farm_oil_cost_profile.csv',['Farm','From','Through','Processed gallons (25 L)',*[label+' (GHS)' for _,label in CATEGORIES],'Recorded costs (GHS)','Cost per gallon (GHS; shared costs excluded)','Harvests awaiting output','Missing processing dates'],rows)
    return render_template('finances/oil_costs.html',profile=profile,categories=CATEGORIES,date_from=start,date_to=end,today=today)
