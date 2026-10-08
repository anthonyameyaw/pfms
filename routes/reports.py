from database.periods import business_today
"""Reports & Export — CSV and PDF with date range and correct net profit."""

import csv, io, zipfile
from decimal import Decimal
from xml.sax.saxutils import escape
from datetime import date
from flask import Blueprint, render_template, request, Response, flash, redirect, url_for
from database.db import query
from database.financials import financial_summary, farm_financials

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
    return financial_summary(date_from, date_to)


def _get_farm_pl(date_from='', date_to=''):
    return farm_financials(date_from, date_to)


@reports_bp.route('/')
def index():
    date_from = request.args.get('date_from', '')
    date_to   = request.args.get('date_to', '')
    summary   = _get_summary(date_from, date_to)
    farms     = _get_farm_pl(date_from, date_to)
    return render_template('reports/index.html',
        today=business_today(), summary=summary, farms=farms,
        date_from=date_from, date_to=date_to,
    )


# ── CSV exports ───────────────────────────────────────────────────────────────

@reports_bp.route('/export/financial-summary.csv')
def export_financial_summary():
    summary = financial_summary(request.args.get('date_from',''), request.args.get('date_to',''))
    rows = [['Income', i['label'], Decimal(str(i['value'])).quantize(Decimal('0.01'))] for i in summary['income_items']]
    rows += [['Expense', i['label'], Decimal(str(i['value'])).quantize(Decimal('0.01'))] for i in summary['expense_items']]
    rows += [['Excluded internal transfer', 'Own-farm processing fees and matching farm expenses', Decimal(str(summary['internal_processing_fees'])).quantize(Decimal('0.01'))]]
    rows += [['Total', 'Income', Decimal(str(summary['total_income'])).quantize(Decimal('0.01'))],
             ['Total', 'Expenses', Decimal(str(summary['total_exp'])).quantize(Decimal('0.01'))],
             ['Total', 'Net', Decimal(str(summary['net'])).quantize(Decimal('0.01'))]]
    return _csv('financial_summary.csv', ['Type','Category','Amount (GHS)'], rows)


@reports_bp.route('/export/harvests.csv')
def export_harvests():
    rows = query("""SELECT h.*,f.name AS farm FROM harvests h JOIN farms f ON f.id=h.farm_id ORDER BY h.date DESC""")
    return _csv('harvests.csv', ['Farm','Harvest Date','Bunches','Processed','Processing Date','Gallons Produced (25 L)','Harvest Labour (GHS)','Defruiting (GHS)','Total Labour (GHS)','Notes'],
        [[r['farm'],r['date'],r['bunches_harvested'],r['husks_processed'],r['processing_date'],r['gallons_produced'],r['harvesting_cost'],r['threshing_cost'],(r['harvesting_cost'] or 0)+(r['threshing_cost'] or 0),r['notes']] for r in rows])


@reports_bp.route('/export/storage.csv')
def export_storage():
    rows=query("SELECT * FROM storage_transactions WHERE transaction_type IN ('Purchase','Sale') ORDER BY date,id")
    return _csv('pooled_storage.csv',['Date','Type','Oil Type','Gallons (25 L)','Price (GHS)','Amount (GHS)','Buyer','Seller','Notes'],
        [[r['date'],r['transaction_type'],{'Fresh':'Oil for food','Soap':'Oil for soap','Unassessed':'Type not recorded'}[r['quality_type']],r['gallons'],r['price_per_gallon'],r['total_amount'],r['buyer'],r['seller'],r['notes']] for r in rows])


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


def _safe_csv_cell(value):
    # Only text is escaped; actual numeric values stay numeric, including negatives.
    if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@','\t','\r','\n')):
        return "'"+value
    return value

