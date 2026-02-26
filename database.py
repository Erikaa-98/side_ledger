import sqlite3
from datetime import datetime

DB_FILE = "side_ledger.db"

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # 用户表
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE,
        password TEXT,
        monthly_target REAL DEFAULT 0,
        created_at TEXT
    )
    """)
    
    # 机构表
    c.execute("""
    CREATE TABLE IF NOT EXISTS institutions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        status TEXT,
        follow_up_date TEXT,
        note TEXT,
        created_at TEXT
    )
    """)
    
    # 收入表
    c.execute("""
    CREATE TABLE IF NOT EXISTS incomes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        institution_id INTEGER,
        amount REAL,
        tax REAL DEFAULT 0,
        income_date TEXT,
        created_at TEXT
    )
    """)
    
    conn.commit()
    conn.close()
