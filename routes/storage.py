"""Storage — palm oil inventory with per-farm tracking, fresh/soap split."""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from database.db import query, execute
from datetime import date

storage_bp = Blueprint('storage', __name__)


def _current_stock():
    """Total gallons in stock = all produced - all sold."""
    produced = query("SELECT COALESCE(SUM(gallons_produced),0) AS v FROM harvests WHERE gallons_produced>0", one=True)['v'] or 0
    sold     = query("SELECT COALESCE(SUM(gallons_sold),0) AS v FROM harvests WHERE gallons_sold>0", one=True)['v'] or 0
    return float(produced) - float(sold)


def _farm_stock(farm_id):
    """Gallons in storage for a specific farm."""
    produced = query("SELECT COALESCE(SUM(gallons_produced),0) AS v FROM harvests WHERE farm_id=? AND gallons_produced>0", (farm_id,), one=True)['v'] or 0
    sold     = query("SELECT COALESCE(SUM(gallons_sold),0) AS v FROM harvests WHERE farm_id=? AND gallons_sold>0", (farm_id,), one=True)['v'] or 0
    return float(produced) - float(sold)


@storage_bp.route('/')
def index():
    today = date.today()

    # Overall stock
    total_stock = _current_stock()

    # Current price from most recent revaluation
    last_price_row = query(
        "SELECT price_per_gallon FROM storage_transactions WHERE transaction_type='Revaluation' ORDER BY date DESC LIMIT 1",
        one=True)
    current_price = float(last_price_row['price_per_gallon']) if last_price_row else 0.0
    current_value = total_stock * current_price

    # Fresh/soap split — sum from all transactions that have these set
    fresh_total = query("SELECT COALESCE(SUM(fresh_gallons),0) AS v FROM storage_transactions WHERE fresh_gallons>0", one=True)['v'] or 0
    soap_total  = query("SELECT COALESCE(SUM(soap_gallons),0) AS v FROM storage_transactions WHERE soap_gallons>0", one=True)['v'] or 0

    # Per-farm stock (derived from harvests)
    farms_raw = query("""
        SELECT f.id, f.name, f.status,
               COALESCE(SUM(h.gallons_produced),0) AS produced,
               COALESCE(SUM(h.gallons_sold),0)     AS sold
        FROM farms f
        LEFT JOIN harvests h ON h.farm_id=f.id AND h.gallons_produced>0
        WHERE f.crop_type='Oil Palm'
        GROUP BY f.id
        ORDER BY f.name
    """)

    farm_stocks = []
    for f in farms_raw:
        in_storage = float(f['produced'] or 0) - float(f['sold'] or 0)
        pct = round(in_storage / total_stock * 100, 1) if total_stock > 0 else 0
        farm_stocks.append({
            'id':         f['id'],
            'name':       f['name'],
            'status':     f['status'],
            'produced':   float(f['produced'] or 0),
            'sold':       float(f['sold'] or 0),
            'in_storage': in_storage,
            'pct':        pct,
        })

    # Price history
    value_history = query(
        "SELECT date, price_per_gallon, transaction_type, reason FROM storage_transactions WHERE price_per_gallon>0 ORDER BY date",
    )

    # All quality logs (fresh/soap entries)
    quality_logs = query("""
        SELECT * FROM storage_transactions
        WHERE fresh_gallons>0 OR soap_gallons>0
        ORDER BY date DESC
    """)

    # Transaction log (additions/removals/revaluations)
    transactions = query("SELECT * FROM storage_transactions ORDER BY date DESC, id DESC")

    # Running balance per transaction
    balances = {}
    running = 0.0
    for tx in reversed(list(transactions)):
        if tx['transaction_type'] == 'Addition':
            running += float(tx['gallons'] or 0)
        elif tx['transaction_type'] == 'Removal':
            running -= float(tx['gallons'] or 0)
        balances[tx['id']] = running

    return render_template('storage/index.html',
        today=today,
        total_stock=total_stock,
        current_price=current_price,
        current_value=current_value,
        fresh_total=fresh_total,
        soap_total=soap_total,
        farm_stocks=farm_stocks,
        value_history=[dict(r) for r in value_history],
        quality_logs=quality_logs,
        transactions=transactions,
        balances=balances,
    )


@storage_bp.route('/log-quality', methods=['GET', 'POST'])
def log_quality():
    """Log how many gallons are fresh (human consumption) vs soap production."""
    today = date.today()
    total_stock = _current_stock()

    if request.method == 'POST':
        fresh = float(request.form.get('fresh_gallons') or 0)
        soap  = float(request.form.get('soap_gallons') or 0)
        execute("""
            INSERT INTO storage_transactions
                (date, transaction_type, gallons, fresh_gallons, soap_gallons, reason, notes)
            VALUES (?, 'Addition', 0, ?, ?, ?, ?)
        """, (
            request.form.get('date') or today.isoformat(),
            fresh, soap,
            f"Quality assessment — Fresh: {fresh} gal, Soap: {soap} gal",
            request.form.get('notes', ''),
        ))
        flash(f'Quality log recorded — {fresh} gal fresh, {soap} gal for soap.', 'success')
        return redirect(url_for('storage.index'))

    return render_template('storage/log_quality.html',
        today=today.isoformat(), total_stock=total_stock)


@storage_bp.route('/revalue', methods=['GET', 'POST'])
def revalue():
    today       = date.today()
    total_stock = _current_stock()
    last_row    = query("SELECT price_per_gallon FROM storage_transactions WHERE transaction_type='Revaluation' ORDER BY date DESC LIMIT 1", one=True)
    current_price = float(last_row['price_per_gallon']) if last_row else 0.0
    current_value = total_stock * current_price

    if request.method == 'POST':
        new_price = float(request.form.get('new_price') or 0)
        execute("""
            INSERT INTO storage_transactions
                (date, transaction_type, gallons, price_per_gallon, reason, notes)
            VALUES (?, 'Revaluation', 0, ?, 'Price update', ?)
        """, (
            request.form.get('date') or today.isoformat(),
            new_price,
            request.form.get('notes', ''),
        ))
        flash(f'Price updated to GHS {new_price:.2f}/gal.', 'success')
        return redirect(url_for('storage.index'))

    return render_template('storage/revalue.html',
        today=today.isoformat(),
        current_gallons=total_stock,
        current_price=current_price,
        current_value=current_value,
    )


@storage_bp.route('/delete/<int:tx_id>', methods=['POST'])
def delete_transaction(tx_id):
    execute("DELETE FROM storage_transactions WHERE id=?", (tx_id,))
    flash('Transaction deleted.', 'success')
    return redirect(url_for('storage.index'))
