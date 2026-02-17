import streamlit as st
from datetime import datetime, timedelta, timezone, date
import pandas as pd
import auth
import database
import calendar
import utils

# --- 0. 日本時間の設定 ---
JST = timezone(timedelta(hours=+9))
now = datetime.now(JST)

# --- 1. ページ設定 ---
st.set_page_config(page_title="TSC 勤怠システム", layout="wide")

# メンバーリスト（共通設定）
MEMBERS_CONFIG = [
    ("古賀", "1234", "事務局", "admin", "08:30", "17:15", "sh"),
    ("森岡", "1234", "事務局", "staff", "08:30", "16:30", "sh"),
    ("松田", "1234", "事務局", "staff", "09:00", "17:00", "sh"),
    ("矢野", "1234", "施設管理", "staff", "08:30", "17:15", "sat"),
    ("片岡", "1234", "施設管理", "staff", "09:00", "17:00", "sun_holi"),
    ("山本", "1234", "カヌーアカデミー", "staff", "", "", ""),
    ("梅原", "1234", "カヌーアカデミー", "staff", "", "", ""),
    ("眞田", "1234", "カヌーアカデミー", "staff", "", "", ""),
]

# 休暇種類の選択肢
LEAVE_TYPES = ["", "公休", "休日勤務", "有給休暇", "振替休暇", "特別休暇", "早退", "遅刻"]

# --- 2. 自動メンバー登録 & 予定作成ロジック ---
def initialize_system():
    database.create_tables()
    for name, pw, dept, role, _, _, _ in MEMBERS_CONFIG:
        if not database.get_user_by_username(name):
            database.create_user(name, pw, dept, role)

def auto_generate_schedule(user, year, month):
    """表示している年月のデータがなければ、実績データを保護しつつ予定を作成"""
    num_days = calendar.monthrange(year, month)[1]
    existing_records = database.get_monthly_records(user['id'], year, month)
    
    config = next((m for m in MEMBERS_CONFIG if m[0] == user['username']), None)
    if config:
        name, _, _, _, def_start, def_end, holiday_type = config
        if def_start and def_end:
            updated = False
            for day in range(1, num_days + 1):
                # 実績データがある日は上書きしない
                if day in existing_records: continue
                
                t_date = date(year, month, day)
                weekday = t_date.weekday()
                is_holiday = utils.is_jp_holiday(t_date)
                
                skip = False
                if holiday_type == "sh" and (weekday >= 5 or is_holiday): skip = True
                elif holiday_type == "sun_holi" and (weekday == 6 or is_holiday): skip = True
                elif holiday_type == "sat" and weekday == 5: skip = True
                elif holiday_type == "sat_holi" and (weekday == 5 or is_holiday): skip = True
                
                if not skip:
                    dt_ps = datetime.strptime(def_start, "%H:%M")
                    dt_pe = datetime.strptime(def_end, "%H:%M")
                    database.upsert_attendance_record(
                        user['id'], t_date,
                        scheduled_start_time=datetime.combine(t_date, dt_ps.time()),
                        scheduled_end_time=datetime.combine(t_date, dt_pe.time()),
                        scheduled_break_duration=60 
                    )
                    updated = True
            if updated: st.rerun()

initialize_system()

# --- ヘルパー関数 ---
def try_parse_datetime(dt_str):
    if not dt_str: return None
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S'):
        try: return datetime.strptime(dt_str, fmt)
        except ValueError: pass
    return None

def normalize_time_str(t_str):
    if not t_str: return ""
    table = str.maketrans({chr(0xFF10 + i): chr(0x30 + i) for i in range(10)})
    t_str = t_str.translate(table)
    t_str = t_str.replace("：", ":").strip()
    return t_str

def to_float(val):
    try: return float(val)
    except: return 0.0

