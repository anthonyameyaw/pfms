"""Fix farms.py to correctly calculate gallons_in_storage per farm from harvests."""

content = open('routes/farms.py').read()
original = content

# The correct calculation for per-farm storage:
correct_calc = """    # Gallons in storage = produced - sold (derived from harvests, not storage table)
    storage_row = query(\"\"\"
        SELECT COALESCE(SUM(gallons_produced),0) AS produced,
               COALESCE(SUM(gallons_sold),0)     AS sold
        FROM harvests WHERE farm_id=? AND gallons_produced>0
    \"\"\", (farm_id,), one=True)
    gallons_in_storage = float(storage_row['produced'] or 0) - float(storage_row['sold'] or 0)
    gallons_produced_total = float(storage_row['produced'] or 0)
    gallons_sold_total     = float(storage_row['sold'] or 0)"""

# Find and replace the old storage calculation
import re

# Pattern A: direct query to storage_transactions
replaced = False
old_a = re.search(
    r"gallons_in_storage\s*=\s*query\(['\"]SELECT[^;]+?farm_id[^;]+?['\"][^)]*\)[^'\"]*\['[^'\"]+'\]",
    content, re.DOTALL
)
if old_a:
    content = content[:old_a.start()] + "    gallons_in_storage = float(query(\"SELECT COALESCE(SUM(gallons_produced),0)-COALESCE(SUM(gallons_sold),0) AS v FROM harvests WHERE farm_id=? AND gallons_produced>0\", (farm_id,), one=True)['v'] or 0)" + content[old_a.end():]
    replaced = True
    print("✅ Pattern A replaced")

# Pattern B: gallons_in_storage = 0 (hardcoded)
if not replaced:
    old_b = "    gallons_in_storage = 0"
    if old_b in content:
        content = content.replace(old_b,
            "    gallons_in_storage = float(query(\"SELECT COALESCE(SUM(gallons_produced),0)-COALESCE(SUM(gallons_sold),0) AS v FROM harvests WHERE farm_id=? AND gallons_produced>0\", (farm_id,), one=True)['v'] or 0)",
            1)
        replaced = True
        print("✅ Pattern B replaced (was hardcoded 0)")

# Pattern C: look for any storage-related line in detail and replace
if not replaced:
    lines = content.split('\n')
    new_lines = []
    in_detail = False
    replaced_in_detail = False
    for i, line in enumerate(lines):
        if 'def detail(farm_id' in line:
            in_detail = True
        if in_detail and 'gallons_in_storage' in line and not replaced_in_detail:
            # Replace this line with correct calculation
            indent = len(line) - len(line.lstrip())
            sp = ' ' * indent
            new_lines.append(f"{sp}gallons_in_storage = float(query(\"SELECT COALESCE(SUM(gallons_produced),0)-COALESCE(SUM(gallons_sold),0) AS v FROM harvests WHERE farm_id=? AND gallons_produced>0\", (farm_id,), one=True)['v'] or 0)")
            replaced_in_detail = True
            replaced = True
            print(f"✅ Pattern C replaced at line {i+1}: {line.strip()}")
            continue
        new_lines.append(line)
    if replaced:
        content = '\n'.join(new_lines)

if not replaced:
    # Last resort: add the calculation before render_template in detail route
    old_render = "    return render_template('farms/detail.html',"
    if old_render in content:
        content = content.replace(old_render,
            "    gallons_in_storage = float(query(\"SELECT COALESCE(SUM(gallons_produced),0)-COALESCE(SUM(gallons_sold),0) AS v FROM harvests WHERE farm_id=? AND gallons_produced>0\", (farm_id,), one=True)['v'] or 0)\n" + old_render,
            1)
        replaced = True
        print("✅ Last resort: added before render_template")

if replaced:
    open('routes/farms.py','w').write(content)
    print("✅ farms.py updated — per-farm storage now reads from harvests")
else:
    print("⚠ Could not find storage pattern. Showing all storage-related lines:")
    for i, line in enumerate(content.split('\n'), 1):
        if 'storage' in line.lower():
            print(f"  {i}: {line}")
