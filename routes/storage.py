from database.periods import business_today
"""Storage — palm oil inventory with purchases, sales, per-farm tracking, fresh/soap split."""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from database.db import query, execute
from datetime import date
import json
from decimal import Decimal, ROUND_HALF_UP
from database.db import get_connection
from database.harvest_workflow import number, valid_date, validate_stock

from database.oil_quality import balances, KINDS

def quality_balances():
    conn=get_connection()
    try:return balances(conn)
    finally:conn.close()

storage_bp = Blueprint('storage', __name__)


def _current_stock():
    """Total gallons in stock = produced + purchased - sold."""
    produced  = query("SELECT COALESCE(SUM(gallons_produced),0) AS v FROM harvests WHERE husks_processed=1 AND gallons_produced>0", one=True)['v'] or 0
    purchased = query("SELECT COALESCE(SUM(gallons),0) AS v FROM storage_transactions WHERE transaction_type='Purchase'", one=True)['v'] or 0
    sold_stor = query("SELECT COALESCE(SUM(gallons),0) AS v FROM storage_transactions WHERE transaction_type='Sale'", one=True)['v'] or 0
    return float(produced) + float(purchased) - float(sold_stor)


@storage_bp.route('/')
def index():
    today = business_today()
    total_stock = _current_stock()

    # Current price
    last_price_row = query("SELECT price_per_gallon FROM storage_transactions WHERE transaction_type='Revaluation' ORDER BY date DESC LIMIT 1", one=True)
    current_price = float(last_price_row['price_per_gallon']) if last_price_row else 0.0
    current_value = total_stock * current_price

    # Purchase totals
    purchase_stats = query("""
        SELECT COALESCE(SUM(gallons),0) AS total_gal,
               COALESCE(SUM(total_amount),0) AS total_spent,
               COUNT(*) AS count
        FROM storage_transactions WHERE transaction_type='Purchase'
    """, one=True)

    # Sale totals (from storage_transactions)
    sale_stats = query("""
        SELECT COALESCE(SUM(gallons),0) AS total_gal,
               COALESCE(SUM(total_amount),0) AS total_revenue,
               COUNT(*) AS count
        FROM storage_transactions WHERE transaction_type='Sale'
    """, one=True)

    total_oil_revenue = float(sale_stats['total_revenue'] or 0)
    sales_by_quality={kind:dict(gallons=0,revenue=0) for kind in KINDS}
    for row in query("SELECT quality_type,SUM(gallons) gallons,SUM(total_amount) revenue FROM storage_transactions WHERE transaction_type='Sale' GROUP BY quality_type"):
        sales_by_quality[row['quality_type']]=dict(gallons=row['gallons'],revenue=row['revenue'])

    quality=quality_balances()
    fresh_total=quality['Fresh'];soap_total=quality['Soap']

    # Historical production contribution, never a claim on remaining stock.
    farm_stocks = [dict(row) for row in query("""SELECT f.id,f.name,f.status,
        COALESCE(SUM(CASE WHEN h.husks_processed=1 THEN h.gallons_produced ELSE 0 END),0) AS produced
        FROM farms f LEFT JOIN harvests h ON h.farm_id=f.id
        WHERE f.crop_type='Oil Palm' GROUP BY f.id ORDER BY f.name""")]
    farm_total = sum(f['produced'] for f in farm_stocks)
    for f in farm_stocks:
        f['pct'] = round(f['produced']/farm_total*100,1) if farm_total else 0
    review_items=[]
    for row in query('SELECT * FROM harvest_sales_archive WHERE reviewed=0'):
        old=json.loads(row['original_record'])
        review_items.append(dict(date=old['date'],harvest_id=row['harvest_id'],
            amount=old.get('gallons_sold_income') or old.get('oil_income') or 0,
            note=row['review_note']))

    # All transactions
    transactions = query("SELECT * FROM storage_transactions ORDER BY date DESC, id DESC")
    quality_logs = query("SELECT * FROM storage_transactions WHERE transaction_type IN ('Assessment','Legacy assessment') ORDER BY date DESC,id DESC")
    purchases    = query("SELECT * FROM storage_transactions WHERE transaction_type='Purchase' ORDER BY date DESC")
    sales        = query("SELECT * FROM storage_transactions WHERE transaction_type='Sale' ORDER BY date DESC")
    value_history= query("SELECT date, price_per_gallon, transaction_type, reason FROM storage_transactions WHERE price_per_gallon>0 ORDER BY date")

    return render_template('storage/index.html',
        today=today,
        review_items=review_items,
        total_stock=total_stock,
        current_price=current_price,
        current_value=current_value,
        purchase_stats=dict(purchase_stats),
        sale_stats=dict(sale_stats),
        total_oil_revenue=total_oil_revenue,
        sales_by_quality=sales_by_quality,
        unassessed_total=quality['Unassessed'],
        fresh_total=fresh_total,
        soap_total=soap_total,
        farm_stocks=farm_stocks,
        transactions=transactions,
        quality_logs=quality_logs,
        purchases=purchases,
        sales=sales,
        value_history=[dict(r) for r in value_history],
    )


