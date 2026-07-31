"""Fix broken chart JS in all templates caused by datalabels patch remnants."""
import re, os

fixed = []

for root, dirs, files in os.walk('templates'):
    for fname in files:
        if not fname.endswith('.html'):
            continue
        path = os.path.join(root, fname)
        content = open(path).read()
        original = content

        # Remove orphaned datalabels properties injected into plugins blocks
        # Pattern: font: { size:..., weight:..., family:... }, color: '#...', clip: false,
        content = re.sub(
            r'\s*font:\s*\{\s*size:\s*\d+,\s*weight:\s*[\'"][^"\']+[\'"],\s*family:\s*[^\}]+\},?\s*\n\s*color:\s*[\'"]#[a-f0-9]+[\'"],?\s*\n\s*clip:\s*false,?\s*\n',
            '\n',
            content, flags=re.IGNORECASE
        )

        # Also remove standalone clip: false lines
        content = re.sub(r'\s*clip:\s*false,?\s*\n', '\n', content)

        # Remove any remaining datalabels: { ... } blocks
        def remove_datalabels(text):
            out = []
            i = 0
            while i < len(text):
                m = re.search(r'\n?\s*datalabels\s*:\s*\{', text[i:])
                if not m:
                    out.append(text[i:])
                    break
                out.append(text[i:i+m.start()])
                start = i + m.end()
                depth = 1
                j = start
                while j < len(text) and depth > 0:
                    if text[j] == '{': depth += 1
                    elif text[j] == '}': depth -= 1
                    j += 1
                # Skip trailing comma
                while j < len(text) and text[j] in ', \n':
                    if text[j] == '\n': break
                    j += 1
                i = j
            return ''.join(out)

        if 'datalabels' in content:
            content = remove_datalabels(content)

        if content != original:
            open(path, 'w').write(content)
            fixed.append(path)
            remaining = content.count('clip: false') + content.count('datalabels')
            print(f"✅ Fixed: {path} (remaining issues: {remaining})")

if not fixed:
    print("No files needed fixing")
else:
    print(f"\n{len(fixed)} files fixed")
