import csv,io,unittest,zipfile
import test_financials as fixture
from database import db
from database.oil_costs import cost_profile,floor_price

class OilCostTests(unittest.TestCase):
    setUp=fixture.FinancialTests.setUp
    context=fixture.FinancialTests.context
    def test_harvest_costs_exclude_overhead_and_match_output(self):
        harvest=db.execute("INSERT INTO harvests(farm_id,date,processing_date,husks_processed,gallons_produced,harvesting_cost,threshing_cost) VALUES(4,'2026-09-01','2026-09-02',1,10,100,20)")
        db.execute("INSERT INTO harvests(farm_id,date,husks_processed,gallons_produced) VALUES(4,'2026-09-03',0,90)")
        db.execute("INSERT INTO activities(farm_id,date,activity_type,labour_cost) VALUES(4,'2026-09-01','Harvesting',120)")
        db.execute("INSERT INTO activities(farm_id,date,activity_type,labour_cost) VALUES(4,'2026-09-01','Pruning',30)")
        db.execute("INSERT INTO farm_expenses(farm_id,date,category,amount) VALUES(4,'2026-09-01','Other',50)")
        db.execute("INSERT INTO transport_logs(farm_id,date,transport_type,rental_cost) VALUES(4,'2026-09-01','Tricycle',10)")
        run=db.execute("INSERT INTO processing_runs(date,own_farms_gallons,gross_revenue,outside_farmer_fees) VALUES('2026-09-02',10,400,0)")
        db.execute('INSERT INTO processing_run_farms(run_id,farm_id,gallons_contributed) VALUES(?,4,10)',(run,))
        db.execute('UPDATE harvests SET processing_run_id=? WHERE id=?',(run,harvest))
        db.execute('UPDATE transport_logs SET harvest_id=?',(harvest,))
        db.execute("INSERT INTO pickup_maintenance(date,cost) VALUES('2026-09-01',70)")
        db.execute("INSERT INTO storage_transactions(date,transaction_type,gallons,total_amount) VALUES('2026-09-01','Purchase',5,999)")
        p=cost_profile('2026-09-01','2026-09-30');r=next(x for x in p['rows'] if x['id']==4)
        self.assertEqual((r['cost'],r['gallons'],r['unit_cost'],r['pending']),(530,10,53,1))
        self.assertEqual(sum(x['cost'] for x in p['shared']),70)
        h=self.context('finances','/finances/')['harvest_analytics'][0]
        self.assertEqual(h['levelized'],53)
        self.assertEqual(h['total_cost'],530)
        self.assertEqual(self.client.get('/finances/oil-costs').status_code,200)
    def test_weighted_rate_no_output_and_unknown_dates(self):
        for farm,gallons,cost in [(4,10,100),(6,30,600),(5,0,80)]:
            db.execute("INSERT INTO farm_expenses(farm_id,date,category,amount) VALUES(?,'2026-09-01','Other',?)",(farm,cost))
            if gallons:db.execute("INSERT INTO harvests(farm_id,date,husks_processed,gallons_produced) VALUES(?,'2026-09-01',1,?)",(farm,gallons))
            if gallons:db.execute('UPDATE harvests SET harvesting_cost=? WHERE farm_id=?',(cost,farm))
        p=cost_profile('','2026-10-02')
        self.assertEqual(p['unit_cost'],17.5)
        self.assertEqual(p['no_output_cost'],0)
        self.assertEqual(sum(r['unknown_dates'] for r in p['rows']),2)
        self.assertEqual(floor_price(100,3),33.33)
        self.assertIsNone(floor_price(100,0))
    def test_periods_export_and_bad_range(self):
        db.execute("INSERT INTO harvests(farm_id,date,processing_date,husks_processed,gallons_produced) VALUES(4,'2026-08-31','2026-09-02',1,10)")
        self.assertEqual(cost_profile('2026-09-01','2026-09-30')['gallons'],10)
        self.assertEqual(cost_profile('2026-08-01','2026-08-31')['gallons'],0)
        for args in ['date_from=2026-10-03&date_to=2026-10-02','date_to=2027-01-01','date_from=bad']:
            self.assertEqual(self.client.get('/finances/oil-costs?'+args).status_code,400)
        self.assertEqual(self.client.get('/finances/oil-costs?download=csv').status_code,200)
    def test_exports_escape_text_preserve_negative_numbers_and_include_all_tables(self):
        from routes.reports import _csv
        with fixture.app.test_request_context('/'):
            result=_csv('test.csv',['Text','Number'],[[' =SUM(1,2)',-10]])
        row=list(csv.reader(io.StringIO(result.get_data(as_text=True))))[1]
        self.assertEqual(row,["' =SUM(1,2)",'-10'])
        response=self.client.get('/reports/export/all-records.zip')
        self.assertEqual(response.status_code,200)
        with zipfile.ZipFile(io.BytesIO(response.data)) as z:
            for f in ['investments.csv','investor_returns.csv','pruning_batches.csv','storage_transactions.csv','processing_run_farms.csv','README.txt']:self.assertIn(f,z.namelist())
    def test_dashboard_income_reconciles_and_no_misleading_radar(self):
        db.execute("INSERT INTO storage_transactions(date,transaction_type,gallons,total_amount) VALUES('2026-09-01','Sale',1,500)")
        d=self.context('dashboard','/')
        self.assertEqual(d['alltime_farm_income']+d['alltime_plant_income']+d['pooled_income'],d['alltime_income'])
        self.assertNotIn('Farm Comparison Radar',self.client.get('/').get_data(as_text=True))
    def test_plant_income_share_and_chart_do_not_count_fees_twice(self):
        db.execute("INSERT INTO processing_runs(date,gross_revenue,outside_farmer_fees,total_output_litres,electricity_cost,company_revenue) VALUES('2026-09-01',1000,250,250,60,658)")
        c=self.context('plant','/plant/')
        k=next(k for k in c['kpis'] if k['label']=='Outside Farmer Revenue')
        self.assertEqual(k['value'],'25.0%')
        html=self.client.get('/plant/').get_data(as_text=True)
        self.assertNotIn("label: 'Outside Farmer Fees',",html)
        self.assertNotIn('Small batches raise cost',html)
    def test_zero_income_maintenance_has_no_invented_percentage(self):
        db.execute("INSERT INTO plant_expenses(date,amount) VALUES('2026-09-01',100)")
        c=self.context('dashboard','/')
        self.assertIsNone(next(r for r in c['monthly_elec_maint'] if r['month']=='2026-09')['maint_pct'])
    def test_all_updated_pages_render(self):
        for path in ['/','/finances/','/finances/oil-costs','/reports/','/plant/','/labour/','/farms/4']:
            self.assertEqual(self.client.get(path).status_code,200,path)
    def test_empty_month_has_no_production_percentage(self):
        c=self.context('plant','/plant/')
        self.assertIsNone(c['all_own_pct'])
        self.assertTrue(all(m['own_farm_pct'] is None and m['outside_farm_pct'] is None for m in c['monthly_chart']))
        run=db.execute("INSERT INTO processing_runs(date,own_farms_gallons,outside_farmers_gallons,total_output_gallons) VALUES('2026-09-01',10,30,40)")
        db.execute('INSERT INTO processing_run_farms(run_id,farm_id,gallons_contributed) VALUES(?,4,10)',(run,))
        c=self.context('plant','/plant/')
        m=next(m for m in c['monthly_chart'] if m['month']=='2026-09')
        self.assertEqual((m['own_farm_pct'],m['outside_farm_pct']),(25,75))
        empty=next(m for m in c['monthly_chart'] if m['month']=='2026-10')
        self.assertIsNone(empty['own_farm_pct'])
        self.assertIsNone(empty['outside_farm_pct'])
        self.assertEqual(c['monthly_chart'][0]['month'],'2026-09')
        f=next(f for f in c['farm_contributions'] if f['gallons'])
        self.assertEqual(f['share'],25)
        self.assertEqual(c['unallocated_gallons'],0)
        self.assertIn('All farms combined',self.client.get('/finances/').get_data(as_text=True))
