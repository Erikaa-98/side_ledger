import sqlite3
from datetime import datetime

DB_PATH = "side_ledger.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
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
        created_at TEXT
    )
    """)
    # 机构表
    c.execute("""
    CREATE TABLE IF NOT EXISTS institutions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        contract_date TEXT,
        follow_up_date TEXT,
        note TEXT,
        created_at TEXT,
        user_id INTEGER,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)
    # 收入表
    c.execute("""
    CREATE TABLE IF NOT EXISTS incomes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        institution_id INTEGER,
        amount REAL,
        tax REAL,
        income_type TEXT,
        income_date TEXT,
        created_at TEXT,
        user_id INTEGER,
        FOREIGN KEY(institution_id) REFERENCES institutions(id),
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)
    conn.commit()
    conn.close()