"""Regression checks for finding 1. Runs only against disposable databases.
Run: python3 -m unittest discover -s tests -v
"""
import importlib
import shutil
import sqlite3
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TEMP = tempfile.TemporaryDirectory(prefix='pfms-financial-tests-')
DB = Path(TEMP.name) / 'test.db'
with sqlite3.connect(DB) as conn:
    conn.executescript((ROOT/'tests/financial_fixture.sql').read_text())
    conn.executescript((ROOT/'database/seed.sql').read_text())
from database import db
# Set test DB before app import, because app initializes its DB at import time.
db.DB_PATH = str(DB)
from app import app
from flask.testing import FlaskClient
import secrets

class FormClient(FlaskClient):
    """Submit normal test forms with the session token, as the browser does."""
    def open(self, *args, **kwargs):
        if kwargs.get("method", "GET").upper() == "POST":
            with self.session_transaction() as session:
                token=session.setdefault("_csrf_token",secrets.token_hex(32))
            data=kwargs.get("data", {}).copy()
            data.setdefault("csrf_token",token)
            kwargs["data"]=data
        return super().open(*args, **kwargs)

app.test_client_class=FormClient
from database.financials import financial_summary, monthly_financials, farm_financials
app.config.update(TESTING=True)
BASE = Path(TEMP.name) / 'empty.db'
shutil.copy2(DB, BASE)

class AuditDate(date):
    @classmethod
    def today(cls):
        return cls(2026, 10, 2)

