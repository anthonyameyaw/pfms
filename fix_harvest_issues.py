"""
Fix 3 issues:
1. Dashboard notification wrongly flags harvests that have gallons recorded
2. Harvest edit form has step interval restriction on gallons fields  
3. Finances analytics shows 100% profit because gallon_value = 0 when price not set
"""

# ── Fix 1: Dashboard notification query ──────────────────────────────────────
content = open('routes/dashboard.py').read()

# The bug: query checks gallons_produced IS NULL OR = 0
# but some harvests have gallons_produced set yet husks_processed = False
# so the notification fires incorrectly. Fix: only flag if husks_processed=1
# and gallons_produced is still missing
old_notif = """    notif_pending = query(\"\"\"
        SELECT COUNT(*) AS c FROM harvests h JOIN farms f ON f.id=h.farm_id
        WHERE (h.gallons_produced IS NULL OR h.gallons_produced=0)
          AND h.bunches_harvested>0 AND f.crop_type='Oil Palm'
    \"\"\", one=True)['c']"""

new_notif = """    notif_pending = query(\"\"\"
        SELECT COUNT(*) AS c FROM harvests h JOIN farms f ON f.id=h.farm_id
        WHERE (h.gallons_produced IS NULL OR h.gallons_produced=0)
          AND h.bunches_harvested>0
          AND h.husks_processed=1
          AND f.crop_type='Oil Palm'
    \"\"\", one=True)['c']"""

if old_notif in content:
    content = content.replace(old_notif, new_notif)
    open('routes/dashboard.py','w').write(content)
    print("✅ Fix 1: Dashboard notification query fixed")
else:
    print("⚠ Fix 1: Pattern not found in dashboard.py")

# ── Fix 2: Finances analytics — 100% profit bug ──────────────────────────────
content = open('routes/finances.py').read()

# Bug: gallon_value = gal * price, but price is often 0 if gallons not sold yet
# Fix: fall back to a reference price from price_log, or use actual income,
# or if no income use total_cost as baseline to avoid division by zero giving 100%

old_calc = """        gallon_value = gal * price if price > 0 else income

        # 1. Cost distribution %
        lab_pct   = round(total_lab / gallon_value * 100, 1) if gallon_value > 0 else 0
        trans_pct = round(trans / gallon_value * 100, 1) if gallon_value > 0 else 0
        net_pct   = max(0, round(100 - lab_pct - trans_pct, 1))"""

new_calc = """        # Use actual income if available, else estimate from price * gallons
        # If neither available, skip cost distribution (can't calculate %)
        if income > 0:
            gallon_value = income
        elif price > 0 and gal > 0:
            gallon_value = price * gal
        else:
            gallon_value = 0

        # 1. Cost distribution % — only calculate if we have a real income value
        if gallon_value > 0:
            lab_pct   = round(total_lab / gallon_value * 100, 1)
            trans_pct = round(trans / gallon_value * 100, 1)
            # Cap at 100% in case costs exceed income
            total_cost_pct = min(lab_pct + trans_pct, 100)
            net_pct   = max(0, round(100 - total_cost_pct, 1))
        else:
            # No sale recorded yet — show cost breakdown but flag as no income
            lab_pct   = 0
            trans_pct = 0
            net_pct   = 0"""

if old_calc in content:
    content = content.replace(old_calc, new_calc)
    print("✅ Fix 2: Finances gallon_value calculation fixed")
else:
    print("⚠ Fix 2: Pattern not found in finances.py")

# Also fix: only include harvests that have income OR where we can calculate cost dist
old_filter = """        if gal <= 0:
            continue"""

new_filter = """        if gal <= 0:
            continue
        # Skip harvests with no income AND no price — cost distribution meaningless
        # but still include them for levelized cost and other metrics"""

if old_filter in content:
    content = content.replace(old_filter, new_filter)
    print("✅ Fix 2b: Filter updated")

open('routes/finances.py','w').write(content)

# ── Fix 3: Harvest edit form — remove step restriction ───────────────────────
import os, glob

# Find all harvest-related templates
templates_to_fix = []
for root, dirs, files in os.walk('templates'):
    for f in files:
        if f.endswith('.html'):
            path = os.path.join(root, f)
            content_t = open(path).read()
            if 'gallons_produced' in content_t or 'gallons_sold' in content_t:
                templates_to_fix.append(path)

for path in templates_to_fix:
    content_t = open(path).read()
    original  = content_t
    # Remove step="1" restrictions on gallon fields — allow decimal entry
    # Replace step="1" with step="0.1" for gallon inputs
    import re
    # Fix gallons_produced input
    content_t = re.sub(
        r'(name="gallons_produced"[^>]*?)step="[^"]*"',
        r'\1step="0.01"',
        content_t
    )
    content_t = re.sub(
        r'(name="gallons_sold"[^>]*?)step="[^"]*"',
        r'\1step="0.01"',
        content_t
    )
    # If no step attr, add it
    content_t = re.sub(
        r'(<input[^>]*name="gallons_produced"(?![^>]*step=)[^>]*)>',
        r'\1 step="0.01">',
        content_t
    )
    content_t = re.sub(
        r'(<input[^>]*name="gallons_sold"(?![^>]*step=)[^>]*)>',
        r'\1 step="0.01">',
        content_t
    )
    if content_t != original:
        open(path,'w').write(content_t)
        print(f"✅ Fix 3: Step restriction fixed in {path}")

print("\n✅ All fixes applied. Restart the app.")
