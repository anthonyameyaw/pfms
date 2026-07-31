"""Adds date range selection to PDF reports in reports/index.html and routes/reports.py"""
import re, os

# ── routes/reports.py ────────────────────────────────────────────────────────
content = open('routes/reports.py').read()

# Add date range to pdf_farm
old = "@reports_bp.route('/pdf/farm/<int:farm_id>')\ndef pdf_farm(farm_id):\n    \"\"\"PDF report for a single farm.\"\"\""
new = """@reports_bp.route('/pdf/farm/<int:farm_id>')
def pdf_farm(farm_id):
    \"\"\"PDF report for a single farm with optional date range.\"\"\"
    date_from = request.args.get('date_from','')
    date_to   = request.args.get('date_to','')
    period_label = (f'{date_from} to {date_to}' if date_from and date_to
                    else f'From {date_from}' if date_from
                    else f'Up to {date_to}' if date_to else 'All Time')
    df, dp = '', []
    if date_from: df += ' AND date>=?'; dp.append(date_from)
    if date_to:   df += ' AND date<=?'; dp.append(date_to)"""

if old in content:
    content = content.replace(old, new)
    print("✅ pdf_farm signature updated")

# Update harvest/transport/activity queries in pdf_farm
old2 = '''    harvests = query(\"\"\"
        SELECT date, bunches_harvested, gallons_produced, gallons_sold,
               gallons_sold_income, harvesting_cost FROM harvests
        WHERE farm_id=? ORDER BY date DESC
    \"\"\", (farm_id,))

    transport = query(\"\"\"
        SELECT date, transport_type, driver_pay, fuel_cost, rental_cost, total_cost
        FROM transport_logs WHERE farm_id=? ORDER BY date DESC
    \"\"\", (farm_id,))

    activities = query(\"\"\"
        SELECT date, activity_type, description, num_labourers, labour_cost, materials_cost
        FROM activities WHERE farm_id=? AND activity_type!='Harvesting' ORDER BY date DESC
    \"\"\", (farm_id,))

    income     = _s("SELECT COALESCE(SUM(gallons_sold_income),0) FROM harvests WHERE farm_id=? AND gallons_sold_income>0", (farm_id,))
    harv_cost  = _s("SELECT COALESCE(SUM(harvesting_cost),0) FROM harvests WHERE farm_id=?", (farm_id,))
    trans_cost = _s("SELECT COALESCE(SUM(total_cost),0) FROM transport_logs WHERE farm_id=?", (farm_id,))
    act_cost   = _s("SELECT COALESCE(SUM(labour_cost+materials_cost),0) FROM activities WHERE farm_id=? AND activity_type!='Harvesting'", (farm_id,))
    total_exp  = harv_cost + trans_cost + act_cost
    net        = income - total_exp'''

new2 = '''    harvests   = query(f"SELECT date,bunches_harvested,gallons_produced,gallons_sold,gallons_sold_income,harvesting_cost FROM harvests WHERE farm_id=?{df} ORDER BY date DESC",(farm_id,*dp))
    transport  = query(f"SELECT date,transport_type,driver_pay,fuel_cost,rental_cost,total_cost FROM transport_logs WHERE farm_id=?{df} ORDER BY date DESC",(farm_id,*dp))
    activities = query(f"SELECT date,activity_type,description,num_labourers,labour_cost,materials_cost FROM activities WHERE farm_id=? AND activity_type!='Harvesting'{df} ORDER BY date DESC",(farm_id,*dp))
    income     = _s(f"SELECT COALESCE(SUM(gallons_sold_income),0) FROM harvests WHERE farm_id=? AND gallons_sold_income>0{df}",(farm_id,*dp))
    harv_cost  = _s(f"SELECT COALESCE(SUM(harvesting_cost),0) FROM harvests WHERE farm_id=?{df}",(farm_id,*dp))
    trans_cost = _s(f"SELECT COALESCE(SUM(total_cost),0) FROM transport_logs WHERE farm_id=?{df}",(farm_id,*dp))
    act_cost   = _s(f"SELECT COALESCE(SUM(labour_cost+materials_cost),0) FROM activities WHERE farm_id=? AND activity_type!='Harvesting'{df}",(farm_id,*dp))
    total_exp  = harv_cost + trans_cost + act_cost
    net        = income - total_exp'''

if old2 in content:
    content = content.replace(old2, new2)
    print("✅ pdf_farm queries updated")

# Add period to farm PDF subtitle
old3 = "story.append(Paragraph(f\"Report generated: {date.today().strftime('%d %B %Y')}\", s_small))"
new3 = "story.append(Paragraph(f\"Period: {period_label} &nbsp;·&nbsp; Generated: {date.today().strftime('%d %B %Y')}\", s_small))"
if old3 in content:
    content = content.replace(old3, new3)
    print("✅ pdf_farm period label added")

