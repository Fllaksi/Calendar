
from decimal import Decimal, ROUND_HALF_UP

# ========== Базовые константы ==========
DB_FILE = "salary_calendar.db"
DEC = Decimal
BASE_AMOUNT = DEC("90610.5")
REQUIRED_MINUTES = 9 * 60  # 540 минут

# ========== Цвета UI ==========
COLOR_OTHER_MONTH = "#f0f0f0"
COLOR_WEEKDAY_OK = "#c6efce"
COLOR_PAST_NO_DATA = "#e8e8e8"
COLOR_TODAY = "#fff2a8"
COLOR_WEEKEND = "#ffd9b3"
COLOR_UNDERTIME = "#ffcccc"
COLOR_HEADER_BG = "#f7f7f7"
COLOR_GOLD = "#ffd700"
COLOR_WEEKLY_OVERTIME = "#d4f7d4"
COLOR_WEEKLY_UNDERTIME = "#ffd8d8"

# ========== Денежные/временные утилиты ==========
def money_to_cents(amount: Decimal) -> int:
    return int((amount * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

def cents_to_money(cents: int) -> Decimal:
    return (DEC(cents) / 100).quantize(DEC('0.01'), rounding=ROUND_HALF_UP)

def format_minutes_hhmm(minutes: int) -> str:
    sign = ""
    if minutes < 0:
        sign = "-"; minutes = -minutes
    h = minutes // 60
    m = minutes % 60
    return f"{sign}{h}:{m:02d}"
