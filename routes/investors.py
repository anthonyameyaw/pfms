from database.periods import business_today
"""Investors — tracking investments, expected returns, and outstanding amounts."""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from database.db import query, execute, get_connection
from datetime import date

investors_bp = Blueprint('investors', __name__)


from decimal import Decimal
from database.validation import money

def _calc_expected(amount, return_pct):
    """expected_return = amount * (1 + return_pct/100)"""
    return money(Decimal(str(amount or 0)) * (1 + Decimal(str(return_pct or 0)) / 100))


def _balance_status(expected, paid, requested='Active'):
    if Decimal(str(paid)) >= Decimal(str(expected)):
        return 'Completed'
    return 'Defaulted' if requested == 'Defaulted' else 'Active'


def _sync_status(conn, investment_id, requested=None):
    inv=conn.execute('SELECT * FROM investments WHERE id=?',(investment_id,)).fetchone()
    pct=inv['return_pct'] if inv['return_pct'] is not None else inv['equity_pct'] or 0
    expected=_calc_expected(inv['amount'],pct)
    paid=conn.execute('SELECT COALESCE(SUM(amount),0) FROM investor_returns WHERE investment_id=?',(investment_id,)).fetchone()[0]
    status=_balance_status(expected, money(paid), requested if requested is not None else inv['status'])
    conn.execute('UPDATE investments SET status=?, expected_return=? WHERE id=?',(status,expected,investment_id))


def _get_investments(investor_id=None):
    where = "WHERE inv.investor_id=?" if investor_id else "WHERE 1=1"
    params = (investor_id,) if investor_id else ()
    today = business_today().isoformat()

    rows = query(f"""
        SELECT inv.*, i.name AS investor_name,
               COALESCE(f.name,'—') AS farm_name,
               COALESCE((SELECT SUM(r.amount) FROM investor_returns r
                         WHERE r.investment_id=inv.id), 0) AS paid_back
        FROM investments inv
        JOIN investors i ON i.id=inv.investor_id
        LEFT JOIN farms f ON f.id=inv.farm_id
        {where}
        ORDER BY inv.return_date ASC
    """, params)

    result = []
    for r in rows:
        pct          = float(r['return_pct'] if r['return_pct'] is not None else r['equity_pct'] or 0)
        amount       = float(r['amount'] or 0)
        expected     = _calc_expected(amount, pct)
        paid         = float(r['paid_back'] or 0)
        outstanding  = max(0, round(expected - paid, 2))
        is_due       = r['return_date'] and r['return_date'] <= today
        is_overdue   = is_due and outstanding > 0

        result.append({
            'id':            r['id'],
            'investor_id':   r['investor_id'],
            'investor_name': r['investor_name'],
            'farm_name':     r['farm_name'],
            'farm_id':       r['farm_id'],
            'amount':        amount,
            'return_pct':    pct,
            'expected':      expected,
            'interest':      money(Decimal(str(expected))-Decimal(str(amount))),
            'paid':          round(paid, 2),
            'outstanding':   outstanding,
            'return_date':   r['return_date'],
            'date':          r['date'],
            'investment_type': r['investment_type'],
            'status':        _balance_status(expected, round(paid, 2), r['status']),
            'notes':         r['notes'],
            'is_due':        is_due,
            'is_overdue':    is_overdue,
        })
    return result


def _investor_summaries(investors, investments):
    rows=[]
    for investor in investors:
        entries=[i for i in investments if i['investor_id']==investor['id']]
        principal=money(sum(Decimal(str(i['amount'])) for i in entries))
        expected=money(sum(Decimal(str(i['expected'])) for i in entries))
        rates=sorted(set(i['return_pct'] for i in entries))
        due=sorted(i['return_date'] for i in entries if i['outstanding']>0 and i['return_date'])
        rows.append(dict(investor,principal=principal,interest=money(Decimal(str(expected))-Decimal(str(principal))),
            expected=expected,paid=money(sum(Decimal(str(i['paid'])) for i in entries)),
            outstanding=money(sum(Decimal(str(i['outstanding'])) for i in entries)),
            rates=rates,next_due=due[0] if due else None,count=len(entries),
            missing_dates=sum(1 for i in entries if i['outstanding']>0 and not i['return_date']),
            overdue=sum(1 for i in entries if i['is_overdue'])))
    return rows


