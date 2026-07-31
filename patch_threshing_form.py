"""Adds threshing_cost field to harvest activity form and route."""
import re

# ── 1. activities route — save threshing_cost when logging harvest ────────────
content = open('routes/activities.py').read()

# Find where harvesting_cost is saved and add threshing_cost next to it
if 'threshing_cost' not in content:
    old = "harvesting_cost = harvester_pay + collector_pay"
    new = """threshing_cost  = float(request.form.get('threshing_cost') or 0)
        harvesting_cost = harvester_pay + collector_pay"""
    if old in content:
        content = content.replace(old, new)
        print("✅ threshing_cost variable added")

    # Save to DB
    old2 = "threshing_cost=0,"
    new2 = "threshing_cost=threshing_cost,"
    if old2 in content:
        content = content.replace(old2, new2)
        print("✅ threshing_cost saved to DB")
    else:
        # Try to find the INSERT for harvests and add the field
        old3 = "harvesting_cost=harvesting_cost,"
        new3 = "harvesting_cost=harvesting_cost,\n                threshing_cost=threshing_cost,"
        if old3 in content:
            content = content.replace(old3, new3)
            print("✅ threshing_cost added to INSERT")

    open('routes/activities.py','w').write(content)
else:
    print("— threshing_cost already in activities.py")

# ── 2. Add threshing cost field to the harvest activity form ──────────────────
# Find the harvest step in the activities add template
for tmpl_path in ['templates/activities/add.html', 'templates/activities/index.html']:
    try:
        tmpl = open(tmpl_path).read()
        if 'threshing' not in tmpl and 'Harvesting' in tmpl:
            # Add after collector_pay field
            old_t = """<div class="form-group">
          <label>Collector Pay (GHS)</label>
          <input type="number" step="0.01" name="collector_pay" placeholder="e.g. 150">
        </div>"""
            new_t = """<div class="form-group">
          <label>Collector Pay (GHS)</label>
          <input type="number" step="0.01" name="collector_pay" placeholder="e.g. 150">
        </div>
        <div class="form-group">
          <label>Threshing Labour Cost (GHS) <span class="muted small">— separating fruits from husks</span></label>
          <input type="number" step="0.01" name="threshing_cost" placeholder="e.g. 80">
        </div>"""
            if old_t in tmpl:
                tmpl = tmpl.replace(old_t, new_t)
                open(tmpl_path,'w').write(tmpl)
                print(f"✅ Threshing field added to {tmpl_path}")
            else:
                print(f"— Collector pay pattern not found in {tmpl_path}")
    except FileNotFoundError:
        pass

print("\nDone. Run migrate_threshing.py first if not already done.")
