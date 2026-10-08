import unittest
import test_financials as base
from database import db
from routes.storage import _current_stock

class ProcessingDateTests(unittest.TestCase):
    setUp=base.FinancialTests.setUp
    processing_form=base.FinancialTests.processing_form
    def harvest(self):
        return dict(farm_id='4',date='2026-09-24',bunches_harvested='80',harvester_pay='240',collector_pay='200',husks_processed='1',gallons_produced='4',processing_date='')
    def test_harvest_uses_matching_plant_date_and_edits_follow(self):
        self.client.post('/plant/run/add',data=self.processing_form())
        run=db.query('SELECT id FROM processing_runs',one=True)['id']
        self.client.post('/harvests/add',data=self.harvest())
        h=db.query('SELECT * FROM harvests',one=True)
        self.assertEqual((h['processing_date'],h['processing_run_id']),('2026-10-01',run))
        self.client.post('/plant/run/%s/edit'%run,data=self.processing_form(date='2026-10-02'))
        self.assertEqual(db.query('SELECT processing_date FROM harvests',one=True)['processing_date'],'2026-10-02')
        self.assertEqual(_current_stock(),4)
    def test_ambiguous_run_does_not_guess(self):
        for _ in range(2):self.client.post('/plant/run/add',data=self.processing_form())
        response=self.client.post('/harvests/add',data=self.harvest(),follow_redirects=True)
        self.assertIn('No unique matching processing run',response.get_data(as_text=True))
        self.assertEqual(db.query('SELECT * FROM harvests'),[])
    def test_plant_edit_rolls_back_if_it_would_put_sale_before_production(self):
        self.client.post('/plant/run/add',data=self.processing_form())
        run=db.query('SELECT id FROM processing_runs',one=True)['id']
        self.client.post('/harvests/add',data=self.harvest())
        self.client.post('/storage/log-sale',data=dict(date='2026-10-01',gallons='4',price_per_gallon='400',quality_type='Fresh'))
        self.client.post('/plant/run/%s/edit'%run,data=self.processing_form(date='2026-10-02'))
        self.assertEqual(db.query('SELECT date FROM processing_runs',one=True)['date'],'2026-10-01')
        self.assertEqual(db.query('SELECT processing_date FROM harvests',one=True)['processing_date'],'2026-10-01')
    def test_deleting_run_clears_derived_date_and_keeps_production(self):
        self.client.post('/plant/run/add',data=self.processing_form())
        run=db.query('SELECT id FROM processing_runs',one=True)['id']
        self.client.post('/harvests/add',data=self.harvest())
        self.client.post('/plant/run/%s/delete'%run)
        h=db.query('SELECT * FROM harvests',one=True)
        self.assertIsNone(h['processing_date']);self.assertIsNone(h['processing_run_id'])
        self.assertEqual(_current_stock(),4)
