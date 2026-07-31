"""Adds offline route and static file serving to app.py. Run once."""
content = open('app.py').read()

# Add offline route if not already there
if 'offline' not in content:
    old = "if __name__ == '__main__':"
    new = """@app.route('/offline')
def offline():
    return render_template('offline.html')

if __name__ == '__main__':"""
    content = content.replace(old, new)

    # Make sure render_template is imported
    if 'render_template' not in content:
        content = content.replace(
            'from flask import Flask',
            'from flask import Flask, render_template'
        )

    open('app.py','w').write(content)
    print("✅ Offline route added to app.py")
else:
    print("— Offline route already exists")
