"""Adds Net Profit row to all PDF reports."""

content = open('routes/reports.py').read()

# ── Fix 1: Farm PDF summary table — add Net Profit row ───────────────────────
old1 = """    summary_data = [
        ['', 'Amount'],
        ['Total Income (Sold Gallons)', money(income)],
        ['Harvesting Labour',           money(harv_cost)],
        ['Transport Costs',             money(trans_cost)],
        ['Activity Labour & Materials', money(act_cost)],
        ['Total Expenses',              money(total_exp)],
        ['Net Profit / Loss',           money(net)],
    ]"""

new1 = """    summary_data = [
        ['', 'Amount'],
        ['Total Income (Sold Gallons)', money(income)],
        ['Harvesting Labour',           money(harv_cost)],
        ['Transport Costs',             money(trans_cost)],
        ['Activity Labour & Materials', money(act_cost)],
        ['Total Expenses',              money(total_exp)],
        ['NET PROFIT / LOSS',           money(net)],
    ]"""

if old1 in content:
    content = content.replace(old1, new1)
    print("Farm PDF net row label updated")

# Make sure net row styling exists and is prominent
old2 = """    t = Table(summary_data, colWidths=[11*cm, 5*cm])
    ts = tbl_style()
    ts.add('FONTNAME',  (0,6),(-1,6), 'Helvetica-Bold')
    ts.add('FONTSIZE',  (0,6),(-1,6), 9)
    ts.add('TEXTCOLOR', (1,6),(1,6),  GREEN if net >= 0 else colors.red)
    t.setStyle(ts)"""

new2 = """    t = Table(summary_data, colWidths=[11*cm, 5*cm])
    ts = tbl_style()
    ts.add('FONTNAME',     (0,6),(-1,6), 'Helvetica-Bold')
    ts.add('FONTSIZE',     (0,6),(-1,6), 11)
    ts.add('BACKGROUND',   (0,6),(-1,6), colors.HexColor('#eef7f1'))
    ts.add('TEXTCOLOR',    (0,6),(0,6),  GREEN)
    ts.add('TEXTCOLOR',    (1,6),(1,6),  GREEN if net >= 0 else colors.red)
    ts.add('TOPPADDING',   (0,6),(-1,6), 10)
    ts.add('BOTTOMPADDING',(0,6),(-1,6), 10)
    t.setStyle(ts)"""

if old2 in content:
    content = content.replace(old2, new2)
    print("Farm PDF net row styled prominently")
else:
    # Try simpler match
    old2b = """    ts = tbl_style()
    ts.add('FONTNAME',     (0,6),(-1,6), 'Helvetica-Bold')
    ts.add('FONTSIZE',     (0,6),(-1,6), 10)
    ts.add('BACKGROUND',   (0,6),(-1,6), colors.HexColor('#f2f7f4'))
    ts.add('TEXTCOLOR',    (1,6),(1,6),  GREEN if net >= 0 else colors.red)
    ts.add('BOTTOMPADDING',(0,6),(-1,6), 8)
    ts.add('TOPPADDING',   (0,6),(-1,6), 8)
    t.setStyle(ts)"""

    new2b = """    ts = tbl_style()
    ts.add('FONTNAME',     (0,6),(-1,6), 'Helvetica-Bold')
    ts.add('FONTSIZE',     (0,6),(-1,6), 11)
    ts.add('BACKGROUND',   (0,6),(-1,6), colors.HexColor('#eef7f1'))
    ts.add('TEXTCOLOR',    (0,6),(0,6),  GREEN)
    ts.add('TEXTCOLOR',    (1,6),(1,6),  GREEN if net >= 0 else colors.red)
    ts.add('TOPPADDING',   (0,6),(-1,6), 10)
    ts.add('BOTTOMPADDING',(0,6),(-1,6), 10)
    t.setStyle(ts)"""

    if old2b in content:
        content = content.replace(old2b, new2b)
        print("Farm PDF net row styled (variant)")
    else:
        print("WARNING: Farm PDF net styling not found - will add net row manually")

# ── Fix 2: All-farms consolidated PDF ────────────────────────────────────────
old3 = """    sd = [
        ['Category', 'Amount'],
        ['Total Farm Income',              money(summary['farm_income'])],
        ['Total Plant Income',             money(summary['plant_income'])],
        ['TOTAL INCOME',                   money(summary['total_income'])],
        ['Harvesting Labour',              money(summary['harv_exp'])],
        ['Transport',                      money(summary['trans_exp'])],
        ['Activity Labour & Materials',    money(summary['act_exp'])],
        ['Plant Electricity + Operator',   money(summary['plant_exp'])],
        ['Other Plant Expenses',           money(summary['p_other'])],
        ['TOTAL EXPENSES',                 money(summary['total_exp'])],
        ['NET PROFIT / LOSS',              money(summary['net'])],
    ]"""

# Already has NET PROFIT - just ensure styling is right
if old3 in content:
    print("All-farms PDF already has NET PROFIT row")
else:
    # Check what's there
    idx = content.find("'Category', 'Amount'")
    if idx > 0:
        print("Found summary table at index", idx)
        print(repr(content[idx:idx+600]))

