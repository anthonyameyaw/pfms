import sqlite3
import unittest
from unittest.mock import patch
import test_financials as base
from database import db

class AtomicPruningTests(unittest.TestCase):
    setUp = base.FinancialTests.setUp

    def form(self):
        return dict(farm_id='4',date='2026-10-01',trees_pruned='10',cost='100',num_labourers='2')

    def test_success_updates_batch_and_completes_cycle(self):
        db.execute('UPDATE farms SET total_trees=10 WHERE id=4')
        self.assertEqual(self.client.post('/pruning/add-batch',data=self.form()).status_code,302)
        cycle=db.query('SELECT * FROM pruning_cycles',one=True)
        self.assertEqual((cycle['total_trees_pruned'],cycle['is_complete'],cycle['cycle_end_date']),(10,1,'2026-10-01'))
        self.assertEqual(db.query('SELECT cost FROM pruning_batches',one=True)['cost'],100)

    def test_failure_after_cycle_creation_rolls_back_everything(self):
        db.execute("CREATE TRIGGER fail_batch BEFORE INSERT ON pruning_batches BEGIN SELECT RAISE(ABORT,'injected'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.client.post('/pruning/add-batch',data=self.form())
        self.assertEqual(db.query('SELECT * FROM pruning_cycles'),[])
        self.assertEqual(db.query('SELECT * FROM pruning_batches'),[])

    def test_failure_after_batch_insert_preserves_existing_cycle(self):
        db.execute("INSERT INTO pruning_cycles(farm_id,cycle_start_date,total_trees_pruned) VALUES(4,'2026-09-01',3)")
        db.execute("CREATE TRIGGER fail_total BEFORE UPDATE OF total_trees_pruned ON pruning_cycles BEGIN SELECT RAISE(ABORT,'injected'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.client.post('/pruning/add-batch',data=self.form())
        self.assertEqual(db.query('SELECT total_trees_pruned FROM pruning_cycles',one=True)['total_trees_pruned'],3)
        self.assertEqual(db.query('SELECT * FROM pruning_batches'),[])

    def test_completion_failure_rolls_back_batch_and_totals(self):
        db.execute('UPDATE farms SET total_trees=10 WHERE id=4')
        db.execute("CREATE TRIGGER fail_completion BEFORE UPDATE OF is_complete ON pruning_cycles BEGIN SELECT RAISE(ABORT,'injected'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.client.post('/pruning/add-batch',data=self.form())
        self.assertEqual(db.query('SELECT * FROM pruning_cycles'),[])
        self.assertEqual(db.query('SELECT * FROM pruning_batches'),[])

    def test_invalid_date_leaves_no_records(self):
        form=self.form();form['date']='invalid'
        self.assertEqual(self.client.post('/pruning/add-batch',data=form).status_code,302)
        self.assertEqual(db.query('SELECT * FROM pruning_cycles'),[])

    def test_helpers_close_connections_on_failure_and_batch_rolls_back(self):
        connection=db.get_connection()
        with patch.object(db,'get_connection',return_value=connection):
            with self.assertRaises(sqlite3.OperationalError):db.query('SELECT * FROM missing_table')
        with self.assertRaises(sqlite3.ProgrammingError):connection.execute('SELECT 1')
        connection=db.get_connection()
        with patch.object(db,'get_connection',return_value=connection):
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute_many('INSERT INTO activities(farm_id,date,activity_type) VALUES(?,?,?)',[(4,'2026-10-01','Pruning'),(999999,'2026-10-01','Pruning')])
        with self.assertRaises(sqlite3.ProgrammingError):connection.execute('SELECT 1')
        self.assertEqual(db.query('SELECT * FROM activities'),[])
