"""
Database Setup & Migration Script for Library Book Usage Analysis System
Executes database.sql schema and verifies initial sample datasets.
"""

import sys
import os
import pymysql
from config import Config
import db

def setup_mysql():
    print(f"Connecting to MySQL Server at {Config.MYSQL_HOST}:{Config.MYSQL_PORT} as {Config.MYSQL_USER}...")
    try:
        conn = pymysql.connect(
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            autocommit=True
        )
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{Config.MYSQL_DB}` CHARACTER SET utf8mb4;")
            print(f"Database `{Config.MYSQL_DB}` confirmed/created.")
            cur.execute(f"USE `{Config.MYSQL_DB}`;")
            
            sql_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.sql')
            with open(sql_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            statements = [stmt.strip() for stmt in content.split(';') if stmt.strip()]
            for stmt in statements:
                if stmt.upper().startswith('CREATE DATABASE') or stmt.upper().startswith('USE '):
                    continue
                try:
                    cur.execute(stmt)
                except Exception as ex:
                    if 'already exists' not in str(ex).lower() and 'duplicate entry' not in str(ex).lower():
                        print(f"Notice: {ex}")
        conn.close()
        print("MySQL database setup completed successfully!")
        return True
    except Exception as e:
        print(f"Error setting up MySQL: {e}")
        return False

def main():
    print("=" * 60)
    print(" Library Book Usage Analysis System - Database Setup")
    print("=" * 60)
    
    # Try initializing via db module
    success = db.init_db()
    status = db.get_db_status()
    print(f"Active Engine: {status['active_engine']}")
    print(f"Connected:     {status['connected']}")
    if status.get('version'):
        print(f"Version:       {status['version']}")
        
    books = db.query_one("SELECT COUNT(*) as cnt FROM books;")
    borrowers = db.query_one("SELECT COUNT(*) as cnt FROM borrowers;")
    loans = db.query_one("SELECT COUNT(*) as cnt FROM loans;")
    print("-" * 60)
    print(f"Records loaded: {books['cnt']} Books, {borrowers['cnt']} Borrowers, {loans['cnt']} Loans.")
    print("=" * 60)

if __name__ == '__main__':
    main()
