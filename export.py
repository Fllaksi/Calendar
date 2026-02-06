
import csv
from datetime import date
from .constants import cents_to_money

def export_shifts(conn, delimiter=';', encoding='utf-8-sig'):
    fname = f"salary_export_{date.today().isoformat()}.csv"
    cur = conn.cursor()
    cur.execute("SELECT day, activation, end, duration_min, undertime_min, overtime_min, day_pay_cents, overtime_pay_cents, notes FROM shifts ORDER BY day")
    rows = cur.fetchall()
    with open(fname, "w", newline='', encoding=encoding) as f:
        writer = csv.writer(f, delimiter=delimiter, quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["day", "activation", "end", "duration_min", "undertime_min", "overtime_min", "day_pay_rub", "overtime_pay_rub", "notes"])
        for r in rows:
            day, act, endt, duration, undertime, overtime, day_pay_cents, overtime_pay_cents, notes = r
            day_pay_str = f"{cents_to_money(day_pay_cents)}" if day_pay_cents else "0.00"
            ot_pay_str = f"{cents_to_money(overtime_pay_cents)}" if overtime_pay_cents else "0.00"
            writer.writerow([day, act or "", endt or "", duration or "", undertime or 0, overtime or 0, day_pay_str, ot_pay_str, notes or ""])
    return fname
