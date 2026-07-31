"""
Palm Farm Management System (PFMS)
====================================
Local web application for managing farm activities,
finances, harvests, and processing plant operations.

Run with:  python app.py
Open:      http://localhost:5001
"""

from flask import Flask
from database.db import init_db

# ── Import all route blueprints ──────────────────────────────────────────────
from routes.dashboard  import dashboard_bp
from routes.farms      import farms_bp
from routes.activities import activities_bp
from routes.harvests   import harvests_bp
from routes.pruning    import pruning_bp
from routes.plant      import plant_bp
from routes.transport  import transport_bp
from routes.finances   import finances_bp
from routes.prices     import prices_bp
from routes.labour     import labour_bp
from routes.reports    import reports_bp
from routes.investors  import investors_bp
from routes.storage    import storage_bp

app = Flask(__name__)
app.secret_key = 'pfms-local-secret-2024'

# ── Register blueprints ──────────────────────────────────────────────────────
app.register_blueprint(dashboard_bp)
app.register_blueprint(farms_bp,      url_prefix='/farms')
app.register_blueprint(activities_bp, url_prefix='/activities')
app.register_blueprint(harvests_bp,   url_prefix='/harvests')
app.register_blueprint(pruning_bp,    url_prefix='/pruning')
app.register_blueprint(plant_bp,      url_prefix='/plant')
app.register_blueprint(transport_bp,  url_prefix='/transport')
app.register_blueprint(finances_bp,   url_prefix='/finances')
app.register_blueprint(prices_bp,     url_prefix='/prices')
app.register_blueprint(labour_bp,     url_prefix='/labour')
app.register_blueprint(reports_bp,    url_prefix='/reports')
app.register_blueprint(investors_bp,  url_prefix='/investors')
app.register_blueprint(storage_bp,    url_prefix='/storage')

# ── Initialize DB on startup ─────────────────────────────────────────────────
with app.app_context():
    init_db()

@app.route('/offline')
def offline():
    return render_template('offline.html')

if __name__ == '__main__':
    print("\n" + "="*50)
    print("  🌴 Palm Farm Management System")
    print("  Open your browser: http://localhost:5001")
    print("="*50 + "\n")
    app.run(host="0.0.0.0", debug=True, port=5001)