# Add date range to pdf_all_farms
old4 = "@reports_bp.route('/pdf/all-farms')\ndef pdf_all_farms():\n    \"\"\"PDF report for all farms consolidated.\"\"\""
new4 = """@reports_bp.route('/pdf/all-farms')
def pdf_all_farms():
    \"\"\"PDF report for all farms consolidated with optional date range.\"\"\"
    date_from = request.args.get('date_from','')
    date_to   = request.args.get('date_to','')
    period_label = (f'{date_from} to {date_to}' if date_from and date_to
                    else f'From {date_from}' if date_from
                    else f'Up to {date_to}' if date_to else 'All Time')
    df, dp = '', []
    if date_from: df += ' AND date>=?'; dp.append(date_from)
    if date_to:   df += ' AND date<=?'; dp.append(date_to)"""

if old4 in content:
    content = content.replace(old4, new4)
    print("✅ pdf_all_farms signature updated")

# Replace farms/summary data in all-farms
old5 = "    farms   = _get_farm_pl()\n    summary = _get_summary()"
new5 = '''    farms_raw = query(f"""
        SELECT f.id,f.name,f.status,f.crop_type,f.size_acres,
               COALESCE((SELECT SUM(h.gallons_sold_income) FROM harvests h WHERE h.farm_id=f.id AND h.gallons_sold_income>0{df}),0) AS income,
               COALESCE((SELECT SUM(h.harvesting_cost) FROM harvests h WHERE h.farm_id=f.id{df}),0) AS harv_cost,
               COALESCE((SELECT SUM(t.total_cost) FROM transport_logs t WHERE t.farm_id=f.id{df}),0) AS trans_cost,
               COALESCE((SELECT SUM(a.labour_cost+a.materials_cost) FROM activities a WHERE a.farm_id=f.id AND a.activity_type!='Harvesting'{df}),0) AS act_cost
        FROM farms f ORDER BY f.name
    """, dp*4)
    farms = [dict(f, expenses=f['harv_cost']+f['trans_cost']+f['act_cost'],
                  net=f['income']-f['harv_cost']-f['trans_cost']-f['act_cost']) for f in farms_raw]
    fi = sum(f['income'] for f in farms)
    fe = sum(f['expenses'] for f in farms)
    pi = _s(f"SELECT COALESCE(SUM(gross_revenue),0) FROM processing_runs WHERE 1=1{df}", dp)
    pe = _s(f"SELECT COALESCE(SUM(electricity_cost+operator_pay),0) FROM processing_runs WHERE 1=1{df}", dp) + \
         _s(f"SELECT COALESCE(SUM(amount),0) FROM plant_expenses WHERE 1=1{df}", dp)
    summary = dict(farm_income=fi,plant_income=pi,total_income=fi+pi,
                   harv_exp=sum(f['harv_cost'] for f in farms),
                   trans_exp=sum(f['trans_cost'] for f in farms),
                   act_exp=sum(f['act_cost'] for f in farms),
                   plant_exp=pe,p_other=0,total_exp=fe+pe,net=fi+pi-fe-pe)'''

if old5 in content:
    content = content.replace(old5, new5)
    print("✅ pdf_all_farms data updated")

# Add period to all-farms subtitle
old6 = "story.append(Paragraph(f\"Nkrankwanta, Dormaa West, Ghana &nbsp;·&nbsp; Generated: {date.today().strftime('%d %B %Y')}\", s_sub))"
new6 = "story.append(Paragraph(f\"Nkrankwanta, Dormaa West, Ghana &nbsp;·&nbsp; Period: {period_label} &nbsp;·&nbsp; Generated: {date.today().strftime('%d %B %Y')}\", s_sub))"
content = content.replace(old6, new6)

# Add date range to pdf_plant
old7 = "@reports_bp.route('/pdf/plant')\ndef pdf_plant():\n    \"\"\"PDF report for the processing plant.\"\"\""
new7 = """@reports_bp.route('/pdf/plant')
def pdf_plant():
    \"\"\"PDF report for the processing plant with optional date range.\"\"\"
    date_from = request.args.get('date_from','')
    date_to   = request.args.get('date_to','')
    period_label = (f'{date_from} to {date_to}' if date_from and date_to
                    else f'From {date_from}' if date_from
                    else f'Up to {date_to}' if date_to else 'All Time')
    df, dp = '', []
    if date_from: df += ' AND date>=?'; dp.append(date_from)
    if date_to:   df += ' AND date<=?'; dp.append(date_to)"""

if old7 in content:
    content = content.replace(old7, new7)
    print("✅ pdf_plant signature updated")

old8 = '    runs = query("SELECT * FROM processing_runs ORDER BY date DESC")\n    totals = query(\"\"\"'
new8 = f'    runs = query(f"SELECT * FROM processing_runs WHERE 1=1{{df}} ORDER BY date DESC", dp)\n    totals = query(f"""'
content = content.replace(old8, new8)

old9 = '        FROM processing_runs\n    \"\"\", one=True)'
new9 = '        FROM processing_runs WHERE 1=1{df}""", dp, one=True)'
content = content.replace(old9, new9)

