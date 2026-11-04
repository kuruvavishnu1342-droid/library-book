"""
Database Access Layer for Library Book Usage Analysis System.
Provides transparent connectivity to MySQL (primary) with automatic SQLite
fallback for development and testing environments.
Always uses parameterized queries, enforces foreign keys, and provides transaction safety.
"""

import os
import sqlite3
import pymysql
import pymysql.cursors
from datetime import datetime, date
from config import Config

_current_engine = None  # 'mysql' or 'sqlite'
_last_error = None

def get_connection():
    """
    Returns a database connection based on Config.
    Tries MySQL first if DB_TYPE is 'mysql' or 'auto'.
    Falls back to SQLite if MySQL fails or DB_TYPE is 'sqlite'.
    """
    global _current_engine, _last_error
    
    # Try MySQL if requested or auto
    if Config.DB_TYPE in ('mysql', 'auto'):
        try:
            # First try connecting to server to ensure database exists
            conn = pymysql.connect(
                host=Config.MYSQL_HOST,
                port=Config.MYSQL_PORT,
                user=Config.MYSQL_USER,
                password=Config.MYSQL_PASSWORD,
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=False,
                connect_timeout=3
            )
            # Create DB if not exists
            with conn.cursor() as cur:
                cur.execute(f"CREATE DATABASE IF NOT EXISTS `{Config.MYSQL_DB}` CHARACTER SET utf8mb4;")
            conn.select_db(Config.MYSQL_DB)
            _current_engine = 'mysql'
            _last_error = None
            return conn
        except Exception as e:
            _last_error = str(e)
            if Config.DB_TYPE == 'mysql':
                # Explicitly required MySQL, so re-raise
                raise ConnectionError(f"Failed to connect to MySQL: {e}")
            # If auto, proceed to SQLite fallback
    
    # SQLite Fallback
    _current_engine = 'sqlite'
    conn = sqlite3.connect(Config.SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def is_mysql():
    return _current_engine == 'mysql'

def get_engine_name():
    return 'MySQL 8.0' if _current_engine == 'mysql' else 'SQLite (MySQL Mode)'

def get_db_status():
    """Returns database connection status diagnostics."""
    global _current_engine, _last_error
    status = {
        'preferred_type': Config.DB_TYPE,
        'active_engine': get_engine_name(),
        'is_mysql': _current_engine == 'mysql',
        'host': Config.MYSQL_HOST if _current_engine == 'mysql' else 'local file',
        'port': Config.MYSQL_PORT if _current_engine == 'mysql' else 'N/A',
        'database': Config.MYSQL_DB if _current_engine == 'mysql' else Config.SQLITE_PATH,
        'connected': False,
        'error': _last_error
    }
    try:
        conn = get_connection()
        if _current_engine == 'mysql':
            with conn.cursor() as cur:
                cur.execute("SELECT VERSION() as ver;")
                res = cur.fetchone()
                status['version'] = res['ver'] if res else 'Unknown'
            conn.close()
        else:
            cur = conn.cursor()
            cur.execute("SELECT sqlite_version() as ver;")
            res = cur.fetchone()
            status['version'] = f"SQLite {res['ver']}"
            conn.close()
        status['connected'] = True
    except Exception as e:
        status['error'] = str(e)
    return status

def _adapt_sql(sql):
    """Translates SQL placeholders and functions between MySQL and SQLite."""
    if _current_engine == 'sqlite':
        # Replace %s with ? for parameterized queries
        sql = sql.replace('%s', '?')
        # Replace CURDATE() with DATE('now')
        sql = sql.replace('CURDATE()', "DATE('now')")
        # Replace DATEDIFF(a, b) with CAST(JULIANDAY(a) - JULIANDAY(b) AS INTEGER)
        # Handle standard pattern DATEDIFF(CURDATE(), due_date)
        sql = sql.replace("DATEDIFF(DATE('now'), due_date)", "CAST(JULIANDAY('now') - JULIANDAY(due_date) AS INTEGER)")
        sql = sql.replace("DATEDIFF(CURDATE(), due_date)", "CAST(JULIANDAY('now') - JULIANDAY(due_date) AS INTEGER)")
    return sql

def query_all(sql, params=None):
    """Executes a query and returns all matching records as dictionaries."""
    conn = get_connection()
    try:
        sql = _adapt_sql(sql)
        if _current_engine == 'mysql':
            with conn.cursor() as cur:
                cur.execute(sql, params or ())
                return cur.fetchall()
        else:
            cur = conn.cursor()
            cur.execute(sql, params or ())
            rows = cur.fetchall()
            return [dict(row) for row in rows]
    finally:
        conn.close()

def query_one(sql, params=None):
    """Executes a query and returns a single record as a dictionary or None."""
    conn = get_connection()
    try:
        sql = _adapt_sql(sql)
        if _current_engine == 'mysql':
            with conn.cursor() as cur:
                cur.execute(sql, params or ())
                return cur.fetchone()
        else:
            cur = conn.cursor()
            cur.execute(sql, params or ())
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()

def execute_statement(sql, params=None, commit=True):
    """Executes an INSERT, UPDATE, or DELETE statement. Returns lastrowid or rowcount."""
    conn = get_connection()
    try:
        sql = _adapt_sql(sql)
        if _current_engine == 'mysql':
            with conn.cursor() as cur:
                cur.execute(sql, params or ())
                last_id = cur.lastrowid
                row_count = cur.rowcount
            if commit:
                conn.commit()
            return {'lastrowid': last_id, 'rowcount': row_count}
        else:
            cur = conn.cursor()
            cur.execute(sql, params or ())
            last_id = cur.lastrowid
            row_count = cur.rowcount
            if commit:
                conn.commit()
            return {'lastrowid': last_id, 'rowcount': row_count}
    except Exception as e:
        if commit:
            conn.rollback()
        raise e
    finally:
        conn.close()

def execute_transaction(operations):
    """
    Executes multiple SQL operations inside a single atomic transaction.
    operations is a list of tuples: (sql, params).
    Rolls back automatically on any error.
    """
    conn = get_connection()
    try:
        results = []
        if _current_engine == 'mysql':
            with conn.cursor() as cur:
                for sql, params in operations:
                    adapted = _adapt_sql(sql)
                    cur.execute(adapted, params or ())
                    results.append({'lastrowid': cur.lastrowid, 'rowcount': cur.rowcount})
            conn.commit()
        else:
            cur = conn.cursor()
            for sql, params in operations:
                adapted = _adapt_sql(sql)
                cur.execute(adapted, params or ())
                results.append({'lastrowid': cur.lastrowid, 'rowcount': cur.rowcount})
            conn.commit()
        return results
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_setting(key, default=None):
    """Retrieves a configuration setting from the settings table."""
    try:
        row = query_one("SELECT setting_value FROM settings WHERE setting_key = %s;", (key,))
        if row:
            return row['setting_value']
    except Exception:
        pass
    return default

def set_setting(key, value):
    """Upserts a setting into the settings table."""
    if _current_engine == 'mysql':
        sql = """
        INSERT INTO settings (setting_key, setting_value) 
        VALUES (%s, %s) 
        ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value);
        """
    else:
        sql = """
        INSERT INTO settings (setting_key, setting_value) 
        VALUES (%s, %s)
        ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value;
        """
    execute_statement(sql, (key, str(value)))

def init_db(force_reinit=False):
    """
    Initializes database schema and populates sample data if tables don't exist.
    """
    conn = get_connection()
    try:
        # Check if books table exists
        check_sql = "SELECT COUNT(*) as cnt FROM books;"
        try:
            if _current_engine == 'mysql':
                with conn.cursor() as cur:
                    cur.execute(check_sql)
                    res = cur.fetchone()
                    if res and res['cnt'] > 0 and not force_reinit:
                        return True
            else:
                cur = conn.cursor()
                cur.execute(check_sql)
                res = cur.fetchone()
                if res and res['cnt'] > 0 and not force_reinit:
                    return True
        except Exception:
            # Table doesn't exist yet, proceed with creation
            pass
            
        sql_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.sql')
        if not os.path.exists(sql_file):
            return False

        with open(sql_file, 'r', encoding='utf-8') as f:
            full_sql = f.read()

        if _current_engine == 'mysql':
            with conn.cursor() as cur:
                statements = [stmt.strip() for stmt in full_sql.split(';') if stmt.strip()]
                for stmt in statements:
                    # Skip CREATE DATABASE/USE if already connected
                    if stmt.upper().startswith('CREATE DATABASE') or stmt.upper().startswith('USE '):
                        continue
                    try:
                        cur.execute(stmt)
                    except Exception as err:
                        # Skip if already exists
                        if 'already exists' not in str(err).lower() and 'duplicate entry' not in str(err).lower():
                            print(f"Warning in MySQL init: {err}")
            conn.commit()
        else:
            # Initialize SQLite
            cur = conn.cursor()
            # SQLite-compatible schema
            sqlite_schema = """
            CREATE TABLE IF NOT EXISTS books (
                book_id INTEGER PRIMARY KEY AUTOINCREMENT,
                isbn TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                category TEXT NOT NULL,
                total_copies INTEGER NOT NULL,
                copies_available INTEGER NOT NULL CHECK (copies_available >= 0 AND copies_available <= total_copies AND total_copies > 0)
            );

            CREATE TABLE IF NOT EXISTS borrowers (
                borrower_id INTEGER PRIMARY KEY AUTOINCREMENT,
                borrower_name TEXT NOT NULL,
                roll_no TEXT UNIQUE NOT NULL
            );

            CREATE TABLE IF NOT EXISTS loans (
                loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                borrower_id INTEGER NOT NULL,
                issue_date TEXT NOT NULL,
                due_date TEXT NOT NULL,
                return_date TEXT NULL,
                FOREIGN KEY (book_id) REFERENCES books(book_id) ON DELETE RESTRICT,
                FOREIGN KEY (borrower_id) REFERENCES borrowers(borrower_id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_books_isbn ON books(isbn);
            CREATE INDEX IF NOT EXISTS idx_books_category ON books(category);
            CREATE INDEX IF NOT EXISTS idx_borrowers_roll ON borrowers(roll_no);
            CREATE INDEX IF NOT EXISTS idx_loans_book ON loans(book_id);
            CREATE INDEX IF NOT EXISTS idx_loans_borrower ON loans(borrower_id);
            CREATE INDEX IF NOT EXISTS idx_loans_issue_date ON loans(issue_date);
            CREATE INDEX IF NOT EXISTS idx_loans_due_date ON loans(due_date);
            CREATE INDEX IF NOT EXISTS idx_loans_return_date ON loans(return_date);
            """
            cur.executescript(sqlite_schema)
            
            # Insert settings
            cur.execute("INSERT OR REPLACE INTO settings (setting_key, setting_value) VALUES ('borrowing_period_days', '14');")
            cur.execute("INSERT OR REPLACE INTO settings (setting_key, setting_value) VALUES ('system_name', 'Library Book Usage Analysis System');")

            # Extract sample data inserts from database.sql
            import re
            inserts = re.findall(r'(INSERT\s+INTO\s+.*?;)', full_sql, re.DOTALL | re.IGNORECASE)
            for ins in inserts:
                # Remove MySQL-specific ON DUPLICATE KEY UPDATE
                clean_ins = re.sub(r'ON\s+DUPLICATE\s+KEY\s+UPDATE\s+.*?;', ';', ins, flags=re.IGNORECASE)
                clean_ins = clean_ins.replace('INSERT INTO', 'INSERT OR IGNORE INTO')
                try:
                    cur.execute(clean_ins)
                except Exception as e:
                    # Ignore minor errors during sample population
                    pass
            conn.commit()

        return True
    finally:
        conn.close()
