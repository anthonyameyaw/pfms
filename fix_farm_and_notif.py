"""
Fix 1: Farm detail charts - match variable names to what route passes
Fix 2: Harvest notification - only flag husks_processed=1 with no gallons
"""
import re

# ── Fix 1: Check what farms route passes ─────────────────────────────────────
farms_content = open('routes/farms.py').read()

# Find render_template call
rt_match = re.search(r'return render_template\([^)]+\)', farms_content, re.DOTALL)
if rt_match:
    rt_text = rt_match.group()
    print("Farms route render_template:")
    print(rt_text[:800])
    print()

# Find monthly chart variable names
monthly_vars = re.findall(r'(\w+)\s*=\s*\[.*?month.*?\]', farms_content[:5000])
print("Monthly-related variables:", monthly_vars[:10])

# Check what's passed
for var in ['monthly_trend', 'monthly_chart', 'monthly_income_rows', 'monthly_data']:
    if var in farms_content:
        print(f"Found: {var}")

# ── Fix 2: Update dashboard notification query ────────────────────────────────
dash = open('routes/dashboard.py').read()

# Make notification only fire for husks_processed=1 AND gallons=0
old1 = """    notif_pending = query(\"\"\"
        SELECT COUNT(*) AS c FROM harvests h JOIN farms f ON f.id=h.farm_id
        WHERE (h.gallons_produced IS NULL OR h.gallons_produced=0)
          AND h.bunches_harvested>0
          AND h.husks_processed=1
          AND f.crop_type='Oil Palm'
    \"\"\", one=True)['c']"""

# Check if already correct
if 'husks_processed=1' in dash:
    print("\n✅ Notification query already correct (husks_processed=1)")
else:
    old_notif = re.search(
        r'notif_pending\s*=\s*query\(.*?one=True\)\[[\'"]c[\'"]\]',
        dash, re.DOTALL
    )
    if old_notif:
        new_notif = """notif_pending = query(\"\"\"
        SELECT COUNT(*) AS c FROM harvests h JOIN farms f ON f.id=h.farm_id
        WHERE (h.gallons_produced IS NULL OR h.gallons_produced=0)
          AND h.bunches_harvested>0
          AND h.husks_processed=1
          AND f.crop_type='Oil Palm'
    \"\"\", one=True)['c']"""
        dash = dash[:old_notif.start()] + new_notif + dash[old_notif.end():]
        open('routes/dashboard.py','w').write(dash)
        print("\n✅ Fixed notification query")
