"""Activities — single point of entry for all farm activities including harvests."""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from database.db import query, execute, get_all_farms

from database.harvest_workflow import save_harvest, delete_harvest
from database.pruning_workflow import change_linked_activity

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
            try:
                save_harvest(request.form)
            except ValueError as exc:
                flash(str(exc), 'error')
                return redirect(request.url)
            flash('Harvest saved. Processed oil is in pooled storage; record sales in Storage.', 'success')
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
            "SELECT * FROM transport_logs WHERE harvest_id=?",
            (linked_harvest['id'],), one=True
        )

    if request.method == 'POST':
        farm_id       = request.form['farm_id']
        activity_type = request.form['activity_type']
        date_val      = request.form['date']

        if (activity['activity_type']=='Harvesting') != (activity_type=='Harvesting'):
            flash('A harvest activity cannot be changed to another type. Edit its harvest details instead.', 'error')
            return redirect(request.url)
        if activity_type == 'Harvesting':
            try:
                save_harvest(request.form, harvest_id=linked_harvest['id'] if linked_harvest else None,
                             activity_id=activity_id if activity['activity_type']=='Harvesting' else None)
            except ValueError as exc:
                flash(str(exc), 'error')
                return redirect(request.url)
            flash('Harvest updated.', 'success')
        elif query('SELECT id FROM pruning_batches WHERE activity_id=?', (activity_id,), one=True):
            try:
                change_linked_activity(activity_id, request.form)
            except ValueError as exc:
                flash(str(exc), 'error')
                return redirect(request.url)
            flash('Pruning activity and batch updated.', 'success')
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
    harvest = query('SELECT id FROM harvests WHERE activity_id=?', (activity_id,), one=True)
    if harvest:
        try:
            delete_harvest(harvest['id'])
        except ValueError as exc:
            flash(str(exc), 'error')
            return redirect(url_for('activities.index'))
    elif query('SELECT id FROM pruning_batches WHERE activity_id=?', (activity_id,), one=True):
        try:
            change_linked_activity(activity_id)
        except ValueError as exc:
            flash(str(exc), 'error')
            return redirect(url_for('activities.index'))
    else:
        execute("DELETE FROM activities WHERE id=?", (activity_id,))
    flash('Activity deleted.', 'success')
    return redirect(url_for('activities.index'))
