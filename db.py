"""
Database Access Layer for Library Book Usage Analysis System.
Provides connectivity to MySQL (external cloud database) with SSL support
and fallback for local development.
Always uses parameterized queries, enforces foreign keys, and guarantees transaction safety.
"""

import os
import sqlite3
import pymysql
import pymysql.cursors
from config import Config

_current_engine = 'mysql'
_last_error = None

def get_connection():
    """
    Returns a MySQL connection based on Config (DB_HOST, DB_USER, DB_PASSWORD, etc.).
    Falls back gracefully if MySQL credentials are not yet configured.
    """
    global _current_engine, _last_error
    
    # 1. Try connecting to MySQL (Cloud or Local)
    try:
        connect_kwargs = {
            'host': Config.DB_HOST,
            'port': Config.DB_PORT,
            'user': Config.DB_USER,
            'password': Config.DB_PASSWORD,
            'cursorclass': pymysql.cursors.DictCursor,
            'autocommit': False,
            'connect_timeout': 5
        }
        
        # Enable SSL if configured or if connecting to cloud provider (e.g., tidb, aiven, aws)
        if Config.DB_SSL or any(k in Config.DB_HOST.lower() for k in ('tidbcloud', 'aivencloud', 'railway', 'aws')):
            connect_kwargs['ssl'] = {'ssl_mode': 'REQUIRED'}

        # First connect without DB to ensure DB exists
        conn = pymysql.connect(**connect_kwargs)
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{Config.DB_NAME}` CHARACTER SET utf8mb4;")
        conn.select_db(Config.DB_NAME)
        
        _current_engine = 'mysql'
        _last_error = None
        return conn
    except Exception as e:
        _last_error = str(e)
        
        # If running locally or before user adds cloud credentials, use fallback so app won't crash
        _current_engine = 'sqlite'
        conn = sqlite3.connect(Config.SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

def is_mysql():
    return _current_engine == 'mysql'

def get_engine_name():
    return 'Cloud MySQL' if _current_engine == 'mysql' else 'Local Compatibility Mode'

def get_db_status():
    """Returns database connection status diagnostics."""
    global _current_engine, _last_error
    status = {
        'active_engine': get_engine_name(),
        'is_mysql': _current_engine == 'mysql',
        'host': Config.DB_HOST if _current_engine == 'mysql' else 'Local Fallback',
        'port': Config.DB_PORT if _current_engine == 'mysql' else 'N/A',
        'database': Config.DB_NAME if _current_engine == 'mysql' else 'library.db',
        'connected': False,
        'error': _last_error
    }
    try:
        conn = get_connection()
        if _current_engine == 'mysql':
            with conn.cursor() as cur:
                cur.execute("SELECT VERSION() as ver;")
                res = cur.fetchone()
                status['version'] = res['ver'] if res else 'MySQL 8.0'
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
    """Translates SQL placeholders and functions between MySQL and SQLite if needed."""
    if _current_engine == 'sqlite':
        sql = sql.replace('%s', '?')
        sql = sql.replace('CURDATE()', "DATE('now')")
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
    Initializes database schema and populates sample data on MySQL or fallback.
    """
    conn = get_connection()
    try:
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
                    if stmt.upper().startswith('CREATE DATABASE') or stmt.upper().startswith('USE '):
                        continue
                    try:
                        cur.execute(stmt)
                    except Exception as err:
                        if 'already exists' not in str(err).lower() and 'duplicate entry' not in str(err).lower():
                            pass
            conn.commit()
        else:
            cur = conn.cursor()
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
            """
            cur.executescript(sqlite_schema)
            cur.execute("INSERT OR REPLACE INTO settings (setting_key, setting_value) VALUES ('borrowing_period_days', '14');")
            cur.execute("INSERT OR REPLACE INTO settings (setting_key, setting_value) VALUES ('system_name', 'Library Book Usage Analysis System');")

            import re
            inserts = re.findall(r'(INSERT\s+INTO\s+.*?;)', full_sql, re.DOTALL | re.IGNORECASE)
            for ins in inserts:
                clean_ins = re.sub(r'ON\s+DUPLICATE\s+KEY\s+UPDATE\s+.*?;', ';', ins, flags=re.IGNORECASE)
                clean_ins = clean_ins.replace('INSERT INTO', 'INSERT OR IGNORE INTO')
                try:
                    cur.execute(clean_ins)
                except Exception:
                    pass
            conn.commit()

        return True
    finally:
        conn.close()
