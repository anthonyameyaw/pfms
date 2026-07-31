"""Reports & Export — CSV and PDF with date range and correct net profit."""

import csv, io
from datetime import date
from flask import Blueprint, render_template, request, Response, flash, redirect, url_for
from database.db import query

reports_bp = Blueprint('reports', __name__)


def _s(sql, params=()):
    row = query(sql, params, one=True)
    return float(list(row)[0]) if row else 0.0


def _df(date_from, date_to):
    """Return (clause_string, params_list) for date filtering."""
    clauses, params = [], []
    if date_from: clauses.append('date>=?'); params.append(date_from)
    if date_to:   clauses.append('date<=?'); params.append(date_to)
    return (' AND ' + ' AND '.join(clauses) if clauses else ''), params


def _get_summary(date_from='', date_to=''):
    """Correct consolidated financials for given period."""
    dc, dp = _df(date_from, date_to)

    farm_income  = _s(f"SELECT COALESCE(SUM(gallons_sold_income),0) FROM harvests WHERE gallons_sold_income>0{dc}", dp)
    plant_income = _s(f"SELECT COALESCE(SUM(gross_revenue),0) FROM processing_runs WHERE 1=1{dc}", dp)
    total_income = farm_income + plant_income

    harv_exp  = _s(f"SELECT COALESCE(SUM(harvesting_cost),0) FROM harvests WHERE 1=1{dc}", dp)
    trans_exp = _s(f"SELECT COALESCE(SUM(total_cost),0) FROM transport_logs WHERE 1=1{dc}", dp)
    act_exp   = _s(f"SELECT COALESCE(SUM(labour_cost+materials_cost),0) FROM activities WHERE activity_type!='Harvesting'{dc}", dp)
    elec_exp  = _s(f"SELECT COALESCE(SUM(electricity_cost),0) FROM processing_runs WHERE 1=1{dc}", dp)
    op_exp    = _s(f"SELECT COALESCE(SUM(operator_pay),0) FROM processing_runs WHERE 1=1{dc}", dp)
    plant_other = _s(f"SELECT COALESCE(SUM(amount),0) FROM plant_expenses WHERE 1=1{dc}", dp)
    total_exp = harv_exp + trans_exp + act_exp + elec_exp + op_exp + plant_other

    return dict(
        farm_income=farm_income, plant_income=plant_income,
        total_income=total_income,
        harv_exp=harv_exp, trans_exp=trans_exp, act_exp=act_exp,
        elec_exp=elec_exp, op_exp=op_exp, plant_other=plant_other,
        total_exp=total_exp,
        net=total_income - total_exp,
    )


def _get_farm_pl(date_from='', date_to=''):
    dc, dp = _df(date_from, date_to)
    farms = query(f"""
        SELECT f.id, f.name, f.status, f.crop_type, f.size_acres, f.location,
               COALESCE((SELECT SUM(h.gallons_sold_income) FROM harvests h
                          WHERE h.farm_id=f.id AND h.gallons_sold_income>0{dc}),0) AS income,
               COALESCE((SELECT SUM(h.harvesting_cost) FROM harvests h WHERE h.farm_id=f.id{dc}),0) AS harv_cost,
               COALESCE((SELECT SUM(t.total_cost) FROM transport_logs t WHERE t.farm_id=f.id{dc}),0) AS trans_cost,
               COALESCE((SELECT SUM(a.labour_cost+a.materials_cost) FROM activities a
                          WHERE a.farm_id=f.id AND a.activity_type!='Harvesting'{dc}),0) AS act_cost,
               COALESCE((SELECT SUM(h.bunches_harvested) FROM harvests h WHERE h.farm_id=f.id{dc}),0) AS bunches,
               COALESCE((SELECT SUM(h.gallons_produced) FROM harvests h
                          WHERE h.farm_id=f.id AND h.gallons_produced>0{dc}),0) AS gallons
        FROM farms f ORDER BY f.name
    """, dp * 6)
    result = []
    for f in farms:
        exp = f['harv_cost'] + f['trans_cost'] + f['act_cost']
        result.append(dict(f, expenses=exp, net=f['income'] - exp))
    return result


@reports_bp.route('/')
def index():
    date_from = request.args.get('date_from', '')
    date_to   = request.args.get('date_to', '')
    summary   = _get_summary(date_from, date_to)
    farms     = _get_farm_pl(date_from, date_to)
    return render_template('reports/index.html',
        today=date.today(), summary=summary, farms=farms,
        date_from=date_from, date_to=date_to,
    )


