"""Fix incorrect number of SQL bindings in _get_farm_pl."""

content = open('routes/reports.py').read()

old = """def _get_farm_pl(date_from='', date_to=''):
    dc, dp = _df(date_from, date_to)
    farms = query(f\"\"\"
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
    \"\"\", dp * 4)"""

new = """def _get_farm_pl(date_from='', date_to=''):
    dc, dp = _df(date_from, date_to)
    farms = query(f\"\"\"
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
    \"\"\", dp * 6)"""

if old in content:
    content = content.replace(old, new)
    open('routes/reports.py', 'w').write(content)
    print("✅ Fixed: dp * 4 → dp * 6 (6 subqueries each needing date params)")
else:
    # Try to find and fix automatically
    import re
    content = re.sub(r'dp \* \d+\)', lambda m: 'dp * 6)', content)
    open('routes/reports.py', 'w').write(content)
    print("✅ Fixed via regex: corrected dp multiplier to 6")
