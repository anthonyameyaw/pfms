"""Rewrite the broken chart JS in plant/index.html extra_js block."""

content = open('templates/plant/index.html').read()

# Find the extra_js block and replace everything in it
import re

# Find start and end of extra_js block
start = content.find('{% block extra_js %}')
end   = content.find('{% endblock %}', start)

if start == -1 or end == -1:
    print("Could not find extra_js block")
    exit()

before = content[:start]
after  = content[end + len('{% endblock %}'):]

new_js = """{% block extra_js %}
<script>
(function() {
  var data = {{ monthly_chart | tojson }};
  if (!data || !data.length) return;
  var labels = data.map(function(d) { return d.month; });
  var G = '#3fa66b', R = '#c0392b', GOLD = '#d4a843', AM = '#e67e22';

  // Income vs Expenses
  var c1 = document.getElementById('incExpChart');
  if (c1) new Chart(c1, {
    type: 'bar',
    data: { labels: labels, datasets: [
      { label: 'Income',   data: data.map(function(d){return d.income;}),   backgroundColor: G, borderRadius: 4 },
      { label: 'Expenses', data: data.map(function(d){return d.expenses;}), backgroundColor: R, borderRadius: 4 },
    ]},
    options: { responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'top' } },
      scales: { x: { grid: { display: false } }, y: { beginAtZero: true, grid: { color: '#eef4f0' }, ticks: { callback: function(v) { return 'GHS ' + v.toLocaleString(); } } } } }
  });

  // Net profit line
  var c2 = document.getElementById('netChart');
  if (c2) new Chart(c2, {
    type: 'line',
    data: { labels: labels, datasets: [{ label: 'Net', data: data.map(function(d){return d.net;}),
      borderColor: GOLD, backgroundColor: 'rgba(212,168,67,0.1)', fill: true, tension: 0.3,
      pointBackgroundColor: data.map(function(d){return d.net>=0?GOLD:R;}), pointRadius: 4 }]},
    options: { responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { x: { grid: { display: false } }, y: { beginAtZero: false, grid: { color: '#eef4f0' }, ticks: { callback: function(v) { return 'GHS ' + v.toLocaleString(); } } } } }
  });

  // Output gallons
  var c3 = document.getElementById('outputChart');
  if (c3) new Chart(c3, {
    type: 'bar',
    data: { labels: labels, datasets: [
      { label: 'Own Farm (gal)',    data: data.map(function(d){return d.own_gal||0;}),    backgroundColor: G,    borderRadius: 4, stack: 's' },
      { label: 'Outside Farm (gal)',data: data.map(function(d){return d.out_gal||0;}),    backgroundColor: GOLD, borderRadius: 4, stack: 's' },
    ]},
    options: { responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'top' } },
      scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, beginAtZero: true, grid: { color: '#eef4f0' }, ticks: { callback: function(v) { return v + ' gal'; } } } } }
  });

  // Cash collected vs outstanding
  var c4 = document.getElementById('cashChart');
  if (c4) new Chart(c4, {
    type: 'bar',
    data: { labels: labels, datasets: [
      { label: 'Collected',    data: data.map(function(d){return d.cash_collected||0;}),    backgroundColor: G,  borderRadius: 4, stack: 'cash' },
      { label: 'Outstanding',  data: data.map(function(d){return d.cash_outstanding||0;}),  backgroundColor: AM, borderRadius: 4, stack: 'cash' },
    ]},
    options: { responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'top' } },
      scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, beginAtZero: true, grid: { color: '#eef4f0' }, ticks: { callback: function(v) { return 'GHS ' + v.toLocaleString(); } } } } }
  });

  // Revenue breakdown
  var c5 = document.getElementById('revBreakChart');
  if (c5) new Chart(c5, {
    type: 'bar',
    data: { labels: labels, datasets: [
      { label: 'Company Revenue (70%)', data: data.map(function(d){return d.company_revenue||0;}), backgroundColor: G,    borderRadius: 2, stack: 'rev' },
      { label: 'Outside Farmer Fees',   data: data.map(function(d){return d.outside_fees||0;}),   backgroundColor: GOLD, borderRadius: 2, stack: 'rev' },
      { label: 'Electricity',           data: data.map(function(d){return d.electricity||0;}),     backgroundColor: R,    borderRadius: 2, stack: 'rev' },
      { label: 'Operator Pay (30%)',    data: data.map(function(d){return d.operator_pay||0;}),    backgroundColor: AM,   borderRadius: 2, stack: 'rev' },
    ]},
    options: { responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'top' } },
      scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, beginAtZero: true, grid: { color: '#eef4f0' }, ticks: { callback: function(v) { return 'GHS ' + v.toLocaleString(); } } } } }
  });

  // Farm share chart
  var c6 = document.getElementById('farmShareChart');
  if (c6) new Chart(c6, {
    type: 'bar',
    data: { labels: labels, datasets: [
      { label: 'Own Farm %',    data: data.map(function(d){return d.own_farm_pct||0;}),                             backgroundColor: G,    borderRadius: 4, stack: 's' },
      { label: 'Outside Farm %',data: data.map(function(d){return 100-(d.own_farm_pct||0);}), backgroundColor: GOLD, borderRadius: 4, stack: 's' },
    ]},
    options: { responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'top' } },
      scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, beginAtZero: true, max: 100, grid: { color: '#eef4f0' }, ticks: { callback: function(v) { return v + '%'; } } } } }
  });

  // Monthly distribution chart
  var c7 = document.getElementById('monthlyDistChart');
  if (c7) new Chart(c7, {
    type: 'bar',
    data: { labels: labels, datasets: [
      { label: 'Own Farms (gal)',      data: data.map(function(d){return d.own_gal||0;}),  backgroundColor: '#2d6a4f', borderRadius: 4, stack: 'total' },
      { label: 'Outside Farmers (gal)',data: data.map(function(d){return d.out_gal||0;}),  backgroundColor: '#e9c46a', borderRadius: 4, stack: 'total' },
    ]},
    options: { responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: { legend: { position: 'top' } },
      scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, beginAtZero: true, grid: { color: '#eef4f0' }, ticks: { callback: function(v) { return v + ' gal'; } } } } }
  });

})();
</script>
{% endblock %}"""

open('templates/plant/index.html', 'w').write(before + new_js + after)
print("✅ plant/index.html extra_js rewritten cleanly")