def _save_oil_transaction(form, kind):
    gallons=number(form,'gallons');price=number(form,'price_per_gallon')
    day=valid_date(form.get('date') or business_today().isoformat())
    if gallons<=0 or price<=0:raise ValueError('Enter positive gallons and price.')
    amount=float((Decimal(str(gallons))*Decimal(str(price))).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))
    quality=form.get('quality_type','Unassessed')
    if quality not in KINDS:raise ValueError('Select Fresh, Soap, or Not yet assessed.')
    conn=get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute("""INSERT INTO storage_transactions
            (date,transaction_type,gallons,price_per_gallon,total_amount,buyer,seller,reason,notes,quality_type)
            VALUES(?,?,?,?,?,?,?,?,?,?)""",(day,kind,gallons,price,amount,form.get('buyer',''),form.get('seller',''),
            'Pooled oil '+kind.lower(),form.get('notes',''),quality))
        validate_stock(conn);conn.commit()
    except Exception:
        conn.rollback();raise
    finally:conn.close()


@storage_bp.route('/log-purchase', methods=['GET', 'POST'])
def log_purchase():
    today = business_today()
    if request.method == 'POST':
        try:
            _save_oil_transaction(request.form, 'Purchase')
        except ValueError as exc:
            flash(str(exc), 'error')
            return redirect(request.url)
        flash('Purchase recorded in pooled storage.', 'success')
        return redirect(url_for('storage.index'))

    return render_template('storage/log_purchase.html', today=today.isoformat())


@storage_bp.route('/log-sale', methods=['GET', 'POST'])
def log_sale():
    today       = business_today()
    total_stock = _current_stock()
    last_price  = query("SELECT price_per_gallon FROM storage_transactions WHERE transaction_type='Revaluation' ORDER BY date DESC LIMIT 1", one=True)
    current_price = float(last_price['price_per_gallon']) if last_price else 0.0

    if request.method == 'POST':
        try:
            _save_oil_transaction(request.form, 'Sale')
        except ValueError as exc:
            flash(str(exc), 'error')
            return redirect(request.url)
        flash('Sale recorded in pooled storage.', 'success')
        return redirect(url_for('storage.index'))

    return render_template('storage/log_sale.html',
        today=today.isoformat(), total_stock=total_stock, current_price=current_price, quality=quality_balances())


@storage_bp.route('/log-quality', methods=['GET', 'POST'])
def log_quality():
    today = business_today()
    total_stock = _current_stock()
    if request.method == 'POST':
        conn=get_connection()
        try:
            fresh=number(request.form,'fresh_gallons');soap=number(request.form,'soap_gallons')
            day=valid_date(request.form.get('date') or today.isoformat())
            conn.execute('BEGIN IMMEDIATE')
            conn.execute("""INSERT INTO storage_transactions
                (date,transaction_type,gallons,fresh_gallons,soap_gallons,reason,notes)
                VALUES (?,'Assessment',0,?,?,?,?)""",(day,fresh,soap,'Full oil-quality stock assessment',request.form.get('notes','')))
            validate_stock(conn)
            conn.commit()
        except ValueError as exc:
            conn.rollback();flash(str(exc),'error')
            return redirect(request.url)
        except Exception:
            conn.rollback();raise
        finally:conn.close()
        flash('Quality split updated. Total stock is unchanged.', 'success')
        return redirect(url_for('storage.index'))
    return render_template('storage/log_quality.html', today=today.isoformat(), total_stock=total_stock)


@storage_bp.route('/revalue', methods=['GET', 'POST'])
def revalue():
    today = business_today()
    total_stock = _current_stock()
    last_row    = query("SELECT price_per_gallon FROM storage_transactions WHERE transaction_type='Revaluation' ORDER BY date DESC LIMIT 1", one=True)
    current_price = float(last_row['price_per_gallon']) if last_row else 0.0

    if request.method == 'POST':
        new_price = float(request.form.get('new_price') or 0)
        execute("""
            INSERT INTO storage_transactions
                (date, transaction_type, gallons, price_per_gallon, reason, notes)
            VALUES (?, 'Revaluation', 0, ?, ?, ?)
        """, (request.form.get('date') or today.isoformat(), new_price,
              f'Price update: GHS {current_price:.2f} → GHS {new_price:.2f}/gal',
              request.form.get('notes', '')))
        flash(f'Price updated to GHS {new_price:.2f}/gal.', 'success')
        return redirect(url_for('storage.index'))

    return render_template('storage/revalue.html',
        today=today.isoformat(), current_gallons=total_stock,
        current_price=current_price, current_value=total_stock * current_price)


@storage_bp.route('/delete/<int:tx_id>', methods=['POST'])
def delete_transaction(tx_id):
    conn=get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('DELETE FROM storage_transactions WHERE id=?', (tx_id,))
        validate_stock(conn);conn.commit()
    except ValueError as exc:
        conn.rollback();flash(str(exc), 'error')
        return redirect(url_for('storage.index'))
    finally:conn.close()
    flash('Transaction deleted.', 'success')
    return redirect(url_for('storage.index'))
