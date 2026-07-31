"""Activities — single point of entry for all farm activities including harvests."""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from database.db import query, execute, get_all_farms

activities_bp = Blueprint('activities', __name__)

ACTIVITY_TYPES = ['Harvesting', 'Weeding', 'Fertilising', 'Spraying',
                  'Pruning', 'Planting', 'Other']

PICKUP_FARM_ID = 6  # Palm Farm Masu → Pickup truck; all others → Tricycle


@activities_bp.route('/')
def index():
    farm_id   = request.args.get('farm_id', '')
    act_type  = request.args.get('activity_type', '')
    date_from = request.args.get('date_from', '')
    date_to   = request.args.get('date_to', '')

    sql    = """SELECT a.*, f.name AS farm_name
                FROM activities a JOIN farms f ON f.id=a.farm_id WHERE 1=1"""
    params = []
    if farm_id:
        sql += " AND a.farm_id=?"; params.append(farm_id)
    if act_type:
        sql += " AND a.activity_type=?"; params.append(act_type)
    if date_from:
        sql += " AND a.date>=?"; params.append(date_from)
    if date_to:
        sql += " AND a.date<=?"; params.append(date_to)
    sql += " ORDER BY a.date DESC"

    activities = query(sql, params)
    farms      = get_all_farms()
    return render_template('activities/index.html',
        activities=activities, farms=farms,
        activity_types=ACTIVITY_TYPES,
        filters=dict(farm_id=farm_id, activity_type=act_type,
                     date_from=date_from, date_to=date_to),
    )


