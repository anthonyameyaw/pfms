"""Fix broken plugins blocks in plant, farms, and finances templates."""
import re, os

def fix_plugins(content):
    """Fix all broken chart options blocks."""
    
    # Fix 1: Remove duplicate legend outside plugins
    # e.g. options:{ plugins:{legend:{position:'top'}}, legend:{position:'top'} }
    content = re.sub(
        r'(options\s*:\s*\{[^}]*plugins\s*:\s*\{[^}]*\}[^}]*),\s*legend\s*:\s*\{[^}]*\}',
        r'\1',
        content
    )
    
    # Fix 2: Empty plugins block -> add legend
    content = re.sub(
        r'plugins\s*:\s*\{\s*\n?\s*\}',
        "plugins:{legend:{position:'top'}}",
        content
    )
    
    # Fix 3: plugins block with only whitespace
    content = re.sub(
        r'plugins\s*:\s*\{\s+\}',
        "plugins:{legend:{position:'top'}}",
        content
    )
    
    return content

files_fixed = []
for root, dirs, files in os.walk('templates'):
    for fname in files:
        if not fname.endswith('.html'):
            continue
        path = os.path.join(root, fname)
        if 'new Chart(' not in open(path).read():
            continue
        content = open(path).read()
        original = content
        content = fix_plugins(content)
        if content != original:
            open(path, 'w').write(content)
            files_fixed.append(path)
            print(f"Fixed: {path}")

print(f"\nFixed {len(files_fixed)} files")

# Now validate - try to find obvious JS syntax errors
print("\nValidating chart options...")
for root, dirs, files in os.walk('templates'):
    for fname in files:
        if not fname.endswith('.html'):
            continue
        path = os.path.join(root, fname)
        content = open(path).read()
        if 'new Chart(' not in content:
            continue
        
        # Check for common issues
        issues = []
        if re.search(r'options\s*:\s*\{[^}]*\},\s*legend\s*:', content):
            issues.append('duplicate legend outside plugins')
        if re.search(r'plugins\s*:\s*\{\s*\n?\s*\}', content):
            issues.append('empty plugins block')
        if 'clip: false' in content:
            issues.append('orphaned clip:false')
        if 'datalabels' in content:
            issues.append('datalabels remnant')
            
        if issues:
            print(f"  ⚠ {path}: {issues}")
        else:
            charts = content.count('new Chart(')
            print(f"  ✅ {path}: {charts} chart(s) - OK")
