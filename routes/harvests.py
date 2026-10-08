from database.periods import business_today, comparison_periods, shift_month
"""Harvests — linked to activities, with full labour breakdown and transport."""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from database.db import query, execute, get_all_farms
from datetime import date, timedelta
import statistics

from database.harvest_workflow import save_harvest, delete_harvest

harvests_bp = Blueprint('harvests', __name__)

PICKUP_FARM_ID = 6   # Palm Farm Masu → Pickup truck
# All other oil palm farms → Tricycle


@harvests_bp.route('/')
def index():
    farm_id   = request.args.get('farm_id', '')
    date_from = request.args.get('date_from', '')
    date_to   = request.args.get('date_to', '')

    sql    = "SELECT h.*, f.name AS farm_name FROM harvests h JOIN farms f ON f.id=h.farm_id WHERE 1=1"
    params = []
    if farm_id:
        sql += " AND h.farm_id=?"; params.append(farm_id)
    if date_from:
        sql += " AND h.date>=?"; params.append(date_from)
    if date_to:
        sql += " AND h.date<=?"; params.append(date_to)
    sql += " ORDER BY h.date DESC"

    harvests   = query(sql, params)
    farms      = get_all_farms()
    farm_totals = query("""
        SELECT f.name, COALESCE(SUM(h.bunches_harvested),0) AS total_bunches,
               COALESCE(SUM(h.gallons_produced),0) AS total_gallons
        FROM farms f LEFT JOIN harvests h ON h.farm_id=f.id
        WHERE f.crop_type='Oil Palm'
        GROUP BY f.id ORDER BY f.id
    """)

    return render_template('harvests/index.html',
        harvests=harvests, farms=farms, farm_totals=farm_totals,
        filters=dict(farm_id=farm_id, date_from=date_from, date_to=date_to),
    )


@harvests_bp.route('/add', methods=['GET', 'POST'])
def add():
    farms       = get_all_farms()
    farm_id     = request.args.get('farm_id', '')
    activity_id = request.args.get('activity_id', '')

    if request.method == 'POST':
        try:
            save_harvest(request.form, activity_id=request.form.get('activity_id') or None)
        except ValueError as exc:
            flash(str(exc), 'error')
            return redirect(request.url)
        flash('Harvest saved. Processed oil contributes to pooled storage; record sales in Storage.', 'success')
        return redirect(url_for('harvests.index'))

    # Determine default transport mode based on farm
    default_transport = 'Pickup' if str(farm_id) == str(PICKUP_FARM_ID) else 'Tricycle'

    return render_template('harvests/add.html',
        farms=farms,
        farm_id=farm_id,
        activity_id=activity_id,
        pickup_farm_id=PICKUP_FARM_ID,
        default_transport=default_transport,
    )


@harvests_bp.route('/<int:harvest_id>/edit', methods=['GET', 'POST'])
def edit(harvest_id):
    harvest = query("SELECT * FROM harvests WHERE id=?", (harvest_id,), one=True)
    if not harvest:
        flash('Harvest not found.', 'error')
        return redirect(url_for('harvests.index'))
    farms = get_all_farms()
    if request.method == 'POST':
        try:
            save_harvest(request.form, harvest_id=harvest_id)
        except ValueError as exc:
            flash(str(exc), 'error')
            return redirect(request.url)
        flash('Harvest updated. Pooled stock reflects the saved production once.', 'success')
        return redirect(url_for('harvests.index'))
    transport = query('SELECT * FROM transport_logs WHERE harvest_id=?', (harvest_id,), one=True)
    harvest = dict(harvest)
    if transport:
        harvest.update(driver_pay=transport['driver_pay'],fuel_cost=transport['fuel_cost'],tricycle_rent=transport['rental_cost'],transport_mode=transport['transport_type'])
    return render_template('harvests/edit.html',
        harvest=harvest, farms=farms, pickup_farm_id=PICKUP_FARM_ID)


@harvests_bp.route('/<int:harvest_id>/delete', methods=['POST'])
def delete(harvest_id):
    try:
        delete_harvest(harvest_id)
    except ValueError as exc:
        flash(str(exc), 'error')
        return redirect(url_for('harvests.index'))
    flash('Harvest deleted.', 'success')
    return redirect(url_for('harvests.index'))


@harvests_bp.route('/forecast')
def forecast():
    today=business_today()
    last_complete=today.replace(day=1)-timedelta(days=1)
    first=shift_month(today.replace(day=1),-12)
    months=[shift_month(first,i).strftime('%Y-%m') for i in range(12)]
    farms=query("SELECT * FROM farms WHERE status='Active' AND crop_type='Oil Palm'")
    forecasts=[]
    for farm in farms:
        rows=query("""SELECT substr(date,1,7) month,SUM(bunches_harvested) total,COUNT(*) records
            FROM harvests WHERE farm_id=? AND date>=? AND date<=? GROUP BY month""",
            (farm['id'],first.isoformat(),last_complete.isoformat()))
        found={r['month']:r for r in rows}
        monthly=[dict(month=m,total=(found[m]['total'] or 0) if m in found else 0,has_records=m in found) for m in months]
        values=[m['total'] for m in monthly]
        avg=statistics.mean(values)
        enough=sum(r['records'] for r in rows)>=2
        projected=[dict(month=shift_month(today.replace(day=1),i).strftime('%B %Y'),
                        bunches=max(0,round(avg))) for i in range(1,4)] if enough else []
        forecasts.append(dict(farm=farm,monthly=monthly,average=round(avg),projected=projected,
                              unrecorded_months=sum(not m['has_records'] for m in monthly)))
    return render_template('harvests/forecast.html',forecasts=forecasts,
                           period_start=first.isoformat(),period_end=last_complete.isoformat())
