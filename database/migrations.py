"""Ordered, transactional database upgrades. Never discard recorded rows."""
from pathlib import Path
import sqlite3
from datetime import datetime

ROOT = Path(__file__).parent
VERSIONS = [(1, 'current_schema'), (2, 'processing_farm_links'), (3, 'pooled_storage'), (4, 'oil_quality'), (5, 'processing_dates')]


def statements(path):
    pending = ''
    for line in path.read_text().splitlines(True):
        pending += line
        if sqlite3.complete_statement(pending):
            yield pending
            pending = ''
    if pending.strip():
        raise RuntimeError('Incomplete schema statement: '+str(path))


def quote(name):
    return '"'+name.replace('"','""')+'"'


def columns(conn, table):
    return {row['name']: row for row in conn.execute('PRAGMA table_xinfo('+quote(table)+')')}


def column_declaration(row):
    if row['hidden'] or row['pk']:
        raise RuntimeError('Cannot automatically add or preserve special column '+row['name'])
    text=quote(row['name'])+' '+row['type']
    if row['notnull']: text+=' NOT NULL'
    if row['dflt_value'] is not None: text+=' DEFAULT '+row['dflt_value']
    return text


def rebuild(conn, table, sql, target):
    """Use SQLite's create/copy/drop/rename procedure with FK checks at commit."""
    old=columns(conn,table)
    extras=[row for name,row in old.items() if name not in target]
    fresh='pfms_upgrade_'+table
    if conn.execute('SELECT 1 FROM sqlite_master WHERE name=?',(fresh,)).fetchone():
        raise RuntimeError('Unexpected temporary upgrade table '+fresh)
    definition=sql[sql.index('('):]
    if extras:
        pos=definition.rfind(')')
        definition=definition[:pos]+', '+', '.join(column_declaration(row) for row in extras)+definition[pos:]
    conn.execute('CREATE TABLE '+quote(fresh)+' '+definition)
    new=columns(conn,fresh)
    common=[name for name,row in new.items() if name in old and not row['hidden']]
    names=','.join(quote(name) for name in common)
    conn.execute('INSERT INTO '+quote(fresh)+' ('+names+') SELECT '+names+' FROM '+quote(table))
    # Retain custom indexes/triggers and AUTOINCREMENT high-water marks.
    objects=[r[0] for r in conn.execute("SELECT sql FROM sqlite_master WHERE tbl_name=? AND type IN ('index','trigger') AND sql IS NOT NULL",(table,))]
    seq=conn.execute('SELECT seq FROM sqlite_sequence WHERE name=?',(table,)).fetchone()
    conn.execute('DROP TABLE '+quote(table))
    conn.execute('ALTER TABLE '+quote(fresh)+' RENAME TO '+quote(table))
    if seq:
        conn.execute('UPDATE sqlite_sequence SET seq=MAX(seq,?) WHERE name=?',(seq[0],table))
    for obj in objects: conn.execute(obj)


def align_schema(conn):
    baseline=sqlite3.connect(':memory:');baseline.row_factory=sqlite3.Row
    try:
        for sql in statements(ROOT/'schema.sql'): baseline.execute(sql)
        for row in baseline.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
            table,sql=row['name'],row['sql']
            existing=conn.execute('SELECT sql FROM sqlite_master WHERE type=\'table\' AND name=?',(table,)).fetchone()
            if existing is None:
                conn.execute(sql)
                continue
            current=columns(conn,table);target=columns(baseline,table)
            needs_rebuild=(table=='processing_runs' and any(c['hidden'] for c in current.values())) or (table=='storage_transactions' and 'CHECK' in existing[0].upper())
            if needs_rebuild:
                rebuild(conn,table,sql,target)
            else:
                for name,col in target.items():
                    if name not in current:
                        declaration=column_declaration(col)
                        # Preserve the explicit relationship when adding this nullable column.
                        if table=='transport_logs' and name=='harvest_id':
                            declaration+=' REFERENCES harvests(id) ON DELETE CASCADE'
                        if table=='harvests' and name=='processing_run_id':
                            declaration+=' REFERENCES processing_runs(id) ON DELETE SET NULL'
                        conn.execute('ALTER TABLE '+quote(table)+' ADD COLUMN '+declaration)
        for row in baseline.execute("SELECT name,sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"):
            if not conn.execute('SELECT 1 FROM sqlite_master WHERE name=?',(row['name'],)).fetchone():conn.execute(row['sql'])
    finally:
        baseline.close()


def upgrade(conn, db_path):
    if conn.in_transaction: raise RuntimeError('Upgrade requires a connection without an active transaction.')
    conn.row_factory=sqlite3.Row
    # Rebuilding a referenced table requires FK enforcement off until final validation.
    conn.execute('PRAGMA foreign_keys=OFF')
    try:
        conn.execute('BEGIN IMMEDIATE')
        tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        fresh=not tables
        applied={r[0] for r in conn.execute('SELECT version FROM schema_migrations')} if 'schema_migrations' in tables else set()
        if applied-set(v for v,_ in VERSIONS):
            raise RuntimeError('This database was upgraded by a newer PFMS version. Use that version of the app.')
        pending=[(v,n) for v,n in VERSIONS if v not in applied]
        if not pending:
            conn.commit()
            return
        if not fresh and str(db_path)!=':memory:':
            folder=Path(db_path).parent/'backups';folder.mkdir(exist_ok=True)
            backup=folder/('before-schema-upgrade-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.db')
            source=sqlite3.connect(Path(db_path).resolve().as_uri()+'?mode=ro',uri=True)
            dest=sqlite3.connect(backup)
            try:source.backup(dest)
            finally:dest.close();source.close()
        conn.execute('CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY,name TEXT NOT NULL,applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
        for version,name in pending:
            if version==1:align_schema(conn)
            elif version==2:
                from database.processing import migrate_processing_farms
                migrate_processing_farms(conn)
            elif version==3:
                from database.harvest_workflow import migrate_pooled_storage
                migrate_pooled_storage(conn)
            elif version==4:
                from database.oil_quality import migrate_quality
                migrate_quality(conn)
            elif version==5:
                from database.processing_dates import migrate_dates
                migrate_dates(conn)
            conn.execute('INSERT INTO schema_migrations(version,name) VALUES(?,?)',(version,name))
        if fresh:
            for sql in statements(ROOT/'seed.sql'):conn.execute(sql)
        violations=conn.execute('PRAGMA foreign_key_check').fetchall()
        if violations:raise RuntimeError('Upgrade rolled back: database relationships need review: '+str([tuple(r) for r in violations]))
        if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise RuntimeError('Upgrade rolled back: database integrity check failed.')
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute('PRAGMA foreign_keys=ON')