class FinancialTests(unittest.TestCase):
    def setUp(self):
        shutil.copy2(BASE, DB)
        db.DB_PATH = str(DB)
        self.client = app.test_client()
        for name in ['dashboard','farms','plant','harvests','finances','reports','storage','investors']:
            clock_patch=patch('routes.'+name+'.business_today',return_value=AuditDate.today())
            clock_patch.start();self.addCleanup(clock_patch.stop)
        for name in ['dashboard', 'finances', 'farms', 'reports', 'plant']:
            p = patch('routes.'+name+'.date', AuditDate)
            p.start(); self.addCleanup(p.stop)

    def context(self, module, path, **args):
        mod = importlib.import_module('routes.'+module)
        with app.test_request_context(path), patch.object(mod, 'render_template', side_effect=lambda _, **kw: kw):
            endpoint, routeargs = app.url_map.bind('').match(path.split('?')[0])
            return app.view_functions[endpoint](**routeargs)

    def seed(self):
        db.execute("""INSERT INTO harvests(farm_id,date,bunches_harvested,gallons_produced,
            husks_processed,harvesting_cost,threshing_cost)
            VALUES (4,'2026-09-15',100,10,1,100,20)""")
        db.execute("INSERT INTO activities(farm_id,date,activity_type,labour_cost,materials_cost) VALUES(4,'2026-09-15','Weeding',30,10)")
        db.execute("INSERT INTO storage_transactions(date,transaction_type,gallons,total_amount) VALUES('2026-09-15','Sale',2,1000)")
        # Linked harvest labour must not be included twice.
        db.execute("INSERT INTO activities(farm_id,date,activity_type,labour_cost) VALUES(4,'2026-09-15','Harvesting',100)")
        db.execute("INSERT INTO farm_expenses(farm_id,date,category,amount) VALUES(4,'2026-09-15','Other',50)")
        db.execute("INSERT INTO transport_logs(farm_id,date,transport_type,rental_cost) VALUES(4,'2026-09-15','Tricycle',60)")
        db.execute("INSERT INTO transport_logs(date,transport_type,rental_cost) VALUES('2026-09-15','Tricycle',7)")
        db.execute("INSERT INTO pickup_maintenance(date,cost) VALUES('2026-09-15',70)")
        db.execute("INSERT INTO processing_runs(date,gross_revenue,outside_farmer_fees,electricity_cost,operator_pay) VALUES('2026-09-15',300,300,80,90)")
        db.execute("INSERT INTO plant_expenses(date,category,amount) VALUES('2026-09-15','Other',100)")
        db.execute("INSERT INTO farm_income(farm_id,date,income_type,quantity,unit_price) VALUES(4,'2026-09-15','Other',1,200)")
        db.execute("INSERT INTO storage_transactions(date,transaction_type,gallons,total_amount) VALUES('2026-09-15','Purchase',10,110)")
        db.execute("INSERT INTO storage_transactions(date,transaction_type,gallons,total_amount) VALUES('2026-09-15','Sale',2,400)")
        # Non-financial changes must never count as sales/purchases.
        db.execute("INSERT INTO storage_transactions(date,transaction_type,gallons,total_amount) VALUES('2026-09-15','Revaluation',0,9999)")

    def test_internal_fees_are_plant_revenue_and_eliminated_on_consolidation(self):
        for day, own, outside in [('2026-09-01',400,200),('2026-10-01',160,0),('2026-10-02',0,80)]:
            db.execute("INSERT INTO processing_runs(date,gross_revenue,outside_farmer_fees,electricity_cost,operator_pay) VALUES(?,?,?,?,?)",(day,own+outside,outside,60,102))
        s = financial_summary()
        plant = financial_summary(scope='plant')
        farms = financial_summary(scope='farms')
        self.assertEqual((s['total_income'],s['total_exp']),(280,486))
        self.assertEqual((plant['total_income'],plant['total_exp']),(840,486))
        self.assertEqual(farms['internal_processing_exp'],560)
        self.assertEqual(plant['net']+farms['net'],s['net'])
        self.assertEqual(financial_summary('2026-09-01','2026-09-30')['unallocated_processing_fees'],400)
        self.assertEqual([x['income'] for x in monthly_financials('2026-09-01','2026-10-02')],[200,80])
        self.assertEqual([x['income'] for x in monthly_financials('2026-09-01','2026-10-02',scope='plant')],[600,240])
        f=self.context('finances','/finances/')
        self.assertEqual(f['plant_income'],840)
        self.assertEqual(f['total_farm_expenses'],560)
        self.assertEqual(financial_summary(farm_id=4)['total_exp'],0)

    def processing_form(self, **overrides):
        form = dict(date='2026-10-01',own_farms_gallons_input='4',
            outside_farmers_gallons_input='0',outside_farmer_fees='0',
            own_farms_bunches='78',outside_farmers_bunches='0',cash_collected='160',
            contributing_farm_ids='4',contributing_bunches='',contributing_gallons='')
        form.update(overrides)
        return form

    def test_selected_farm_without_bunches_saves_and_edit_reloads(self):
        result=self.client.post('/plant/run/add',data=self.processing_form())
        self.assertEqual(result.status_code,302)
        link=db.query('SELECT * FROM processing_run_farms',one=True)
        self.assertEqual((link['farm_id'],link['gallons_contributed']),(4,4))
        run_id=link['run_id']
        html=self.client.get('/plant/run/%s/edit'%run_id).get_data(as_text=True)
        self.assertIn('value="4" selected',html)
        self.assertIn('value="4.0"',html)
        self.assertEqual(financial_summary(farm_id=4)['internal_processing_exp'],160)
        self.assertEqual(financial_summary()['unallocated_processing_fees'],0)
        self.assertEqual(financial_summary()['total_income'],0)
        f=self.context('farms','/farms/4')
        self.assertEqual(f['total_expenses'],160)
        self.assertEqual(sum(x['total'] for x in f['exp_by_cat']),160)
        row=next(x for x in farm_financials() if x['id']==4)
        self.assertEqual(row['processing_cost'],160)
        self.client.post('/plant/run/%s/edit'%run_id,data=self.processing_form(contributing_farm_ids='6'))
        self.assertEqual(financial_summary(farm_id=4)['total_exp'],0)
        self.assertEqual(financial_summary(farm_id=6)['total_exp'],160)
        self.client.post('/plant/run/%s/delete'%run_id)
        self.assertEqual(len(db.query('SELECT * FROM processing_run_farms')),0)
        self.assertEqual(financial_summary(farm_id=6)['total_exp'],0)

    def test_split_farms_and_rounding_reconcile(self):
        from werkzeug.datastructures import MultiDict
        form=MultiDict(self.processing_form(own_farms_gallons_input='9.5'))
        form.setlist('contributing_farm_ids',['4','6'])
        form.setlist('contributing_bunches',['',''])
        form.setlist('contributing_gallons',['3','6.5'])
        self.client.post('/plant/run/add',data=form)
        self.assertEqual(financial_summary(farm_id=4)['total_exp'],120)
        self.assertEqual(financial_summary(farm_id=6)['total_exp'],260)
        self.assertEqual(financial_summary()['unallocated_processing_fees'],0)
        self.assertEqual(monthly_financials('2026-10-01','2026-10-31',farm_id=6)[0]['expenses'],260)
        # Historical edited fee: allocation rounding must still sum exactly.
        db.execute('UPDATE processing_runs SET gross_revenue=1.01')
        self.assertEqual(round(sum(financial_summary(farm_id=f)['total_exp'] for f in (4,6)),2),1.01)
        self.assertEqual(financial_summary()['unallocated_processing_fees'],0)

    def test_invalid_contributions_rejected_without_partial_run(self):
        from werkzeug.datastructures import MultiDict
        for ids,gallons in [(['4','4'],['2','2']),(['4','6'],['1','1']),(['999'],['4']),(['4','6'],['',''])]:
            form=MultiDict(self.processing_form())
            form.setlist('contributing_farm_ids',ids)
            form.setlist('contributing_bunches',['']*len(ids))
            form.setlist('contributing_gallons',gallons)
            self.client.post('/plant/run/add',data=form)
            self.assertEqual(len(db.query('SELECT * FROM processing_runs')),0)
        with patch('routes.plant.save_contributions',side_effect=sqlite3.IntegrityError('simulated link failure')):
            with self.assertRaises(sqlite3.IntegrityError):
                self.client.post('/plant/run/add',data=self.processing_form())
        self.assertEqual(len(db.query('SELECT * FROM processing_runs')),0)
        self.client.post('/plant/run/add',data=self.processing_form())
        row=dict(db.query('SELECT * FROM processing_runs',one=True))
        with patch('routes.plant.save_contributions',side_effect=sqlite3.IntegrityError('simulated link failure')):
            with self.assertRaises(sqlite3.IntegrityError):
                self.client.post('/plant/run/%s/edit'%row['id'],data=self.processing_form(own_farms_gallons_input='5'))
        self.assertEqual(dict(db.query('SELECT * FROM processing_runs',one=True)),row)

    def test_legacy_foreign_key_repair_preserves_links_and_is_idempotent(self):
        from database.processing import migrate_processing_farms
        c=sqlite3.connect(':memory:')
        c.executescript("""CREATE TABLE processing_runs(id INTEGER PRIMARY KEY);
            CREATE TABLE farms(id INTEGER PRIMARY KEY);
            INSERT INTO processing_runs VALUES(7); INSERT INTO farms VALUES(4);
            CREATE TABLE processing_run_farms(id INTEGER PRIMARY KEY,run_id INTEGER REFERENCES processing_runs_old(id),farm_id INTEGER REFERENCES farms(id),bunches_contributed INTEGER);
            INSERT INTO processing_run_farms VALUES(3,7,4,100);""")
        c.execute('PRAGMA foreign_keys=ON')
        with c:migrate_processing_farms(c)
        with c:migrate_processing_farms(c)
        self.assertEqual(c.execute('SELECT * FROM processing_run_farms').fetchall(),[(3,7,4,100,None)])
        self.assertEqual(c.execute('PRAGMA foreign_key_check').fetchall(),[])
        c.execute('DELETE FROM processing_runs WHERE id=7')
        self.assertEqual(c.execute('SELECT * FROM processing_run_farms').fetchall(),[])
        c.close()

    def test_all_sources_exactly_once(self):
        self.seed()
        s = financial_summary()
        self.assertEqual(s['total_income'], 1900)
        self.assertEqual(s['total_exp'], 727)
        self.assertEqual(s['net'], 1173)
        self.assertEqual(sum(x['value'] for x in s['income_items']), 1900)
        self.assertEqual(sum(x['value'] for x in s['expense_items']), 727)

    def test_screens_and_chart_reconcile(self):
        self.seed()
        d = self.context('dashboard','/')
        f = self.context('finances','/finances/')
        r = self.context('reports','/reports/')['summary']
        self.assertEqual((d['alltime_income'],d['alltime_expenses'],d['alltime_net']), (1900,727,1173))
        self.assertEqual((f['total_income'],f['total_expenses'],f['total_net']), (1900,727,1173))
        self.assertEqual((r['total_income'],r['total_exp'],r['net']), (1900,727,1173))
        self.assertEqual(d['monthly_chart'],f['monthly_chart'])
        self.assertEqual(sum(x['income'] for x in f['monthly_chart']),1900)
        self.assertEqual(sum(x['expenses'] for x in f['monthly_chart']),727)
        self.assertEqual((f['ytd_income'],f['ytd_exp']),(1900,727))

    def test_farm_scope_and_components_reconcile(self):
        self.seed()
        f = self.context('farms','/farms/4')
        row = next(x for x in farm_financials() if x['id']==4)
        self.assertEqual((row['income'],row['expenses'],row['net']),(200,270,-70))
        self.assertEqual((f['total_income'],f['total_expenses'],f['total_net']),(200,270,-70))
        self.assertEqual(f['farm_exp_total']+f['harvest_exp_total']+f['transport_exp_total'],270)
        self.assertEqual(sum(x['total'] for x in f['exp_by_cat']),270)
        self.assertEqual(sum(x['expenses'] for x in f['monthly_chart']),270)
        self.assertEqual(row['gallons_produced'],10)

    def test_purchase_expense_stock_and_sale_revenue(self):
        from routes.storage import _current_stock
        result = self.client.post('/storage/log-purchase', data={'date':'2026-09-01','gallons':'10','price_per_gallon':'300'})
        self.assertEqual(result.status_code,302)
        self.assertEqual(_current_stock(),10)
        self.assertEqual(financial_summary('2026-09-01','2026-09-01')['total_exp'],3000)
        result = self.client.post('/storage/log-sale', data={'date':'2026-09-02','gallons':'4','price_per_gallon':'400'})
        self.assertEqual(result.status_code,302)
        self.assertEqual(_current_stock(),6)
        s = financial_summary()
        self.assertEqual((s['total_income'],s['total_exp'],s['net']),(1600,3000,-1400))
        f = self.context('finances','/finances/')
        self.assertEqual((f['ytd_income'],f['ytd_exp']),(1600,3000))
        r = self.context('reports','/reports/?date_from=2026-09-02&date_to=2026-09-02')['summary']
        self.assertEqual((r['total_income'],r['total_exp']),(1600,0))

    def test_inclusive_dates_empty_months_future_ytd(self):
        for day,amount in [('2025-12-31',1),('2026-01-01',2),('2026-09-01',3),('2026-09-30',4),('2026-10-02',5),('2026-10-03',6)]:
            db.execute("INSERT INTO pickup_maintenance(date,cost) VALUES(?,?)",(day,amount))
        self.assertEqual(financial_summary('2026-09-01','2026-09-30')['total_exp'],7)
        self.assertEqual(financial_summary('2026-01-01','2026-10-02')['total_exp'],14)
        m = monthly_financials('2026-08-01','2026-10-02')
        self.assertEqual([r['expenses'] for r in m],[0,7,5])
        self.assertEqual(self.context('finances','/finances/')['ytd_exp'],14)
        d = self.context('dashboard','/')
        self.assertEqual(d['monthly_expenses'],5)
        self.assertEqual(d['expenses_pct'],66.7)  # Oct 1–2 versus Sep 1–2.

    def test_pages_pdfs_and_applied_period_render(self):
        self.seed()
        for path in ['/','/finances/','/farms/4','/reports/','/reports/?date_from=2026-09-01&date_to=2026-09-30','/reports/pdf/all-farms','/reports/pdf/farm/4']:
            with self.subTest(path=path):
                result=self.client.get(path)
                self.assertEqual(result.status_code,200)
                if '/pdf/' in path:self.assertTrue(result.data.startswith(b'%PDF'))
        text=self.client.get('/reports/?date_from=2026-10-01&date_to=2026-10-02').get_data(as_text=True)
        self.assertIn('value="2026-10-01"',text)
        self.assertIn('Apply Period',text)
        self.assertNotIn('GHS 1,900.00',text)

    def test_financial_csv_uses_applied_period(self):
        import csv, io
        self.seed()
        response = self.client.get('/reports/export/financial-summary.csv?date_from=2026-09-01&date_to=2026-09-30')
        rows = list(csv.reader(io.StringIO(response.get_data(as_text=True))))
        self.assertEqual(rows[-3:], [['Total','Income','1900.00'], ['Total','Expenses','727.00'], ['Total','Net','1173.00']])
        response = self.client.get('/reports/export/financial-summary.csv?date_from=2026-10-01')
        self.assertIn('Total,Net,0.00', response.get_data(as_text=True))

    def test_fractional_money_reconciles_across_months(self):
        for day in ['2026-08-01','2026-09-01']:
            db.execute("INSERT INTO storage_transactions(date,transaction_type,gallons,total_amount) VALUES(?,'Purchase',0.1,0.105)",(day,))
            db.execute("INSERT INTO plant_expenses(date,category,amount) VALUES(?,'Other',0.105)",(day,))
        s=financial_summary()
        monthly=monthly_financials('2026-08-01','2026-09-30')
        self.assertEqual(s['total_exp'],0.44)
        self.assertAlmostEqual(sum(m['expenses'] for m in monthly),s['total_exp'])
        self.assertAlmostEqual(sum(i['value'] for i in s['expense_items']),s['total_exp'])

    def test_plant_scope_and_expense_only_month(self):
        self.seed()
        db.execute("INSERT INTO plant_expenses(date,category,amount) VALUES('2026-08-01','Other',12.50)")
        p=self.context('plant','/plant/')
        self.assertEqual((p['all_income'],p['all_expenses'],p['all_net']),(300,282.5,17.5))
        august=next(m for m in p['monthly_chart'] if m['month']=='2026-08')
        self.assertEqual((august['income'],august['expenses'],august['net']),(0,12.5,-12.5))
        self.assertEqual(sum(m['expenses'] for m in p['monthly_chart']),p['all_expenses'])
        for path in ['/plant/','/reports/pdf/plant']:
            self.assertEqual(self.client.get(path).status_code,200)

    def test_snapshot_is_read_only_for_reporting(self):
        self.seed()
        before = DB.read_bytes()
        for path in ['/','/finances/','/farms/4','/reports/','/reports/pdf/all-farms']:
            self.assertEqual(self.client.get(path).status_code,200)
        self.assertEqual(DB.read_bytes(),before)

if __name__ == '__main__':
    unittest.main()
