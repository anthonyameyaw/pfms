"""Patches base.html to add PWA support. Run once."""
import re

content = open('templates/base.html').read()

# 1. Add PWA meta tags and manifest link to <head>
old_head = "  <script src=\"https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js\"></script>"
new_head = """  <!-- PWA -->
  <link rel="manifest" href="/static/manifest.json">
  <meta name="theme-color" content="#1a3c2e">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="PFMS">
  <link rel="apple-touch-icon" href="/static/icons/icon-192.png">
  <link rel="apple-touch-icon" sizes="152x152" href="/static/icons/icon-152.png">
  <link rel="apple-touch-icon" sizes="144x144" href="/static/icons/icon-144.png">
  <link rel="apple-touch-icon" sizes="128x128" href="/static/icons/icon-128.png">

  <!-- Mobile CSS -->
  <link rel="stylesheet" href="/static/mobile.css">

  <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>"""

content = content.replace(old_head, new_head)

# 2. Add hamburger button and overlay before the sidebar
old_sidebar = '<aside class="sidebar">'
new_sidebar = """<div class="sidebar-overlay" id="sidebarOverlay"></div>
<button class="mobile-menu-btn" id="mobileMenuBtn" onclick="toggleMobileSidebar()" style="display:none;">☰</button>

<aside class="sidebar" id="mainSidebar">"""
content = content.replace(old_sidebar, new_sidebar)

# 3. Add mobile bottom nav and FAB before closing </div> of main
old_main_end = "</div>\n\n<script>"
new_main_end = """  <!-- Mobile bottom nav -->
  <nav class="mobile-bottom-nav" id="mobileBottomNav" style="display:none;">
    <a href="/" class="mobile-nav-item {% if request.endpoint == 'dashboard.index' %}active{% endif %}">
      <span class="nav-icon">🏠</span><span>Home</span>
    </a>
    <a href="/farms/" class="mobile-nav-item {% if request.endpoint and 'farms.' in request.endpoint %}active{% endif %}">
      <span class="nav-icon">🌿</span><span>Farms</span>
    </a>
    <a href="/activities/add" class="mobile-nav-item">
      <span class="nav-icon" style="font-size:1.8rem;color:var(--green-mid);">＋</span><span>Log</span>
    </a>
    <a href="/plant/" class="mobile-nav-item {% if request.endpoint and 'plant.' in request.endpoint %}active{% endif %}">
      <span class="nav-icon">🏭</span><span>Plant</span>
    </a>
    <a href="/finances/" class="mobile-nav-item {% if request.endpoint and 'finances.' in request.endpoint %}active{% endif %}">
      <span class="nav-icon">💰</span><span>Finance</span>
    </a>
  </nav>
</div>

<script>"""
content = content.replace(old_main_end, new_main_end)

# 4. Add mobile JS before closing </script>
old_script_end = "  // Chart.js defaults — warm green palette"
new_script_end = """  // ── PWA Service Worker ─────────────────────────────
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/static/sw.js')
        .then(r => console.log('SW registered'))
        .catch(e => console.log('SW error', e));
    });
  }

  // ── Mobile detection ────────────────────────────────
  function isMobile() { return window.innerWidth <= 768; }

  function applyMobileUI() {
    const mobile = isMobile();
    const menuBtn   = document.getElementById('mobileMenuBtn');
    const bottomNav = document.getElementById('mobileBottomNav');
    const sbToggle  = document.getElementById('sbToggle');
    if (menuBtn)   menuBtn.style.display   = mobile ? 'flex' : 'none';
    if (bottomNav) bottomNav.style.display = mobile ? 'flex' : 'none';
    if (sbToggle)  sbToggle.style.display  = mobile ? 'none' : 'flex';
  }
  applyMobileUI();
  window.addEventListener('resize', applyMobileUI);

  // ── Mobile sidebar toggle ───────────────────────────
  function toggleMobileSidebar() {
    const sidebar  = document.getElementById('mainSidebar');
    const overlay  = document.getElementById('sidebarOverlay');
    const isOpen   = sidebar.classList.contains('mobile-open');
    sidebar.classList.toggle('mobile-open', !isOpen);
    overlay.classList.toggle('show', !isOpen);
  }
  document.getElementById('sidebarOverlay').addEventListener('click', () => {
    document.getElementById('mainSidebar').classList.remove('mobile-open');
    document.getElementById('sidebarOverlay').classList.remove('show');
  });

  // ── Chart.js defaults — warm green palette"""

content = content.replace(old_script_end, new_script_end)

# 5. Add offline route reference (topbar hamburger icon for mobile)
old_topbar_h2 = '<div style="display:flex;align-items:center;gap:12px;">'
new_topbar_h2 = '<div style="display:flex;align-items:center;gap:4px;">\n      <button class="mobile-menu-btn" onclick="toggleMobileSidebar()" style="display:none;" id="mobileMenuBtn2">☰</button>'
content = content.replace(old_topbar_h2, new_topbar_h2, 1)

open('templates/base.html','w').write(content)
print("✅ base.html patched with PWA support")
