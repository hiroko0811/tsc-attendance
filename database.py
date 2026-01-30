import sqlite3
from datetime import datetime, date

DB_NAME = 'attendance.db'

def get_connection():
    return sqlite3.connect(DB_NAME)

# --- ユーザー認証 (ここが前回抜けていました) ---
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
    # シンプルにusernameをIDとして扱います
    c.execute("INSERT OR IGNORE INTO users (id, username, password, department, role) VALUES (?, ?, ?, ?, ?)", 
              (username, username, password, department, role))
    conn.commit()
    conn.close()

# --- 基本機能 ---
def create_tables():
    conn = get_connection()
    c = conn.cursor()
    # ユーザーテーブル
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id TEXT PRIMARY KEY, username TEXT, password TEXT, department TEXT, role TEXT)''')
    # 勤怠テーブル
    c.execute('''CREATE TABLE IF NOT EXISTS attendance
                 (user_id TEXT, date TEXT, 
                  start_time TEXT, end_time TEXT, 
                  break_duration INTEGER, manual_work_time INTEGER, note TEXT,
                  scheduled_start_time TEXT, scheduled_end_time TEXT, scheduled_break_duration INTEGER,
                  work_tag TEXT, leave_type TEXT, practice_duration INTEGER,
                  PRIMARY KEY (user_id, date))''')
    # 年間予定テーブル
    c.execute('''CREATE TABLE IF NOT EXISTS annual_plans
                 (username TEXT, year INTEGER, annual_hours INTEGER,
                  PRIMARY KEY (username, year))''')
    conn.commit()
    conn.close()

# --- 打刻・データ操作 ---

# 修正後（末尾に , start_time=None を追加）
def clock_in(user_id, work_tag, start_time=None):
    if start_time is None:
        from datetime import datetime, timedelta, timezone
        JST = timezone(timedelta(hours=+9))
        start_time = datetime.now(JST)
    # ...以下の処理はそのまま...
    conn = get_connection()
    c = conn.cursor()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    today_str = date.today().isoformat()
    
    c.execute("SELECT * FROM attendance WHERE user_id=? AND date=?", (user_id, today_str))
    if c.fetchone():
        c.execute("UPDATE attendance SET start_time=COALESCE(start_time, ?) WHERE user_id=? AND date=?", (now_str, user_id, today_str))
    else:
        c.execute("INSERT INTO attendance (user_id, date, start_time, work_tag) VALUES (?, ?, ?, ?)", (user_id, today_str, now_str, work_tag))
    conn.commit()
    conn.close()

def clock_out(user_id, end_time=None, break_duration=60, manual_work_time=None, **kwargs):
    conn = get_connection()
    c = conn.cursor()
    if end_time is None: end_time = datetime.now()
    end_str = end_time.strftime('%Y-%m-%d %H:%M:%S')
    today_str = date.today().isoformat()
    
    c.execute("UPDATE attendance SET end_time=?, break_duration=? WHERE user_id=? AND date=?", 
              (end_str, break_duration, user_id, today_str))
    conn.commit()
    conn.close()

def upsert_attendance_record(user_id, target_date, **kwargs):
    """
    データの保存・更新（強制上書き対応版）
    Noneが渡された項目は NULL (データなし) として保存します。
    """
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
        # UPDATE: 指定された値をそのままセットする（NoneならNULLになりデータが消える）
        set_clause = ", ".join([f"{f}=?" for f in fields])
        sql = f"UPDATE attendance SET {set_clause} WHERE user_id=? AND date=?"
        c.execute(sql, values + [user_id, d_str])
    else:
        # INSERT
        col_str = ", ".join(['user_id', 'date'] + fields)
        ph_str = ", ".join(['?'] * (2 + len(fields)))
        c.execute(f"INSERT INTO attendance ({col_str}) VALUES ({ph_str})", [user_id, d_str] + values)
        
    conn.commit()
    conn.close()

# --- 参照系 ---

def get_today_record(user_id):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM attendance WHERE user_id=? AND date=?", (user_id, date.today().isoformat()))
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

def get_monthly_work_breakdown(user_id, year):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM attendance WHERE user_id=? AND date LIKE ?", (user_id, f"{year}%"))
    rows = c.fetchall()
    conn.close()
    
    summary = {}
    for r in rows:
        try:
            dt = datetime.strptime(r['date'], '%Y-%m-%d')
            m = dt.month
            if m not in summary:
                summary[m] = {'practice':0, 'expedition':0, 'operation':0, 'other':0, 'break':0}
            
            # 簡易集計ロジック
            summary[m]['operation'] += (r['manual_work_time'] or 0)
            summary[m]['break'] += (r['break_duration'] or 0)
        except:
            pass
        
    return summary

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