# ── Fix 3: Plant PDF ──────────────────────────────────────────────────────────
# Check if plant PDF has net profit
if 'net_plant' in content or 'plant_net' in content or 'Net' in content:
    # Find plant summary table
    idx = content.find("'Metric', 'Value'")
    if idx > 0:
        end = content.find('])', idx)
        plant_table = content[idx:end+2]
        if 'Net' not in plant_table and 'net' not in plant_table.lower():
            # Add net profit to plant table
            old_plant_tbl = """    sd = [
        ['Metric', 'Value'],
        ['Total Gallons Processed',    f"{float(totals['gallons'] or 0):,.1f} gal"],
        ['Gross Revenue (All Income)', money(totals['gross'])],
        ['Electricity Cost',           money(totals['elec'])],
        ['Operator Pay (30%)',         money(totals['op_pay'])],
        ['Company Revenue (70%)',      money(totals['co_rev'])],
        ['Outside Farmer Fees',        money(totals['out_fees'])],
        ['Cash Collected',             money(totals['collected'])],
        ['Cash Outstanding',           money(totals['outstanding'])],
    ]"""
            new_plant_tbl = """    plant_elec    = float(totals['elec'] or 0)
    plant_op      = float(totals['op_pay'] or 0)
    plant_gross   = float(totals['gross'] or 0)
    plant_net_val = plant_gross - plant_elec - plant_op
    sd = [
        ['Metric', 'Value'],
        ['Total Gallons Processed',    f"{float(totals['gallons'] or 0):,.1f} gal"],
        ['Gross Revenue (All Income)', money(totals['gross'])],
        ['Electricity Cost',           money(totals['elec'])],
        ['Operator Pay (30%)',         money(totals['op_pay'])],
        ['Company Revenue (70%)',      money(totals['co_rev'])],
        ['Outside Farmer Fees',        money(totals['out_fees'])],
        ['Cash Collected',             money(totals['collected'])],
        ['Cash Outstanding',           money(totals['outstanding'])],
        ['NET PROFIT / LOSS',          money(plant_net_val)],
    ]"""
            if old_plant_tbl in content:
                content = content.replace(old_plant_tbl, new_plant_tbl)
                print("Plant PDF net profit row added")

                # Add styling for net row (row index 9)
                old_plant_style = "    story.append(tbl(sd, [10*cm, 6*cm]))"
                new_plant_style = """    plant_tbl = tbl(sd, [10*cm, 6*cm])
    from reportlab.platypus import TableStyle as TS2
    plant_tbl.setStyle(TS2([
        ('FONTNAME',     (0,9),(-1,9), 'Helvetica-Bold'),
        ('FONTSIZE',     (0,9),(-1,9), 11),
        ('BACKGROUND',   (0,9),(-1,9), colors.HexColor('#eef7f1')),
        ('TEXTCOLOR',    (1,9),(1,9),  GREEN if plant_net_val >= 0 else colors.red),
        ('TOPPADDING',   (0,9),(-1,9), 10),
        ('BOTTOMPADDING',(0,9),(-1,9), 10),
    ]))
    story.append(plant_tbl)"""
                if old_plant_style in content:
                    content = content.replace(old_plant_style, new_plant_style)
                    print("Plant PDF net row styled")

# ── Fix 4: Ensure all-farms net row is styled ────────────────────────────────
old4 = """    for bold_row in [3, 9, 10]:
        style.add('FONTNAME', (0,bold_row),(-1,bold_row), 'Helvetica-Bold')
    style.add('TEXTCOLOR', (1,10),(1,10), GREEN if summary['net'] >= 0 else colors.red)
    t.setStyle(style)"""

new4 = """    for bold_row in [3, 9, 10]:
        style.add('FONTNAME', (0,bold_row),(-1,bold_row), 'Helvetica-Bold')
    # Net profit row extra prominent
    style.add('FONTSIZE',     (0,10),(-1,10), 11)
    style.add('BACKGROUND',   (0,10),(-1,10), colors.HexColor('#eef7f1'))
    style.add('TEXTCOLOR',    (0,10),(0,10),  GREEN)
    style.add('TEXTCOLOR',    (1,10),(1,10),  GREEN if summary['net'] >= 0 else colors.red)
    style.add('TOPPADDING',   (0,10),(-1,10), 10)
    style.add('BOTTOMPADDING',(0,10),(-1,10), 10)
    t.setStyle(style)"""

if old4 in content:
    content = content.replace(old4, new4)
    print("All-farms net row styled prominently")
else:
    # Try variant
    old4b = """    for bold_row in [3, 9, 10]:
        style.add('FONTNAME', (0,bold_row),(-1,bold_row), 'Helvetica-Bold')
        style.add('FONTSIZE', (0,bold_row),(-1,bold_row), 9)
    # Highlight net profit row
    style.add('BACKGROUND',   (0,10),(-1,10), colors.HexColor('#f2f7f4'))
    style.add('FONTSIZE',     (0,10),(-1,10), 10)
    style.add('TOPPADDING',   (0,10),(-1,10), 8)
    style.add('BOTTOMPADDING',(0,10),(-1,10), 8)
    style.add('TEXTCOLOR',    (1,10),(1,10), GREEN if summary['net'] >= 0 else colors.red)"""
    new4b = """    for bold_row in [3, 9, 10]:
        style.add('FONTNAME', (0,bold_row),(-1,bold_row), 'Helvetica-Bold')
    style.add('FONTSIZE',     (0,10),(-1,10), 11)
    style.add('BACKGROUND',   (0,10),(-1,10), colors.HexColor('#eef7f1'))
    style.add('TEXTCOLOR',    (0,10),(0,10),  GREEN)
    style.add('TEXTCOLOR',    (1,10),(1,10),  GREEN if summary['net'] >= 0 else colors.red)
    style.add('TOPPADDING',   (0,10),(-1,10), 10)
    style.add('BOTTOMPADDING',(0,10),(-1,10), 10)"""
    if old4b in content:
        content = content.replace(old4b, new4b)
        print("All-farms net row styled (variant)")

open('routes/reports.py','w').write(content)
print("\nDone — restart the app and download a PDF to see net profit highlighted")
