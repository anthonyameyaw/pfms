"""Shared recorded-income/expense reporting (purchases expensed on purchase date).

Production, inventory revaluation and investor funding are not sale income.
Legacy FFB Sale rows can duplicate old harvest auto-income; reconciliation of
that entry workflow is separate. Internal processing fees remain plant revenue
and a matching farm expense, eliminated on consolidation.
"""
from datetime import date
from database.db import query

INCOME_LABELS = {
    'harvest_sales': 'Legacy harvest sales (archived)',
    'other_income': 'Other farm income',
    'storage_sales': 'Storage oil sales',
    'plant_income': 'Outside-farmer processing fees',
    'plant_internal_income': 'Own-farm processing fees',
}
EXPENSE_LABELS = {
    'harv_exp': 'Harvest labour',
    'thresh_exp': 'Threshing labour',
    'act_exp': 'Farm activity labour and materials',
    'manual_exp': 'Other recorded farm expenses',
    'trans_exp': 'Transport',
    'maint_exp': 'Pickup maintenance',
    'elec_exp': 'Plant electricity',
    'op_exp': 'Plant operator pay',
    'plant_other': 'Other plant expenses',
    'purchase_exp': 'Oil purchases',
    'internal_processing_exp': 'Own-farm processing charges',
}
# Allocate recorded internal fees by oil quantity. Cumulative rounding makes
# farm allocations add back to each run exactly, including fractional pesewas.
PROCESSING_ALLOCATIONS = """
WITH links AS (
 SELECT l.id, l.run_id, l.farm_id, r.date,
        ROUND((COALESCE(r.gross_revenue,0)-COALESCE(r.outside_farmer_fees,0))*100) AS fee_cents,
        r.own_farms_gallons AS total_gallons,
        COALESCE(l.gallons_contributed,
            CASE WHEN COUNT(*) OVER (PARTITION BY l.run_id)=1 THEN r.own_farms_gallons ELSE 0 END) AS gallons
 FROM processing_run_farms l JOIN processing_runs r ON r.id=l.run_id
), portions AS (
 SELECT *, SUM(gallons) OVER (PARTITION BY run_id ORDER BY id) AS cumulative
 FROM links WHERE total_gallons>0 AND gallons>0
)
SELECT run_id, farm_id, date,
 (ROUND(fee_cents*MIN(cumulative,total_gallons)/total_gallons) -
  ROUND(fee_cents*MIN(cumulative-gallons,total_gallons)/total_gallons))/100.0 AS amount
 FROM portions
"""

# Only these sources enter recorded financial results. Storage is pooled until
# sales can be allocated to farm/stock lots; never guess a farm attribution.
ENTRIES = f"""
SELECT date, farm_id, 'harvest_sales' AS category,
       0 AS income, 0 AS expense FROM harvests WHERE 0
UNION ALL SELECT date, farm_id, 'other_income', COALESCE(total_amount,0), 0
    FROM farm_income WHERE income_type='Other'
UNION ALL SELECT date, NULL, 'storage_sales', COALESCE(total_amount,0), 0
    FROM storage_transactions WHERE transaction_type='Sale'
UNION ALL SELECT date, NULL, 'plant_income', COALESCE(outside_farmer_fees,0), 0 FROM processing_runs
UNION ALL SELECT date, NULL, 'plant_internal_income',
    COALESCE(gross_revenue,0)-COALESCE(outside_farmer_fees,0), 0 FROM processing_runs
UNION ALL SELECT date, farm_id, 'internal_processing_exp', 0, amount FROM ({PROCESSING_ALLOCATIONS})
UNION ALL SELECT r.date, NULL, 'internal_processing_exp', 0,
    ROUND(COALESCE(r.gross_revenue,0)-COALESCE(r.outside_farmer_fees,0),2)-COALESCE(a.amount,0)
    FROM processing_runs r LEFT JOIN
      (SELECT run_id,SUM(amount) AS amount FROM ({PROCESSING_ALLOCATIONS}) GROUP BY run_id) a ON a.run_id=r.id
UNION ALL SELECT date, farm_id, 'harv_exp', 0, COALESCE(harvesting_cost,0) FROM harvests
UNION ALL SELECT date, farm_id, 'thresh_exp', 0, COALESCE(threshing_cost,0) FROM harvests
UNION ALL SELECT date, farm_id, 'act_exp', 0, COALESCE(labour_cost,0)+COALESCE(materials_cost,0)
    FROM activities WHERE activity_type!='Harvesting'
UNION ALL SELECT date, farm_id, 'manual_exp', 0, COALESCE(amount,0) FROM farm_expenses
UNION ALL SELECT date, farm_id, 'trans_exp', 0, COALESCE(total_cost,0) FROM transport_logs
UNION ALL SELECT date, NULL, 'maint_exp', 0, COALESCE(cost,0) FROM pickup_maintenance
UNION ALL SELECT date, NULL, 'elec_exp', 0, COALESCE(electricity_cost,0) FROM processing_runs
UNION ALL SELECT date, NULL, 'op_exp', 0, COALESCE(operator_pay,0) FROM processing_runs
UNION ALL SELECT date, NULL, 'plant_other', 0, COALESCE(amount,0) FROM plant_expenses
UNION ALL SELECT date, NULL, 'purchase_exp', 0, COALESCE(total_amount,0)
    FROM storage_transactions WHERE transaction_type='Purchase'
"""

# Round each recorded component to pesewas once so grouped totals and monthly
# charts reconcile even when fractional quantities produce sub-pesewa amounts.
MONEY_ENTRIES = f"""SELECT date, farm_id, category,
    CAST(ROUND(income * 100, 0) AS INTEGER) AS income_cents,
    CAST(ROUND(expense * 100, 0) AS INTEGER) AS expense_cents
    FROM ({ENTRIES})"""


