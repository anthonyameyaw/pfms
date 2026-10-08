import unittest
from decimal import Decimal
import test_financials as base
from database import db
from database.validation import SPECS, numeric
from routes.plant import _calc_run
from routes.investors import _calc_expected

class ValidationTests(unittest.TestCase):
    setUp=base.FinancialTests.setUp
    def snapshot(self):
        tables=db.query("SELECT name FROM sqlite_master WHERE type='table'")
        return {r['name']:[tuple(x) for x in db.query('SELECT * FROM "'+r['name']+'" ORDER BY rowid')] for r in tables}
    def reject(self,path,data):
        before=self.snapshot()
        response=self.client.post(path,data=data)
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.snapshot(),before,path)
        with self.client.session_transaction() as session:
            self.assertTrue(any(level=='error' for level,_ in session.get('_flashes',[])),path)
            session.pop('_flashes',None)
    def test_invalid_numbers_do_not_write_to_remaining_routes(self):
        cases=[('/activities/add',dict(farm_id='4',date='2026-10-01',activity_type='Weeding'),'labour_cost'),
               ('/transport/add',dict(date='2026-10-01',transport_type='Pickup'),'fuel_cost'),
               ('/transport/maintenance/add',dict(date='2026-10-01'),'cost'),
               ('/plant/expenses/add',dict(date='2026-10-01',category='Other'),'amount'),
               ('/prices/add',dict(date='2026-10-01',product='Palm Oil',negotiation_outcome='Accepted'),'price_offered'),
               ('/storage/log-quality',dict(date='2026-10-01'),'fresh_gallons'),
               ('/storage/revalue',dict(date='2026-10-01'),'new_price'),
               ('/farms/add',dict(name='Test',crop_type='Oil Palm',status='Active'),'size_acres')]
        for path,data,field in cases:
            for bad in ['-1','NaN','inf','abc','0.001','1e999']:
                with self.subTest(path=path,bad=bad):self.reject(path,dict(data,**{field:bad}))
    def test_invalid_dates_enums_and_foreign_keys(self):
        self.reject('/activities/add',dict(farm_id='4',date='2026-02-30',activity_type='Weeding'))
        self.reject('/activities/add',dict(farm_id='999999',date='2026-10-01',activity_type='Weeding'))
        self.reject('/activities/add',dict(farm_id='4',date='2026-10-01',activity_type='Bad'))
        self.reject('/activities/add',dict(farm_id='4',date='2026-10-01',activity_type='Weeding',num_labourers='1.5'))
        self.reject('/plant/run/add',dict(date='not-a-date',own_farms_gallons_input='2'))
        self.reject('/transport/add',dict(date='2026-10-01',transport_type='Bad'))
    def test_repayment_ownership_dates_and_investment_validation(self):
        a=db.execute("INSERT INTO investors(name) VALUES('A')");b=db.execute("INSERT INTO investors(name) VALUES('B')")
        inv=db.execute("INSERT INTO investments(investor_id,date,amount) VALUES(?,'2026-10-01',100)",(a,))
        self.reject('/investors/%s/log-return'%b,dict(investment_id=str(inv),date='2026-10-02',amount='10'))
        self.reject('/investors/%s/log-return'%a,dict(investment_id=str(inv),date='2026-09-30',amount='10'))
        self.reject('/investors/%s/add-investment'%a,dict(date='2026-10-01',amount='-100'))
        self.reject('/investors/%s/add-investment'%a,dict(date='2026-10-01',amount='100',return_date='2026-09-01'))
        self.reject('/investors/investment/%s/edit'%inv,dict(date='2026-10-01',amount='nan'))
    def test_valid_submissions_and_zero_costs_still_save(self):
        self.client.post('/activities/add',data=dict(farm_id='4',date='2026-10-01',activity_type='Weeding',num_labourers='2',labour_cost='12.50',materials_cost='0'))
        self.assertEqual(db.query('SELECT total_cost FROM activities',one=True)['total_cost'],12.5)
        self.client.post('/transport/add',data=dict(date='2026-10-01',transport_type='Pickup',fuel_cost='.50',driver_pay='0'))
        self.assertEqual(db.query('SELECT total_cost FROM transport_logs',one=True)['total_cost'],.5)
        self.client.post('/transport/maintenance/add',data=dict(date='2026-10-01',cost='0'))
        self.assertEqual(db.query('SELECT cost FROM pickup_maintenance',one=True)['cost'],0)
    def test_invalid_edit_preserves_existing_values(self):
        aid=db.execute("INSERT INTO activities(farm_id,date,activity_type,labour_cost) VALUES(4,'2026-10-01','Weeding',50)")
        self.reject('/activities/%s/edit'%aid,dict(farm_id='4',date='2026-10-01',activity_type='Weeding',labour_cost='-20'))
    def test_rounding_and_extreme_numbers(self):
        self.assertEqual(_calc_expected('1','0.5'),1.01)
        run=_calc_run('0','0','0.05')
        self.assertEqual(run['operator_pay'],.02)
        self.assertEqual(Decimal(str(run['operator_pay']))+Decimal(str(run['company_revenue'])),Decimal(str(run['net_revenue'])))
        self.reject('/storage/log-purchase',dict(date='2026-10-01',gallons='999999999999',price_per_gallon='999999999999'))
        with self.assertRaises(ValueError):numeric('9'*1000,'amount')
    def test_all_form_save_endpoints_are_registered(self):
        for rule in base.app.url_map.iter_rules():
            if 'POST' in rule.methods and 'delete' not in rule.endpoint:
                self.assertIn(rule.endpoint,SPECS)

    def test_valid_investment_and_repayment(self):
        aid=db.execute("INSERT INTO investors(name) VALUES('A')")
        self.client.post('/investors/%s/add-investment'%aid,data=dict(date='2026-10-01',amount='100',return_pct='10',investment_type='Cash'))
        inv=db.query('SELECT * FROM investments',one=True)
        self.assertEqual(inv['expected_return'],110)
        self.client.post('/investors/%s/log-return'%aid,data=dict(date='2026-10-02',amount='10',investment_id=str(inv['id'])))
        self.assertEqual(db.query('SELECT amount FROM investor_returns',one=True)['amount'],10)

    def test_invalid_contribution_number_rejected_before_decimal_arithmetic(self):
        self.reject('/plant/run/add',dict(date='2026-10-01',own_farms_gallons_input='2',contributing_farm_ids='4',contributing_bunches='10',contributing_gallons='9'*1000))

    def test_repayment_requires_investment(self):
        investor=db.execute("INSERT INTO investors(name) VALUES('Repayment test')")
        inv=db.execute("INSERT INTO investments(investor_id,date,amount) VALUES(?,'2026-10-01',100)",(investor,))
        path=f'/investors/{investor}/log-return'
        for value in [None,'','   ']:
            data=dict(date='2026-10-02',amount='25')
            if value is not None:data['investment_id']=value
            self.reject(path,data)
        page=self.client.get(path).get_data(as_text=True)
        self.assertIn('name="investment_id" required',page)
        self.assertNotIn('General payment',page)
        self.client.post(path,data=dict(date='2026-10-02',amount='25',investment_id=str(inv)))
        from routes.investors import _get_investments
        investment=_get_investments(investor)[0]
        self.assertEqual(investment['paid'],25)
        self.assertEqual(investment['outstanding'],75)
