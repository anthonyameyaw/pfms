"""Rewrite the broken chart JS in finances/index.html extra_js block."""

content = open('templates/finances/index.html').read()
import re

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
  // Monthly income/expenses chart
  var mc = {{ monthly_chart | tojson }};
  var c1 = document.getElementById('monthlyChart');
  if (c1 && mc && mc.length) {
    new Chart(c1, {
      type: 'bar',
      data: { labels: mc.map(function(d){return d.month;}), datasets: [
        { label:'Income',   data:mc.map(function(d){return d.income;}),   backgroundColor:'#52b788', borderRadius:4 },
        { label:'Expenses', data:mc.map(function(d){return d.expenses;}), backgroundColor:'#e63946', borderRadius:4 },
        { label:'Net', data:mc.map(function(d){return d.net;}), type:'line',
          borderColor:'#e9c46a', backgroundColor:'rgba(233,196,106,0.08)',
          fill:true, tension:0.35, pointRadius:3, borderWidth:2 },
      ]},
      options: { responsive:true, maintainAspectRatio:false,
        interaction:{mode:'index',intersect:false},
        plugins:{legend:{position:'top'}},
        scales:{ x:{grid:{display:false}}, y:{beginAtZero:true, grid:{color:'#eef4f0'},
          ticks:{callback:function(v){return 'GHS '+(v>=1000?(v/1000).toFixed(0)+'k':v);}}} } }
    });
  }

  // Harvest analytics charts
  var ha = {{ harvest_analytics | tojson }};
  if (!ha || !ha.length) return;

  var labels = ha.map(function(d) { return d.date + ' · ' + d.farm.replace('Palm Farm ',''); });

  // Cost distribution
  var c2 = document.getElementById('costDistChart');
  var haIncome = ha.filter(function(d){return d.income > 0;});
  var labelsIncome = haIncome.map(function(d){return d.date+' · '+d.farm.replace('Palm Farm ','');});
  if (c2 && haIncome.length) {
    new Chart(c2, {
      type:'bar',
      data:{ labels:labelsIncome, datasets:[
        { label:'Labour %',    data:haIncome.map(function(d){return d.lab_pct;}),   backgroundColor:'#2d6a4f', stack:'s', borderRadius:2 },
        { label:'Transport %', data:haIncome.map(function(d){return d.trans_pct;}), backgroundColor:'#f4a261', stack:'s', borderRadius:2 },
        { label:'Net Margin %',data:haIncome.map(function(d){return d.net_pct;}),   backgroundColor:'#e9c46a', stack:'s', borderRadius:2 },
      ]},
      options:{ responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false}},
        scales:{ x:{stacked:true,grid:{display:false},ticks:{maxRotation:45,font:{size:10}}},
          y:{stacked:true,beginAtZero:true,max:100,ticks:{callback:function(v){return v+'%';}},grid:{color:'#eef4f0'}} } }
    });
  }

  // Husks per gallon
  var c3 = document.getElementById('husksPerGalChart');
  if (c3) new Chart(c3, {
    type:'bar',
    data:{ labels:labels, datasets:[{ label:'Husks/Gallon',
      data:ha.map(function(d){return d.husks_per_gal;}),
      backgroundColor:ha.map(function(d){return d.husks_per_gal<=8?'#52b788':d.husks_per_gal<=15?'#f4a261':'#e63946';}),
      borderRadius:4 }]},
    options:{ responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false}},
      scales:{ x:{grid:{display:false},ticks:{maxRotation:45,font:{size:10}}},
        y:{beginAtZero:true,grid:{color:'#eef4f0'},ticks:{callback:function(v){return v+' hks/gal';}}} } }
  });

  // Levelized cost
  var c4 = document.getElementById('levelizedChart');
  if (c4) new Chart(c4, {
    type:'bar',
    data:{ labels:labels, datasets:[{ label:'Levelized Cost (GHS/gal)',
      data:ha.map(function(d){return d.levelized;}),
      backgroundColor:ha.map(function(d){return d.levelized<=20?'#52b788':d.levelized<=35?'#f4a261':'#e63946';}),
      borderRadius:4 }]},
    options:{ responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false}},
      scales:{ x:{grid:{display:false},ticks:{maxRotation:45,font:{size:10}}},
        y:{beginAtZero:true,grid:{color:'#eef4f0'},ticks:{callback:function(v){return 'GHS '+v;}}} } }
  });

  // Gross margin per gallon
  var haPrice = ha.filter(function(d){return d.price>0;});
  var labelsPrice = haPrice.map(function(d){return d.date+' · '+d.farm.replace('Palm Farm ','');});
  var c5 = document.getElementById('marginChart');
  if (c5 && haPrice.length) new Chart(c5, {
    type:'bar',
    data:{ labels:labelsPrice, datasets:[{ label:'Margin/Gallon (GHS)',
      data:haPrice.map(function(d){return d.margin_per_gal;}),
      backgroundColor:haPrice.map(function(d){return d.margin_per_gal>=20?'#52b788':d.margin_per_gal>=5?'#e9c46a':'#e63946';}),
      borderRadius:4 }]},
    options:{ responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false}},
      scales:{ x:{grid:{display:false},ticks:{maxRotation:45,font:{size:10}}},
        y:{beginAtZero:true,grid:{color:'#eef4f0'},ticks:{callback:function(v){return 'GHS '+v;}}} } }
  });

  // Cost stack
  var c6 = document.getElementById('costStackChart');
  if (c6) new Chart(c6, {
    type:'bar',
    data:{ labels:labels, datasets:[
      { label:'Harvest Labour', data:ha.map(function(d){return d.harv_cost;}),   backgroundColor:'#2d6a4f', stack:'s', borderRadius:2 },
      { label:'Threshing',      data:ha.map(function(d){return d.thresh_cost;}), backgroundColor:'#52b788', stack:'s', borderRadius:2 },
      { label:'Transport',      data:ha.map(function(d){return d.trans_cost;}),  backgroundColor:'#f4a261', stack:'s', borderRadius:2 },
    ]},
    options:{ responsive:true, maintainAspectRatio:false,
      interaction:{mode:'index',intersect:false},
      plugins:{legend:{position:'top'}},
      scales:{ x:{stacked:true,grid:{display:false},ticks:{maxRotation:45,font:{size:10}}},
        y:{stacked:true,beginAtZero:true,grid:{color:'#eef4f0'},ticks:{callback:function(v){return 'GHS '+v;}}} } }
  });

  // Labour ROI
  var c7 = document.getElementById('labourRoiChart');
  if (c7) new Chart(c7, {
    type:'bar',
    data:{ labels:labels, datasets:[{ label:'Income per GHS Labour',
      data:ha.map(function(d){return d.labour_roi;}),
      backgroundColor:ha.map(function(d){return d.labour_roi>=3?'#52b788':d.labour_roi>=1.5?'#e9c46a':'#e63946';}),
      borderRadius:4 }]},
    options:{ responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false}},
      scales:{ x:{grid:{display:false},ticks:{maxRotation:45,font:{size:10}}},
        y:{beginAtZero:true,grid:{color:'#eef4f0'},ticks:{callback:function(v){return v+'x';}}} } }
  });

})();
</script>
{% endblock %}"""

open('templates/finances/index.html', 'w').write(before + new_js + after)
print("✅ finances/index.html extra_js rewritten cleanly")
