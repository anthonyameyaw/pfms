"""
Add chartjs-plugin-datalabels to base.html.
Sets smart global defaults so all charts show values automatically.
"""

content = open('templates/base.html').read()

# 1. Add datalabels plugin CDN after Chart.js
old_cdn = '<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>'
new_cdn = '''<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js"></script>'''

if old_cdn in content and 'datalabels' not in content:
    content = content.replace(old_cdn, new_cdn)
    print("✅ CDN added")
elif 'datalabels' in content:
    print("— datalabels plugin already present")
else:
    print("⚠ Chart.js CDN pattern not found")

# 2. Replace Chart defaults block to add datalabels registration and config
old_defaults = """  // Chart.js defaults — warm green palette
  Chart.defaults.font.family = "'DM Sans', sans-serif";
  Chart.defaults.font.size   = 12;
  Chart.defaults.color       = '#5a7566';
  Chart.defaults.plugins.tooltip.backgroundColor = '#1a3c2e';
  Chart.defaults.plugins.tooltip.titleColor      = '#e9c46a';
  Chart.defaults.plugins.tooltip.bodyColor       = '#f8faf9';
  Chart.defaults.plugins.tooltip.padding         = 10;
  Chart.defaults.plugins.tooltip.cornerRadius    = 8;
  Chart.defaults.plugins.legend.labels.usePointStyle  = true;
  Chart.defaults.plugins.legend.labels.pointStyleWidth = 10;
  Chart.defaults.plugins.legend.labels.padding   = 16;"""

new_defaults = """  // Chart.js defaults — warm green palette
  Chart.register(ChartDataLabels);

  Chart.defaults.font.family = "'DM Sans', sans-serif";
  Chart.defaults.font.size   = 12;
  Chart.defaults.color       = '#5a7566';
  Chart.defaults.plugins.tooltip.backgroundColor = '#1a3c2e';
  Chart.defaults.plugins.tooltip.titleColor      = '#e9c46a';
  Chart.defaults.plugins.tooltip.bodyColor       = '#f8faf9';
  Chart.defaults.plugins.tooltip.padding         = 10;
  Chart.defaults.plugins.tooltip.cornerRadius    = 8;
  Chart.defaults.plugins.legend.labels.usePointStyle  = true;
  Chart.defaults.plugins.legend.labels.pointStyleWidth = 10;
  Chart.defaults.plugins.legend.labels.padding   = 16;

  // Global datalabels defaults
  Chart.defaults.plugins.datalabels.display = false; // off by default — each chart opts in"""

if old_defaults in content:
    content = content.replace(old_defaults, new_defaults)
    print("✅ Chart defaults updated with datalabels registration")
else:
    print("⚠ Chart defaults pattern not found — trying to append registration")
    # Find Chart.register or Chart.defaults and insert before it
    if 'Chart.defaults.font.family' in content:
        content = content.replace(
            'Chart.defaults.font.family',
            'Chart.register(ChartDataLabels);\n\n  Chart.defaults.font.family',
            1
        )
        print("✅ Registration added before Chart.defaults")

open('templates/base.html', 'w').write(content)
print("base.html updated")

# 3. Now patch each template's charts to opt-in to datalabels
import os, re

def fmt_val(v_js):
    """JS formatter: show GHS prefix for large values, otherwise plain number."""
    return '''function(v) {
            if (v === null || v === undefined || v === 0) return '';
            var n = parseFloat(v);
            if (isNaN(n) || n === 0) return '';
            if (Math.abs(n) >= 1000) return 'GHS ' + (n/1000).toFixed(1)+'k';
            if (Math.abs(n) < 10) return n.toFixed(1);
            return Math.round(n).toString();
          }'''

DL_BAR = """datalabels: {
          display: true,
          anchor: 'end',
          align: 'top',
          formatter: """ + fmt_val('v') + """,
          font: { size: 9, weight: '600', family: "'DM Sans',sans-serif" },
          color: '#1a3c2e',
          clip: false,
        }"""

DL_STACKED = """datalabels: {
          display: function(ctx) {
            // Only show label on the last visible dataset (total on top)
            return ctx.datasetIndex === ctx.chart.data.datasets.length - 1;
          },
          anchor: 'end',
          align: 'top',
          formatter: function(v, ctx) {
            var total = ctx.chart.data.datasets.reduce(function(s, ds) {
              return s + (parseFloat(ds.data[ctx.dataIndex]) || 0);
            }, 0);
            if (!total) return '';
            if (total >= 1000) return (total/1000).toFixed(1)+'k';
            return total % 1 === 0 ? total : total.toFixed(1);
          },
          font: { size: 9, weight: '600', family: "'DM Sans',sans-serif" },
          color: '#1a3c2e',
          clip: false,
        }"""

DL_PIE = """datalabels: {
          display: true,
          formatter: function(v, ctx) {
            var total = ctx.chart.data.datasets[0].data
              .reduce(function(a,b){ return a + (parseFloat(b)||0); }, 0);
            if (!total || !v) return '';
            var pct = (parseFloat(v) / total * 100).toFixed(1);
            return pct + '%\\n' + (parseFloat(v)>=1000 ? 'GHS '+(parseFloat(v)/1000).toFixed(1)+'k' : 'GHS '+Math.round(parseFloat(v)));
          },
          color: '#fff',
          font: { size: 10, weight: '700', family: "'DM Sans',sans-serif" },
          textAlign: 'center',
        }"""

patched_files = []

for root, dirs, files in os.walk('templates'):
    for fname in files:
        if not fname.endswith('.html') or fname == 'base.html':
            continue
        path = os.path.join(root, fname)
        tmpl = open(path).read()
        if 'new Chart(' not in tmpl:
            continue

        original = tmpl

        # Inject datalabels into bar charts (non-stacked)
        def inject_bar(m):
            block = m.group(0)
            if 'datalabels' in block:
                return block
            if 'stacked: true' in block or "stack: '" in block or 'stack:"' in block:
                # stacked — inject stacked datalabels
                return re.sub(
                    r'(plugins\s*:\s*\{)',
                    r'\1\n          ' + DL_STACKED + ',',
                    block, count=1
                )
            # plain bar
            return re.sub(
                r'(plugins\s*:\s*\{)',
                r'\1\n          ' + DL_BAR + ',',
                block, count=1
            )

        def inject_pie(m):
            block = m.group(0)
            if 'datalabels' in block:
                return block
            return re.sub(
                r'(plugins\s*:\s*\{)',
                r'\1\n          ' + DL_PIE + ',',
                block, count=1
            )

        if "'bar'" in tmpl or '"bar"' in tmpl:
            tmpl = re.sub(
                r"(type\s*:\s*['\"]bar['\"].*?)((?=new Chart\()|(?=</script>))",
                inject_bar,
                tmpl, flags=re.DOTALL
            )

        if "'doughnut'" in tmpl or "'pie'" in tmpl:
            tmpl = re.sub(
                r"(type\s*:\s*['\"](?:doughnut|pie)['\"].*?)((?=new Chart\()|(?=</script>))",
                inject_pie,
                tmpl, flags=re.DOTALL
            )

        if tmpl != original:
            open(path, 'w').write(tmpl)
            patched_files.append(path)
            print(f"  Patched: {path}")

print(f"\n✅ Done — {len(patched_files)} chart templates updated")
print("Restart the app to see data labels on all charts.")
