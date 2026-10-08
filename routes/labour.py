"""Labour Intelligence — collector cost per husk, trends, and planning calculator."""

from flask import Blueprint, render_template
from database.db import query
from datetime import date

labour_bp = Blueprint('labour', __name__)


def _collector_metrics(farm_id=None):
    """Per-harvest collector cost per husk for oil palm farms.

    Column mapping (validated against DB):
      bunches_harvested = number of husks (bunches) harvested
      collector_pay     = total collectors pay
      num_collectors    = number of collectors (labourers)
      harvester_pay     = harvester pay
      total_labour = harvesting_cost + threshing_cost
    """
    where = "AND h.farm_id=?" if farm_id else ""
    params = (farm_id,) if farm_id else ()

    rows = query(f"""
        SELECT h.id, h.date,
               f.id   AS farm_id,
               f.name AS farm_name,
               COALESCE(h.bunches_harvested, 0) AS husks,
               COALESCE(h.num_collectors, 0)    AS num_collectors,
               COALESCE(h.num_labourers, 0)     AS num_labourers,
               COALESCE(h.collector_pay, 0)     AS collector_pay,
               COALESCE(h.harvester_pay, 0)     AS harvester_pay,
               (COALESCE(h.harvesting_cost, 0) + COALESCE(h.threshing_cost, 0)) AS total_labour
        FROM harvests h
        JOIN farms f ON f.id = h.farm_id
        WHERE f.crop_type = 'Oil Palm'
          AND h.bunches_harvested > 0
          {where}
        ORDER BY h.date DESC
    """, params)

    metrics = []
    for r in rows:
        husks         = float(r['husks'] or 0)
        collector_pay = float(r['collector_pay'] or 0)
        harvester_pay = float(r['harvester_pay'] or 0)
        total_labour  = float(r['total_labour'] or 0)
        num_col       = int(r['num_collectors'] or 0)

        # +10% adjustment for fallen fruits collected from ground
        husks_adj = round(husks * 1.10, 1)

        # Cost per husk (using adjusted count)
        cost_per_husk = round(collector_pay / husks_adj, 4) if husks_adj > 0 else 0

        # Cost per collector per harvest
        cost_per_collector = round(collector_pay / num_col, 2) if num_col > 0 else 0

        metrics.append({
            'id':                r['id'],
            'date':              r['date'],
            'farm_id':           r['farm_id'],
            'farm':              r['farm_name'],
            'husks':             int(husks),
            'husks_adj':         husks_adj,
            'num_collectors':    num_col,
            'collector_pay':     round(collector_pay, 2),
            'harvester_pay':     round(harvester_pay, 2),
            'total_labour':      round(total_labour, 2),
            'cost_per_husk':     cost_per_husk,
            'cost_per_collector':cost_per_collector,
        })
    return metrics


def _farm_summary(metrics, overall_avg_cph):
    """Aggregate metrics per farm."""
    farms = {}
    for m in metrics:
        fid = m['farm_id']
        if fid not in farms:
            farms[fid] = {
                'farm_id': fid, 'farm': m['farm'],
                'harvests': 0,
                'total_husks': 0.0, 'total_husks_adj': 0.0,
                'total_collector': 0.0, 'total_harvester': 0.0,
                'total_collectors_used': 0,
                'cph_list': [],
            }
        f = farms[fid]
        f['harvests']             += 1
        f['total_husks']          += m['husks']
        f['total_husks_adj']      += m['husks_adj']
        f['total_collector']      += m['collector_pay']
        f['total_harvester']      += m['harvester_pay']
        f['total_collectors_used']+= m['num_collectors']
        if m['cost_per_husk'] > 0:
            f['cph_list'].append(m['cost_per_husk'])

    result = []
    for f in farms.values():
        avg_cph     = round(f['total_collector'] / f['total_husks_adj'], 4) if f['total_husks_adj'] else 0
        overall_cph = round(f['total_collector'] / f['total_husks_adj'], 4) if f['total_husks_adj'] > 0 else 0
        vs_avg      = round(overall_cph - overall_avg_cph, 4)
        result.append({
            **f,
            'avg_cph':     avg_cph,
            'overall_cph': overall_cph,
            'vs_avg':      vs_avg,
        })

    return sorted(result, key=lambda x: x['overall_cph'])


@labour_bp.route('/')
def index():
    today       = date.today()
    all_metrics = _collector_metrics()

    # Overall average cost per husk
    total_collector = sum(m['collector_pay'] for m in all_metrics)
    total_husks_adj = sum(m['husks_adj']     for m in all_metrics)
    overall_avg_cph = round(total_collector / total_husks_adj, 4) if total_husks_adj > 0 else 0

    farm_summary = _farm_summary(all_metrics, overall_avg_cph)

    # Active oil palm farms for calculator dropdown
    farms_raw = query("""
        SELECT f.id, f.name FROM farms f
        WHERE f.crop_type='Oil Palm' AND f.status='Active'
        ORDER BY f.name
    """)

    # Per-farm trend data
    farm_trends = {}
    for f in farms_raw:
        fm = list(reversed(_collector_metrics(f['id'])[:15]))
        farm_trends[str(f['id'])] = {
            'name': f['name'],
            'data': [{'date': m['date'], 'cost_per_husk': m['cost_per_husk'],
                      'husks': m['husks'], 'husks_adj': m['husks_adj'],
                      'collector_pay': m['collector_pay'],
                      'num_collectors': m['num_collectors']} for m in fm],
        }

    return render_template('labour/index.html',
        today=today,
        all_metrics=all_metrics,
        farm_summary=farm_summary,
        overall_avg_cph=overall_avg_cph,
        total_collector=total_collector,
        total_husks_adj=total_husks_adj,
        farm_trends=farm_trends,
        farms=farms_raw,
    )