# ── CSV exports ───────────────────────────────────────────────────────────────

@reports_bp.route('/export/harvests.csv')
def export_harvests():
    rows = query("""
        SELECT f.name AS farm, h.date, h.bunches_harvested,
               h.gallons_produced, h.gallons_sold, h.gallons_sold_income,
               h.harvester_pay, h.collector_pay, h.harvesting_cost, h.notes
        FROM harvests h JOIN farms f ON f.id=h.farm_id ORDER BY h.date DESC
    """)
    return _csv('harvests.csv',
        ['Farm','Date','Bunches','Gallons Produced','Gallons Sold','Sale Income (GHS)',
         'Harvester Pay','Collector Pay','Total Labour Cost','Notes'],
        [[r['farm'],r['date'],r['bunches_harvested'],r['gallons_produced'],
          r['gallons_sold'],r['gallons_sold_income'],
          r['harvester_pay'],r['collector_pay'],r['harvesting_cost'],r['notes']] for r in rows])


@reports_bp.route('/export/activities.csv')
def export_activities():
    rows = query("""
        SELECT f.name AS farm, a.date, a.activity_type, a.description,
               a.num_labourers, a.labour_cost, a.materials_used, a.materials_cost, a.notes
        FROM activities a JOIN farms f ON f.id=a.farm_id ORDER BY a.date DESC
    """)
    return _csv('activities.csv',
        ['Farm','Date','Type','Description','Labourers','Labour Cost','Materials','Mat. Cost','Notes'],
        [[r['farm'],r['date'],r['activity_type'],r['description'],
          r['num_labourers'],r['labour_cost'],r['materials_used'],r['materials_cost'],r['notes']] for r in rows])


@reports_bp.route('/export/transport.csv')
def export_transport():
    rows = query("""
        SELECT f.name AS farm, t.date, t.transport_type,
               t.driver_pay, t.fuel_cost, t.rental_cost, t.total_cost, t.notes
        FROM transport_logs t LEFT JOIN farms f ON f.id=t.farm_id ORDER BY t.date DESC
    """)
    return _csv('transport.csv',
        ['Farm','Date','Type','Driver Pay','Fuel Cost','Rental Cost','Total Cost','Notes'],
        [[r['farm'],r['date'],r['transport_type'],r['driver_pay'],
          r['fuel_cost'],r['rental_cost'],r['total_cost'],r['notes']] for r in rows])


@reports_bp.route('/export/plant.csv')
def export_plant():
    rows = query("SELECT * FROM processing_runs ORDER BY date DESC")
    return _csv('processing_plant.csv',
        ['Date','Own Gallons','Outside Gallons','Total Gallons','Gross Revenue',
         'Electricity','Net Revenue','Operator Pay','Company Revenue',
         'Outside Fees','Cash Collected','Cash Outstanding'],
        [[r['date'],r['own_farms_gallons'],r['outside_farmers_gallons'],
          r['total_output_gallons'],r['gross_revenue'],r['electricity_cost'],
          r['net_revenue'],r['operator_pay'],r['company_revenue'],
          r['outside_farmer_fees'],r['cash_collected'],r['cash_outstanding']] for r in rows])