# --- メイン画面 ---
def login_page():
    st.header("ログイン")
    with st.form("login_form"):
        username = st.text_input("ユーザー名")
        password = st.text_input("パスワード", type="password")
        if st.form_submit_button("ログイン"):
            user = auth.login_user(username, password)
            if user:
                for key in list(st.session_state.keys()): del st.session_state[key]
                st.session_state['user'] = user
                st.session_state['app_phase'] = 'dashboard'
                st.rerun()
            else:
                st.error("ユーザー名またはパスワードが間違っています")

def attendance_table_view(user):
    if 'at_view_year' not in st.session_state: st.session_state['at_view_year'] = now.year
    if 'at_view_month' not in st.session_state: st.session_state['at_view_month'] = now.month
    
    c1, c2 = st.columns([1, 4])
    with c1:
        y = st.number_input("年", value=st.session_state['at_view_year'], min_value=2024, max_value=2030)
        m = st.number_input("月", value=st.session_state['at_view_month'], min_value=1, max_value=12)
        st.session_state['at_view_year'] = y
        st.session_state['at_view_month'] = m

    # ★ 画面で選択した年月の予定を自動作成
    auto_generate_schedule(user, y, m)

    st.header(f"勤怠表 ({y}年度 {m}月度) - {user['username']}")
    edit_mode = st.toggle("編集モード", value=False)
    
    records = database.get_monthly_records(user['id'], y, m)
    jp_days = ["月", "火", "水", "木", "金", "土", "日"]
    num_days = calendar.monthrange(y, m)[1]
    
    rows = []
    red_rows = []
    total_vals = {'pb':0.0, 'pt':0.0, 'ab':0.0, 'at':0.0}

    for day in range(1, num_days + 1):
        d_obj = datetime(y, m, day)
        wk = jp_days[d_obj.weekday()]
        if utils.is_jp_holiday(d_obj) or d_obj.weekday() >= 5: red_rows.append(day)
        rec = records.get(day, {})
        keys = {k: f"{k}_{day}" for k in ['ps','pe','pb','as','ae','ab','aw','nt','lt']}
        
        def get_v(key, db_val, is_time=False):
            if key in st.session_state: return st.session_state[key]
            if db_val:
                if is_time:
                    dt = try_parse_datetime(db_val)
                    if dt: return dt.strftime('%H:%M')
                return db_val
            return ""

        v_ps = get_v(keys['ps'], rec.get('scheduled_start_time'), True)
        v_pe = get_v(keys['pe'], rec.get('scheduled_end_time'), True)
        v_pb = to_float(st.session_state.get(keys['pb'], float(rec.get('scheduled_break_duration') or 60)/60))
        v_as = get_v(keys['as'], rec.get('start_time'), True)
        v_ae = get_v(keys['ae'], rec.get('end_time'), True)
        
        db_ab_val = rec.get('break_duration')
        if db_ab_val is None:
            v_ab = to_float(st.session_state.get(keys['ab'], 1.0))
        else:
            v_ab = to_float(st.session_state.get(keys['ab'], float(db_ab_val)/60))
            
        v_nt = st.session_state.get(keys['nt'], rec.get('note', ""))
        v_lt = st.session_state.get(keys['lt'], rec.get('leave_type', ""))

        c_pt = 0.0
        try:
            if v_ps and v_pe:
                t1 = datetime.strptime(normalize_time_str(v_ps), "%H:%M")
                t2 = datetime.strptime(normalize_time_str(v_pe), "%H:%M")
                c_pt = max(0.0, (t2-t1).total_seconds()/3600 - v_pb)
        except: pass
        
        c_at_calc = 0.0
        try:
            if v_as and v_ae:
                t1 = datetime.strptime(normalize_time_str(v_as), "%H:%M")
                t2 = datetime.strptime(normalize_time_str(v_ae), "%H:%M")
                c_at_calc = max(0.0, (t2-t1).total_seconds()/3600 - v_ab)
        except: pass
        
        final_at = c_at_calc if (v_as and v_ae) else 0.0
        if not (v_as and v_ae):
            if keys['aw'] in st.session_state: final_at = to_float(st.session_state[keys['aw']])
            elif rec.get('manual_work_time') is not None: final_at = float(rec['manual_work_time'])/60.0

        total_vals['pb']+=v_pb; total_vals['pt']+=c_pt; total_vals['ab']+=v_ab; total_vals['at']+=final_at
        
        rows.append({
            "day": day, "wk": wk,
            "ps": v_ps, "pe": v_pe, "pb": v_pb, "pt": c_pt,
            "as": v_as, "ae": v_ae, "ab": v_ab, "at": final_at, "nt": v_nt, "lt": v_lt,
            "keys": keys
        })

    if not edit_mode:
        st.markdown("""<style>.ac-table {width:100%; border-collapse:collapse; font-size:0.9rem;} .ac-table th, .ac-table td {border:1px solid #ccc; text-align:center; padding:4px;} .ac-table th {background:#f2f2f2;} .red-text {color:red;}</style>""", unsafe_allow_html=True)
        html = '<table class="ac-table"><thead><tr><th rowspan="2">日</th><th rowspan="2">曜</th><th colspan="4">就業 (予定)</th><th colspan="4">就業 (実績)</th><th rowspan="2">種類</th><th rowspan="2">備考</th></tr><tr><th>開始</th><th>終了</th><th>休憩</th><th>時間</th><th>出勤</th><th>退勤</th><th>休憩</th><th>時間</th></tr></thead><tbody>'
        for r in rows:
            cls = "red-text" if r['day'] in red_rows else ""
            html += f'<tr><td class="{cls}">{r["day"]}</td><td class="{cls}">{r["wk"]}</td><td>{r["ps"]}</td><td>{r["pe"]}</td><td>{r["pb"]:.2f}</td><td>{r["pt"]:.2f}</td><td>{r["as"]}</td><td>{r["ae"]}</td><td>{r["ab"]:.2f}</td><td>{r["at"]:.2f}</td><td>{r["lt"]}</td><td style="text-align:left;">{r["nt"]}</td></tr>'
        html += f'<tr style="font-weight:bold;"><td>合計</td><td></td><td></td><td></td><td>{total_vals["pb"]:.2f}</td><td>{total_vals["pt"]:.2f}</td><td></td><td></td><td>{total_vals["ab"]:.2f}</td><td>{total_vals["at"]:.2f}</td><td></td><td></td></tr></tbody></table>'
        st.markdown(html, unsafe_allow_html=True)
    else:
        cols_cfg = [0.4, 0.4, 1.0, 1.0, 0.7, 0.7, 1.0, 1.0, 0.7, 0.7, 1.2, 1.5]
        h_cols = st.columns(cols_cfg)
        headers = ["日","曜","予始","予終","予休","予時","実始","実終","実休","実時","種類","備考"]
        for c, t in zip(h_cols, headers): c.markdown(f"**{t}**")
        
        for r in rows:
            c = st.columns(cols_cfg)
            col_mk = f":red[{r['day']}]" if r['day'] in red_rows else f"{r['day']}"
            c[0].markdown(col_mk); c[1].markdown(f":red[{r['wk']}]" if r['day'] in red_rows else f"{r['wk']}")
            c[2].text_input("PS", r['ps'], key=r['keys']['ps'], label_visibility="collapsed")
            c[3].text_input("PE", r['pe'], key=r['keys']['pe'], label_visibility="collapsed")
            c[4].text_input("PB", r['pb'], key=r['keys']['pb'], label_visibility="collapsed")
            c[5].write(f"{r['pt']:.2f}")
            c[6].text_input("AS", r['as'], key=r['keys']['as'], label_visibility="collapsed")
            c[7].text_input("AE", r['ae'], key=r['keys']['ae'], label_visibility="collapsed")
            c[8].text_input("AB", f"{r['ab']:.2f}", key=r['keys']['ab'], label_visibility="collapsed")
            c[9].text_input("AW", f"{r['at']:.2f}", key=r['keys']['aw'], label_visibility="collapsed")
            
            idx = 0
            if r['lt'] in LEAVE_TYPES: idx = LEAVE_TYPES.index(r['lt'])
            c[10].selectbox("LT", LEAVE_TYPES, index=idx, key=r['keys']['lt'], label_visibility="collapsed")
            
            c[11].text_input("NT", r['nt'], key=r['keys']['NT'], label_visibility="collapsed")

        if st.button("全データを保存", type="primary", use_container_width=True):
            for r in rows:
                t_date = date(y, m, r['day'])
                s_ps = normalize_time_str(st.session_state.get(r['keys']['ps'], ""))
                s_pe = normalize_time_str(st.session_state.get(r['keys']['pe'], ""))
                s_pb = to_float(st.session_state.get(r['keys']['pb'], 1.0))
                s_as = normalize_time_str(st.session_state.get(r['keys']['as'], ""))
                s_ae = normalize_time_str(st.session_state.get(r['keys']['ae'], ""))
                s_ab = to_float(st.session_state.get(r['keys']['ab'], 1.0))
                s_nt = st.session_state.get(r['keys']['nt'], "")
                s_lt = st.session_state.get(r['keys']['lt'], "")
                s_aw_man = to_float(st.session_state.get(r['keys']['aw'], 0.0))
                
                dt_ps = datetime.strptime(s_ps, "%H:%M") if s_ps else None
                dt_pe = datetime.strptime(s_pe, "%H:%M") if s_pe else None
                dt_as = datetime.strptime(s_as, "%H:%M") if s_as else None
                dt_ae = datetime.strptime(s_ae, "%H:%M") if s_ae else None
                
                mins = int(max(0.0, (dt_ae-dt_as).total_seconds()/3600 - s_ab)*60) if (dt_as and dt_ae) else int(s_aw_man*60)
                
                database.upsert_attendance_record(
                    user['id'], t_date,
                    start_time=datetime.combine(t_date, dt_as.time()) if dt_as else None,
                    end_time=datetime.combine(t_date, dt_ae.time()) if dt_ae else None,
                    break_duration=int(s_ab*60), manual_work_time=mins, note=s_nt,
                    leave_type=s_lt,
                    scheduled_start_time=datetime.combine(t_date, dt_ps.time()) if dt_ps else None,
                    scheduled_end_time=datetime.combine(t_date, dt_pe.time()) if dt_pe else None,
                    scheduled_break_duration=int(s_pb*60)
                )
            st.success("保存しました！"); st.rerun()

