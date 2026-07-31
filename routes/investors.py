"""Investors — track farm investors, contributions, equity, and returns."""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from database.db import query, execute
from datetime import date

investors_bp = Blueprint('investors', __name__)

INVESTMENT_TYPES = ['Cash', 'Equipment', 'Land', 'Labour', 'Other']
STATUSES = ['Active', 'Settled', 'Pending', 'Withdrawn']


def _s(sql, params=()):
    row = query(sql, params, one=True)
    return float(list(row)[0]) if row else 0.0


# ── Investors list ────────────────────────────────────────────────────────────
@investors_bp.route('/')
def index():
    investors = query("""
        SELECT i.*,
               COUNT(DISTINCT inv.id)            AS num_investments,
               COALESCE(SUM(inv.amount), 0)       AS total_invested,
               COALESCE(SUM(ir.amount), 0)        AS total_returned
        FROM investors i
        LEFT JOIN investments inv ON inv.investor_id = i.id
        LEFT JOIN investor_returns ir ON ir.investor_id = i.id
        GROUP BY i.id
        ORDER BY total_invested DESC
    """)

    total_invested  = _s("SELECT COALESCE(SUM(amount),0) FROM investments")
    total_returned  = _s("SELECT COALESCE(SUM(amount),0) FROM investor_returns")
    active_count    = query("SELECT COUNT(*) AS c FROM investors", one=True)['c']
    active_inv      = query("SELECT COUNT(*) AS c FROM investments WHERE status='Active'", one=True)['c']

    return render_template('investors/index.html',
        investors=investors,
        total_invested=total_invested,
        total_returned=total_returned,
        active_count=active_count,
        active_inv=active_inv,
        today=date.today(),
    )


# ── Add investor ──────────────────────────────────────────────────────────────
@investors_bp.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        execute("""
            INSERT INTO investors (name, phone, email, location, notes, date_joined)
            VALUES (?,?,?,?,?,?)
        """, (
            request.form['name'],
            request.form.get('phone',''),
            request.form.get('email',''),
            request.form.get('location',''),
            request.form.get('notes',''),
            request.form.get('date_joined') or date.today().isoformat(),
        ))
        flash(f"Investor {request.form['name']} added.", 'success')
        return redirect(url_for('investors.index'))
    return render_template('investors/add.html', today=date.today().isoformat())


# ── Investor detail ───────────────────────────────────────────────────────────
@investors_bp.route('/<int:investor_id>')
def detail(investor_id):
    investor = query("SELECT * FROM investors WHERE id=?", (investor_id,), one=True)
    if not investor:
        flash('Investor not found.', 'error')
        return redirect(url_for('investors.index'))

    investments = query("""
        SELECT inv.*, f.name AS farm_name
        FROM investments inv
        LEFT JOIN farms f ON f.id = inv.farm_id
        WHERE inv.investor_id = ?
        ORDER BY inv.date DESC
    """, (investor_id,))

    returns = query("""
        SELECT ir.*, inv.farm_id,
               f.name AS farm_name,
               inv.amount AS investment_amount
        FROM investor_returns ir
        LEFT JOIN investments inv ON inv.id = ir.investment_id
        LEFT JOIN farms f ON f.id = inv.farm_id
        WHERE ir.investor_id = ?
        ORDER BY ir.date DESC
    """, (investor_id,))

    total_invested = _s("SELECT COALESCE(SUM(amount),0) FROM investments WHERE investor_id=?", (investor_id,))
    total_returned = _s("SELECT COALESCE(SUM(amount),0) FROM investor_returns WHERE investor_id=?", (investor_id,))
    outstanding    = total_invested - total_returned
    roi            = round((total_returned / total_invested * 100) - 100, 1) if total_invested > 0 else 0

    farms = query("SELECT * FROM farms ORDER BY name")

    return render_template('investors/detail.html',
        investor=investor,
        investments=investments,
        returns=returns,
        total_invested=total_invested,
        total_returned=total_returned,
        outstanding=outstanding,
        roi=roi,
        farms=farms,
        investment_types=INVESTMENT_TYPES,
        statuses=STATUSES,
        today=date.today().isoformat(),
    )


# ── Edit investor ─────────────────────────────────────────────────────────────
@investors_bp.route('/<int:investor_id>/edit', methods=['GET', 'POST'])
def edit(investor_id):
    investor = query("SELECT * FROM investors WHERE id=?", (investor_id,), one=True)
    if not investor:
        flash('Investor not found.', 'error')
        return redirect(url_for('investors.index'))
    if request.method == 'POST':
        execute("""
            UPDATE investors SET name=?, phone=?, email=?, location=?, notes=?, date_joined=?
            WHERE id=?
        """, (
            request.form['name'], request.form.get('phone',''),
            request.form.get('email',''), request.form.get('location',''),
            request.form.get('notes',''), request.form.get('date_joined',''),
            investor_id,
        ))
        flash('Investor updated.', 'success')
        return redirect(url_for('investors.detail', investor_id=investor_id))
    return render_template('investors/edit.html', investor=investor)


