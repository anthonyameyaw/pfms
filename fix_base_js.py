"""Fix JS errors in base.html: null reference, duplicate declarations, syntax error."""
import re

content = open('templates/base.html').read()
original = content

# ── Fix 1: applySb references element that may be null ──────────────────────
# The sbToggle or mobileMenuBtn may not exist on all pages
old_applySb = """function applySb() {
    document.body.classList.toggle('sb-collapsed', sbCollapsed);
    sbToggle.innerHTML = sbCollapsed ? '&#9654;' : '&#9664;';
  }"""

new_applySb = """function applySb() {
    document.body.classList.toggle('sb-collapsed', sbCollapsed);
    if (sbToggle) sbToggle.innerHTML = sbCollapsed ? '&#9654;' : '&#9664;';
  }"""

if old_applySb in content:
    content = content.replace(old_applySb, new_applySb)
    print("✅ Fix 1: applySb null guard added")
else:
    # Try broader pattern
    content = re.sub(
        r'(sbToggle\.innerHTML\s*=)',
        r'if (sbToggle) sbToggle.innerHTML =; //patched\n    if (sbToggle) sbToggle.innerHTML =',
        content
    )
    # More targeted fix
    content = re.sub(
        r'(\bsbToggle\b\.innerHTML)',
        r'(sbToggle && sbToggle.innerHTML)',
        content
    )
    print("✅ Fix 1: sbToggle null guard applied via regex")

# ── Fix 2: Duplicate searchInput declaration ─────────────────────────────────
# Find all occurrences of searchInput declaration
declarations = [(m.start(), m.group()) for m in re.finditer(r'\bconst\s+searchInput\b', content)]
print(f"Found {len(declarations)} searchInput declarations")
if len(declarations) > 1:
    # Keep the first, change subsequent ones to assignments
    for start, match in declarations[1:]:
        content = content[:start] + content[start:].replace('const searchInput', 'searchInput', 1)
    print("✅ Fix 2: Duplicate searchInput declarations fixed")

# Also check for other duplicates
for var in ['searchResults', 'searchBtn', 'toast', 'hint']:
    decls = [(m.start(), m.group()) for m in re.finditer(rf'\bconst\s+{var}\b', content)]
    if len(decls) > 1:
        for start, match in decls[1:]:
            content = content[:start] + content[start:].replace(f'const {var}', var, 1)
        print(f"✅ Fixed duplicate: {var}")

# ── Fix 3: Find and fix syntax error near line 1989 ─────────────────────────
# Look for misplaced closing paren
lines = content.split('\n')
for i, line in enumerate(lines):
    # Look for lines that are just ')' or ');' which would be orphaned
    stripped = line.strip()
    if stripped in (')', ');', '),') and i > 1500:
        prev = lines[i-1].strip() if i > 0 else ''
        print(f"  Suspicious line {i+1}: '{stripped}' after '{prev}'")

# Common cause: double-closed function or orphaned paren from patch
# Find })(); or similar orphaned patterns
orphan = re.findall(r'\n\s*\)\s*;\s*\n\s*\)\s*;', content)
if orphan:
    print(f"Found {len(orphan)} orphaned )]; patterns")
    content = re.sub(r'(\n\s*\)\s*;\s*\n)\s*\)\s*;', r'\1', content)
    print("✅ Fix 3: Orphaned parens removed")

# ── Fix 4: Ensure all chart code runs after DOM ready ────────────────────────
# Wrap the main script block in DOMContentLoaded if not already
if 'DOMContentLoaded' not in content and 'window.onload' not in content:
    print("Note: consider wrapping scripts in DOMContentLoaded")

open('templates/base.html', 'w').write(content)
print(f"\n{'='*50}")
print("✅ base.html fixes applied")
if content != original:
    print("File was changed")
else:
    print("No changes made - errors may be elsewhere")
    # Show lines around the error areas
    lines = content.split('\n')
    total = len(lines)
    print(f"Total lines in base.html: {total}")
    for target in [1519, 1706, 1987]:
        if target < total:
            start = max(0, target-3)
            end = min(total, target+3)
            print(f"\nLines around {target}:")
            for i in range(start, end):
                print(f"  {i+1}: {lines[i][:100]}")
