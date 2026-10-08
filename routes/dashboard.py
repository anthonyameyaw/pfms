from database.periods import business_today, comparison_periods, shift_month
"""Dashboard — enriched with farm-of-month, heatmap, radar, notifications, trends."""

from flask import Blueprint, render_template, url_for
from database.db import query
from database.financials import financial_summary, monthly_financials, farm_financials, month_start_months_ago
from datetime import date, timedelta

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
def index():
    today       = business_today()
    periods = comparison_periods(today)
    month_start = today.replace(day=1).isoformat()
    last_month  = (today.replace(day=1) - timedelta(days=1)).replace(day=1).isoformat()
    year_start  = today.replace(month=1, day=1).isoformat()

    summary = financial_summary()
    alltime_farm_income = summary['farm_income']
    alltime_plant_income = summary['plant_income']
    alltime_income, alltime_expenses, alltime_net = summary['total_income'], summary['total_exp'], summary['net']
    net_margin = round(alltime_net / alltime_income * 100, 1) if alltime_income > 0 else 0
    exp_ratio = round(alltime_expenses / alltime_income * 100, 1) if alltime_income > 0 else 0
    irr_proxy = round(alltime_net / alltime_expenses * 100, 1) if alltime_expenses > 0 else 0
    current = financial_summary(month_start, today.isoformat())
    previous = financial_summary(periods['previous_month_start'],periods['previous_month_end'])
    ytd = financial_summary(year_start, today.isoformat())
    monthly_income, monthly_expenses, monthly_net = current['total_income'], current['total_exp'], current['net']
    prev_month_income = previous['total_income']
    ytd_income, ytd_expenses, ytd_net = ytd['total_income'], ytd['total_exp'], ytd['net']

    # Trend arrows
    def trend(current, previous):
        if previous == 0: return 'flat', None
        pct = round(abs(current - previous) / abs(previous) * 100, 1)
        return ('up' if current > previous else 'down' if current < previous else 'flat'), pct

    income_trend,   income_pct   = trend(monthly_income, prev_month_income)
    expenses_trend, expenses_pct = trend(monthly_expenses, previous['total_exp'])
    net_trend,      net_pct      = trend(monthly_net, prev_month_income - previous['total_exp'])

    # ── Last palm oil price ───────────────────────────────────────────────────
    last_price = query("SELECT * FROM price_log ORDER BY date DESC LIMIT 1", one=True)

    # Highest production contribution, without mixing money and oil volume.
    candidates=[dict(row) for row in query("""SELECT f.id,f.name,
        COALESCE(SUM(CASE WHEN substr(COALESCE(h.processing_date,h.date),1,7)=? THEN h.gallons_produced ELSE 0 END),0) AS m_income,
        COALESCE(SUM(h.gallons_produced),0) AS at_income,
        COALESCE(SUM(h.bunches_harvested),0) AS bunches
        FROM farms f LEFT JOIN harvests h ON h.farm_id=f.id AND h.husks_processed=1 AND COALESCE(h.processing_date,h.date)<=?
        WHERE f.crop_type='Oil Palm' AND f.status='Active' GROUP BY f.id""", (today.strftime('%Y-%m'),today.isoformat()))]
    use_alltime=not any(c['m_income']>0 for c in candidates)
    fotm=max(candidates,key=lambda c:c['at_income'] if use_alltime else c['m_income'],default=None)
    if fotm: fotm['alltime']=use_alltime

    # ── Harvest heatmap (last 365 days) ──────────────────────────────────────
    heatmap_rows = query("""
        SELECT date, SUM(bunches_harvested) AS bunches
        FROM harvests WHERE date >= ? AND date <= ?
        GROUP BY date ORDER BY date
    """, ((today-timedelta(days=365)).isoformat(),today.isoformat()))
    heatmap_data = {r['date']: int(r['bunches']) for r in heatmap_rows}

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
        WHERE pc.next_due_date <= ? AND pc.is_complete=1
    """, ((today+timedelta(days=30)).isoformat(),), one=True)['c']

    notif_count = notif_pending + notif_pruning

    # ── Charts ────────────────────────────────────────────────────────────────
    bunches_per_farm = query("""
        SELECT f.name, COALESCE(SUM(h.bunches_harvested),0) AS bunches
        FROM farms f LEFT JOIN harvests h ON h.farm_id=f.id
        WHERE f.crop_type='Oil Palm'
        GROUP BY f.id ORDER BY bunches DESC
    """)

    monthly_chart = monthly_financials(month_start_months_ago(today, 11), today.isoformat())
    farm_pl_chart = [
        {'name': f['name'], 'income': f['income'], 'expenses': f['expenses'], 'net': f['net']}
        for f in farm_financials() if f['crop_type'] == 'Oil Palm'
    ]

    plant_monthly = query("""
        SELECT strftime('%Y-%m',date) AS month,
               SUM(total_output_gallons) AS gallons,
               SUM(gross_revenue) AS revenue,
               SUM(electricity_cost) AS electricity
        FROM processing_runs WHERE date>=? AND date<=?
        GROUP BY month ORDER BY month
    """, (month_start_months_ago(today,11), today.isoformat()))

    elec_rows = query("""
        SELECT strftime('%Y-%m',date) AS month, SUM(electricity_cost) AS e, SUM(gross_revenue) AS g
        FROM processing_runs WHERE date>=? AND date<=? GROUP BY month ORDER BY month
    """, (month_start_months_ago(today,11), today.isoformat()))
    maint_rows = query("""
        SELECT strftime('%Y-%m',date) AS month, SUM(amount) AS m
        FROM plant_expenses WHERE date>=? AND date<=? GROUP BY month ORDER BY month
    """, (month_start_months_ago(today,11), today.isoformat()))
    em = {r['month']: {'electricity': r['e'] or 0, 'gross': r['g'] or 0} for r in elec_rows}
    mm = {r['month']: r['m'] or 0 for r in maint_rows}
    all_em = [row['month'] for row in monthly_chart]
    monthly_elec_maint = [
        {'month': m, 'electricity': round(em.get(m,{}).get('electricity',0),2),
         'gross_revenue': round(em.get(m,{}).get('gross',0),2),
         'maintenance': round(mm.get(m,0),2),
         'maint_pct': round(mm.get(m,0) / em[m]['gross'] * 100, 1) if em.get(m,{}).get('gross',0)>0 else None}
        for m in all_em
    ]

    income_distribution = summary['income_items']

    day=today.isoformat()
    stock=query("""SELECT
        (SELECT COALESCE(SUM(gallons_produced),0) FROM harvests WHERE husks_processed=1 AND gallons_produced>0 AND COALESCE(processing_date,date)<=?)
        +(SELECT COALESCE(SUM(CASE WHEN transaction_type='Purchase' THEN gallons WHEN transaction_type='Sale' THEN -gallons ELSE 0 END),0) FROM storage_transactions WHERE date<=?) AS gallons""",(day,day),one=True)['gallons']
    attention=[]
    payments=query("""SELECT SUM(CASE WHEN cash_collected IS NULL THEN 1 ELSE 0 END) missing,
        COALESCE(SUM(cash_outstanding),0) outstanding FROM processing_runs WHERE date<=?""",(day,),one=True)
    if payments['missing']:
        attention.append(dict(label='Plant payments not recorded',value=str(payments['missing'])+' runs',url=url_for('plant.index'),tone='amber'))
    if payments['outstanding']>0:
        attention.append(dict(label='Processing fees outstanding',value='GHS {:,.2f}'.format(payments['outstanding']),url=url_for('plant.index'),tone='amber'))
    from routes.investors import _get_investments
    due=[i for i in _get_investments() if i['outstanding']>0 and i['return_date'] and i['return_date']<=day]
    if due:
        attention.append(dict(label='Investor repayments due',value='GHS {:,.2f}'.format(sum(i['outstanding'] for i in due)),url=url_for('investors.index'),tone='red'))
    pending=query("SELECT COUNT(*) n FROM harvests WHERE date<=? AND bunches_harvested>0 AND (husks_processed IS NOT 1 OR COALESCE(gallons_produced,0)<=0)",(day,),one=True)['n']
    if pending:
        attention.append(dict(label='Harvests awaiting oil output',value=str(pending)+' harvests',url=url_for('harvests.index'),tone='amber'))
    pruning=query("""SELECT COUNT(*) n FROM pruning_cycles c WHERE c.is_complete=1 AND c.next_due_date<=?
        AND NOT EXISTS(SELECT 1 FROM pruning_cycles newer WHERE newer.farm_id=c.farm_id
            AND (newer.cycle_start_date>c.cycle_start_date OR (newer.cycle_start_date=c.cycle_start_date AND newer.id>c.id)))""",
        ((today+timedelta(days=30)).isoformat(),),one=True)['n']
    if pruning:
        attention.append(dict(label='Pruning due within 30 days or overdue',value=str(pruning)+' farms',url=url_for('pruning.index'),tone='amber'))
    recent=[]
    sources=[
        ("SELECT h.id,h.date,f.name label,h.gallons_produced amount FROM harvests h JOIN farms f ON f.id=h.farm_id WHERE h.date<=? ORDER BY h.date DESC,h.id DESC LIMIT 8",'Harvest','gallons','harvests.edit','harvest_id'),
        ("SELECT id,date,'Processing run' label,total_output_gallons amount FROM processing_runs WHERE date<=? ORDER BY date DESC,id DESC LIMIT 8",'Processing','gallons','plant.run_detail','run_id'),
        ("SELECT id,date,COALESCE(NULLIF(buyer,''),'Oil sale') label,total_amount amount FROM storage_transactions WHERE transaction_type='Sale' AND date<=? ORDER BY date DESC,id DESC LIMIT 8",'Oil sale','GHS','storage.index',None),
        ("SELECT e.id,e.date,f.name label,e.amount FROM farm_expenses e JOIN farms f ON f.id=e.farm_id WHERE e.date<=? ORDER BY e.date DESC,e.id DESC LIMIT 8",'Farm expense','GHS','farms.detail','farm_id'),
        ("SELECT id,date,category label,amount FROM plant_expenses WHERE date<=? ORDER BY date DESC,id DESC LIMIT 8",'Plant expense','GHS','plant.expenses',None),
        ("SELECT a.id,a.date,f.name || ' · ' || a.activity_type label,COALESCE(a.labour_cost,0)+COALESCE(a.materials_cost,0) amount FROM activities a JOIN farms f ON f.id=a.farm_id WHERE a.activity_type!='Harvesting' AND a.date<=? ORDER BY a.date DESC,a.id DESC LIMIT 8",'Farm activity','GHS','activities.index',None)]
    for sql,kind,unit,endpoint,arg in sources:
        for row in query(sql,(day,)):
            args={arg:row['id']} if arg else {}
            if kind=='Farm expense':
                args={'farm_id':query('SELECT farm_id FROM farm_expenses WHERE id=?',(row['id'],),one=True)['farm_id']}
            recent.append(dict(row,kind=kind,unit=unit,url=url_for(endpoint,**args)))
    recent=sorted(recent,key=lambda x:(x['date'],x['id'],x['kind']),reverse=True)[:8]
    production=query("""SELECT f.id,f.name,COALESCE(SUM(h.gallons_produced),0) gallons FROM farms f
        LEFT JOIN harvests h ON h.farm_id=f.id AND h.husks_processed=1 AND COALESCE(h.processing_date,h.date)>=? AND COALESCE(h.processing_date,h.date)<=?
        WHERE f.crop_type='Oil Palm' GROUP BY f.id ORDER BY gallons DESC,f.name""",(month_start,day))
    return render_template('dashboard.html',
        today=today, stock_gallons=stock, attention=attention, recent=recent, production=production,
        # All-time
        alltime_income=alltime_income, alltime_expenses=alltime_expenses,
        alltime_net=alltime_net, alltime_farm_income=alltime_farm_income,
        alltime_plant_income=alltime_plant_income,
        pooled_income=summary['storage_sales'],
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
        heatmap_data=heatmap_data,
        notif_count=notif_count, notif_pending=notif_pending,
        notif_pruning=notif_pruning,
        # Charts
        monthly_chart=monthly_chart, farm_pl_chart=farm_pl_chart,
        bunches_per_farm=[dict(r) for r in bunches_per_farm],
        plant_monthly=[dict(r) for r in plant_monthly],
        monthly_elec_maint=monthly_elec_maint,
        income_distribution=income_distribution,
    )
