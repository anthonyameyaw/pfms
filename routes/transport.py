"""Transport — pickup trips, tricycle rentals, pickup maintenance."""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from database.db import query, execute, get_all_farms

transport_bp = Blueprint('transport', __name__)


@transport_bp.route('/')
def index():
    farm_id   = request.args.get('farm_id', '')
    t_type    = request.args.get('transport_type', '')
    date_from = request.args.get('date_from', '')
    date_to   = request.args.get('date_to', '')

    sql    = "SELECT t.*, f.name AS farm_name FROM transport_logs t LEFT JOIN farms f ON f.id=t.farm_id WHERE 1=1"
    params = []
    if farm_id:
        sql += " AND t.farm_id=?"; params.append(farm_id)
    if t_type:
        sql += " AND t.transport_type=?"; params.append(t_type)
    if date_from:
        sql += " AND t.date>=?"; params.append(date_from)
    if date_to:
        sql += " AND t.date<=?"; params.append(date_to)
    sql += " ORDER BY t.date DESC"

    logs  = query(sql, params)
    farms = get_all_farms()

    totals = query("""
        SELECT
            COALESCE(SUM(CASE WHEN transport_type='Pickup' THEN total_cost ELSE 0 END),0) AS pickup_total,
            COALESCE(SUM(CASE WHEN transport_type='Tricycle' THEN total_cost ELSE 0 END),0) AS tricycle_total,
            COALESCE(SUM(total_cost),0) AS grand_total
        FROM transport_logs
    """, one=True)

    maintenance = query(
        "SELECT * FROM pickup_maintenance ORDER BY date DESC LIMIT 5"
    )
    maint_total = query(
        "SELECT COALESCE(SUM(cost),0) AS t FROM pickup_maintenance", one=True
    )['t']

    return render_template('transport/index.html',
        logs=logs, farms=farms, totals=totals,
        maintenance=maintenance, maint_total=maint_total,
        filters=dict(farm_id=farm_id, transport_type=t_type,
                     date_from=date_from, date_to=date_to),
    )


@transport_bp.route('/add', methods=['GET', 'POST'])
def add():
    farms = get_all_farms()
    if request.method == 'POST':
        t_type = request.form['transport_type']
        execute("""
            INSERT INTO transport_logs
                (date, transport_type, farm_id, fuel_cost, driver_pay, rental_cost, notes)
            VALUES (?,?,?,?,?,?,?)
        """, (
            request.form['date'],
            t_type,
            request.form.get('farm_id') or None,
            request.form.get('fuel_cost') or 0,
            request.form.get('driver_pay') or 0,
            request.form.get('rental_cost') or 0,
            request.form.get('notes',''),
        ))
        flash('Transport log added.', 'success')
        return redirect(url_for('transport.index'))
    return render_template('transport/add.html', farms=farms)


@transport_bp.route('/<int:log_id>/delete', methods=['POST'])
def delete(log_id):
    execute("DELETE FROM transport_logs WHERE id=?", (log_id,))
    flash('Transport log deleted.', 'success')
    return redirect(url_for('transport.index'))


@transport_bp.route('/maintenance/add', methods=['GET', 'POST'])
def add_maintenance():
    if request.method == 'POST':
        execute("""
            INSERT INTO pickup_maintenance (date, description, cost, notes)
            VALUES (?,?,?,?)
        """, (
            request.form['date'],
            request.form.get('description',''),
            request.form.get('cost') or 0,
            request.form.get('notes',''),
        ))
        flash('Maintenance record added.', 'success')
        return redirect(url_for('transport.index'))
    return render_template('transport/add_maintenance.html')


@transport_bp.route('/maintenance/<int:maint_id>/delete', methods=['POST'])
def delete_maintenance(maint_id):
    execute("DELETE FROM pickup_maintenance WHERE id=?", (maint_id,))
    flash('Maintenance record deleted.', 'success')
    return redirect(url_for('transport.index'))