@activities_bp.route('/add', methods=['GET', 'POST'])
def add():
    farms = get_all_farms()

    if request.method == 'POST':
        farm_id       = request.form['farm_id']
        activity_type = request.form['activity_type']
        date_val      = request.form['date']

        if activity_type == 'Harvesting':
            # ── Harvest-specific data from the inline form ────────────────
            bunches        = int(request.form.get('bunches_harvested') or 0)
            harvester_pay  = float(request.form.get('harvester_pay') or bunches * 3.0)
            collector_pay  = float(request.form.get('collector_pay') or 0)
            num_collectors = int(request.form.get('num_collectors') or 0)
            total_labour   = harvester_pay + collector_pay

            husks_processed  = request.form.get('husks_processed', '')
            gallons_produced = float(request.form.get('gallons_produced') or 0) if husks_processed == '1' else 0
            price_per_gallon = 0.0  # price tracked at sale level now

            # Sale details
            gallons_sold_yn    = request.form.get('gallons_sold_yn', '')
            gallons_sold       = float(request.form.get('gallons_sold') or 0) if gallons_sold_yn == '1' else 0
            gallons_sold_price = float(request.form.get('gallons_sold_price') or 0)
            gallons_sold_income= float(request.form.get('gallons_sold_income') or 0)
            oil_income         = gallons_sold_income  # income = only from sold gallons

            transport_mode = request.form.get('transport_mode', '')
            driver_pay     = float(request.form.get('driver_pay') or 0)
            fuel_cost      = float(request.form.get('fuel_cost') or 0)
            tricycle_rent  = float(request.form.get('tricycle_rent') or 0)

            # 1. Save the activity record
            activity_id = execute("""
                INSERT INTO activities
                    (farm_id, date, activity_type, description,
                     num_labourers, labour_cost, materials_used, materials_cost, notes)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                farm_id, date_val, 'Harvesting',
                f'{bunches} husks harvested',
                num_collectors, total_labour,
                '', 0,
                request.form.get('notes', ''),
            ))

            # 2. Save the harvest record
            execute("""
                INSERT INTO harvests
                    (farm_id, activity_id, date, bunches_harvested,
                     num_labourers, num_collectors,
                     harvester_pay, collector_pay, harvesting_cost,
                     husks_processed, gallons_produced, price_per_gallon, oil_income,
                     gallons_sold, gallons_sold_price, gallons_sold_income,
                     transport_mode, driver_pay, fuel_cost, tricycle_rent,
                     notes)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,0,0,?)
            """, (
                farm_id, activity_id, date_val, bunches,
                num_collectors, num_collectors,
                harvester_pay, collector_pay, total_labour,
                1 if husks_processed == '1' else 0,
                gallons_produced, price_per_gallon, gallons_sold_income,
                gallons_sold, gallons_sold_price, gallons_sold_income,
                transport_mode,
                request.form.get('notes', ''),
            ))

            # Income is stored directly in harvests.gallons_sold_income
            # No separate farm_income insert needed - avoids duplicates

            # 4. Auto-record transport cost
            if transport_mode == 'Pickup' and (driver_pay > 0 or fuel_cost > 0):
                execute("""
                    INSERT INTO transport_logs
                        (date, transport_type, farm_id, driver_pay, fuel_cost, notes)
                    VALUES (?,?,?,?,?,?)
                """, (date_val, 'Pickup', farm_id, driver_pay, fuel_cost,
                      'Auto from harvest activity log'))

            elif transport_mode == 'Tricycle' and tricycle_rent > 0:
                execute("""
                    INSERT INTO transport_logs
                        (date, transport_type, farm_id, rental_cost, notes)
                    VALUES (?,?,?,?,?)
                """, (date_val, 'Tricycle', farm_id, tricycle_rent,
                      'Auto from harvest activity log'))

            flash('Harvest activity logged — husks, labour, oil income, and transport all recorded.', 'success')
            return redirect(url_for('activities.index'))

        elif activity_type == 'Pruning':
            # Save activity then redirect to pruning batch form
            activity_id = execute("""
                INSERT INTO activities
                    (farm_id, date, activity_type, description,
                     num_labourers, labour_cost, materials_used, materials_cost, notes)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                farm_id, date_val, 'Pruning',
                request.form.get('description', ''),
                request.form.get('num_labourers') or 0,
                request.form.get('labour_cost') or 0,
                request.form.get('materials_used', ''),
                request.form.get('materials_cost') or 0,
                request.form.get('notes', ''),
            ))
            flash('Activity logged. Now record the pruning batch details.', 'success')
            return redirect(url_for('pruning.add_batch',
                farm_id=farm_id, activity_id=activity_id))

        else:
            # Standard activity
            execute("""
                INSERT INTO activities
                    (farm_id, date, activity_type, description,
                     num_labourers, labour_cost, materials_used, materials_cost, notes)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                farm_id, date_val, activity_type,
                request.form.get('description', ''),
                request.form.get('num_labourers') or 0,
                request.form.get('labour_cost') or 0,
                request.form.get('materials_used', ''),
                request.form.get('materials_cost') or 0,
                request.form.get('notes', ''),
            ))
            flash('Activity logged.', 'success')
            return redirect(url_for('activities.index'))

    preselect_farm = request.args.get('farm_id', '')
    return render_template('activities/add.html',
        farms=farms,
        activity_types=ACTIVITY_TYPES,
        preselect_farm=preselect_farm,
        pickup_farm_id=PICKUP_FARM_ID,
    )


@activities_bp.route('/<int:activity_id>/edit', methods=['GET', 'POST'])
def edit(activity_id):
    activity = query("SELECT * FROM activities WHERE id=?", (activity_id,), one=True)
    if not activity:
        flash('Activity not found.', 'error')
        return redirect(url_for('activities.index'))
    farms = get_all_farms()

    # Fetch linked harvest record if this is a harvest activity
    linked_harvest = query(
        "SELECT * FROM harvests WHERE activity_id=? ORDER BY id DESC LIMIT 1",
        (activity_id,), one=True
    )

    # Fetch transport from transport_logs (source of truth)
    linked_transport = None
    if linked_harvest and activity['activity_type'] == 'Harvesting':
        linked_transport = query(
            "SELECT * FROM transport_logs WHERE farm_id=? AND date=? AND notes LIKE '%harvest%' ORDER BY id DESC LIMIT 1",
            (activity['farm_id'], activity['date']), one=True
        )

    if request.method == 'POST':
        farm_id       = request.form['farm_id']
        activity_type = request.form['activity_type']
        date_val      = request.form['date']

        if activity_type == 'Harvesting':
            bunches        = int(request.form.get('bunches_harvested') or 0)
            harvester_pay  = float(request.form.get('harvester_pay') or bunches * 3.0)
            collector_pay  = float(request.form.get('collector_pay') or 0)
            num_collectors = int(request.form.get('num_collectors') or 0)
            total_labour   = harvester_pay + collector_pay
            husks_processed   = request.form.get('husks_processed', '')
            gallons           = float(request.form.get('gallons_produced') or 0) if husks_processed == '1' else 0
            gallons_sold_yn    = request.form.get('gallons_sold_yn', '')
            gallons_sold       = float(request.form.get('gallons_sold') or 0) if gallons_sold_yn == '1' else 0
            gallons_sold_price = float(request.form.get('gallons_sold_price') or 0)
            oil_income         = round(gallons_sold * gallons_sold_price, 2)
            transport_mode = request.form.get('transport_mode', '')
            driver_pay     = float(request.form.get('driver_pay') or 0)
            fuel_cost      = float(request.form.get('fuel_cost') or 0)
            tricycle_rent  = float(request.form.get('tricycle_rent') or 0)

            # Update activity
            execute("""
                UPDATE activities SET farm_id=?, date=?, activity_type=?,
                description=?, num_labourers=?, labour_cost=?,
                materials_used=?, materials_cost=?, notes=?
                WHERE id=?
            """, (
                farm_id, date_val, 'Harvesting',
                f'{bunches} husks harvested',
                num_collectors, total_labour, '', 0,
                request.form.get('notes', ''), activity_id,
            ))

            # Update or insert harvest record
            if linked_harvest:
                execute("""
                    UPDATE harvests SET
                        farm_id=?, date=?, bunches_harvested=?,
                        num_labourers=?, num_collectors=?,
                        harvester_pay=?, collector_pay=?, harvesting_cost=?,
                        husks_processed=?, gallons_produced=?, price_per_gallon=?, oil_income=?,
                        gallons_sold=?, gallons_sold_price=?, gallons_sold_income=?,
                        transport_mode=?, driver_pay=0, fuel_cost=0, tricycle_rent=0,
                        notes=?
                    WHERE activity_id=?
                """, (
                    farm_id, date_val, bunches,
                    num_collectors, num_collectors,
                    harvester_pay, collector_pay, total_labour,
                    1 if husks_processed == '1' else 0,
                    gallons, 0, oil_income,
                    gallons_sold, gallons_sold_price, oil_income,
                    transport_mode,
                    request.form.get('notes', ''), activity_id,
                ))
                # Income stored in harvests.gallons_sold_income - no farm_income insert needed

                # ── Update transport log for this harvest ─────────────────────
                # Remove old auto-transport entry for this activity and re-insert
                harvest_row = query(
                    "SELECT id FROM harvests WHERE activity_id=? LIMIT 1",
                    (activity_id,), one=True
                )
                # Delete any existing auto-transport logs for this farm+date
                # (identified by matching date and farm — only remove auto-entries)
                if transport_mode == 'Pickup' and (driver_pay > 0 or fuel_cost > 0):
                    execute("""
                        DELETE FROM transport_logs
                        WHERE farm_id=? AND date=? AND transport_type='Pickup'
                          AND notes LIKE '%harvest%'
                    """, (farm_id, date_val))
                    execute("""
                        INSERT INTO transport_logs
                            (date, transport_type, farm_id, driver_pay, fuel_cost, notes)
                        VALUES (?,?,?,?,?,?)
                    """, (date_val, 'Pickup', farm_id, driver_pay, fuel_cost,
                          'Auto from harvest activity log'))
                elif transport_mode == 'Tricycle' and tricycle_rent > 0:
                    execute("""
                        DELETE FROM transport_logs
                        WHERE farm_id=? AND date=? AND transport_type='Tricycle'
                          AND notes LIKE '%harvest%'
                    """, (farm_id, date_val))
                    execute("""
                        INSERT INTO transport_logs
                            (date, transport_type, farm_id, rental_cost, notes)
                        VALUES (?,?,?,?,?)
                    """, (date_val, 'Tricycle', farm_id, tricycle_rent,
                          'Auto from harvest activity log'))
            else:
                execute("""
                    INSERT INTO harvests
                        (farm_id, activity_id, date, bunches_harvested,
                         num_labourers, num_collectors,
                         harvester_pay, collector_pay, harvesting_cost,
                         gallons_produced, price_per_gallon, oil_income,
                         transport_mode, driver_pay, fuel_cost, tricycle_rent, notes)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    farm_id, activity_id, date_val, bunches,
                    num_collectors, num_collectors,
                    harvester_pay, collector_pay, total_labour,
                    gallons, price, oil_income,
                    transport_mode, driver_pay, fuel_cost, tricycle_rent,
                    request.form.get('notes', ''),
                ))

            flash('Harvest activity updated.', 'success')
        else:
            execute("""
                UPDATE activities SET farm_id=?, date=?, activity_type=?,
                description=?, num_labourers=?, labour_cost=?,
                materials_used=?, materials_cost=?, notes=?
                WHERE id=?
            """, (
                farm_id, date_val, activity_type,
                request.form.get('description', ''),
                request.form.get('num_labourers') or 0,
                request.form.get('labour_cost') or 0,
                request.form.get('materials_used', ''),
                request.form.get('materials_cost') or 0,
                request.form.get('notes', ''),
                activity_id,
            ))
            flash('Activity updated.', 'success')

        return redirect(url_for('activities.index'))

    return render_template('activities/edit.html',
        activity=activity,
        farms=farms,
        activity_types=ACTIVITY_TYPES,
        linked_harvest=linked_harvest,
        linked_transport=linked_transport,
        pickup_farm_id=PICKUP_FARM_ID,
    )


@activities_bp.route('/<int:activity_id>/delete', methods=['POST'])
def delete(activity_id):
    execute("DELETE FROM activities WHERE id=?", (activity_id,))
    flash('Activity deleted.', 'success')
    return redirect(url_for('activities.index'))