@investors_bp.route('/')
def index():
    today = business_today()
    investors = query("SELECT * FROM investors ORDER BY name")
    investments = _get_investments()

    total_invested  = sum(i['amount']      for i in investments)
    total_expected  = sum(i['expected']    for i in investments)
    total_paid      = sum(i['paid']        for i in investments)
    total_outstanding = sum(i['outstanding'] for i in investments)
    overdue_count   = sum(1 for i in investments if i['is_overdue'])

    # Returns log
    returns = query("""
        SELECT r.*, i.name AS investor_name, inv.amount AS inv_amount
        FROM investor_returns r
        JOIN investors i ON i.id=r.investor_id
        LEFT JOIN investments inv ON inv.id=r.investment_id
        ORDER BY r.date DESC
    """)

    return render_template('investors/index.html',
        investor_rows=_investor_summaries(investors,investments),
        today=today,
        investors=investors,
        investments=investments,
        returns=returns,
        total_invested=total_invested,
        total_expected=total_expected,
        total_paid=total_paid,
        total_outstanding=total_outstanding,
        overdue_count=overdue_count,
    )


@investors_bp.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        name  = request.form.get('name','').strip()
        phone = request.form.get('phone','').strip()
        email = request.form.get('email','').strip()
        loc   = request.form.get('location','').strip()
        notes = request.form.get('notes','').strip()
        if not name:
            flash('Name is required.', 'error')
            return redirect(url_for('investors.add'))
        execute("INSERT INTO investors (name,phone,email,location,notes,date_joined) VALUES (?,?,?,?,?,?)",
                (name, phone, email, loc, notes, business_today().isoformat()))
        flash(f'{name} added as investor.', 'success')
        return redirect(url_for('investors.index'))
    return render_template('investors/add.html', today=business_today().isoformat())


@investors_bp.route('/<int:investor_id>')
def detail(investor_id):
    investor    = query("SELECT * FROM investors WHERE id=?", (investor_id,), one=True)
    if not investor:
        flash('Investor not found.', 'error')
        return redirect(url_for('investors.index'))
    investments = _get_investments(investor_id)
    returns     = query("""
        SELECT r.*, inv.amount AS inv_amount
        FROM investor_returns r
        LEFT JOIN investments inv ON inv.id=r.investment_id
        WHERE r.investor_id=? ORDER BY r.date DESC
    """, (investor_id,))

    total_invested   = sum(i['amount']      for i in investments)
    total_expected   = sum(i['expected']    for i in investments)
    total_paid       = sum(i['paid']        for i in investments)
    total_outstanding= sum(i['outstanding'] for i in investments)

    investments.sort(key=lambda i:(i['date'],i['id']),reverse=True)
    return render_template('investors/detail.html',
        investor=investor, investments=investments, returns=returns,
        total_invested=total_invested, total_expected=total_expected,
        total_paid=total_paid, total_outstanding=total_outstanding,
        today=business_today(),
    )


