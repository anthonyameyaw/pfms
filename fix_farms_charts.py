"""Rewrite broken chart JS in farms/detail.html extra_js block."""

content = open('templates/farms/detail.html').read()
import re

start = content.find('{% block extra_js %}')
end   = content.find('{% endblock %}', start)

if start == -1 or end == -1:
    print("Could not find extra_js block — checking for script block")
    # Try to find any script in extra_js
    print("Last 500 chars of file:")
    print(repr(content[-500:]))
    exit()

before = content[:start]
after  = content[end + len('{% endblock %}'):]

new_js = """{% block extra_js %}
<script>
(function() {
  var mc = {{ monthly_trend | tojson }};
  var c1 = document.getElementById('monthlyChart');
  if (c1 && mc && mc.length) {
    new Chart(c1, {
      type: 'bar',
      data: { labels: mc.map(function(d){return d.month;}), datasets: [
        { label:'Income',   data:mc.map(function(d){return d.income;}),   backgroundColor:'#52b78866', borderColor:'#52b788', borderWidth:1.5, borderRadius:4 },
        { label:'Expenses', data:mc.map(function(d){return d.expenses;}), backgroundColor:'#e6394666', borderColor:'#e63946', borderWidth:1.5, borderRadius:4 },
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

  var hc = document.getElementById('harvestChart');
  var mh = {{ monthly_harvest | tojson }};
  if (hc && mh && mh.length) {
    new Chart(hc, {
      type:'bar',
      data:{ labels:mh.map(function(d){return d.month;}), datasets:[
        { label:'Bunches', data:mh.map(function(d){return d.bunches;}), backgroundColor:'#2d6a4f', borderRadius:4 }
      ]},
      options:{ responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false}},
        scales:{ x:{grid:{display:false}}, y:{beginAtZero:true, grid:{color:'#eef4f0'}} } }
    });
  }
})();
</script>
{% endblock %}"""

open('templates/farms/detail.html', 'w').write(before + new_js + after)
print("✅ farms/detail.html extra_js rewritten cleanly")