def staff_dashboard(user):
    st.header(f"本日の状況 - {user['username']}")
    st.write(f"現在時刻: {now.strftime('%H:%M')}")
    rec = database.get_today_record(user['id'])
    if not rec or (not rec.get('start_time') and not rec.get('end_time')):
        if st.button("【 出 勤 】", type="primary", use_container_width=True):
            database.clock_in(user['id'], "Academy", start_time=now); st.rerun()
    elif rec.get('status') == 'working':
        if st.button("【 退 勤 】", type="primary", use_container_width=True):
            database.clock_out(user['id'], end_time=now); st.rerun()
    else:
        st.success("本日の業務は終了しました")

def main():
    if 'app_phase' not in st.session_state: st.session_state['app_phase'] = 'portal'
    if st.session_state['app_phase'] == 'portal':
        st.title("TSC 勤怠システム")
        if st.button("ログイン画面へ"): st.session_state['app_phase'] = 'login'; st.rerun()
    elif st.session_state['app_phase'] == 'login':
        login_page()
    elif st.session_state['app_phase'] == 'dashboard':
        user = st.session_state.get('user')
        with st.sidebar:
            mode = st.radio("メニュー", ["本日の状況", "勤怠表"])
            if st.button("ログアウト"): del st.session_state['user']; st.session_state['app_phase'] = 'portal'; st.rerun()
        if mode == "本日の状況": staff_dashboard(user)
        elif mode == "勤怠表": attendance_table_view(user)

if __name__ == '__main__':
    main()