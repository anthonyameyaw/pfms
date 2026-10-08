"""Recorded period costs per gallon. No attribution of pooled sales to farms."""
from decimal import Decimal, ROUND_HALF_UP
from database.db import query
from database.financials import financial_summary, MONEY_ENTRIES, PROCESSING_ALLOCATIONS

CATEGORIES = [('harv_exp','Harvest labour'),('thresh_exp','Defruiting'),
              ('trans_exp','Linked harvest transport'),('internal_processing_exp','Processing fees')]

def harvest_costs(start,end):
    """Match costs to the same processed harvests as the output denominator."""
    allocations={(x['run_id'],x['farm_id']):x['amount'] for x in query(PROCESSING_ALLOCATIONS)}
    linked={(x['processing_run_id'],x['farm_id']):x['gallons'] for x in query(
        "SELECT processing_run_id,farm_id,SUM(gallons_produced) gallons FROM harvests WHERE husks_processed=1 AND gallons_produced>0 GROUP BY processing_run_id,farm_id")}
    result=[]
    for h in query("""SELECT h.*,f.name farm,
        COALESCE((SELECT SUM(total_cost) FROM transport_logs WHERE harvest_id=h.id),0) trans_cost
        FROM harvests h JOIN farms f ON f.id=h.farm_id
        WHERE f.crop_type='Oil Palm' AND h.husks_processed=1 AND h.gallons_produced>0
        AND COALESCE(h.processing_date,h.date)>=? AND COALESCE(h.processing_date,h.date)<=?
        ORDER BY h.date DESC,h.id DESC""",(start or '0001-01-01',end)):
        key=(h['processing_run_id'],h['farm_id']);g=float(h['gallons_produced'])
        fee=allocations.get(key,0)*g/linked[key] if key in allocations and linked.get(key) else 0
        labour=float(h['harvesting_cost'] or 0);thresh=float(h['threshing_cost'] or 0)
        total=labour+thresh+h['trans_cost']+fee
        result.append(dict(h,id=h['id'],farm_id=h['farm_id'],gallons=g,bunches=h['bunches_harvested'] or 0,
            harv_exp=labour,thresh_exp=thresh,trans_exp=h['trans_cost'],internal_processing_exp=fee,
            total_lab=labour+thresh,total_cost=total,levelized=floor_price(total,g),
            missing_processing=key not in allocations,
            bunches_per_gallon=h['bunches_harvested']/g if (h['bunches_harvested'] or 0)>0 else None))
    return result

def floor_price(cost,gallons):
    if not gallons:return None
    return float((Decimal(str(cost))/Decimal(str(gallons))).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))

def cost_profile(start,end):
    rows=[]
    harvests=harvest_costs(start,end)
    for farm in query("SELECT * FROM farms WHERE crop_type='Oil Palm' ORDER BY name"):
        selected=[h for h in harvests if h['farm_id']==farm['id']]
        pending=query("""SELECT COUNT(*) n FROM harvests WHERE farm_id=? AND date>=? AND date<=?
            AND (husks_processed IS NOT 1 OR COALESCE(gallons_produced,0)<=0)""",
            (farm['id'],start or '0001-01-01',end),one=True)['n']
        components=[dict(key=k,label=label,cost=round(sum(h[k] for h in selected),2)) for k,label in CATEGORIES]
        total=round(sum(h['total_cost'] for h in selected),2)
        gallons=sum(h['gallons'] for h in selected)
        rows.append(dict(id=farm['id'],name=farm['name'],status=farm['status'],components=components,
                         cost=total,gallons=gallons,unit_cost=floor_price(total,gallons),
                         unknown_dates=sum(not h['processing_date'] for h in selected),pending=pending,
                         missing_processing=sum(h['missing_processing'] for h in selected)))
    total=round(sum(r['cost'] for r in rows),2)
    gallons=sum(r['gallons'] for r in rows)
    shared=query(f"""SELECT category,SUM(expense_cents)/100.0 cost FROM ({MONEY_ENTRIES})
        WHERE farm_id IS NULL AND date>=? AND date<=?
        AND category IN ('trans_exp','maint_exp','internal_processing_exp') GROUP BY category""",
        (start or '0001-01-01',end))
    labels={'trans_exp':'Transport without a farm','maint_exp':'Pickup maintenance',
            'internal_processing_exp':'Processing fees without a farm allocation'}
    return dict(rows=rows,cost=total,gallons=gallons,unit_cost=floor_price(total,gallons),
                shared=[dict(label=labels[r['category']],cost=r['cost']) for r in shared],
                no_output_cost=round(sum(r['cost'] for r in rows if not r['gallons']),2))
