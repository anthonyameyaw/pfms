"""Harvests — linked to activities, with full labour breakdown and transport."""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from database.db import query, execute, get_all_farms
from datetime import date, timedelta
import statistics

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
               COALESCE(SUM(h.oil_income),0) AS total_income
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
        fid         = int(request.form['farm_id'])
        bunches     = int(request.form.get('bunches_harvested') or 0)

        # Issue 6: Labour breakdown
        harvester_pay = float(request.form.get('harvester_pay') or 0)
        # Auto-calc: 3 GHS per bunch for harvester if not overridden
        if not harvester_pay and bunches:
            harvester_pay = bunches * 3.0

        collector_pay  = float(request.form.get('collector_pay') or 0)
        num_collectors = int(request.form.get('num_collectors') or 0)
        num_labourers  = num_collectors
        total_labour   = harvester_pay + collector_pay

        # Issue 2: Gallons & income
        gallons_produced = float(request.form.get('gallons_produced') or 0)
        price_per_gallon = float(request.form.get('price_per_gallon') or 0)
        oil_income       = gallons_produced * price_per_gallon

        # Issue 7: Transport
        transport_mode = request.form.get('transport_mode', '')
        driver_pay     = float(request.form.get('driver_pay') or 0)
        fuel_cost      = float(request.form.get('fuel_cost') or 0)
        tricycle_rent  = float(request.form.get('tricycle_rent') or 0)

        harvest_id = execute("""
            INSERT INTO harvests
                (farm_id, activity_id, date, bunches_harvested,
                 num_labourers, num_collectors,
                 harvester_pay, collector_pay, harvesting_cost,
                 gallons_produced, price_per_gallon, oil_income,
                 transport_mode, driver_pay, fuel_cost, tricycle_rent,
                 notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            fid,
            request.form.get('activity_id') or None,
            request.form['date'],
            bunches,
            num_labourers,
            num_collectors,
            harvester_pay,
            collector_pay,
            total_labour,
            gallons_produced,
            price_per_gallon,
            oil_income,
            transport_mode,
            driver_pay,
            fuel_cost,
            tricycle_rent,
            request.form.get('notes', ''),
        ))

        # Update the linked activity's labour_cost to match harvest total labour
        act_id = request.form.get('activity_id')
        if act_id:
            execute("UPDATE activities SET labour_cost=?, num_labourers=? WHERE id=?",
                    (total_labour, num_labourers, act_id))

        # Auto-record oil income as farm_income entry
        if oil_income > 0:
            execute("""
                INSERT INTO farm_income (farm_id, date, income_type, buyer, quantity, unit_price, notes)
                VALUES (?,?,'FFB Sale','Palm Oil Sales',?,?,?)
            """, (fid, request.form['date'], gallons_produced, price_per_gallon,
                  f'Auto from harvest log — {bunches} bunches → {gallons_produced} gallons'))

        # Auto-record transport as transport_log entry
        if transport_mode == 'Pickup' and (driver_pay > 0 or fuel_cost > 0):
            execute("""
                INSERT INTO transport_logs (date, transport_type, farm_id, driver_pay, fuel_cost, notes)
                VALUES (?,?,?,?,?,?)
            """, (request.form['date'], 'Pickup', fid, driver_pay, fuel_cost,
                  'Auto from harvest log'))

        if transport_mode == 'Tricycle' and tricycle_rent > 0:
            execute("""
                INSERT INTO transport_logs (date, transport_type, farm_id, rental_cost, notes)
                VALUES (?,?,?,?,?)
            """, (request.form['date'], 'Tricycle', fid, tricycle_rent,
                  'Auto from harvest log'))

        flash('Harvest recorded successfully.', 'success')
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
        bunches       = int(request.form.get('bunches_harvested') or 0)
        harvester_pay = float(request.form.get('harvester_pay') or bunches * 3.0)
        collector_pay = float(request.form.get('collector_pay') or 0)
        total_labour  = harvester_pay + collector_pay
        gallons       = float(request.form.get('gallons_produced') or 0)
        price         = float(request.form.get('price_per_gallon') or 0)
        execute("""
            UPDATE harvests SET farm_id=?, date=?, bunches_harvested=?,
            num_collectors=?, harvester_pay=?, collector_pay=?, harvesting_cost=?,
            gallons_produced=?, price_per_gallon=?, oil_income=?,
            transport_mode=?, driver_pay=?, fuel_cost=?, tricycle_rent=?, notes=?
            WHERE id=?
        """, (
            request.form['farm_id'], request.form['date'], bunches,
            request.form.get('num_collectors') or 0,
            harvester_pay, collector_pay, total_labour,
            gallons, price, gallons * price,
            request.form.get('transport_mode', ''),
            request.form.get('driver_pay') or 0,
            request.form.get('fuel_cost') or 0,
            request.form.get('tricycle_rent') or 0,
            request.form.get('notes', ''),
            harvest_id,
        ))
        flash('Harvest updated.', 'success')
        return redirect(url_for('harvests.index'))
    return render_template('harvests/edit.html',
        harvest=harvest, farms=farms, pickup_farm_id=PICKUP_FARM_ID)


@harvests_bp.route('/<int:harvest_id>/delete', methods=['POST'])
def delete(harvest_id):
    execute("DELETE FROM harvests WHERE id=?", (harvest_id,))
    flash('Harvest deleted.', 'success')
    return redirect(url_for('harvests.index'))


@harvests_bp.route('/forecast')
def forecast():
    farms     = query("SELECT * FROM farms WHERE status='Active' AND crop_type='Oil Palm'")
    forecasts = []
    for farm in farms:
        monthly = query("""
            SELECT strftime('%Y-%m', date) AS month, SUM(bunches_harvested) AS total
            FROM harvests WHERE farm_id=? AND date >= DATE('now','-12 months')
            GROUP BY month ORDER BY month
        """, (farm['id'],))
        if monthly:
            values    = [r['total'] for r in monthly]
            avg       = statistics.mean(values)
            trend     = values[-1] - values[0] if len(values) > 1 else 0
            projected = []
            for i in range(1, 4):
                proj_month = (date.today().replace(day=1) + timedelta(days=32*i)).replace(day=1)
                proj_value = max(0, round(avg + (trend * i / len(values))))
                projected.append({'month': proj_month.strftime('%B %Y'), 'bunches': proj_value})
            forecasts.append({'farm': farm, 'monthly': [dict(r) for r in monthly],
                              'average': round(avg), 'projected': projected})
        else:
            forecasts.append({'farm': farm, 'monthly': [], 'average': 0, 'projected': []})
    return render_template('harvests/forecast.html', forecasts=forecasts)
