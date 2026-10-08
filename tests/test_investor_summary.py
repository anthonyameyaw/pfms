import unittest
import test_financials as fixture
from database import db
from routes.investors import _get_investments,_investor_summaries
class InvestorSummaryTests(unittest.TestCase):
    setUp=fixture.FinancialTests.setUp
    def test_one_row_and_separate_interest_rates_dates(self):
        investor=db.execute("INSERT INTO investors(name) VALUES('Unique Investor')")
        db.execute("INSERT INTO investments(investor_id,date,amount,return_pct,return_date,status) VALUES(?,'2026-01-01',1000,10,'2026-09-01','Active')",(investor,))
        db.execute("INSERT INTO investments(investor_id,date,amount,return_pct,return_date,status) VALUES(?,'2026-02-01',2000,20,'2026-11-01','Active')",(investor,))
        row=_investor_summaries(db.query('SELECT * FROM investors'),_get_investments())[0]
        self.assertEqual((row['principal'],row['interest'],row['expected'],row['outstanding']),(3000,500,3500,3500))
        self.assertEqual(row['rates'],[10,20]);self.assertEqual(row['next_due'],'2026-09-01')
        page=self.client.get('/investors/').get_data(as_text=True)
        self.assertEqual(page.count('Unique Investor'),1)
        page=self.client.get(f'/investors/{investor}').get_data(as_text=True)
        self.assertIn('Expected interest',page);self.assertIn('Investment history',page)
    def test_zero_rate_and_no_investments(self):
        investor=db.execute("INSERT INTO investors(name) VALUES('Empty')")
        row=_investor_summaries(db.query('SELECT * FROM investors'),[])[0]
        self.assertEqual(row['interest'],0);self.assertIsNone(row['next_due'])
        self.assertEqual(self.client.get(f'/investors/{investor}').status_code,200)
