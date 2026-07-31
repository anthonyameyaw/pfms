"""Replace the entire <script> block in base.html with a clean version."""

content = open('templates/base.html').read()

# Find the opening <script> tag before the JS and the closing </script>
# then replace everything between them

import re

# Find the main script block (the one containing Chart.defaults)
# It starts with <script> and ends with </script> before {% block extra_js %}

pattern = r'(<script>)(.*?)(</script>\s*\n\s*\{%\s*block extra_js'
m = re.search(pattern, content, re.DOTALL)
if m:
    print(f"Found main script block ({len(m.group(2))} chars)")
    # Count how many JS blocks we have
    all_scripts = re.findall(r'<script>', content)
    print(f"Total <script> tags: {len(all_scripts)}")
else:
    print("Pattern not found, trying alternate approach")
    # Count script tags
    starts = [m.start() for m in re.finditer(r'<script>', content)]
    ends   = [m.start() for m in re.finditer(r'</script>', content)]
    print(f"Script starts: {starts}")
    print(f"Script ends:   {ends}")

NEW_SCRIPT = """<script>
  // ── Date ────────────────────────────────────────────────────────
  function updateDate() {
    var d = new Date();
    var el = document.getElementById('topbar-date');
    if (el) el.textContent = d.toLocaleDateString('en-GB',
      { weekday:'short', day:'numeric', month:'short', year:'numeric' });
  }
  updateDate();

  // ── Live clock ──────────────────────────────────────────────────
  function tick() {
    var d = new Date();
    var el = document.getElementById('liveClock');
    if (!el) return;
    var h = String(d.getHours()).padStart(2,'0');
    var mn = String(d.getMinutes()).padStart(2,'0');
    var s = String(d.getSeconds()).padStart(2,'0');
    el.textContent = h+':'+mn+':'+s;
  }
  tick();
  setInterval(tick, 1000);

  // ── Confirm deletes ──────────────────────────────────────────────
  document.querySelectorAll('form[data-confirm]').forEach(function(f) {
    f.addEventListener('submit', function(e) {
      if (!confirm(f.dataset.confirm || 'Are you sure?')) e.preventDefault();
    });
  });

  // ── Sidebar collapse ─────────────────────────────────────────────
  var sbToggle = document.getElementById('sbToggle');
  var sbCollapsed = localStorage.getItem('sb') === '1';

  function applySb() {
    document.body.classList.toggle('sb-collapsed', sbCollapsed);
    if (sbToggle) sbToggle.innerHTML = sbCollapsed ? '&#9654;' : '&#9664;';
  }
  applySb();

  if (sbToggle) {
    sbToggle.addEventListener('click', function() {
      sbCollapsed = !sbCollapsed;
      localStorage.setItem('sb', sbCollapsed ? '1' : '0');
      applySb();
    });
  }

  // ── Search ───────────────────────────────────────────────────────
  var PAGES = [
    { label:'Dashboard',          icon:'🏠', url:'{{ url_for("dashboard.index") }}' },
    { label:'All Farms',          icon:'🌿', url:'{{ url_for("farms.index") }}' },
    { label:'Activities',         icon:'📋', url:'{{ url_for("activities.index") }}' },
    { label:'Log Activity',       icon:'➕', url:'{{ url_for("activities.add") }}' },
    { label:'Harvests',           icon:'🌾', url:'{{ url_for("harvests.index") }}' },
    { label:'Pruning',            icon:'✂️', url:'{{ url_for("pruning.index") }}' },
    { label:'Processing Plant',   icon:'🏭', url:'{{ url_for("plant.index") }}' },
    { label:'Log Processing Run', icon:'➕', url:'{{ url_for("plant.add_run") }}' },
    { label:'Transport',          icon:'🚛', url:'{{ url_for("transport.index") }}' },
    { label:'Finances',           icon:'💰', url:'{{ url_for("finances.index") }}' },
    { label:'Storage',            icon:'🛢', url:'{{ url_for("storage.index") }}' },
    { label:'Price Tracker',      icon:'📈', url:'{{ url_for("prices.index") }}' },
    { label:'Labour Intel',       icon:'👷', url:'{{ url_for("labour.index") }}' },
    { label:'Reports & Export',   icon:'📊', url:'{{ url_for("reports.index") }}' },
    { label:'Investors',          icon:'🤝', url:'{{ url_for("investors.index") }}' },
  ];

  var searchInput   = document.getElementById('searchInput');
  var searchResults = document.getElementById('searchResults');
  var activeIdx = -1;

  function showResults(q) {
    if (!searchInput || !searchResults) return;
    var matches = q
      ? PAGES.filter(function(p) { return p.label.toLowerCase().includes(q.toLowerCase()); }).slice(0,7)
      : PAGES.slice(0,7);
    activeIdx = -1;
    if (!matches.length) {
      searchResults.innerHTML = '<div class="search-empty">No results</div>';
    } else {
      searchResults.innerHTML = matches.map(function(p, i) {
        return '<a class="search-result" href="'+p.url+'" data-idx="'+i+'"><span>'+p.icon+'</span><span>'+p.label+'</span></a>';
      }).join('');
    }
    searchResults.classList.add('open');
  }

  if (searchInput) {
    searchInput.addEventListener('focus', function() { showResults(searchInput.value); });
    searchInput.addEventListener('input', function() { showResults(searchInput.value); });
    searchInput.addEventListener('keydown', function(e) {
      var items = searchResults.querySelectorAll('.search-result');
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        activeIdx = Math.min(activeIdx+1, items.length-1);
        items.forEach(function(el,i) { el.classList.toggle('active', i===activeIdx); });
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        activeIdx = Math.max(activeIdx-1, 0);
        items.forEach(function(el,i) { el.classList.toggle('active', i===activeIdx); });
      } else if (e.key === 'Enter' && activeIdx >= 0) {
        items[activeIdx].click();
      } else if (e.key === 'Escape') {
        searchResults.classList.remove('open');
        searchInput.blur();
      }
    });
  }

  document.addEventListener('click', function(e) {
    var wrap = document.querySelector('.search-wrap');
    if (wrap && !wrap.contains(e.target) && searchResults) {
      searchResults.classList.remove('open');
    }
  });

  // ── Keyboard shortcuts ───────────────────────────────────────────
  var SHORTCUTS = {
    'd': ['{{ url_for("dashboard.index") }}', 'Dashboard'],
    'f': ['{{ url_for("farms.index") }}',     'All Farms'],
    'h': ['{{ url_for("harvests.index") }}',  'Harvests'],
    'a': ['{{ url_for("activities.index") }}','Activities'],
    'p': ['{{ url_for("plant.index") }}',     'Processing Plant'],
    't': ['{{ url_for("transport.index") }}', 'Transport'],
    'i': ['{{ url_for("finances.index") }}',  'Finances'],
    'r': ['{{ url_for("reports.index") }}',   'Reports'],
    's': ['{{ url_for("storage.index") }}',   'Storage'],
  };

  var toast = document.createElement('div');
  toast.className = 'kbd-toast';
  document.body.appendChild(toast);
  var toastTimer;

  function showToast(msg) {
    toast.textContent = msg;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function() { toast.classList.remove('show'); }, 1400);
  }

  document.addEventListener('keydown', function(e) {
    if (['INPUT','SELECT','TEXTAREA'].includes(e.target.tagName)) return;
    if (e.ctrlKey && e.key === 'k') {
      e.preventDefault();
      if (searchInput) { searchInput.focus(); showResults(''); }
      return;
    }
    if (e.ctrlKey && e.key === 'b') {
      e.preventDefault();
      if (sbToggle) sbToggle.click();
      return;
    }
    if (e.ctrlKey || e.metaKey || e.altKey) return;

    if (e.key === '?') {
      var rows = Object.entries(SHORTCUTS).map(function(kv) {
        return '<div style="display:flex;justify-content:space-between;padding:5px 0;font-size:0.84rem;"><span>'+kv[1][1]+'</span><kbd style="background:var(--surface);border:1px solid var(--border);padding:2px 8px;border-radius:4px;font-size:0.75rem;">'+kv[0].toUpperCase()+'</kbd></div>';
      }).join('');
      var ov = document.createElement('div');
      ov.style.cssText = 'position:fixed;inset:0;background:rgba(26,60,46,0.55);z-index:1000;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(4px);';
      ov.innerHTML = '<div style="background:white;border-radius:18px;padding:30px 34px;max-width:360px;width:90%;box-shadow:0 24px 80px rgba(0,0,0,0.2);"><div style="font-family:\'Cormorant Garamond\',serif;font-size:1.5rem;font-weight:600;color:var(--green-dark);margin-bottom:18px;">⌨ Keyboard Shortcuts</div>'+rows+'<div style="margin-top:14px;padding-top:14px;border-top:1px solid var(--border);font-size:0.76rem;color:var(--ink-soft);"><b>Ctrl+K</b> — Search &nbsp;·&nbsp; <b>Ctrl+B</b> — Toggle sidebar</div><button onclick="this.closest(\'div[style]\').remove()" style="margin-top:16px;width:100%;padding:9px;background:var(--green-mid);color:white;border:none;border-radius:var(--r-sm);cursor:pointer;font-family:\'DM Sans\',sans-serif;font-size:0.85rem;font-weight:500;">Close</button></div>';
      document.body.appendChild(ov);
      ov.addEventListener('click', function(e) { if (e.target===ov) ov.remove(); });
      return;
    }

    var sc = SHORTCUTS[e.key.toLowerCase()];
    if (sc) {
      showToast('→ ' + sc[1]);
      setTimeout(function() { window.location.href = sc[0]; }, 350);
    }
  });

  // ── Mobile sidebar ───────────────────────────────────────────────
  function isMobile() { return window.innerWidth <= 768; }

  function applyMobileUI() {
    var mobile = isMobile();
    var menuBtn   = document.getElementById('mobileMenuBtn');
    var bottomNav = document.getElementById('mobileBottomNav');
    if (menuBtn)   menuBtn.style.display   = mobile ? 'flex' : 'none';
    if (bottomNav) bottomNav.style.display = mobile ? 'flex' : 'none';
    if (sbToggle)  sbToggle.style.display  = mobile ? 'none' : 'flex';
  }
  applyMobileUI();
  window.addEventListener('resize', applyMobileUI);

  function toggleMobileSidebar() {
    var sidebar  = document.getElementById('mainSidebar');
    var overlay  = document.getElementById('sidebarOverlay');
    if (!sidebar) return;
    var isOpen = sidebar.classList.contains('mobile-open');
    sidebar.classList.toggle('mobile-open', !isOpen);
    if (overlay) overlay.classList.toggle('show', !isOpen);
  }

  var sidebarOverlay = document.getElementById('sidebarOverlay');
  if (sidebarOverlay) {
    sidebarOverlay.addEventListener('click', function() {
      var sidebar = document.getElementById('mainSidebar');
      if (sidebar) sidebar.classList.remove('mobile-open');
      sidebarOverlay.classList.remove('show');
    });
  }

  // ── Chart.js defaults ────────────────────────────────────────────
  if (typeof Chart !== 'undefined') {
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
  }
</script>"""

# Replace ALL <script>...</script> blocks before {% block extra_js %}
# by finding the first <script> after </aside> and everything up to before {% block extra_js %}

# Find the start of the main JS block
js_start = content.find('<script>', content.find('</body>') - 15000)
# Find just before {% block extra_js %}
js_end = content.find('{% block extra_js %}')

if js_start > 0 and js_end > js_start:
    before = content[:js_start]
    after  = content[js_end:]
    new_content = before + NEW_SCRIPT + '\n\n' + after
    open('templates/base.html', 'w').write(new_content)
    print(f"✅ Script block replaced ({js_end - js_start} chars → {len(NEW_SCRIPT)} chars)")
    print(f"Total lines now: {len(new_content.split(chr(10)))}")
else:
    print(f"⚠ Could not find boundaries: js_start={js_start}, js_end={js_end}")
