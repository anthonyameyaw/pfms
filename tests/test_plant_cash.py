import unittest
import test_financials as fixture
from database import db
from routes.plant import _cash_balance
class CashTests(unittest.TestCase):
    setUp=fixture.FinancialTests.setUp
    context=fixture.FinancialTests.context
    processing_form=fixture.FinancialTests.processing_form
    def test_unknown_zero_partial_and_excess_add_edit(self):
        self.client.post('/plant/run/add',data=self.processing_form(cash_collected=''))
        run=db.query('SELECT * FROM processing_runs',one=True)
        self.assertIsNone(run['cash_collected']);self.assertIsNone(run['cash_outstanding'])
        self.assertIn('Not recorded',self.client.get('/plant/').get_data(as_text=True))
        c=self.context('plant','/plant/')
        self.assertEqual(c['totals']['unknown_cash_count'],1)
        month=next(m for m in c['monthly_chart'] if m['month']=='2026-10')
        self.assertIsNone(month['cash_collected'])
        for cash,balance in [('0',160),('60.01',99.99),('160',0),('180',0),('',None)]:
            self.client.post(f"/plant/run/{run['id']}/edit",data=self.processing_form(cash_collected=cash))
            saved=db.query('SELECT * FROM processing_runs',one=True)
            self.assertEqual(saved['cash_outstanding'],balance)
            if cash=='180':self.assertEqual(self.context('plant','/plant/')['totals']['overpaid'],20)
        self.assertEqual(_cash_balance(1,.99),.01)
        self.assertIsNone(_cash_balance(100,None))
