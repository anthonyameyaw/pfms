"""Prices — oil palm price tracking and trend analysis."""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from database.db import query, execute

prices_bp = Blueprint('prices', __name__)

PRODUCTS  = ['FFB', 'Palm Oil']
OUTCOMES  = ['Accepted', 'Rejected', 'Countered']


@prices_bp.route('/')
def index():
    product   = request.args.get('product', '')
    date_from = request.args.get('date_from', '')
    date_to   = request.args.get('date_to', '')

    sql    = "SELECT * FROM price_log WHERE 1=1"
    params = []
    if product:
        sql += " AND product=?"; params.append(product)
    if date_from:
        sql += " AND date>=?"; params.append(date_from)
    if date_to:
        sql += " AND date<=?"; params.append(date_to)
    sql += " ORDER BY date DESC"

    prices = query(sql, params)

    # Stats per product
    stats = {}
    for prod in PRODUCTS:
        rows = query("""
            SELECT
                MAX(price_accepted) AS highest,
                MIN(price_accepted) AS lowest,
                AVG(price_accepted) AS average,
                COUNT(*) AS count
            FROM price_log WHERE product=? AND price_accepted > 0
        """, (prod,), one=True)
        stats[prod] = rows

    # Trend data for chart
    trend = query("""
        SELECT date, product, price_offered, price_accepted
        FROM price_log ORDER BY date ASC
    """)

    return render_template('prices/index.html',
        prices=prices, stats=stats, trend=trend,
        trend_json=[dict(r) for r in trend],
        products=PRODUCTS, outcomes=OUTCOMES,
        filters=dict(product=product, date_from=date_from, date_to=date_to),
    )


@prices_bp.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        execute("""
            INSERT INTO price_log
                (date, product, buyer_source, price_offered, price_accepted,
                 unit, negotiation_outcome, notes)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            request.form['date'],
            request.form['product'],
            request.form.get('buyer_source',''),
            request.form.get('price_offered') or 0,
            request.form.get('price_accepted') or 0,
            request.form.get('unit',''),
            request.form['negotiation_outcome'],
            request.form.get('notes',''),
        ))
        flash('Price entry logged.', 'success')
        return redirect(url_for('prices.index'))
    return render_template('prices/add.html', products=PRODUCTS, outcomes=OUTCOMES)


@prices_bp.route('/<int:price_id>/delete', methods=['POST'])
def delete(price_id):
    execute("DELETE FROM price_log WHERE id=?", (price_id,))
    flash('Price entry deleted.', 'success')
    return redirect(url_for('prices.index'))
