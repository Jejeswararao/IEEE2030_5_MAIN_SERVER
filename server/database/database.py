import sqlite3
import os

# =========================================================
# DATABASE FILE (SINGLE SOURCE OF TRUTH)
# =========================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "ieee2030.db")

# =========================================================
# CONNECTION
# =========================================================
def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# =========================================================
# GENERIC QUERY (KEPT)
# =========================================================
def query(sql, params=(), one=False):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(sql, params)

    result = cursor.fetchone() if one else cursor.fetchall()

    conn.close()

    return result

# =========================================================
# EXECUTE (KEPT + FIXED COMMIT)
# =========================================================
def execute(sql, params=()):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql, params)
    conn.commit()
    conn.close()

# =========================================================
# DER LIST (KEPT)
# =========================================================
def get_ders():
    return query("SELECT * FROM ders")

# =========================================================
# DER PROGRAM SUPPORT (NEW - REQUIRED BY ROUTER)
# =========================================================
def get_programs():
    return query("SELECT * FROM der_programs")

# =========================================================
# DEFAULT DER CONTROL SUPPORT (REQUIRED BY ROUTER)
# =========================================================
def get_default_control():
    return query(
        "SELECT * FROM default_der_control ORDER BY id DESC LIMIT 1",
        one=True
    )

def get_program(program_id):
    return query(
        "SELECT * FROM der_programs WHERE id=?",
        (program_id,),
        one=True
    )

# =========================================================
# DATABASE INITIALIZATION (NEW)
# =========================================================
def initialize_database():

    conn = get_connection()
    cursor = conn.cursor()

    # ---- MUP LOG TABLE ----
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mup_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        voltage_a REAL,
        voltage_b REAL,
        voltage_c REAL,
        total_pv_power REAL
    )
    """)

    # ---- DER PROGRAM TABLE ----
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS der_programs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT
    )
    """)

    # ---- DERS TABLE (IF USED ELSEWHERE) ----
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT
    )
    """)


    # ---- DEFAULT DER CONTROL TABLE ----
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS default_der_control (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        power_limit REAL
    )
    """)

    # ---- DER CONTROLS TABLE (VERY IMPORTANT) ----
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS der_controls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mrid TEXT,
        program_id INTEGER,
        created_at INTEGER,
        q_set REAL,
        p_set REAL,
        target_phase INTEGER,
        condition TEXT,
        active INTEGER
    )
    """)
    conn.commit()
    conn.close()
