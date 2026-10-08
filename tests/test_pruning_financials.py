import sqlite3
import unittest
import test_financials as base
from database import db
from database.financials import financial_summary

class PruningFinancialTests(unittest.TestCase):
    setUp=base.FinancialTests.setUp
    def form(self,**changes):
        data=dict(farm_id='4',date='2026-10-01',trees_pruned='10',cost='123',num_labourers='1')
        data.update(changes);return data
    def test_direct_batch_records_expense_once(self):
        self.client.post('/pruning/add-batch',data=self.form())
        self.assertEqual(financial_summary()['total_exp'],123)
        batch=db.query('SELECT * FROM pruning_batches',one=True)
        self.assertIsNotNone(batch['activity_id'])
        self.assertEqual(db.query('SELECT total_cost FROM activities',one=True)['total_cost'],batch['cost'])
    def test_linked_batch_prefills_and_preserves_materials_without_duplicate_expense(self):
        aid=db.execute("INSERT INTO activities(farm_id,date,activity_type,labour_cost,materials_cost,notes) VALUES(4,'2026-10-01','Pruning',100,23,'original note')")
        text=self.client.get('/pruning/add-batch?activity_id='+str(aid)).get_data(as_text=True)
        self.assertIn('value="123.0"',text)
        self.client.post('/pruning/add-batch',data=self.form(activity_id=str(aid),cost='150'))
        self.assertEqual(financial_summary()['total_exp'],150)
        a=db.query('SELECT * FROM activities',one=True)
        self.assertEqual((a['labour_cost'],a['materials_cost'],a['notes']),(127,23,'original note'))
        response=self.client.post('/pruning/add-batch',data=self.form(activity_id=str(aid)),follow_redirects=True)
        self.assertIn('already has a pruning batch',response.get_data(as_text=True))
        self.assertEqual(len(db.query('SELECT * FROM pruning_batches')),1)
        self.assertEqual(financial_summary()['total_exp'],150)
    def test_edit_and_delete_sync_expense_batch_and_cycle(self):
        self.client.post('/pruning/add-batch',data=self.form())
        a=db.query('SELECT * FROM activities',one=True)
        self.client.post('/activities/%s/edit'%a['id'],data=dict(farm_id='4',activity_type='Pruning',date='2026-10-02',labour_cost='150',materials_cost='20',num_labourers='2',notes='updated'))
        b=db.query('SELECT * FROM pruning_batches',one=True)
        self.assertEqual((b['date'],b['cost'],b['num_labourers'],b['notes']),('2026-10-02',170,2,'updated'))
        self.assertEqual(financial_summary()['total_exp'],170)
        self.client.post('/activities/%s/delete'%a['id'])
        for table in ['activities','pruning_batches','pruning_cycles']:self.assertEqual(db.query('SELECT * FROM '+table),[])
        self.assertEqual(financial_summary()['total_exp'],0)
    def test_failed_batch_save_leaves_no_expense(self):
        db.execute("CREATE TRIGGER fail_batch BEFORE INSERT ON pruning_batches BEGIN SELECT RAISE(ABORT,'injected'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.client.post('/pruning/add-batch',data=self.form())
        self.assertEqual(db.query('SELECT * FROM activities'),[])
        self.assertEqual(financial_summary()['total_exp'],0)
    def test_failed_linked_edit_rolls_back_expense(self):
        self.client.post('/pruning/add-batch',data=self.form())
        a=db.query('SELECT * FROM activities',one=True)
        db.execute("CREATE TRIGGER fail_edit BEFORE UPDATE ON pruning_batches BEGIN SELECT RAISE(ABORT,'injected'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.client.post('/activities/%s/edit'%a['id'],data=dict(farm_id='4',activity_type='Pruning',date='2026-10-02',labour_cost='999'))
        self.assertEqual(financial_summary()['total_exp'],123)
        self.assertEqual(db.query('SELECT date FROM activities',one=True)['date'],'2026-10-01')
