import unittest
import test_financials as base
from database import db

class HarvestYieldTests(unittest.TestCase):
    setUp=base.FinancialTests.setUp
    context=base.FinancialTests.context
    def test_uses_actual_bunch_count(self):
        db.execute("INSERT INTO harvests(farm_id,date,bunches_harvested,gallons_produced,husks_processed) VALUES(4,'2026-10-01',310,20,1)")
        rows=self.context('finances','/finances/')['harvest_analytics']
        self.assertEqual(rows[0]['bunches_per_gallon'],15.5)
        text=self.client.get('/finances/').get_data(as_text=True)
        self.assertIn('Bunches per gallon',text)
        self.assertIn('15.50',text)
    def test_unknown_count_and_unprocessed_harvest(self):
        db.execute("INSERT INTO harvests(farm_id,date,bunches_harvested,gallons_produced,husks_processed) VALUES(4,'2026-10-01',0,20,1)")
        db.execute("INSERT INTO harvests(farm_id,date,bunches_harvested,gallons_produced,husks_processed) VALUES(6,'2026-10-01',100,10,0)")
        rows=self.context('finances','/finances/')['harvest_analytics']
        self.assertEqual(len(rows),1)
        self.assertIsNone(rows[0]['bunches_per_gallon'])