def _where(date_from='', date_to='', farm_id=None, scope=None, financial=True):
    """Dates are inclusive, matching report date controls."""
    conditions, params = [], []
    if date_from:
        conditions.append('date>=?'); params.append(str(date_from))
    if date_to:
        conditions.append('date<=?'); params.append(str(date_to))
    if farm_id is not None:
        conditions.append('farm_id=?'); params.append(farm_id)
    if not financial:
        return (' WHERE ' + ' AND '.join(conditions) if conditions else ''), params
    if scope == 'plant':
        conditions.append("category IN ('plant_income','plant_internal_income','elec_exp','op_exp','plant_other')")
    elif scope == 'farms':
        conditions.append("(farm_id IS NOT NULL OR category='internal_processing_exp')")
    elif scope is None and farm_id is not None:
        conditions.append("category != 'plant_internal_income'")
    elif scope is None:
        conditions.append("category NOT IN ('plant_internal_income','internal_processing_exp')")
    elif scope is not None:
        raise ValueError('Unknown financial scope')
    return (' WHERE ' + ' AND '.join(conditions) if conditions else ''), params


def financial_summary(date_from='', date_to='', farm_id=None, scope=None):
    where, params = _where(date_from, date_to, farm_id, scope)
    rows = query(f"""WITH entries AS ({MONEY_ENTRIES})
        SELECT category, SUM(income_cents) AS income, SUM(expense_cents) AS expense
        FROM entries{where} GROUP BY category""", params)
    result = dict.fromkeys((*INCOME_LABELS, *EXPENSE_LABELS), 0.0)
    for row in rows:
        result[row['category']] = ((row['income'] or 0) + (row['expense'] or 0)) / 100.0
    fee_where, fee_params = _where(date_from, date_to, scope='plant')
    fees = query(f"SELECT COALESCE(SUM(income_cents),0) AS amount FROM ({MONEY_ENTRIES}) {fee_where} AND category='plant_internal_income'", fee_params, one=True)
    result['internal_processing_fees'] = fees['amount'] / 100.0
    unallocated_where, unallocated_params = _where(date_from, date_to, scope='farms')
    unallocated = query(f"SELECT COALESCE(SUM(expense_cents),0) AS amount FROM ({MONEY_ENTRIES}) {unallocated_where} AND category='internal_processing_exp' AND farm_id IS NULL", unallocated_params, one=True)
    result['unallocated_processing_fees'] = unallocated['amount'] / 100.0
    result['farm_income'] = round(result['harvest_sales'] + result['other_income'], 2)
    result['total_income'] = round(sum(result[k] for k in INCOME_LABELS), 2)
    result['total_exp'] = round(sum(result[k] for k in EXPENSE_LABELS), 2)
    result['net'] = round(result['total_income'] - result['total_exp'], 2)
    result['income_items'] = [{'label': label, 'value': result[k]} for k, label in INCOME_LABELS.items() if k != 'harvest_sales' and (k != 'plant_internal_income' or scope == 'plant')]
    result['expense_items'] = [{'label': label, 'value': result[k]} for k, label in EXPENSE_LABELS.items() if k != 'internal_processing_exp' or scope == 'farms' or farm_id is not None]
    return result


def month_start_months_ago(today, months):
    month_index = today.year * 12 + today.month - 1 - months
    year, month = divmod(month_index, 12)
    return date(year, month + 1, 1).isoformat()


def monthly_financials(date_from, date_to, farm_id=None, scope=None):
    """Full calendar series, including months with expenses only or no entries."""
    where, params = _where(date_from, date_to, farm_id, scope)
    rows = query(f"""WITH entries AS ({MONEY_ENTRIES})
        SELECT substr(date,1,7) AS month, SUM(income_cents) AS income, SUM(expense_cents) AS expenses
        FROM entries{where} GROUP BY month ORDER BY month""", params)
    amounts = {r['month']: r for r in rows}
    first, last = date.fromisoformat(str(date_from)), date.fromisoformat(str(date_to))
    result = []
    for n in range(first.year * 12 + first.month - 1, last.year * 12 + last.month):
        y, m = divmod(n, 12)
        key = f'{y:04d}-{m+1:02d}'
        r = amounts.get(key, {})
        income = (r['income'] or 0) / 100.0 if r else 0.0
        expense = (r['expenses'] or 0) / 100.0 if r else 0.0
        result.append({'month': key, 'income': income, 'expenses': expense,
                       'net': round(income - expense, 2)})
    return result


def farm_financials(date_from='', date_to=''):
    result = []
    for farm in query('SELECT * FROM farms ORDER BY name'):
        summary = financial_summary(date_from, date_to, farm['id'])
        where, params = _where(date_from, date_to, farm['id'], financial=False)
        units = query(f"""SELECT COALESCE(SUM(gallons_produced),0) AS gallons,
            COALESCE(SUM(bunches_harvested),0) AS bunches FROM harvests{where}""", params, one=True)
        result.append(dict(farm, income=summary['total_income'], expenses=summary['total_exp'],
            net=summary['net'], harv_cost=summary['harv_exp'], thresh_cost=summary['thresh_exp'],
            trans_cost=summary['trans_exp'], transport_cost=summary['trans_exp'],
            act_cost=summary['act_exp'], activity_cost=summary['act_exp'],
            other_expenses=summary['manual_exp'], processing_cost=summary['internal_processing_exp'], other_income=summary['other_income'],
            gallons_produced=units['gallons'], gallons=units['gallons'], bunches=units['bunches']))
    return result