@reports_bp.route('/export/all-records.zip')
def export_all_records():
    from database.db import get_connection
    conn=get_connection()
    out=io.BytesIO()
    try:
        conn.execute('BEGIN')
        with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as archive:
            tables=conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
            for entry in tables:
                name=entry['name']
                quoted='"'+name.replace('"','""')+'"'
                cursor=conn.execute('SELECT * FROM '+quoted)
                text=io.StringIO();writer=csv.writer(text)
                writer.writerow([c[0] for c in cursor.description])
                writer.writerows([[_safe_csv_cell(v) for v in row] for row in cursor])
                archive.writestr(name+'.csv',text.getvalue())
            archive.writestr('README.txt','All recorded dates. One CSV per database table, including investors, repayments, pruning, processing links, and storage quality assessments. IDs preserve relationships. These are raw records, not additive financial totals: linked activity/harvest costs and legacy archive records may overlap. Use the financial summary for reconciled totals. Formula-leading text is prefixed with an apostrophe for spreadsheet safety. This export is not a restorable database backup.')
    finally:
        conn.close()
    return Response(out.getvalue(),mimetype='application/zip',headers={'Content-Disposition':'attachment; filename="pfms_all_records.zip"'})


def _csv(filename, headers, rows):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(headers)
    w.writerows([[_safe_csv_cell(cell) for cell in row] for row in rows])
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
        s_title  = ParagraphStyle('T',  fontName='Helvetica-Bold', fontSize=20, leading=24, textColor=GREEN, spaceAfter=8),
        s_sub    = ParagraphStyle('S',  fontName='Helvetica',      fontSize=9, leading=12, textColor=DKGREY, spaceAfter=14),
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

    harvests   = query(f"SELECT date,processing_date,bunches_harvested,gallons_produced,harvesting_cost,threshing_cost FROM harvests WHERE farm_id=?{dc} ORDER BY date DESC", (farm_id,*dp))
    transport  = query(f"SELECT date,transport_type,driver_pay,fuel_cost,rental_cost,total_cost FROM transport_logs WHERE farm_id=?{dc} ORDER BY date DESC", (farm_id,*dp))
    activities = query(f"SELECT date,activity_type,description,num_labourers,labour_cost,materials_cost FROM activities WHERE farm_id=? AND activity_type!='Harvesting'{dc} ORDER BY date DESC", (farm_id,*dp))

    summary = financial_summary(date_from, date_to, farm_id)
    income, total_exp, net = summary['total_income'], summary['total_exp'], summary['net']

    st   = _pdf_styles()
    buf  = io.BytesIO()
    doc  = SimpleDocTemplate(buf, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    story = []

    story.append(Paragraph(farm['name'], st['s_title']))
    story.append(Paragraph(f"{farm['location']} · {farm['size_acres']} acres · {farm['crop_type']} · {farm['status']}", st['s_sub']))
    story.append(HRFlowable(width='100%', thickness=2, color=st['GOLD'], spaceAfter=10))
    story.append(Paragraph(f"Period: {period} · Generated: {business_today().strftime('%d %B %Y')}", st['s_small']))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Financial Summary", st['s_h2']))
    story.append(Paragraph("All oil sales belong to the shared pool and are excluded from individual farm income. Individual farm results include assigned processing charges and exclude charges still awaiting allocation. See the Finances page for the farm-group expense.", st['s_small']))
    summary_data = [['Item', 'Amount']]
    summary_data += [[item['label'], _money(item['value'])] for item in summary['income_items'] if item['value']]
    summary_data.append(['Total Income', _money(income)])
    summary_data += [[item['label'], _money(item['value'])] for item in summary['expense_items'] if item['value']]
    summary_data += [['Total Expenses', _money(total_exp)], ['NET INCOME / EXPENSE RESULT', _money(net)]]
    t = Table(summary_data, colWidths=[11*cm, 5*cm])
    t.setStyle(_tbl_style(st, bold_rows=[len(summary_data)-2], net_rows=[len(summary_data)-1], net_positive=net>=0))
    story.append(t)
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"Farm balance before pooled oil sales = Other Income ({_money(income)}) − Total Expenses ({_money(total_exp)}) = {_money(net)}", st['s_small']))

    if harvests:
        story.append(Paragraph("Harvest Records", st['s_h2']))
        data = [['Harvest Date','Processed Date','Bunches','Gallons','Labour*','Defruiting']]
        for r in harvests:
            data.append([r['date'], r['processing_date'] or 'Not recorded',r['bunches_harvested'] or 0,
                         r['gallons_produced'] or 0, _money(r['harvesting_cost']),_money(r['threshing_cost'])])
        t = Table(data, repeatRows=1, colWidths=[3*cm,3*cm,2*cm,2*cm,3*cm,3*cm])
        t.setStyle(_tbl_style(st))
        story.append(t)

    if harvests:
        story.append(Paragraph('*Labour excludes the separately shown defruiting cost.', st['s_small']))

    if transport:
        story.append(Paragraph("Transport Logs", st['s_h2']))
        data = [['Date','Type','Driver Pay','Fuel','Rental','Total']]
        for r in transport:
            data.append([r['date'],r['transport_type'],
                         _money(r['driver_pay']),_money(r['fuel_cost']),
                         _money(r['rental_cost']),_money(r['total_cost'])])
        t = Table(data, repeatRows=1, colWidths=[2.5*cm,2.5*cm,2.5*cm,2.5*cm,2.5*cm,3*cm])
        t.setStyle(_tbl_style(st))
        story.append(t)

    if activities:
        story.append(Paragraph("Farm Activities", st['s_h2']))
        data = [['Date','Type','Description','Workers','Labour','Materials']]
        for r in activities:
            data.append([r['date'],r['activity_type'],Paragraph(escape(r['description'] or ''), st['s_small']),
                         r['num_labourers'] or 0,_money(r['labour_cost']),_money(r['materials_cost'])])
        t = Table(data, repeatRows=1, colWidths=[2.2*cm,2.5*cm,4.3*cm,1.8*cm,2.5*cm,2.7*cm])
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
        headers={'Content-Disposition': f'attachment; filename="{fname}_Report_{business_today()}.pdf"'})


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
    story.append(Paragraph(f"Nkrankwanta, Dormaa West, Ghana · Period: {period} · Generated: {business_today().strftime('%d %B %Y')}", st['s_sub']))
    story.append(HRFlowable(width='100%', thickness=2, color=st['GOLD'], spaceAfter=12))

    # Consolidated summary
    story.append(Paragraph("Consolidated Financial Summary", st['s_h2']))
    sd = [['Category', 'Amount']]
    sd += [[item['label'], _money(item['value'])] for item in summary['income_items']]
    sd.append(['TOTAL INCOME', _money(summary['total_income'])])
    income_total_row = len(sd)-1
    sd += [[item['label'], _money(item['value'])] for item in summary['expense_items']]
    sd += [['TOTAL EXPENSES', _money(summary['total_exp'])],
           ['NET INCOME / EXPENSE RESULT', _money(summary['net'])]]
    t = Table(sd, colWidths=[12*cm, 4*cm])
    t.setStyle(_tbl_style(st, bold_rows=[income_total_row,len(sd)-2], net_rows=[len(sd)-1], net_positive=summary['net']>=0))
    story.append(t)
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"Net Profit = Total Income ({_money(summary['total_income'])}) − Total Expenses ({_money(summary['total_exp'])}) = {_money(summary['net'])}",
        st['s_small']))

    story.append(Paragraph(f"Internal processing fees of {_money(summary['internal_processing_fees'])} and matching farm charges are excluded from combined totals. All oil sales belong to the shared pool. Assigned charges are included in individual farm expenses. Any unassigned charges appear on the Finances page.", st['s_small']))

    # Other plant expenses breakdown
    plant_exp_rows = query(f"SELECT date, category, description, amount FROM plant_expenses WHERE 1=1{dc} ORDER BY date DESC", dp)
    if plant_exp_rows:
        story.append(Paragraph("Other Plant Expenses Breakdown", st['s_h2']))
        data = [['Date', 'Category', 'Description', 'Amount']]
        for r in plant_exp_rows:
            data.append([r['date'], r['category'] or '—', Paragraph(escape(r['description'] or ''), st['s_small']), _money(r['amount'])])
        data.append(['', '', 'TOTAL', _money(summary['plant_other'])])
        t = Table(data, repeatRows=1, colWidths=[2.5*cm, 3*cm, 8*cm, 2.5*cm])
        t.setStyle(_tbl_style(st, net_rows=[len(data)-1], net_positive=True))
        story.append(t)
        story.append(Spacer(1, 8))

    # Per-farm table
    story.append(Paragraph("Per-Farm Performance", st['s_h2']))
    story.append(Paragraph('All amounts in GHS. Farm expenses include harvest and threshing labour, transport, activities and other recorded farm expenses. Pooled storage and shared expenses are included in the consolidated summary above.', st['s_small']))
    data = [['Farm','Income','Total Expenses','Net']]
    for f in farms:
        data.append([Paragraph(escape(f['name']), st['s_small']), _money(f['income']),
                     _money(f['expenses']), _money(f['net'])])
    t = Table(data, repeatRows=1, colWidths=[5*cm,3.6*cm,3.7*cm,3.7*cm])
    t.setStyle(_tbl_style(st))
    story.append(t)

    story.append(Spacer(1, 28))
    story.append(HRFlowable(width='100%', thickness=0.5, color=st['DKGREY']))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Palm Farm Management System · Nkrankwanta, Dormaa West, Ghana", st['s_footer']))

    doc.build(story)
    buf.seek(0)
    return Response(buf.read(), mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="All_Farms_Report_{business_today()}.pdf"'})


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
               COALESCE(SUM(cash_outstanding),0)     AS outstanding,
               SUM(CASE WHEN cash_collected IS NULL THEN 1 ELSE 0 END) AS unknown_cash_count,
               COALESCE(SUM(MAX(0,COALESCE(cash_collected,0)-gross_revenue)),0) AS overpaid
        FROM processing_runs WHERE 1=1{dc}
    """, dp, one=True)

    summary = financial_summary(date_from, date_to, scope='plant')
    plant_other = summary['plant_other']
    gross, elec, op_pay = summary['total_income'], summary['elec_exp'], summary['op_exp']
    total_exp, net = summary['total_exp'], summary['net']

    st   = _pdf_styles()
    buf  = io.BytesIO()
    doc  = SimpleDocTemplate(buf, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    story = []

    story.append(Paragraph("Processing Plant — Financial Report", st['s_title']))
    story.append(Paragraph(f"Nkrankwanta, Dormaa West · Period: {period} · Generated: {business_today().strftime('%d %B %Y')}", st['s_sub']))
    story.append(HRFlowable(width='100%', thickness=2, color=st['GOLD'], spaceAfter=12))

    story.append(Paragraph("Financial Summary", st['s_h2']))
    story.append(Paragraph("Plant revenue includes processing fees from both own farms and outside farmers.", st['s_small']))
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
        ['Known Cash Collected',       _money(totals['collected'])],
        ['Known Cash Outstanding',     _money(totals['outstanding'])],
        ['Runs with payment not recorded', str(totals['unknown_cash_count'] or 0)],
        ['Excess collected (not allocated to other runs)', _money(totals['overpaid'])],
    ]
    t = Table(sd, colWidths=[10*cm, 6*cm])
    t.setStyle(_tbl_style(st, bold_rows=[2,7], net_rows=[8], net_positive=net>=0))
    story.append(t)
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"Net Profit = Gross Revenue ({_money(gross)}) − Total Expenses ({_money(total_exp)}) = {_money(net)}",
        st['s_small']))

    story.append(Paragraph(f"Own-farm fees of {_money(summary['internal_processing_fees'])} are included in plant revenue above. The combined business excludes these fees and matching farm charges.", st['s_small']))

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
        t = Table(data, repeatRows=1, colWidths=[2.5*cm, 3*cm, 7*cm, 3.5*cm])
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
        t = Table(data, repeatRows=1, colWidths=[2.2*cm,1.7*cm,1.7*cm,1.8*cm,2.5*cm,2.3*cm,2*cm,2.3*cm])
        t.setStyle(_tbl_style(st))
        story.append(t)

    story.append(Spacer(1, 24))
    story.append(HRFlowable(width='100%', thickness=0.5, color=st['DKGREY']))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Palm Farm Management System · Nkrankwanta, Dormaa West, Ghana", st['s_footer']))

    doc.build(story)
    buf.seek(0)
    return Response(buf.read(), mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="Plant_Report_{business_today()}.pdf"'})
