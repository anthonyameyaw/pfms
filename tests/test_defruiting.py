import csv,io,unittest
import test_financials as base
from database import db
from database.financials import financial_summary

class DefruitingTests(unittest.TestCase):
    setUp=base.FinancialTests.setUp
    def form(self,**changes):
        data=dict(farm_id='4',date='2026-10-01',activity_type='Harvesting',bunches_harvested='10',harvester_pay='30',collector_pay='20',threshing_cost='12.50',husks_processed='0')
        data.update(changes);return data
    def test_both_entry_screens_save_and_count_once(self):
        for path,farm in [('/harvests/add','4'),('/activities/add','6')]:
            self.client.post(path,data=self.form(farm_id=farm))
        self.assertEqual(financial_summary()['total_exp'],125)
        self.assertEqual(financial_summary()['thresh_exp'],25)
        for h in db.query('SELECT * FROM harvests'):
            self.assertEqual((h['harvesting_cost'],h['threshing_cost']),(50,12.5))
            self.assertEqual(db.query('SELECT labour_cost FROM activities WHERE id=?',(h['activity_id'],),one=True)['labour_cost'],62.5)
    def test_edits_and_missing_field_preserve_cost(self):
        self.client.post('/harvests/add',data=self.form())
        h=db.query('SELECT * FROM harvests',one=True)
        for path in ['/harvests/%s/edit'%h['id'],'/activities/%s/edit'%h['activity_id']]:
            self.client.post(path,data=self.form(threshing_cost='50'))
            self.assertEqual(financial_summary()['total_exp'],100)
            html=self.client.get(path).get_data(as_text=True)
            self.assertIn('name="threshing_cost"',html)
        data=self.form();del data['threshing_cost']
        self.client.post('/harvests/%s/edit'%h['id'],data=data)
        self.assertEqual(financial_summary()['thresh_exp'],50)
        self.client.post('/activities/%s/delete'%h['activity_id'])
        self.assertEqual(financial_summary()['total_exp'],0)
    def test_invalid_cost_rejected_and_export_includes_breakdown(self):
        for bad in ['-1','NaN','1.001']:
            self.client.post('/harvests/add',data=self.form(threshing_cost=bad))
        self.assertEqual(db.query('SELECT * FROM harvests'),[])
        self.client.post('/harvests/add',data=self.form())
        rows=list(csv.DictReader(io.StringIO(self.client.get('/reports/export/harvests.csv').get_data(as_text=True))))
        self.assertEqual(float(rows[0]['Defruiting (GHS)']),12.5)
        self.assertEqual(float(rows[0]['Total Labour (GHS)']),62.5)
