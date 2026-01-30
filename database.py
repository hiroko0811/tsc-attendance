import sqlite3
from datetime import datetime, date, timedelta, timezone

# --- 日本時間の設定 ---
JST = timezone(timedelta(hours=+9))
DB_NAME = 'attendance.db'

def get_connection():
    return sqlite3.connect(DB_NAME)

# --- ユーザー認証 ---
def get_user_by_username(username):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def create_user(username, password, department, role):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (id, username, password, department, role) VALUES (?, ?, ?, ?, ?)", 
              (username, username, password, department, role))
    conn.commit()
    conn.close()

# --- 基本機能（テーブル作成） ---
def create_tables():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id TEXT PRIMARY KEY, username TEXT, password TEXT, department TEXT, role TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS attendance
                 (user_id TEXT, date TEXT, 
                  start_time TEXT, end_time TEXT, 
                  break_duration INTEGER, manual_work_time INTEGER, note TEXT,
                  scheduled_start_time TEXT, scheduled_end_time TEXT, scheduled_break_duration INTEGER,
                  work_tag TEXT, leave_type TEXT, practice_duration INTEGER,
                  PRIMARY KEY (user_id, date))''')
    c.execute('''CREATE TABLE IF NOT EXISTS annual_plans
                 (username TEXT, year INTEGER, annual_hours INTEGER,
                  PRIMARY KEY (username, year))''')
    conn.commit()
    conn.close()

# --- 打刻・データ操作 ---

def clock_in(user_id, work_tag, start_time=None):
    # 日本時間を取得
    if start_time is None:
        start_time = datetime.now(JST)
    
    now_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
    today_str = start_time.strftime('%Y-%m-%d')
    
    conn = get_connection()
    c = conn.cursor()
    
    # 既存の記録があるか確認
    c.execute("SELECT * FROM attendance WHERE user_id=? AND date=?", (user_id, today_str))
    if c.fetchone():
        c.execute("UPDATE attendance SET start_time=COALESCE(start_time, ?) WHERE user_id=? AND date=?", 
                  (now_str, user_id, today_str))
    else:
        c.execute("INSERT INTO attendance (user_id, date, start_time, work_tag) VALUES (?, ?, ?, ?)", 
                  (user_id, today_str, now_str, work_tag))
    conn.commit()
    conn.close()

def clock_out(user_id, end_time=None, break_duration=60):
    if end_time is None:
        end_time = datetime.now(JST)
    
    end_str = end_time.strftime('%Y-%m-%d %H:%M:%S')
    today_str = end_time.strftime('%Y-%m-%d')
    
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE attendance SET end_time=?, break_duration=? WHERE user_id=? AND date=?", 
              (end_str, break_duration, user_id, today_str))
    conn.commit()
    conn.close()

def upsert_attendance_record(user_id, target_date, **kwargs):
    conn = get_connection()
    c = conn.cursor()
    d_str = target_date.isoformat()
    
    c.execute("SELECT 1 FROM attendance WHERE user_id=? AND date=?", (user_id, d_str))
    exists = c.fetchone()
    
    fields = [
        'start_time', 'end_time', 'break_duration', 'manual_work_time', 'note',
        'scheduled_start_time', 'scheduled_end_time', 'scheduled_break_duration',
        'work_tag', 'leave_type', 'practice_duration'
    ]
    
    values = []
    for f in fields:
        val = kwargs.get(f)
        if isinstance(val, (datetime, date)):
            val = val.strftime('%Y-%m-%d %H:%M:%S')
        values.append(val)
        
    if exists:
        set_clause = ", ".join([f"{f}=?" for f in fields])
        sql = f"UPDATE attendance SET {set_clause} WHERE user_id=? AND date=?"
        c.execute(sql, values + [user_id, d_str])
    else:
        col_str = ", ".join(['user_id', 'date'] + fields)
        ph_str = ", ".join(['?'] * (2 + len(fields)))
        c.execute(f"INSERT INTO attendance ({col_str}) VALUES ({ph_str})", [user_id, d_str] + values)
        
    conn.commit()
    conn.close()

# --- 参照系 ---

def get_today_record(user_id):
    today_str = datetime.now(JST).strftime('%Y-%m-%d')
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM attendance WHERE user_id=? AND date=?", (user_id, today_str))
    row = c.fetchone()
    conn.close()
    
    if row:
        d = dict(row)
        if d['start_time'] and not d['end_time']:
            d['status'] = 'working'
        elif d['start_time'] and d['end_time']:
            d['status'] = 'clocked_out'
        else:
            d['status'] = 'not_started'
        return d
    return None

def get_monthly_records(user_id, year, month):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    month_pfx = f"{year}-{month:02d}%"
    c.execute("SELECT * FROM attendance WHERE user_id=? AND date LIKE ?", (user_id, month_pfx))
    rows = c.fetchall()
    conn.close()
    
    results = {}
    for r in rows:
        d_str = r['date']
        day = int(d_str.split('-')[2])
        results[day] = dict(r)
    return results

def get_annual_plans(year):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT username, annual_hours FROM annual_plans WHERE year=?", (year,))
    rows = c.fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}

def set_annual_plan(username, year, hours):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO annual_plans (username, year, annual_hours) VALUES (?, ?, ?)", 
              (username, year, hours))
    conn.commit()
    conn.close()