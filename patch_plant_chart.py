"""Adds monthly own vs outside farm distribution bar chart to plant/index.html"""

content = open('templates/plant/index.html').read()

# ── Step 1: Add chart canvas card ────────────────────────────────────────────
# Insert a new card right before <!-- MoM Snapshot --> section
CARD = """
<!-- Monthly Distribution Chart -->
<div class="card">
  <div class="card-title">📅 Monthly Processing Distribution — Own Farms vs Outside Farmers</div>
  <p class="small muted mb-2">Stacked bars show gallons from each source per month. Tooltip shows % split.</p>
  {% if monthly_chart %}
  <div class="chart-container" style="height:240px;"><canvas id="monthlyDistChart"></canvas></div>
  <div class="flex gap-3 mt-2 small muted items-center">
    <div style="width:12px;height:12px;border-radius:2px;background:#2d6a4f;flex-shrink:0;"></div><span>Own Farms</span>
    <div style="width:12px;height:12px;border-radius:2px;background:#e9c46a;flex-shrink:0;"></div><span>Outside Farmers</span>
  </div>
  {% else %}
  <p class="muted" style="text-align:center;padding:40px 0;">No processing runs logged yet.</p>
  {% endif %}
</div>

"""

# Find a good insertion point — after the farm contribution card, before MoM
if '<!-- MoM Snapshot -->' in content:
    content = content.replace('<!-- MoM Snapshot -->', CARD + '<!-- MoM Snapshot -->')
    print("Card inserted before MoM Snapshot")
elif 'own_farm_pct' in content:
    # Insert after the closing </div> of the farm share card
    idx = content.find('own_farm_pct')
    # Find next card closing after this
    close = content.find('</div>\n\n', idx)
    if close > 0:
        content = content[:close+8] + CARD + content[close+8:]
        print("Card inserted after farm share section")
    else:
        print("Could not find insertion point — appending at end of content block")
        content = content.replace('{% endblock %}\n\n{% block extra_js %}',
                                   CARD + '{% endblock %}\n\n{% block extra_js %}')
else:
    # Safest fallback: add before {% endblock %} of content
    content = content.replace('\n{% endblock %}\n\n{% block extra_js %}',
                              '\n' + CARD + '\n{% endblock %}\n\n{% block extra_js %}', 1)
    print("Card added via fallback")

# ── Step 2: Add chart JS ─────────────────────────────────────────────────────
CHART_JS = """
{% if monthly_chart %}
// Monthly own vs outside distribution stacked bar
(function() {
  const md = {{ monthly_chart | tojson }};
  const ctx = document.getElementById('monthlyDistChart');
  if (!ctx) return;
  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: md.map(d => d.month),
      datasets: [
        {
          label: 'Own Farms (gal)',
          data: md.map(d => parseFloat(d.own_gal) || 0),
          backgroundColor: '#2d6a4f',
          borderRadius: 4,
          stack: 'total',
        },
        {
          label: 'Outside Farmers (gal)',
          data: md.map(d => parseFloat(d.out_gal) || 0),
          backgroundColor: '#e9c46a',
          borderRadius: 4,
          stack: 'total',
        },
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'top' },
        tooltip: {
          callbacks: {
            afterBody: function(items) {
              const own = items.find(i => i.dataset.label.includes('Own'));
              const out = items.find(i => i.dataset.label.includes('Outside'));
              if (own && out) {
                const total = (own.parsed.y||0) + (out.parsed.y||0);
                if (total > 0) {
                  return [
                    'Own: ' + ((own.parsed.y/total)*100).toFixed(1) + '%',
                    'Outside: ' + ((out.parsed.y/total)*100).toFixed(1) + '%',
                    'Total: ' + total.toFixed(1) + ' gal'
                  ];
                }
              }
              return [];
            }
          }
        }
      },
      scales: {
        x: { stacked: true, grid: { display: false } },
        y: {
          stacked: true,
          beginAtZero: true,
          grid: { color: '#eef4f0' },
          ticks: { callback: function(v) { return v + ' gal'; } }
        }
      }
    }
  });
})();
{% endif %}
"""

# Insert JS at the start of the extra_js block
if '{% block extra_js %}' in content:
    content = content.replace('{% block extra_js %}\n', '{% block extra_js %}\n<script>\n' + CHART_JS + '\n</script>\n', 1)
    # But if there's already a <script> tag right after, merge them
    content = content.replace('</script>\n<script>\n', '\n', 1)
    print("JS added to extra_js block")
elif '</script>' in content:
    # Append before last </script>
    last_script = content.rfind('</script>')
    content = content[:last_script] + CHART_JS + '\n' + content[last_script:]
    print("JS inserted before closing script tag")

open('templates/plant/index.html', 'w').write(content)
print("\n✅ Monthly distribution chart added to Processing Plant page")
