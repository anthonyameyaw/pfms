"""Labour Intelligence — benchmarks and cost analysis."""

from flask import Blueprint, render_template, request
from database.db import query

labour_bp = Blueprint('labour', __name__)

ACTIVITY_TYPES = ['Harvesting','Weeding','Fertilising','Spraying',
                  'Pruning','Planting','Maintenance','Other']


@labour_bp.route('/')
def index():
    date_from = request.args.get('date_from', '')
    date_to   = request.args.get('date_to', '')

    # Benchmarks per activity type
    benchmarks = []
    for act in ACTIVITY_TYPES:
        sql    = """
            SELECT
                COUNT(*) AS count,
                COALESCE(SUM(labour_cost),0) AS total_labour,
                COALESCE(SUM(num_labourers),0) AS total_labourers,
                COALESCE(AVG(labour_cost),0) AS avg_cost,
                COALESCE(MIN(labour_cost),0) AS min_cost,
                COALESCE(MAX(labour_cost),0) AS max_cost
            FROM activities
            WHERE activity_type=? AND labour_cost > 0
        """
        params = [act]
        if date_from:
            sql += " AND date>=?"; params.append(date_from)
        if date_to:
            sql += " AND date<=?"; params.append(date_to)

        row = query(sql, params, one=True)

        # Cost per labourer per session
        cost_per_labourer = 0
        if row['total_labourers'] and row['total_labourers'] > 0:
            cost_per_labourer = row['total_labour'] / row['total_labourers']

        benchmarks.append({
            'activity'         : act,
            'count'            : row['count'],
            'avg_cost'         : round(row['avg_cost'], 2),
            'min_cost'         : round(row['min_cost'], 2),
            'max_cost'         : round(row['max_cost'], 2),
            'cost_per_labourer': round(cost_per_labourer, 2),
        })

    # Per-farm labour breakdown
    farm_labour = query("""
        SELECT f.name AS farm_name, a.activity_type,
               COUNT(*) AS sessions,
               COALESCE(SUM(a.labour_cost),0) AS total_cost,
               COALESCE(SUM(a.num_labourers),0) AS total_labourers
        FROM activities a
        JOIN farms f ON f.id = a.farm_id
        WHERE a.labour_cost > 0
        GROUP BY f.id, a.activity_type
        ORDER BY f.name, a.activity_type
    """)

    # Recent high-cost activities for benchmarking awareness
    recent = query("""
        SELECT a.*, f.name AS farm_name
        FROM activities a JOIN farms f ON f.id=a.farm_id
        WHERE a.labour_cost > 0
        ORDER BY a.labour_cost DESC LIMIT 10
    """)

    return render_template('labour/index.html',
        benchmarks  = benchmarks,
        farm_labour = farm_labour,
        recent      = recent,
        filters     = dict(date_from=date_from, date_to=date_to),
    )
