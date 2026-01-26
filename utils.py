from datetime import date

# Hardcoded holidays for 2024-2025 (Simplified List)
# Ideally this should be a library or API, but for standalone stability efficiently:
HOLIDAYS = {
    # 2024
    date(2024, 1, 1): "元日",
    date(2024, 1, 8): "成人の日",
    date(2024, 2, 11): "建国記念の日",
    date(2024, 2, 12): "振替休日",
    date(2024, 2, 23): "天皇誕生日",
    date(2024, 3, 20): "春分の日",
    date(2024, 4, 29): "昭和の日",
    date(2024, 5, 3): "憲法記念日",
    date(2024, 5, 4): "みどりの日",
    date(2024, 5, 5): "こどもの日",
    date(2024, 5, 6): "振替休日",
    date(2024, 7, 15): "海の日",
    date(2024, 8, 11): "山の日",
    date(2024, 8, 12): "振替休日",
    date(2024, 9, 16): "敬老の日",
    date(2024, 9, 22): "秋分の日",
    date(2024, 9, 23): "振替休日",
    date(2024, 10, 14): "スポーツの日",
    date(2024, 11, 3): "文化の日",
    date(2024, 11, 4): "振替休日",
    date(2024, 11, 23): "勤労感謝の日",
    date(2024, 12, 28): "年末年始", # Custom Company Holiday?
    date(2024, 12, 29): "年末年始",
    date(2024, 12, 30): "年末年始",
    date(2024, 12, 31): "年末年始",
    
    # 2025
    date(2025, 1, 1): "元日",
    date(2025, 1, 2): "正月",
    date(2025, 1, 3): "正月",
    date(2025, 1, 13): "成人の日",
    date(2025, 2, 11): "建国記念の日",
    date(2025, 2, 23): "天皇誕生日",
    date(2025, 2, 24): "振替休日",
    date(2025, 3, 20): "春分の日",
    date(2025, 4, 29): "昭和の日",
    date(2025, 5, 3): "憲法記念日",
    date(2025, 5, 4): "みどりの日",
    date(2025, 5, 5): "こどもの日",
    date(2025, 5, 6): "振替休日",
    date(2025, 7, 21): "海の日",
    date(2025, 8, 11): "山の日",
    date(2025, 9, 15): "敬老の日",
    date(2025, 9, 23): "秋分の日",
    date(2025, 10, 13): "スポーツの日",
    date(2025, 11, 3): "文化の日",
    date(2025, 11, 23): "勤労感謝の日",
    date(2025, 11, 24): "振替休日", 
}

def is_jp_holiday(date_obj):
    return date_obj in HOLIDAYS

def get_holiday_name(date_obj):
    return HOLIDAYS.get(date_obj)
