import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import runpy
import test_financials as base
from database import db
from database.migrations import upgrade

class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'test.db'
        self.conn=sqlite3.connect(self.path);self.conn.row_factory=sqlite3.Row
        self.addCleanup(self.conn.close)
    def snapshot(self):
        return {r[0]:[tuple(x) for x in self.conn.execute('SELECT * FROM "'+r[0]+'" ORDER BY rowid')] for r in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name!='schema_migrations'")}
    def test_fresh_install_and_all_main_pages(self):
        upgrade(self.conn,self.path)
        with patch.object(db,'DB_PATH',str(self.path)):
            client=base.app.test_client()
            for path in ['/','/farms/','/harvests/','/activities/','/plant/','/storage/','/investors/','/finances/','/reports/','/pruning/']:
                self.assertEqual(client.get(path).status_code,200,path)
        before=self.snapshot();upgrade(self.conn,self.path);self.assertEqual(self.snapshot(),before)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM schema_migrations').fetchone()[0],5)
    def test_repeated_startup_does_not_recreate_deleted_farm(self):
        upgrade(self.conn,self.path)
        with self.conn:self.conn.execute('DELETE FROM farms WHERE id=1')
        upgrade(self.conn,self.path)
        self.assertIsNone(self.conn.execute('SELECT id FROM farms WHERE id=1').fetchone())
    def test_populated_original_schema_preserves_values_ids_and_links(self):
        self.conn.executescript((base.ROOT/'tests/legacy_schema.sql').read_text())
        with self.conn:
            self.conn.execute("INSERT INTO processing_runs(id,date,total_output_litres,outside_farmer_fees,notes) VALUES(41,'2026-01-01',250,0,'retain')")
            self.conn.execute('INSERT INTO processing_run_farms(id,run_id,farm_id,bunches_contributed) VALUES(9,41,4,100)')
            self.conn.execute("INSERT INTO storage_transactions(id,date,transaction_type,gallons) VALUES(7,'2026-01-01','Addition',10)")
        original=dict(self.conn.execute('SELECT * FROM processing_runs').fetchone())
        upgrade(self.conn,self.path)
        row=dict(self.conn.execute('SELECT * FROM processing_runs').fetchone())
        for key,value in original.items():self.assertEqual(row[key],value,key)
        self.assertEqual(tuple(self.conn.execute('SELECT id,run_id,farm_id,bunches_contributed FROM processing_run_farms').fetchone()),(9,41,4,100))
        self.assertEqual(self.conn.execute('PRAGMA foreign_key_check').fetchall(),[])
        with self.conn:
            self.conn.execute("INSERT INTO storage_transactions(date,transaction_type,gallons,total_amount) VALUES('2026-02-01','Purchase',2,200)")
            self.conn.execute('UPDATE processing_runs SET gross_revenue=410 WHERE id=41')
        before=self.snapshot();upgrade(self.conn,self.path);self.assertEqual(self.snapshot(),before)
        self.assertEqual(len(list((self.path.parent/'backups').glob('*.db'))),1)
    def test_failure_rolls_back_schema_and_data_and_keeps_backup(self):
        self.conn.executescript((base.ROOT/'tests/legacy_schema.sql').read_text())
        before=self.snapshot()
        with patch('database.processing.migrate_processing_farms',side_effect=RuntimeError('injected')):
            with self.assertRaises(RuntimeError):upgrade(self.conn,self.path)
        self.assertEqual(self.snapshot(),before)
        self.assertIsNone(self.conn.execute("SELECT name FROM sqlite_master WHERE name='schema_migrations'").fetchone())
        self.assertEqual(self.conn.execute('PRAGMA foreign_keys').fetchone()[0],1)
        self.assertEqual(len(list((self.path.parent/'backups').glob('*.db'))),1)
    def test_old_script_names_repeat_safely(self):
        upgrade(self.conn,self.path)
        with self.conn:self.conn.execute("INSERT INTO processing_runs(id,date,gross_revenue) VALUES(42,'2026-01-01',400)")
        before=self.snapshot()
        with patch.object(db,'DB_PATH',str(self.path)):
            for script in base.ROOT.glob('migrate*.py'):
                runpy.run_path(str(script),run_name='__main__')
        self.assertEqual(self.snapshot(),before)
