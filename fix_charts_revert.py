"""Revert datalabels plugin changes that broke all charts."""

content = open('templates/base.html').read()

# 1. Remove datalabels CDN
content = content.replace(
    '\n  <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js"></script>',
    ''
)

# 2. Remove Chart.register(ChartDataLabels)
content = content.replace(
    '  Chart.register(ChartDataLabels);\n\n  ', '  '
)
content = content.replace(
    'Chart.register(ChartDataLabels);\n\n  Chart.defaults.font.family',
    'Chart.defaults.font.family'
)
content = content.replace(
    '\n  // Global datalabels defaults\n  Chart.defaults.plugins.datalabels.display = false; // off by default — each chart opts in',
    ''
)

open('templates/base.html', 'w').write(content)
print("✅ base.html reverted")

# 3. Remove datalabels injected into all templates
import os, re

removed = 0
for root, dirs, files in os.walk('templates'):
    for fname in files:
        if not fname.endswith('.html'):
            continue
        path = os.path.join(root, fname)
        tmpl = open(path).read()
        if 'datalabels' not in tmpl:
            continue
        # Remove all datalabels blocks
        clean = re.sub(r'\s*datalabels\s*:\s*\{[^}]*(?:\{[^}]*\}[^}]*)?\},?\s*', '\n          ', tmpl)
        if clean != tmpl:
            open(path, 'w').write(clean)
            removed += 1
            print(f"  Cleaned: {path}")

print(f"✅ Removed datalabels from {removed} templates")
print("Restart the app — charts will be back to normal.")
