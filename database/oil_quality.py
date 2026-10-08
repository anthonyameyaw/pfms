"""Quality balances from production, classified movements and full stock counts."""
from decimal import Decimal

KINDS=('Fresh','Soap','Unassessed')


def balances(conn):
    amounts={kind:Decimal(0) for kind in KINDS}
    events=[]
    for row in conn.execute('SELECT id,COALESCE(processing_date,date) day,gallons_produced FROM harvests WHERE husks_processed=1'):
        events.append((row['day'],0,row['id'],'Production',dict(row)))
    for row in conn.execute("SELECT * FROM storage_transactions WHERE transaction_type IN ('Purchase','Sale','Assessment') ORDER BY date,id"):
        events.append((row['date'],1,row['id'],row['transaction_type'],dict(row)))
    for day,_,identifier,kind,row in sorted(events):
        if kind=='Assessment':
            fresh=Decimal(str(row['fresh_gallons'] or 0));soap=Decimal(str(row['soap_gallons'] or 0))
            total=sum(amounts.values())
            if min(fresh,soap)<0 or abs(fresh+soap-total)>Decimal('0.000001'):
                raise ValueError(f'Assessment on {day} must account for {total:.2f} gallons available at that point. Check the assessment and stock dates.')
            amounts={'Fresh':fresh,'Soap':soap,'Unassessed':Decimal(0)}
        else:
            category='Unassessed' if kind=='Production' else (row.get('quality_type') or 'Unassessed')
            if category not in KINDS:raise ValueError('Select Fresh, Soap, or Not yet assessed.')
            quantity=Decimal(str(row['gallons_produced'] if kind=='Production' else row['gallons']))
            if kind=='Sale' and category!='Unassessed':
                # A sale identifies the oil leaving even if the remaining pool
                # has never been assessed. Never infer its remaining split.
                known=min(amounts[category],quantity)
                amounts[category]-=known
                amounts['Unassessed']-=quantity-known
                if amounts['Unassessed'] < -Decimal('0.000001'):
                    raise ValueError(f'Insufficient {category.lower()} or unassessed oil on {day}. Check the sale type, quantity and dates.')
            else:
                amounts[category]+= -quantity if kind=='Sale' else quantity
            if amounts[category]<-Decimal('0.000001'):
                display='not yet assessed' if category=='Unassessed' else category.lower()
                raise ValueError(f'Insufficient {display} oil on {day}. Check the sale type, quantity and dates, or record a stock assessment first.')
    return {kind:float(value) for kind,value in amounts.items()}


def migrate_quality(conn):
    if 'quality_type' not in {r[1] for r in conn.execute('PRAGMA table_info(storage_transactions)')}:
        conn.execute("ALTER TABLE storage_transactions ADD COLUMN quality_type TEXT NOT NULL DEFAULT 'Unassessed' CHECK(quality_type IN ('Fresh','Soap','Unassessed'))")
    # Old quality logs were encoded as zero-quantity additions. Preserve them for
    # reference without assuming their cumulative figures form valid stock counts.
    conn.execute("UPDATE storage_transactions SET transaction_type='Legacy assessment' WHERE transaction_type='Addition' AND gallons=0 AND (fresh_gallons>0 OR soap_gallons>0)")
