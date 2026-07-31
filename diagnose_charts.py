"""Check what's wrong with charts."""
import os, re

issues = []

# Check base.html
base = open('templates/base.html').read()

if 'datalabels' in base.lower():
    issues.append("base.html still has datalabels references")
    for i, line in enumerate(base.split('\n'), 1):
        if 'datalabels' in line.lower():
            print(f"  base.html line {i}: {line.strip()}")

if 'chart.umd.min.js' not in base:
    issues.append("Chart.js CDN missing from base.html!")
else:
    print("✅ Chart.js CDN present")

if 'Chart.defaults' not in base:
    issues.append("Chart.defaults block missing!")
else:
    print("✅ Chart.defaults block present")

# Check all templates for datalabels or syntax errors
for root, dirs, files in os.walk('templates'):
    for fname in files:
        if not fname.endswith('.html'):
            continue
        path = os.path.join(root, fname)
        tmpl = open(path).read()
        if 'datalabels' in tmpl.lower():
            issues.append(f"{path} still has datalabels")
            for i, line in enumerate(tmpl.split('\n'), 1):
                if 'datalabels' in line.lower():
                    print(f"  {path} line {i}: {line.strip()[:80]}")

# Check dashboard.html specifically
dash = 'templates/dashboard.html'
if os.path.exists(dash):
    d = open(dash).read()
    charts = re.findall(r"new Chart\(", d)
    print(f"\n✅ dashboard.html: {len(charts)} chart(s) found")
    if 'datalabels' in d:
        issues.append("dashboard.html has datalabels!")
else:
    issues.append("templates/dashboard.html NOT FOUND!")

if not issues:
    print("\n✅ No datalabels traces found anywhere")
    print("The charts being blank may be a data issue, not a code issue.")
    print("Check if the app has data — open http://127.0.0.1:5001 and look at the browser console (F12) for JS errors.")
else:
    print(f"\n⚠ Issues found: {len(issues)}")
    for i in issues:
        print(f"  - {i}")
