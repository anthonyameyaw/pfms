"""Nuclear revert — remove ALL datalabels traces from every file."""
import os, re

# Fix base.html
content = open('templates/base.html').read()

# Remove CDN line
content = re.sub(r'\s*<script src="[^"]*datalabels[^"]*"></script>', '', content)

# Remove register calls
content = re.sub(r'\s*Chart\.register\(ChartDataLabels\);?\s*\n?', '\n  ', content)

# Remove global defaults comment
content = re.sub(r'\s*//\s*Global datalabels defaults.*?\n.*?datalabels.*?\n', '\n', content)
content = re.sub(r'\s*Chart\.defaults\.plugins\.datalabels\.[^\n]+\n', '', content)

open('templates/base.html', 'w').write(content)
print("✅ base.html cleaned")

# Fix all other templates — remove datalabels blocks
count = 0
for root, dirs, files in os.walk('templates'):
    for fname in files:
        if not fname.endswith('.html'):
            continue
        path = os.path.join(root, fname)
        tmpl = open(path).read()
        if 'datalabels' not in tmpl:
            continue

        original = tmpl

        # Remove datalabels plugin objects — handles nested braces
        # Pattern: datalabels: { ... }, (with possible nested {})
        def remove_dl(text):
            result = []
            i = 0
            while i < len(text):
                # Look for datalabels key
                m = re.search(r'\n?\s*datalabels\s*:\s*\{', text[i:])
                if not m:
                    result.append(text[i:])
                    break
                result.append(text[i:i+m.start()])
                # Find matching closing brace
                start = i + m.end()
                depth = 1
                j = start
                while j < len(text) and depth > 0:
                    if text[j] == '{': depth += 1
                    elif text[j] == '}': depth -= 1
                    j += 1
                # Skip trailing comma and whitespace
                while j < len(text) and text[j] in ',\n ':
                    j += 1
                i = j
            return ''.join(result)

        tmpl = remove_dl(tmpl)

        if tmpl != original:
            open(path, 'w').write(tmpl)
            count += 1
            print(f"  Cleaned: {path}")

print(f"\n✅ Removed datalabels from {count} templates")

# Verify base.html is clean
base = open('templates/base.html').read()
if 'datalabels' in base:
    print("⚠ base.html still has datalabels references:")
    for i, line in enumerate(base.split('\n'), 1):
        if 'datalabels' in line:
            print(f"  Line {i}: {line.strip()}")
else:
    print("✅ base.html is clean")

print("\nRestart the app — charts should be fully restored.")