# ── Delete investor ───────────────────────────────────────────────────────────
@investors_bp.route('/<int:investor_id>/delete', methods=['POST'])
def delete(investor_id):
    execute("DELETE FROM investors WHERE id=?", (investor_id,))
    flash('Investor removed.', 'success')
    return redirect(url_for('investors.index'))


# ── Add investment ────────────────────────────────────────────────────────────
@investors_bp.route('/<int:investor_id>/invest', methods=['POST'])
def add_investment(investor_id):
    execute("""
        INSERT INTO investments
            (investor_id, farm_id, date, amount, investment_type,
             equity_pct, expected_return, return_date, status, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (
        investor_id,
        request.form.get('farm_id') or None,
        request.form['date'],
        float(request.form.get('amount') or 0),
        request.form.get('investment_type','Cash'),
        float(request.form.get('equity_pct') or 0),
        float(request.form.get('expected_return') or 0),
        request.form.get('return_date') or None,
        request.form.get('status','Active'),
        request.form.get('notes',''),
    ))
    flash('Investment recorded.', 'success')
    return redirect(url_for('investors.detail', investor_id=investor_id))


# ── Edit investment ───────────────────────────────────────────────────────────
@investors_bp.route('/investment/<int:inv_id>/edit', methods=['GET', 'POST'])
def edit_investment(inv_id):
    inv = query("""
        SELECT inv.*, i.name AS investor_name
        FROM investments inv JOIN investors i ON i.id=inv.investor_id
        WHERE inv.id=?
    """, (inv_id,), one=True)
    if not inv:
        flash('Investment not found.', 'error')
        return redirect(url_for('investors.index'))
    farms = query("SELECT * FROM farms ORDER BY name")
    if request.method == 'POST':
        execute("""
            UPDATE investments SET
                farm_id=?, date=?, amount=?, investment_type=?,
                equity_pct=?, expected_return=?, return_date=?, status=?, notes=?
            WHERE id=?
        """, (
            request.form.get('farm_id') or None,
            request.form['date'],
            float(request.form.get('amount') or 0),
            request.form.get('investment_type','Cash'),
            float(request.form.get('equity_pct') or 0),
            float(request.form.get('expected_return') or 0),
            request.form.get('return_date') or None,
            request.form.get('status','Active'),
            request.form.get('notes',''),
            inv_id,
        ))
        flash('Investment updated.', 'success')
        return redirect(url_for('investors.detail', investor_id=inv['investor_id']))
    return render_template('investors/edit_investment.html',
        inv=inv, farms=farms,
        investment_types=INVESTMENT_TYPES, statuses=STATUSES)


# ── Delete investment ─────────────────────────────────────────────────────────
@investors_bp.route('/investment/<int:inv_id>/delete', methods=['POST'])
def delete_investment(inv_id):
    inv = query("SELECT investor_id FROM investments WHERE id=?", (inv_id,), one=True)
    execute("DELETE FROM investments WHERE id=?", (inv_id,))
    flash('Investment deleted.', 'success')
    if inv:
        return redirect(url_for('investors.detail', investor_id=inv['investor_id']))
    return redirect(url_for('investors.index'))


# ── Record return payment ─────────────────────────────────────────────────────
@investors_bp.route('/<int:investor_id>/return', methods=['POST'])
def add_return(investor_id):
    execute("""
        INSERT INTO investor_returns (investor_id, investment_id, date, amount, notes)
        VALUES (?,?,?,?,?)
    """, (
        investor_id,
        request.form.get('investment_id') or None,
        request.form['date'],
        float(request.form.get('amount') or 0),
        request.form.get('notes',''),
    ))
    flash('Return payment recorded.', 'success')
    return redirect(url_for('investors.detail', investor_id=investor_id))


# ── Delete return ─────────────────────────────────────────────────────────────
@investors_bp.route('/return/<int:ret_id>/delete', methods=['POST'])
def delete_return(ret_id):
    ret = query("SELECT investor_id FROM investor_returns WHERE id=?", (ret_id,), one=True)
    execute("DELETE FROM investor_returns WHERE id=?", (ret_id,))
    flash('Return deleted.', 'success')
    if ret:
        return redirect(url_for('investors.detail', investor_id=ret['investor_id']))
    return redirect(url_for('investors.index'))
