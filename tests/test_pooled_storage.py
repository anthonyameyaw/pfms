import json
import sqlite3
import unittest
from unittest.mock import patch
import test_financials as base
from database import db
from database.financials import financial_summary
from database.harvest_workflow import migrate_pooled_storage
from routes.storage import _current_stock

class PooledStorageTests(unittest.TestCase):
    setUp=base.FinancialTests.setUp
    context=base.FinancialTests.context

    def form(self, **changes):
        data=dict(farm_id='4',date='2026-10-01',activity_type='Harvesting',bunches_harvested='10',
            harvester_pay='0',collector_pay='0',num_collectors='0',husks_processed='1',
            gallons_produced='10',processing_date='2026-10-02',transport_mode='Tricycle',tricycle_rent='20')
        data.update(changes);return data

    def test_both_entry_routes_produce_identical_pool_and_no_revenue(self):
        for path,farm in [('/harvests/add','4'),('/activities/add','6')]:
            self.client.post(path,data=self.form(farm_id=farm))
        self.assertEqual(_current_stock(),20)
        self.assertEqual(financial_summary()['total_income'],0)
        self.assertEqual(len(db.query('SELECT * FROM activities')),2)
        self.assertEqual(len(db.query('SELECT * FROM harvests')),2)
        self.assertEqual(len(db.query('SELECT * FROM farm_income')),0)
        rows=db.query('SELECT * FROM harvests')
        self.assertEqual(rows[0]['harvesting_cost'],0)
        self.assertEqual(rows[0]['processing_date'],'2026-10-02')
        self.assertEqual(rows[0]['gallons_sold_income'],0)

    def test_pending_then_processed_and_repeat_save_adds_once(self):
        self.client.post('/harvests/add',data=self.form(husks_processed='0',gallons_produced='999'))
        self.assertEqual(_current_stock(),0)
        h=db.query('SELECT * FROM harvests',one=True)
        for _ in range(2):self.client.post('/activities/%s/edit'%h['activity_id'],data=self.form())
        self.assertEqual(_current_stock(),10)
        self.assertEqual(len(db.query('SELECT * FROM harvests')),1)
        self.assertEqual(len(db.query('SELECT * FROM transport_logs')),1)

    def test_pooled_sale_has_own_date_revenue_and_no_farm_attribution(self):
        self.client.post('/harvests/add',data=self.form())
        self.client.post('/storage/log-sale',data={'date':'2026-10-03','gallons':'4','price_per_gallon':'300'})
        self.assertEqual(_current_stock(),6)
        self.assertEqual(financial_summary('2026-10-02','2026-10-02')['total_income'],0)
        self.assertEqual(financial_summary('2026-10-03','2026-10-03')['total_income'],1200)
        self.assertEqual(financial_summary(farm_id=4)['total_income'],0)
        farms=self.context('storage','/storage/')['farm_stocks']
        self.assertEqual(next(f for f in farms if f['id']==4)['produced'],10)
        self.assertEqual(db.query("SELECT * FROM storage_transactions WHERE transaction_type='Sale'",one=True)['farm_id'],None)

    def test_no_sale_before_processing_or_above_available_stock(self):
        self.client.post('/harvests/add',data=self.form())
        for day,quantity in [('2026-10-01','1'),('2026-10-03','11')]:
            self.client.post('/storage/log-sale',data={'date':day,'gallons':quantity,'price_per_gallon':'300'})
        self.assertEqual(len(db.query('SELECT * FROM storage_transactions')),0)
        self.assertEqual(_current_stock(),10)

    def test_production_reduction_or_delete_cannot_orphan_sales(self):
        self.client.post('/harvests/add',data=self.form())
        h=db.query('SELECT * FROM harvests',one=True)
        self.client.post('/storage/log-sale',data={'date':'2026-10-03','gallons':'8','price_per_gallon':'300'})
        self.client.post('/harvests/%s/edit'%h['id'],data=self.form(gallons_produced='5'))
        self.client.post('/harvests/%s/delete'%h['id'])
        self.client.post('/activities/%s/delete'%h['activity_id'])
        self.assertEqual(_current_stock(),2)
        self.assertEqual(len(db.query('SELECT * FROM harvests')),1)
        self.assertEqual(len(db.query('SELECT * FROM activities')),1)
        self.assertEqual(len(db.query('SELECT * FROM transport_logs')),1)

    def test_different_day_transport_links_stay_separate(self):
        for day,amount in [('2026-10-01','20'),('2026-10-02','30')]:
            self.client.post('/harvests/add',data=self.form(date=day,tricycle_rent=amount))
        rows=db.query('SELECT * FROM harvests ORDER BY id')
        self.client.post('/harvests/%s/edit'%rows[0]['id'],data=self.form(tricycle_rent='0'))
        self.assertEqual(db.query('SELECT SUM(total_cost) AS n FROM transport_logs',one=True)['n'],30)
        self.client.post('/harvests/%s/delete'%rows[0]['id'])
        self.assertEqual(_current_stock(),10)
        self.assertEqual(len(db.query('SELECT * FROM activities')),1)

    def test_legacy_sale_inputs_and_invalid_numbers_are_rejected(self):
        for changes in [{'gallons_sold':'2'},{'gallons_sold_income':'9999'},{'price_per_gallon':'450'},
                        {'gallons_produced':'nan'},{'gallons_produced':'-2'},{'processing_date':'2026-09-30'}]:
            self.client.post('/harvests/add',data=self.form(**changes))
        self.assertEqual(len(db.query('SELECT * FROM harvests')),0)
        self.assertEqual(len(db.query('SELECT * FROM activities')),0)

    def test_atomic_failure_rolls_back_activity_harvest_and_transport(self):
        with patch('database.harvest_workflow.validate_stock',side_effect=ValueError('simulate failure')):
            self.client.post('/harvests/add',data=self.form())
        for table in ['activities','harvests','transport_logs']:
            self.assertEqual(len(db.query('SELECT * FROM '+table)),0)

    def test_legacy_migration_preserves_sales_once_and_flags_estimates(self):
        conn=sqlite3.connect(':memory:');conn.row_factory=sqlite3.Row
        conn.executescript((base.ROOT/'tests/financial_fixture.sql').read_text())
        conn.execute("INSERT INTO harvests(farm_id,date,gallons_produced,gallons_sold,gallons_sold_price,gallons_sold_income,oil_income) VALUES(4,'2026-01-01',10,4,300,1200,1200)")
        conn.execute("INSERT INTO harvests(farm_id,date,gallons_produced,price_per_gallon,oil_income) VALUES(6,'2026-05-14',7,450,3150)")
        with conn:migrate_pooled_storage(conn)
        with conn:migrate_pooled_storage(conn)
        rows=conn.execute("SELECT * FROM storage_transactions WHERE transaction_type='Sale'").fetchall()
        self.assertEqual(len(rows),1)
        self.assertEqual((rows[0]['gallons'],rows[0]['total_amount'],rows[0]['farm_id']),(4,1200,None))
        self.assertEqual(conn.execute('SELECT SUM(gallons_produced),SUM(gallons_sold_income) FROM harvests').fetchone()[:],(17,0))
        archive=conn.execute('SELECT * FROM harvest_sales_archive WHERE harvest_id=2').fetchone()
        self.assertIn('Unconfirmed',archive['review_note'])
        self.assertEqual(json.loads(archive['original_record'])['oil_income'],3150)
        conn.close()

    def test_forms_and_reports_render_without_farm_sale_controls(self):
        self.client.post('/harvests/add',data=self.form())
        h=db.query('SELECT * FROM harvests',one=True)
        for path in ['/harvests/add','/harvests/%s/edit'%h['id'],'/activities/add','/activities/%s/edit'%h['activity_id']]:
            text=self.client.get(path).get_data(as_text=True)
            self.assertIn('name="husks_processed"',text)
            self.assertIn('name="processing_date"',text)
            self.assertNotIn('name="gallons_sold"',text)
            self.assertNotIn('name="price_per_gallon"',text)
        text=self.client.get('/storage/').get_data(as_text=True)
        self.assertIn('Production Contribution',text)
        self.assertNotIn('In Storage (gal)',text)

    def test_transport_delete_clears_harvest_cost_and_does_not_return_on_save(self):
        self.client.post('/harvests/add',data=self.form())
        h=db.query('SELECT * FROM harvests',one=True)
        t=db.query('SELECT * FROM transport_logs',one=True)
        self.client.post('/transport/%s/delete'%t['id'])
        h=db.query('SELECT * FROM harvests',one=True)
        self.assertEqual((h['transport_mode'],h['driver_pay'],h['fuel_cost'],h['tricycle_rent']),('',0,0,0))
        self.client.post('/harvests/%s/edit'%h['id'],data=self.form(transport_mode=h['transport_mode'],tricycle_rent=str(h['tricycle_rent'])))
        self.assertEqual(len(db.query('SELECT * FROM transport_logs')),0)
        self.assertEqual(_current_stock(),10)

    def test_edits_sync_links_and_activity_delete_removes_related_records(self):
        self.client.post('/harvests/add',data=self.form())
        h=db.query('SELECT * FROM harvests',one=True)
        self.client.post('/harvests/%s/edit'%h['id'],data=self.form(farm_id='6',date='2026-09-30',harvester_pay='15',tricycle_rent='25'))
        a=db.query('SELECT * FROM activities WHERE id=?',(h['activity_id'],),one=True)
        t=db.query('SELECT * FROM transport_logs WHERE harvest_id=?',(h['id'],),one=True)
        self.assertEqual((a['farm_id'],a['date'],a['labour_cost']),(6,'2026-09-30',15))
        self.assertEqual((t['farm_id'],t['date'],t['total_cost']),(6,'2026-09-30',25))
        self.client.post('/activities/%s/delete'%h['activity_id'])
        for table in ['activities','harvests','transport_logs']:
            self.assertEqual(len(db.query('SELECT * FROM '+table)),0)
        self.assertEqual(_current_stock(),0)

    def test_duplicate_harvest_blocked_from_both_entry_screens(self):
        self.client.post('/harvests/add',data=self.form())
        for path in ['/harvests/add','/activities/add']:
            response=self.client.post(path,data=self.form(),follow_redirects=True)
            self.assertIn('A harvest already exists',response.get_data(as_text=True))
        for table in ['harvests','activities','transport_logs']:
            self.assertEqual(len(db.query('SELECT * FROM '+table)),1)
        self.assertEqual(_current_stock(),10)

    def test_edit_cannot_move_harvest_to_occupied_farm_date(self):
        self.client.post('/harvests/add',data=self.form())
        self.client.post('/harvests/add',data=self.form(date='2026-09-30'))
        rows=db.query('SELECT * FROM harvests ORDER BY id')
        h=rows[1]
        for path in ['/harvests/%s/edit'%h['id'],'/activities/%s/edit'%h['activity_id']]:
            response=self.client.post(path,data=self.form(),follow_redirects=True)
            self.assertIn('A harvest already exists',response.get_data(as_text=True))
        self.assertEqual(db.query('SELECT date FROM harvests WHERE id=?',(h['id'],),one=True)['date'],'2026-09-30')
        self.assertEqual(db.query('SELECT date FROM activities WHERE id=?',(h['activity_id'],),one=True)['date'],'2026-09-30')
        self.assertEqual(db.query('SELECT date FROM transport_logs WHERE harvest_id=?',(h['id'],),one=True)['date'],'2026-09-30')
        response=self.client.post('/harvests/%s/edit'%rows[0]['id'],data=self.form(),follow_redirects=True)
        self.assertNotIn('A harvest already exists',response.get_data(as_text=True))
        self.assertEqual(_current_stock(),20)