@investors_bp.route('/<int:investor_id>/add-investment', methods=['GET','POST'])
def add_investment(investor_id):
    investor = query("SELECT * FROM investors WHERE id=?", (investor_id,), one=True)
    farms    = query("SELECT id,name FROM farms ORDER BY name")
    if request.method == 'POST':
        amount     = float(request.form.get('amount') or 0)
        return_pct = float(request.form.get('return_pct') or 0)
        expected   = _calc_expected(amount, return_pct)
        execute("""
            INSERT INTO investments
                (investor_id, farm_id, date, amount, investment_type,
                 equity_pct, return_pct, expected_return, return_date, status, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            investor_id,
            request.form.get('farm_id') or None,
            request.form.get('date') or business_today().isoformat(),
            amount,
            request.form.get('investment_type','Cash'),
            return_pct, return_pct, expected,
            request.form.get('return_date',''),
            'Active',
            request.form.get('notes',''),
        ))
        flash(f'Investment of GHS {amount:,.2f} recorded. Expected return: GHS {expected:,.2f}.', 'success')
        return redirect(url_for('investors.detail', investor_id=investor_id))
    return render_template('investors/add_investment.html',
        investor=investor, farms=farms, today=business_today().isoformat())


@investors_bp.route('/<int:investor_id>/log-return', methods=['GET','POST'])
def log_return(investor_id):
    investor    = query("SELECT * FROM investors WHERE id=?", (investor_id,), one=True)
    investments = _get_investments(investor_id)
    if request.method == 'POST':
        amount        = float(request.form.get('amount') or 0)
        investment_id = request.form.get('investment_id') or None
        notes         = request.form.get('notes','')
        conn=get_connection()
        try:
            with conn:
                conn.execute('BEGIN IMMEDIATE')
                conn.execute("""
                    INSERT INTO investor_returns (investor_id, investment_id, date, amount, notes)
                    VALUES (?,?,?,?,?)
                """, (investor_id, investment_id,
                      request.form.get('date') or business_today().isoformat(), amount, notes))
                _sync_status(conn, investment_id)
        finally:
            conn.close()
        flash(f'Return of GHS {amount:,.2f} logged.', 'success')
        return redirect(url_for('investors.detail', investor_id=investor_id))
    return render_template('investors/log_return.html',
        investor=investor, investments=investments, today=business_today().isoformat())


@investors_bp.route('/investment/<int:inv_id>/delete', methods=['POST'])
def delete_investment(inv_id):
    conn=get_connection()
    try:
        with conn:
            conn.execute('BEGIN IMMEDIATE')
            inv=conn.execute('SELECT investor_id FROM investments WHERE id=?',(inv_id,)).fetchone()
            if not inv:
                flash('Investment not found.', 'error')
                return redirect(url_for('investors.index'))
            has_payments=conn.execute('SELECT 1 FROM investor_returns WHERE investment_id=? LIMIT 1',(inv_id,)).fetchone()
            if has_payments:
                flash('This investment cannot be deleted because it has repayment history.', 'error')
            else:
                conn.execute('DELETE FROM investments WHERE id=?',(inv_id,))
                flash('Investment deleted.', 'success')
    finally:
        conn.close()
    return redirect(url_for('investors.detail', investor_id=inv['investor_id']))


@investors_bp.route('/investment/<int:inv_id>/edit', methods=['GET', 'POST'])
def edit_investment(inv_id):
    investments = _get_investments()
    inv = next((i for i in investments if i['id'] == inv_id), None)
    if not inv:
        flash('Investment not found.', 'error')
        return redirect(url_for('investors.index'))
    farms = query("SELECT id, name FROM farms ORDER BY name")

    if request.method == 'POST':
        amount     = float(request.form.get('amount') or 0)
        return_pct = float(request.form.get('return_pct') or 0)
        expected   = _calc_expected(amount, return_pct)
        conn=get_connection()
        try:
            with conn:
                conn.execute('BEGIN IMMEDIATE')
                conn.execute("""
                    UPDATE investments SET
                        date=?, farm_id=?, investment_type=?, amount=?,
                        equity_pct=?, return_pct=?, expected_return=?,
                        return_date=?, status=?, notes=?
                    WHERE id=?
                """, (
                    request.form.get('date') or business_today().isoformat(),
                    request.form.get('farm_id') or None,
                    request.form.get('investment_type', 'Cash'),
                    amount, return_pct, return_pct, expected,
                    request.form.get('return_date') or None,
                    request.form.get('status', 'Active'),
                    request.form.get('notes', ''),
                    inv_id,
                ))
                _sync_status(conn, inv_id, request.form.get('status', 'Active'))
        finally:
            conn.close()
        flash('Investment updated.', 'success')
        return redirect(url_for('investors.detail', investor_id=inv['investor_id']))

    return render_template('investors/edit_investment.html', inv=inv, farms=farms)
