import unittest
import test_financials as fixture
from database import db
from routes.investors import _get_investments

class InvestmentStatusTests(unittest.TestCase):
    setUp=fixture.FinancialTests.setUp
    def seed(self,status='Active',paid=0,pct=0,equity=0):
        investor=db.execute("INSERT INTO investors(name) VALUES('Status test')")
        inv=db.execute("INSERT INTO investments(investor_id,date,amount,return_pct,equity_pct,return_date,status) VALUES(?,'2026-01-01',100,?,?,'2026-09-01',?)",(investor,pct,equity,status))
        if paid:db.execute("INSERT INTO investor_returns(investor_id,investment_id,date,amount) VALUES(?,?,'2026-09-01',?)",(investor,inv,paid))
        return investor,inv
    def edit(self,inv,amount='100',pct='0',status='Active'):
        return self.client.post(f'/investors/investment/{inv}/edit',data=dict(date='2026-01-01',amount=amount,return_pct=pct,status=status,return_date='2026-09-01',investment_type='Cash'))
    def test_zero_return_does_not_use_legacy_percentage(self):
        investor,inv=self.seed(pct=0,equity=20)
        self.assertEqual(_get_investments(investor)[0]['expected'],100)
        db.execute('UPDATE investments SET return_pct=NULL WHERE id=?',(inv,))
        self.assertEqual(_get_investments(investor)[0]['expected'],120)
    def test_unpaid_completion_cannot_hide_overdue_balance(self):
        investor,inv=self.seed(status='Completed',paid=20)
        item=_get_investments(investor)[0]
        self.assertEqual(item['status'],'Active')
        self.assertTrue(item['is_overdue'])
        self.edit(inv,status='Completed')
        self.assertEqual(db.query('SELECT status FROM investments WHERE id=?',(inv,),one=True)['status'],'Active')
    def test_edit_reopens_and_resettles_investment(self):
        investor,inv=self.seed(status='Completed',paid=100)
        self.edit(inv,amount='150')
        item=_get_investments(investor)[0]
        self.assertEqual((item['status'],item['outstanding']),('Active',50))
        self.assertTrue(item['is_overdue'])
        self.edit(inv,amount='100')
        self.assertEqual(db.query('SELECT status FROM investments WHERE id=?',(inv,),one=True)['status'],'Completed')
        self.edit(inv,pct='10')
        self.assertEqual(_get_investments(investor)[0]['status'],'Active')
    def test_defaulted_stays_until_fully_paid(self):
        investor,inv=self.seed(status='Defaulted',paid=20)
        for amount,status in [('30','Defaulted'),('50','Completed')]:
            self.client.post(f'/investors/{investor}/log-return',data=dict(date='2026-10-02',amount=amount,investment_id=str(inv)))
            self.assertEqual(db.query('SELECT status FROM investments WHERE id=?',(inv,),one=True)['status'],status)
    def test_delete_preserves_payment_history_and_handles_missing(self):
        investor,inv=self.seed(paid=20)
        response=self.client.post(f'/investors/investment/{inv}/delete',follow_redirects=True)
        self.assertEqual(response.status_code,200)
        self.assertIn('cannot be deleted because it has repayment history',response.get_data(as_text=True))
        self.assertEqual(db.query('SELECT COUNT(*) c FROM investor_returns',one=True)['c'],1)
        self.assertIsNotNone(db.query('SELECT id FROM investments WHERE id=?',(inv,),one=True))
        other,empty=self.seed()
        self.client.post(f'/investors/investment/{empty}/delete')
        self.assertIsNone(db.query('SELECT id FROM investments WHERE id=?',(empty,),one=True))
        self.assertEqual(self.client.post(f'/investors/investment/{empty}/delete',follow_redirects=True).status_code,200)
