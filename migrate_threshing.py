"""Compatibility entry point: apply the safe, versioned PFMS migrations."""
from database.db import init_db

if __name__ == '__main__':
    init_db()
    print('PFMS database is up to date. Existing records were preserved.')
