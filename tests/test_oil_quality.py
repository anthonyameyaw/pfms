import unittest
import test_financials as base
from database import db
from database.oil_quality import balances
from routes.storage import _current_stock

class QualityTests(unittest.TestCase):
    setUp=base.FinancialTests.setUp
    def stock(self):
        c=db.get_connection()
        try:return balances(c)
        finally:c.close()
    def produce(self):
        self.client.post('/harvests/add',data=dict(farm_id='4',date='2026-10-01',husks_processed='1',processing_date='2026-10-01',gallons_produced='10',bunches_harvested='1',harvester_pay='0'))
    def assess(self,fresh='6',soap='4',day='2026-10-02'):
        return self.client.post('/storage/log-quality',data=dict(date=day,fresh_gallons=fresh,soap_gallons=soap))
    def sale(self,kind,quantity,day='2026-10-03'):
        return self.client.post('/storage/log-sale',data=dict(date=day,gallons=str(quantity),price_per_gallon='100',quality_type=kind))
    def test_unknown_stock_and_repeated_assessments(self):
        self.produce();self.assertEqual(self.stock(),dict(Fresh=0,Soap=0,Unassessed=10))
        self.assess();self.assess()
        self.assertEqual(self.stock(),dict(Fresh=6,Soap=4,Unassessed=0))
        self.assertEqual(_current_stock(),10)
        self.assertEqual(len(db.query("SELECT * FROM storage_transactions WHERE transaction_type='Assessment'")),2)
    def test_sale_reduces_only_selected_category_and_rejects_overdraw(self):
        self.produce();self.assess();self.sale('Fresh',2)
        self.assertEqual(self.stock(),dict(Fresh=4,Soap=4,Unassessed=0))
        self.sale('Soap',5);self.sale('Unassessed',1)
        self.assertEqual(_current_stock(),8)
        self.assertEqual(len(db.query("SELECT * FROM storage_transactions WHERE transaction_type='Sale'")),1)
        self.sale('Soap',1);self.assertEqual(self.stock(),dict(Fresh=4,Soap=3,Unassessed=0))
    def test_mismatched_assessment_and_backdated_sales_roll_back(self):
        self.produce();self.assess('8','8')
        self.assertEqual(db.query('SELECT * FROM storage_transactions'),[])
        self.assess();self.sale('Fresh',1,day='2026-09-30')
        self.assertEqual(_current_stock(),10)
        self.sale('Unassessed',1,day='2026-10-01')
        self.assertEqual(_current_stock(),10) # would invalidate the later count
    def test_delete_and_harvest_edit_cannot_invalidate_assessment(self):
        self.produce();self.assess();self.sale('Fresh',2)
        assessment=db.query("SELECT id FROM storage_transactions WHERE transaction_type='Assessment'",one=True)['id']
        h=db.query('SELECT id FROM harvests',one=True)['id']
        self.client.post('/harvests/%s/edit'%h,data=dict(farm_id='4',date='2026-10-01',husks_processed='1',processing_date='2026-10-01',gallons_produced='12',bunches_harvested='1',harvester_pay='0'))
        self.assertEqual(_current_stock(),8)
        self.client.post('/storage/delete/%s'%assessment)
        self.assertEqual(self.stock(),dict(Fresh=0,Soap=0,Unassessed=8))
    def test_typed_purchase_and_new_production(self):
        self.produce();self.assess()
        self.client.post('/storage/log-purchase',data=dict(date='2026-10-03',gallons='2',price_per_gallon='100',quality_type='Soap'))
        self.client.post('/harvests/add',data=dict(farm_id='4',date='2026-10-04',husks_processed='1',processing_date='2026-10-04',gallons_produced='3',bunches_harvested='1',harvester_pay='0'))
        self.assertEqual(self.stock(),dict(Fresh=6,Soap=6,Unassessed=3))
        self.assess('8','7',day='2026-10-05')
        self.assertEqual(self.stock(),dict(Fresh=8,Soap=7,Unassessed=0))
    def test_full_assessment_zero_and_history_render(self):
        self.assess('0','0')
        self.assertEqual(len(db.query("SELECT * FROM storage_transactions WHERE transaction_type='Assessment'")),1)
        for page in ['/storage/','/storage/log-quality','/storage/log-sale','/storage/log-purchase']:
            self.assertEqual(self.client.get(page).status_code,200)
        self.assertIn('Not yet assessed',self.client.get('/storage/').get_data(as_text=True))

    def test_sale_types_can_be_recorded_before_any_assessment(self):
        self.produce();self.sale('Fresh',2);self.sale('Soap',3)
        self.assertEqual(self.stock(),dict(Fresh=0,Soap=0,Unassessed=5))
        self.assertEqual(_current_stock(),5)
        sales=db.query("SELECT quality_type,gallons,total_amount FROM storage_transactions WHERE transaction_type='Sale' ORDER BY id")
        self.assertEqual([tuple(r) for r in sales],[('Fresh',2,200),('Soap',3,300)])
        html=self.client.get('/storage/').get_data(as_text=True)
        self.assertIn('Oil sales by type',html)
        self.assertIn('Oil for food',html)
        csv=self.client.get('/reports/export/storage.csv').get_data(as_text=True)
        self.assertIn('Oil for soap',csv)
        self.assess('4','1',day='2026-10-04')
        self.assertEqual(self.stock(),dict(Fresh=4,Soap=1,Unassessed=0))