def _csv(filename, headers, rows):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(headers)
    w.writerows(rows)
    return Response(out.getvalue(), mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'})


# ── PDF helpers ───────────────────────────────────────────────────────────────

def _pdf_styles():
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    GREEN  = colors.HexColor('#1a3c2e')
    GOLD   = colors.HexColor('#c8922a')
    LGREY  = colors.HexColor('#f2f7f4')
    HLROW  = colors.HexColor('#e8f4ec')
    DKGREY = colors.HexColor('#5a7566')
    RED    = colors.HexColor('#c0392b')
    return dict(
        GREEN=GREEN, GOLD=GOLD, LGREY=LGREY, HLROW=HLROW, DKGREY=DKGREY, RED=RED,
        s_title  = ParagraphStyle('T',  fontName='Helvetica-Bold', fontSize=20, textColor=GREEN, spaceAfter=4),
        s_sub    = ParagraphStyle('S',  fontName='Helvetica',      fontSize=9,  textColor=DKGREY, spaceAfter=14),
        s_h2     = ParagraphStyle('H2', fontName='Helvetica-Bold', fontSize=12, textColor=GREEN, spaceBefore=16, spaceAfter=6),
        s_small  = ParagraphStyle('Sm', fontName='Helvetica',      fontSize=8,  textColor=DKGREY),
        s_footer = ParagraphStyle('F',  fontName='Helvetica',      fontSize=8,  textColor=DKGREY, alignment=TA_CENTER),
    )


def _tbl_style(st, bold_rows=None, net_rows=None, net_positive=True):
    """Standard table style. bold_rows = list of row indices. net_rows = list of net profit rows."""
    from reportlab.lib import colors
    from reportlab.platypus import TableStyle
    GREEN = colors.HexColor('#1a3c2e')
    LGREY = colors.HexColor('#f2f7f4')
    HLROW = colors.HexColor('#e8f4ec')
    ts = TableStyle([
        ('BACKGROUND',    (0,0),(-1,0),  GREEN),
        ('TEXTCOLOR',     (0,0),(-1,0),  colors.white),
        ('FONTNAME',      (0,0),(-1,0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0,0),(-1,-1), 8),
        ('FONTNAME',      (0,1),(-1,-1), 'Helvetica'),
        ('ROWBACKGROUNDS',(0,1),(-1,-1), [colors.white, LGREY]),
        ('GRID',          (0,0),(-1,-1), 0.4, colors.HexColor('#ddeae1')),
        ('TOPPADDING',    (0,0),(-1,-1), 5),
        ('BOTTOMPADDING', (0,0),(-1,-1), 5),
        ('LEFTPADDING',   (0,0),(-1,-1), 7),
        ('ALIGN',         (1,0),(-1,-1), 'RIGHT'),
    ])
    for r in (bold_rows or []):
        ts.add('FONTNAME',     (0,r),(-1,r), 'Helvetica-Bold')
        ts.add('FONTSIZE',     (0,r),(-1,r), 9)
    for r in (net_rows or []):
        ts.add('BACKGROUND',   (0,r),(-1,r), HLROW)
        ts.add('FONTNAME',     (0,r),(-1,r), 'Helvetica-Bold')
        ts.add('FONTSIZE',     (0,r),(-1,r), 10)
        ts.add('TOPPADDING',   (0,r),(-1,r), 7)
        ts.add('BOTTOMPADDING',(0,r),(-1,r), 7)
        ts.add('TEXTCOLOR',    (1,r),(1,r),  colors.HexColor('#1a3c2e') if net_positive else colors.HexColor('#c0392b'))
    return ts


def _money(v):
    return f"GHS {float(v or 0):,.2f}"


def _period_label(date_from, date_to):
    if date_from and date_to: return f"{date_from} to {date_to}"
    if date_from: return f"From {date_from}"
    if date_to:   return f"Up to {date_to}"
    return "All Time"


# ── PDF: Single farm ──────────────────────────────────────────────────────────

@reports_bp.route('/pdf/farm/<int:farm_id>')
def pdf_farm(farm_id):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, HRFlowable

    date_from = request.args.get('date_from','')
    date_to   = request.args.get('date_to','')
    period    = _period_label(date_from, date_to)
    dc, dp    = _df(date_from, date_to)

    farm = query("SELECT * FROM farms WHERE id=?", (farm_id,), one=True)
    if not farm:
        flash('Farm not found.', 'error')
        return redirect(url_for('reports.index'))

    harvests   = query(f"SELECT date,bunches_harvested,gallons_produced,gallons_sold,gallons_sold_income,harvesting_cost FROM harvests WHERE farm_id=?{dc} ORDER BY date DESC", (farm_id,*dp))
    transport  = query(f"SELECT date,transport_type,driver_pay,fuel_cost,rental_cost,total_cost FROM transport_logs WHERE farm_id=?{dc} ORDER BY date DESC", (farm_id,*dp))
    activities = query(f"SELECT date,activity_type,description,num_labourers,labour_cost,materials_cost FROM activities WHERE farm_id=? AND activity_type!='Harvesting'{dc} ORDER BY date DESC", (farm_id,*dp))

    income     = _s(f"SELECT COALESCE(SUM(gallons_sold_income),0) FROM harvests WHERE farm_id=? AND gallons_sold_income>0{dc}", (farm_id,*dp))
    harv_cost  = _s(f"SELECT COALESCE(SUM(harvesting_cost),0) FROM harvests WHERE farm_id=?{dc}", (farm_id,*dp))
    trans_cost = _s(f"SELECT COALESCE(SUM(total_cost),0) FROM transport_logs WHERE farm_id=?{dc}", (farm_id,*dp))
    act_cost   = _s(f"SELECT COALESCE(SUM(labour_cost+materials_cost),0) FROM activities WHERE farm_id=? AND activity_type!='Harvesting'{dc}", (farm_id,*dp))
    total_exp  = harv_cost + trans_cost + act_cost
    net        = income - total_exp

    st   = _pdf_styles()
    buf  = io.BytesIO()
    doc  = SimpleDocTemplate(buf, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    story = []

    story.append(Paragraph(farm['name'], st['s_title']))
    story.append(Paragraph(f"{farm['location']} · {farm['size_acres']} acres · {farm['crop_type']} · {farm['status']}", st['s_sub']))
    story.append(HRFlowable(width='100%', thickness=2, color=st['GOLD'], spaceAfter=10))
    story.append(Paragraph(f"Period: {period} · Generated: {date.today().strftime('%d %B %Y')}", st['s_small']))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Financial Summary", st['s_h2']))
    summary_data = [
        ['Item', 'Amount'],
        ['Total Income (from sold gallons)', _money(income)],
        ['', ''],
        ['Harvesting Labour Cost', _money(harv_cost)],
        ['Transport Cost',         _money(trans_cost)],
        ['Activity Labour & Materials', _money(act_cost)],
        ['Total Expenses',         _money(total_exp)],
        ['NET PROFIT / LOSS',      _money(net)],
    ]
    t = Table(summary_data, colWidths=[11*cm, 5*cm])
    t.setStyle(_tbl_style(st, bold_rows=[6], net_rows=[7], net_positive=net>=0))
    story.append(t)
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"Net Profit = Total Income ({_money(income)}) − Total Expenses ({_money(total_exp)}) = {_money(net)}", st['s_small']))

    if harvests:
        story.append(Paragraph("Harvest Records", st['s_h2']))
        data = [['Date','Bunches','Gal. Produced','Gal. Sold','Sale Income','Labour Cost']]
        for r in harvests:
            data.append([r['date'], r['bunches_harvested'] or 0,
                         r['gallons_produced'] or 0, r['gallons_sold'] or 0,
                         _money(r['gallons_sold_income']), _money(r['harvesting_cost'])])
        t = Table(data, colWidths=[2.5*cm,2*cm,2.5*cm,2.5*cm,3*cm,3*cm])
        t.setStyle(_tbl_style(st))
        story.append(t)

    if transport:
        story.append(Paragraph("Transport Logs", st['s_h2']))
        data = [['Date','Type','Driver Pay','Fuel','Rental','Total']]
        for r in transport:
            data.append([r['date'],r['transport_type'],
                         _money(r['driver_pay']),_money(r['fuel_cost']),
                         _money(r['rental_cost']),_money(r['total_cost'])])
        t = Table(data, colWidths=[2.5*cm,2.5*cm,2.5*cm,2.5*cm,2.5*cm,3*cm])
        t.setStyle(_tbl_style(st))
        story.append(t)

    if activities:
        story.append(Paragraph("Farm Activities", st['s_h2']))
        data = [['Date','Type','Description','Workers','Labour','Materials']]
        for r in activities:
            data.append([r['date'],r['activity_type'],(r['description'] or '')[:35],
                         r['num_labourers'] or 0,_money(r['labour_cost']),_money(r['materials_cost'])])
        t = Table(data, colWidths=[2.2*cm,2.5*cm,4.3*cm,1.8*cm,2.5*cm,2.7*cm])
        t.setStyle(_tbl_style(st))
        story.append(t)

    story.append(Spacer(1, 24))
    story.append(HRFlowable(width='100%', thickness=0.5, color=st['DKGREY']))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Palm Farm Management System · Nkrankwanta, Dormaa West, Ghana", st['s_footer']))

    doc.build(story)
    buf.seek(0)
    fname = farm['name'].replace(' ','_')
    return Response(buf.read(), mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{fname}_Report_{date.today()}.pdf"'})


# ── PDF: All farms consolidated ───────────────────────────────────────────────

@reports_bp.route('/pdf/all-farms')
def pdf_all_farms():
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, HRFlowable

    date_from = request.args.get('date_from','')
    date_to   = request.args.get('date_to','')
    period    = _period_label(date_from, date_to)

    farms   = _get_farm_pl(date_from, date_to)
    summary = _get_summary(date_from, date_to)
    dc, dp  = _df(date_from, date_to)

    st   = _pdf_styles()
    buf  = io.BytesIO()
    doc  = SimpleDocTemplate(buf, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    story = []

    story.append(Paragraph("All Farms — Financial Report", st['s_title']))
    story.append(Paragraph(f"Nkrankwanta, Dormaa West, Ghana · Period: {period} · Generated: {date.today().strftime('%d %B %Y')}", st['s_sub']))
    story.append(HRFlowable(width='100%', thickness=2, color=st['GOLD'], spaceAfter=12))

    # Consolidated summary
    story.append(Paragraph("Consolidated Financial Summary", st['s_h2']))
    sd = [
        ['Category', 'Amount'],
        ['Farm Oil Sales Income',           _money(summary['farm_income'])],
        ['Plant Processing Income',         _money(summary['plant_income'])],
        ['TOTAL INCOME',                    _money(summary['total_income'])],
        ['', ''],
        ['Harvesting Labour',               _money(summary['harv_exp'])],
        ['Transport Costs',                 _money(summary['trans_exp'])],
        ['Activity Labour & Materials',     _money(summary['act_exp'])],
        ['Plant Electricity',               _money(summary['elec_exp'])],
        ['Plant Operator Pay (30%)',        _money(summary['op_exp'])],
        ['Other Plant Expenses',            _money(summary['plant_other'])],
        ['TOTAL EXPENSES',                  _money(summary['total_exp'])],
        ['NET PROFIT / LOSS',               _money(summary['net'])],
    ]
    t = Table(sd, colWidths=[12*cm, 4*cm])
    t.setStyle(_tbl_style(st, bold_rows=[3,11], net_rows=[12], net_positive=summary['net']>=0))
    story.append(t)
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"Net Profit = Total Income ({_money(summary['total_income'])}) − Total Expenses ({_money(summary['total_exp'])}) = {_money(summary['net'])}",
        st['s_small']))

    # Other plant expenses breakdown
    plant_exp_rows = query(f"SELECT date, category, description, amount FROM plant_expenses WHERE 1=1{dc} ORDER BY date DESC", dp)
    if plant_exp_rows:
        story.append(Paragraph("Other Plant Expenses Breakdown", st['s_h2']))
        data = [['Date', 'Category', 'Description', 'Amount']]
        for r in plant_exp_rows:
            data.append([r['date'], r['category'] or '—', (r['description'] or '—')[:45], _money(r['amount'])])
        data.append(['', '', 'TOTAL', _money(summary['plant_other'])])
        t = Table(data, colWidths=[2.5*cm, 3*cm, 8*cm, 2.5*cm])
        t.setStyle(_tbl_style(st, net_rows=[len(data)-1], net_positive=True))
        story.append(t)
        story.append(Spacer(1, 8))

    # Per-farm table
    story.append(Paragraph("Per-Farm Performance", st['s_h2']))
    data = [['Farm','Status','Income','Harv.Cost','Transport','Activity','Total Exp','NET']]
    for f in farms:
        data.append([
            f['name'].replace('Palm Farm ','').replace('Whitehouse','WH'),
            f['status'],
            _money(f['income']), _money(f['harv_cost']),
            _money(f['trans_cost']), _money(f['act_cost']),
            _money(f['expenses']), _money(f['net'])
        ])
    t = Table(data, colWidths=[3.2*cm,1.8*cm,2.5*cm,2*cm,1.8*cm,1.8*cm,2*cm,2.4*cm])
    t.setStyle(_tbl_style(st))
    story.append(t)

    story.append(Spacer(1, 28))
    story.append(HRFlowable(width='100%', thickness=0.5, color=st['DKGREY']))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Palm Farm Management System · Nkrankwanta, Dormaa West, Ghana", st['s_footer']))

    doc.build(story)
    buf.seek(0)
    return Response(buf.read(), mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="All_Farms_Report_{date.today()}.pdf"'})


# ── PDF: Processing plant ─────────────────────────────────────────────────────

@reports_bp.route('/pdf/plant')
def pdf_plant():
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, HRFlowable

    date_from = request.args.get('date_from','')
    date_to   = request.args.get('date_to','')
    period    = _period_label(date_from, date_to)
    dc, dp    = _df(date_from, date_to)

    runs   = query(f"SELECT * FROM processing_runs WHERE 1=1{dc} ORDER BY date DESC", dp)
    totals = query(f"""
        SELECT COALESCE(SUM(gross_revenue),0)        AS gross,
               COALESCE(SUM(electricity_cost),0)     AS elec,
               COALESCE(SUM(operator_pay),0)         AS op_pay,
               COALESCE(SUM(company_revenue),0)      AS co_rev,
               COALESCE(SUM(outside_farmer_fees),0)  AS out_fees,
               COALESCE(SUM(total_output_gallons),0) AS gallons,
               COALESCE(SUM(cash_collected),0)       AS collected,
               COALESCE(SUM(cash_outstanding),0)     AS outstanding
        FROM processing_runs WHERE 1=1{dc}
    """, dp, one=True)

    plant_other = _s(f"SELECT COALESCE(SUM(amount),0) FROM plant_expenses WHERE 1=1{dc}", dp)
    gross       = float(totals['gross'] or 0)
    elec        = float(totals['elec'] or 0)
    op_pay      = float(totals['op_pay'] or 0)
    total_exp   = elec + op_pay + plant_other
    net         = gross - total_exp

    st   = _pdf_styles()
    buf  = io.BytesIO()
    doc  = SimpleDocTemplate(buf, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    story = []

    story.append(Paragraph("Processing Plant — Financial Report", st['s_title']))
    story.append(Paragraph(f"Nkrankwanta, Dormaa West · Period: {period} · Generated: {date.today().strftime('%d %B %Y')}", st['s_sub']))
    story.append(HRFlowable(width='100%', thickness=2, color=st['GOLD'], spaceAfter=12))

    story.append(Paragraph("Financial Summary", st['s_h2']))
    sd = [
        ['Item', 'Value'],
        ['Total Gallons Processed',    f"{float(totals['gallons'] or 0):,.1f} gal"],
        ['GROSS REVENUE (All Income)', _money(gross)],
        ['', ''],
        ['Electricity Cost',           _money(elec)],
        ['Operator Pay (30% of net)',   _money(op_pay)],
        ['Other Plant Expenses',       _money(plant_other)],
        ['TOTAL EXPENSES',             _money(total_exp)],
        ['NET PROFIT / LOSS',          _money(net)],
        ['', ''],
        ['Cash Collected',             _money(totals['collected'])],
        ['Cash Outstanding',           _money(totals['outstanding'])],
    ]
    t = Table(sd, colWidths=[10*cm, 6*cm])
    t.setStyle(_tbl_style(st, bold_rows=[2,7], net_rows=[8], net_positive=net>=0))
    story.append(t)
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"Net Profit = Gross Revenue ({_money(gross)}) − Total Expenses ({_money(total_exp)}) = {_money(net)}",
        st['s_small']))

    # Other plant expenses breakdown table
    plant_exp_rows = query(f"SELECT date, category, description, amount FROM plant_expenses WHERE 1=1{dc} ORDER BY date DESC", dp)
    if plant_exp_rows:
        story.append(Paragraph("Other Plant Expenses Breakdown", st['s_h2']))
        data = [['Date', 'Category', 'Description', 'Amount']]
        for r in plant_exp_rows:
            data.append([
                r['date'],
                r['category'] or '—',
                (r['description'] or '—')[:40],
                _money(r['amount']),
            ])
        # Totals row
        data.append(['', '', 'TOTAL', _money(plant_other)])
        t = Table(data, colWidths=[2.5*cm, 3*cm, 7*cm, 3.5*cm])
        ts = _tbl_style(st, net_rows=[len(data)-1], net_positive=True)
        t.setStyle(ts)
        story.append(t)
        story.append(Spacer(1, 8))

    if runs:
        story.append(Paragraph("Processing Run Detail", st['s_h2']))
        data = [['Date','Own Gal','Out Gal','Total Gal','Gross Rev','Electricity','Op. Pay','Net Rev']]
        for r in runs:
            row_net = (r['gross_revenue'] or 0) - (r['electricity_cost'] or 0) - (r['operator_pay'] or 0)
            data.append([
                r['date'],
                f"{r['own_farms_gallons'] or 0:.1f}",
                f"{r['outside_farmers_gallons'] or 0:.1f}",
                f"{r['total_output_gallons'] or 0:.1f}",
                _money(r['gross_revenue']),
                _money(r['electricity_cost']),
                _money(r['operator_pay']),
                _money(row_net),
            ])
        t = Table(data, colWidths=[2.2*cm,1.7*cm,1.7*cm,1.8*cm,2.5*cm,2.3*cm,2*cm,2.3*cm])
        t.setStyle(_tbl_style(st))
        story.append(t)

    story.append(Spacer(1, 24))
    story.append(HRFlowable(width='100%', thickness=0.5, color=st['DKGREY']))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Palm Farm Management System · Nkrankwanta, Dormaa West, Ghana", st['s_footer']))

    doc.build(story)
    buf.seek(0)
    return Response(buf.read(), mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="Plant_Report_{date.today()}.pdf"'})
