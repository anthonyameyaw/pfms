"""Remove the duplicate old sidebar/search JS block from base.html."""

content = open('templates/base.html').read()
lines = content.split('\n')
print(f"Total lines before: {len(lines)}")

# Find the two script blocks
# The duplicate old block starts with the old applySidebar function
# and ends at line ~1456 before the new SEARCH_INDEX block

# Strategy: find the OLD sidebar block (uses 'toggle', 'collapsed', 'applySidebar')
# and remove it, keeping the NEW block (uses 'sbToggle', 'sbCollapsed', 'applySb')

# The old block signature:
OLD_SIDEBAR_START = "const sidebar = document.querySelector('.sidebar');"
OLD_SIDEBAR_ALT   = "let collapsed = localStorage.getItem('sidebarCollapsed')"

# Find start of old block
old_start = -1
for i, line in enumerate(lines):
    if OLD_SIDEBAR_START in line or OLD_SIDEBAR_ALT in line:
        # Check it's the OLD one (look for 'toggle.textContent' not 'sbToggle')
        chunk = '\n'.join(lines[i:i+30])
        if 'toggle.textContent' in chunk and 'sbToggle' not in chunk:
            old_start = i
            print(f"Found OLD sidebar block at line {i+1}: {line.strip()[:60]}")
            break

if old_start == -1:
    # Try finding by the duplicate SEARCH_INDEX
    search_indices = []
    for i, line in enumerate(lines):
        if 'const SEARCH_INDEX = [' in line:
            search_indices.append(i)
    print(f"Found SEARCH_INDEX at lines: {[x+1 for x in search_indices]}")

    if len(search_indices) >= 2:
        # The old block ends just before the second SEARCH_INDEX
        # Find where it starts by going back to find the sidebar code
        second_idx = search_indices[1]
        # Go back to find start of old block
        for i in range(second_idx, max(0, second_idx-100), -1):
            if 'const sidebar' in lines[i] or 'let collapsed' in lines[i]:
                old_start = i
                break
        if old_start == -1:
            old_start = max(0, search_indices[1] - 60)
        print(f"OLD block starts around line {old_start+1}")

# Find end of old block — it ends before the new SEARCH_INDEX or new sbToggle block
if old_start >= 0:
    # Find the NEW block start (sbToggle or PAGES array)
    new_start = -1
    for i in range(old_start+1, len(lines)):
        if ('const PAGES = [' in lines[i] or 
            "document.getElementById('sbToggle')" in lines[i] or
            'function updateDate()' in lines[i]):
            new_start = i
            break

    if new_start == -1:
        # Look for the second SEARCH_INDEX occurrence
        count = 0
        for i in range(len(lines)):
            if 'SEARCH_INDEX' in lines[i] or 'PAGES' in lines[i]:
                count += 1
                if count == 2:
                    new_start = i
                    break

    if new_start > old_start:
        print(f"Removing lines {old_start+1} to {new_start} (old duplicate block)")
        # Remove the old block
        new_lines = lines[:old_start] + lines[new_start:]
        new_content = '\n'.join(new_lines)
        open('templates/base.html', 'w').write(new_content)
        print(f"✅ Done. Lines reduced from {len(lines)} to {len(new_lines)}")
    else:
        print(f"⚠ Could not determine end of old block (new_start={new_start})")
        print("Showing lines 1420-1470:")
        for i in range(1420, min(1470, len(lines))):
            print(f"  {i+1}: {lines[i][:80]}")
else:
    print("Could not find old sidebar block")
    print("Showing all lines containing 'applySidebar' or 'applySb':")
    for i, line in enumerate(lines):
        if 'applySidebar' in line or 'applySb' in line:
            print(f"  {i+1}: {line.strip()[:80]}")
