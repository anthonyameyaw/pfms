import unittest
import test_financials as fixture
from database import db

class DashboardLayoutTests(unittest.TestCase):
    setUp = fixture.FinancialTests.setUp
    context = fixture.FinancialTests.context

    def test_stock_and_production_use_processing_date_and_ignore_duplicate_additions(self):
        db.execute("INSERT INTO harvests(farm_id,date,processing_date,bunches_harvested,gallons_produced,husks_processed) VALUES(4,'2026-09-25','2026-10-01',100,10,1)")
        db.execute("INSERT INTO harvests(farm_id,date,processing_date,bunches_harvested,gallons_produced,husks_processed) VALUES(4,'2026-10-02','2026-10-03',100,20,1)")
        for day,kind,gallons in [('2026-10-01','Addition',10),('2026-10-01','Purchase',3),('2026-10-02','Sale',2),('2026-10-03','Sale',5)]:
            db.execute('INSERT INTO storage_transactions(date,transaction_type,gallons,total_amount) VALUES(?,?,?,0)',(day,kind,gallons))
        ctx=self.context('dashboard','/')
        self.assertEqual(ctx['stock_gallons'],11)
        self.assertEqual(sum(r['gallons'] for r in ctx['production']),10)
        self.assertTrue(all(r['date']<='2026-10-02' for r in ctx['recent']))

    def test_unknown_cash_due_investment_and_zero_baseline(self):
        db.execute("INSERT INTO processing_runs(date,gross_revenue,cash_collected,cash_outstanding) VALUES('2026-10-01',80,NULL,NULL)")
        db.execute("INSERT INTO processing_runs(date,gross_revenue,cash_collected,cash_outstanding) VALUES('2026-10-02',80,0,80)")
        investor=db.execute("INSERT INTO investors(name) VALUES('Due investor')")
        db.execute("INSERT INTO investments(investor_id,date,amount,return_pct,return_date,status) VALUES(?,'2026-01-01',1000,10,'2026-10-01','Active')",(investor,))
        ctx=self.context('dashboard','/')
        alerts={r['label']:r['value'] for r in ctx['attention']}
        self.assertEqual(alerts['Plant payments not recorded'],'1 runs')
        self.assertEqual(alerts['Processing fees outstanding'],'GHS 80.00')
        self.assertEqual(alerts['Investor repayments due'],'GHS 1,100.00')
        self.assertIsNone(ctx['income_pct'])
        page=self.client.get('/')
        self.assertEqual(page.status_code,200)
        self.assertIn('No comparison available',page.get_data(as_text=True))

    def test_linked_harvesting_activity_is_not_repeated(self):
        db.execute("INSERT INTO harvests(farm_id,date,bunches_harvested,gallons_produced,husks_processed) VALUES(4,'2026-10-01',100,10,1)")
        db.execute("INSERT INTO activities(farm_id,date,activity_type,labour_cost) VALUES(4,'2026-10-01','Harvesting',100)")
        ctx=self.context('dashboard','/')
        self.assertEqual(len(ctx['recent']),1)
        self.assertEqual(ctx['recent'][0]['kind'],'Harvest')