old10 = "story.append(Paragraph(f\"Nkrankwanta, Dormaa West &nbsp;·&nbsp; Generated: {date.today().strftime('%d %B %Y')}\", s_sub))"
new10 = "story.append(Paragraph(f\"Nkrankwanta, Dormaa West &nbsp;·&nbsp; Period: {period_label} &nbsp;·&nbsp; Generated: {date.today().strftime('%d %B %Y')}\", s_sub))"
content = content.replace(old10, new10)

open('routes/reports.py','w').write(content)
print("✅ routes/reports.py fully updated")

# ── templates/reports/index.html ─────────────────────────────────────────────
tmpl = open('templates/reports/index.html').read()

# Add date range card after page header
old_hdr = '<p>Download financial reports as PDF or CSV for any farm or the processing plant.</p>\n</div>\n</div>'
new_hdr = '''<p>Select a date range then download PDF or CSV reports.</p>
</div>
</div>

<div class="card">
  <div class="card-title">📅 Select Report Period</div>
  <div class="form-grid" style="align-items:flex-end;">
    <div class="form-group">
      <label>From Date</label>
      <input type="date" id="dateFrom" onchange="updateLinks()">
    </div>
    <div class="form-group">
      <label>To Date</label>
      <input type="date" id="dateTo" onchange="updateLinks()">
    </div>
    <div class="form-group">
      <label>Quick Select</label>
      <div class="flex gap-2" style="flex-wrap:wrap;">
        <button class="btn btn-outline btn-sm" onclick="setRange('this_month')">This Month</button>
        <button class="btn btn-outline btn-sm" onclick="setRange('last_month')">Last Month</button>
        <button class="btn btn-outline btn-sm" onclick="setRange('this_year')">This Year</button>
        <button class="btn btn-outline btn-sm" onclick="setRange('all')">All Time</button>
      </div>
    </div>
  </div>
  <div id="periodLabel" class="small muted" style="margin-top:10px;font-weight:500;">
    📄 Report period: <strong>All Time</strong>
  </div>
</div>'''

if old_hdr in tmpl:
    tmpl = tmpl.replace(old_hdr, new_hdr)
    print("✅ Date range card added to template")

# Tag all PDF links
tmpl = re.sub(
    r'(href="{{ url_for\(\'reports\.(pdf_all_farms|pdf_plant)\'\) }}")',
    r'\1 class="pdf-link" data-base="{{ url_for(\'reports.\2\') }}"',
    tmpl
)
tmpl = re.sub(
    r'(href="{{ url_for\(\'reports\.pdf_farm\', farm_id=f\.id\) }}")',
    r'\1 class="pdf-link" data-base="{{ url_for(\'reports.pdf_farm\', farm_id=f.id) }}"',
    tmpl
)

# Add JS block
js_block = """
{% block extra_js %}
<script>
function updateLinks() {
  const from = document.getElementById('dateFrom').value;
  const to   = document.getElementById('dateTo').value;
  let params = '';
  if (from || to) {
    const parts = [];
    if (from) parts.push('date_from=' + from);
    if (to)   parts.push('date_to='   + to);
    params = '?' + parts.join('&');
  }
  document.querySelectorAll('.pdf-link').forEach(a => {
    a.href = a.dataset.base + params;
  });
  const lbl = document.getElementById('periodLabel');
  if (from && to)   lbl.innerHTML = '📄 Report period: <strong>' + from + ' to ' + to + '</strong>';
  else if (from)    lbl.innerHTML = '📄 Report period: <strong>From ' + from + '</strong>';
  else if (to)      lbl.innerHTML = '📄 Report period: <strong>Up to ' + to + '</strong>';
  else              lbl.innerHTML = '📄 Report period: <strong>All Time</strong>';
}
function setRange(preset) {
  const today = new Date();
  const fmt = d => d.toISOString().slice(0,10);
  let from = '', to = '';
  if (preset === 'this_month') {
    from = fmt(new Date(today.getFullYear(), today.getMonth(), 1));
    to   = fmt(today);
  } else if (preset === 'last_month') {
    from = fmt(new Date(today.getFullYear(), today.getMonth()-1, 1));
    to   = fmt(new Date(today.getFullYear(), today.getMonth(), 0));
  } else if (preset === 'this_year') {
    from = today.getFullYear() + '-01-01';
    to   = fmt(today);
  }
  document.getElementById('dateFrom').value = from;
  document.getElementById('dateTo').value   = to;
  updateLinks();
}
</script>
{% endblock %}"""

# Insert before last endblock
last_eb = tmpl.rfind('{% endblock %}')
if last_eb > 0:
    tmpl = tmpl[:last_eb] + js_block + '\n' + tmpl[last_eb:]
    print("✅ JS block added to template")

open('templates/reports/index.html','w').write(tmpl)
print("\n✅ All done. Restart the app to see changes.")
