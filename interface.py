
#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime, timedelta
import calendar, traceback

from .constants import (
    REQUIRED_MINUTES, COLOR_OTHER_MONTH, COLOR_WEEKDAY_OK, COLOR_PAST_NO_DATA, COLOR_TODAY,
    COLOR_WEEKEND, COLOR_UNDERTIME, COLOR_HEADER_BG, COLOR_GOLD, COLOR_WEEKLY_OVERTIME,
    COLOR_WEEKLY_UNDERTIME, cents_to_money, format_minutes_hhmm
)
from . import database, calculations, events, export
from .widgets import Tooltip, EditShiftDialog

class CalendarApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Salary Calendar (Рабочий календарь)")
        self.geometry("1150x740"); self.resizable(False, False)
        self.conn = database.get_conn()
        self.holidays_set, self.holidays_names = self._load_manual_holidays(range(2024,2028))
        self.today = date.today(); self.cur_year = self.today.year; self.cur_month = self.today.month
        self.tooltip = None
        self._build_ui(); self._draw_calendar(); self._start_timer()

    def _load_manual_holidays(self, years):
        hset = set(); names = {}
        for y in years:
            for mday in range(1,10):
                from datetime import date as _d
                hset.add(_d(y,1,mday)); names[_d(y,1,mday)]="Новогодние каникулы"
            from datetime import date as _d
            names[_d(y,1,7)]="Рождество"; hset.add(_d(y,1,7))
            names[_d(y,2,23)]="День защитника Отечества"; hset.add(_d(y,2,23))
            names[_d(y,3,8)]="Международный женский день"; hset.add(_d(y,3,8))
            names[_d(y,5,1)]="Праздник труда"; hset.add(_d(y,5,1))
            names[_d(y,5,9)]="День Победы"; hset.add(_d(y,5,9))
            names[_d(y,6,12)]="День России"; hset.add(_d(y,6,12))
            names[_d(y,11,4)]="День единства"; hset.add(_d(y,11,4))
            names[_d(y, 12, 31)] = "Новый год"; hset.add(_d(y, 12, 31))
        return hset, names

    def _build_ui(self):
        top = ttk.Frame(self); top.pack(fill="x", padx=8, pady=6)
        ttk.Button(top, text="◀", width=3, command=self._prev_month).pack(side="left")
        ttk.Button(top, text="▶", width=3, command=self._next_month).pack(side="right")
        self.lbl_month = ttk.Label(top, text="", font=("Segoe UI", 14, "bold")); self.lbl_month.pack(side="top")
        nav = ttk.Frame(self); nav.pack(fill="x", padx=8)
        ttk.Label(nav, text="Год:").pack(side="left")
        self.spin_year = tk.Spinbox(nav, from_=1970, to=2100, width=6, command=self._on_spin)
        self.spin_year.delete(0,"end"); self.spin_year.insert(0,str(self.cur_year)); self.spin_year.pack(side="left", padx=(6,12))
        ttk.Label(nav, text="Месяц:").pack(side="left")
        self.cmb_month = ttk.Combobox(nav, values=[calendar.month_name[i] for i in range(1,13)], state="readonly", width=18)
        self.cmb_month.current(self.cur_month-1); self.cmb_month.bind("<<ComboboxSelected>>", lambda e: self._on_month_select()); self.cmb_month.pack(side="left", padx=6)

        main = ttk.Frame(self); main.pack(fill="both", expand=True, padx=8, pady=6)
        self.cal_container = ttk.Frame(main); self.cal_container.pack(side="left")
        self.sidebar = ttk.Frame(main, width=240); self.sidebar.pack(side="left", padx=10, fill="y")

        self.week_boxes_frame = ttk.Frame(self.sidebar); self.week_boxes_frame.pack(fill="y", expand=True)

        bottom = ttk.Frame(self); bottom.pack(fill="x", padx=8, pady=6)
        left = ttk.Frame(bottom); left.pack(side="left", anchor="w")
        ttk.Button(left, text="Начать смену", command=self._start_shift).pack(side="left", padx=6)
        ttk.Button(left, text="Закончить смену", command=self._finish_shift).pack(side="left", padx=6)
        ttk.Button(left, text="Экспорт CSV", command=self._export_csv).pack(side="left", padx=6)
        ttk.Button(left, text="Обработать переработки", command=self._process_pending_overtimes).pack(side="left", padx=6)
        right = ttk.Frame(bottom); right.pack(side="right", anchor="e")
        self.lbl_salary_14 = ttk.Label(right, text="Зарплата 14: —"); self.lbl_salary_14.pack(anchor="e")
        self.lbl_salary_29 = ttk.Label(right, text="Зарплата 29: —"); self.lbl_salary_29.pack(anchor="e")

    def _start_timer(self):
        self._update_shift_end_widget()
        self.after(20_000, self._start_timer)

    def _on_spin(self):
        try: y=int(self.spin_year.get()); self.cur_year=y; self._draw_calendar()
        except: pass

    def _on_month_select(self, *_):
        try: m=self.cmb_month.current()+1; self.cur_month=m; self._draw_calendar()
        except: pass

    def _prev_month(self):
        if self.cur_month==1: self.cur_month=12; self.cur_year-=1
        else: self.cur_month-=1
        self._update_nav(); self._draw_calendar()

    def _next_month(self):
        if self.cur_month==12: self.cur_month=1; self.cur_year+=1
        else: self.cur_month+=1
        self._update_nav(); self._draw_calendar()

    def _update_nav(self):
        self.spin_year.delete(0,"end"); self.spin_year.insert(0,str(self.cur_year)); self.cmb_month.current(self.cur_month-1)

    def _draw_calendar(self):
        for w in self.cal_container.winfo_children(): w.destroy()
        for w in self.week_boxes_frame.winfo_children(): w.destroy()
        cell_w, cell_h = 110, 86
        days_names = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]
        grid = ttk.Frame(self.cal_container); grid.pack()
        # top row placeholders
        for c in range(8): tk.Frame(grid, width=cell_w, height=28, bg=COLOR_OTHER_MONTH).grid(row=0, column=c)
        self.shift_end_widget = tk.Label(grid, text="Ожидаемое окончание смены", width=36, height=1, relief="solid", bg=COLOR_HEADER_BG, anchor="center")
        self.shift_end_widget.grid(row=0, column=2, columnspan=3, padx=2, pady=2, sticky="nsew")
        self.overtime_earnings_widget = tk.Label(grid, text="", width=18, height=1, relief="solid", bg=COLOR_HEADER_BG, anchor="center")
        self.overtime_earnings_widget.grid(row=0, column=5, padx=2, pady=2, sticky="nsew")
        self.summary_header = tk.Label(grid, text="Итоги по неделям", bg=COLOR_HEADER_BG, font=("Segoe UI", 11, "bold"), anchor="center")
        self.summary_header.grid(row=0, column=7, padx=2, pady=2, sticky="nsew")
        # weekday headers
        for c, dn in enumerate(days_names):
            frm = tk.Frame(grid, width=cell_w, height=28, highlightthickness=1, relief="solid", bg=COLOR_HEADER_BG)
            frm.grid_propagate(False); frm.grid(row=1, column=c, padx=2, pady=2)
            lbl = tk.Label(frm, text=dn, bg=COLOR_HEADER_BG, anchor="center", font=("Segoe UI", 10, "bold"))
            lbl.place(relx=0.5, rely=0.5, anchor="center")
        wk_hdr = tk.Frame(grid, width=140, height=28, highlightthickness=1, relief="solid", bg=COLOR_HEADER_BG)
        wk_hdr.grid_propagate(False); wk_hdr.grid(row=1, column=7, padx=2, pady=2)
        tk.Label(wk_hdr, text="Неделя разница", bg=COLOR_HEADER_BG).place(relx=0.5, rely=0.5, anchor="center")

        cal = calendar.Calendar(firstweekday=0); weeks = cal.monthdatescalendar(self.cur_year, self.cur_month)
        weekly_summaries = []
        for r, week in enumerate(weeks, start=2):
            week_overtime = 0; week_undertime = 0
            for d in week:
                cur = self.conn.cursor(); cur.execute("SELECT undertime_min, overtime_min FROM shifts WHERE day=?", (d.isoformat(),))
                row = cur.fetchone()
                if row:
                    week_undertime += (row[0] or 0); week_overtime += (row[1] or 0)
            net = week_overtime - week_undertime; weekly_summaries.append(net)
            for c, day in enumerate(week):
                frm = tk.Frame(grid, width=cell_w, height=cell_h, highlightthickness=1, relief="solid", bg=COLOR_OTHER_MONTH)
                frm.grid_propagate(False); frm.grid(row=r, column=c, padx=2, pady=2)
                inner = tk.Frame(frm, bg=COLOR_OTHER_MONTH); inner.place(relx=0, rely=0, relwidth=1, relheight=1)
                bg = self._bg_for_date(day); inner.config(bg=bg)
                lbl_day = tk.Label(inner, text=str(day.day), bg=bg, anchor="nw"); lbl_day.place(x=6, y=4)
                cur = self.conn.cursor(); cur.execute("SELECT undertime_min, overtime_min, overtime_pay_cents FROM shifts WHERE day=?", (day.isoformat(),))
                row = cur.fetchone()
                if row:
                    if row[0] and row[0] > 0:
                        lbl_ud = tk.Label(inner, text=f"-{row[0]}m", bg=bg, font=("Arial", 8)); lbl_ud.place(relx=0.02, rely=0.78, anchor="w")
                    if row[2] and row[2] > 0:
                        lbl_ot = tk.Label(inner, text="+", font=("Arial", 10, "bold"), bg=bg); lbl_ot.place(relx=0.6, rely=0.78, anchor="center")
                def make_enter(d=day):
                    return lambda e: self._on_day_enter(e, d)
                def make_leave(d=day):
                    return lambda e: self._on_day_leave(e, d)
                inner.bind("<Enter>", make_enter()); inner.bind("<Leave>", make_leave()); inner.bind("<Button-1>", lambda e, d=day: self._edit_day(d))
                lbl_day.bind("<Enter>", make_enter()); lbl_day.bind("<Leave>", make_leave()); lbl_day.bind("<Button-1>", lambda e, d=day: self._edit_day(d))
            wk_frame = tk.Frame(grid, width=140, height=cell_h, highlightthickness=1, relief="solid"); wk_frame.grid_propagate(False); wk_frame.grid(row=r, column=7, padx=2, pady=2)
            net = weekly_summaries[-1]
            if net < 0: bg = COLOR_WEEKLY_UNDERTIME; txt = f"Недоработка {format_minutes_hhmm(-net)}"
            elif net > 0: bg = COLOR_WEEKLY_OVERTIME; txt = f"Переработка {format_minutes_hhmm(net)}"
            else: bg = COLOR_PAST_NO_DATA; txt = "0:00"
            lblw = tk.Label(wk_frame, text=txt, bg=bg, anchor="center", justify="center"); lblw.place(relx=0.5, rely=0.5, anchor="center")
        self.weeks = weeks; self.weekly_summaries = weekly_summaries
        self._update_shift_end_widget(); self._update_salary_boxes()

    def _bg_for_date(self, day):
        if day.month != self.cur_month: return COLOR_OTHER_MONTH
        if day.weekday() >= 5 or day in self.holidays_set:
            cur = self.conn.cursor(); cur.execute("SELECT duration_min, overtime_pay_cents FROM shifts WHERE day=?", (day.isoformat(),)); row = cur.fetchone()
            if row and ((row[0] is not None and row[0] > 0) or (row[1] and row[1] > 0)): return COLOR_GOLD
            return COLOR_WEEKEND
        cur = self.conn.cursor(); cur.execute("SELECT duration_min, undertime_min, overtime_min, overtime_pay_cents FROM shifts WHERE day=?", (day.isoformat(),)); row = cur.fetchone()
        if day < self.today:
            if row:
                duration, undertime, overtime, ot_pay = row[0], row[1] or 0, row[2] or 0, row[3] or 0
                if undertime and undertime > 0: return COLOR_UNDERTIME
                if ot_pay and ot_pay > 0: return COLOR_GOLD
                if duration is not None: return COLOR_WEEKDAY_OK
                return COLOR_PAST_NO_DATA
            else: return COLOR_PAST_NO_DATA
        if day == self.today:
            if row and row[1] and row[1] > 0: return COLOR_UNDERTIME
            if row and row[3] and row[3] > 0: return COLOR_GOLD
            return COLOR_TODAY
        return "#ffffff"

    def _on_day_enter(self, event, day):
        if hasattr(self, "tooltip") and self.tooltip: self.tooltip.close(); self.tooltip = None
        cur = self.conn.cursor(); cur.execute("SELECT activation, end, duration_min, undertime_min, overtime_min, day_pay_cents, overtime_pay_cents, notes FROM shifts WHERE day=?", (day.isoformat(),)); row = cur.fetchone()
        lines = [f"{day.isoformat()}"]
        if day in self.holidays_set: lines.append(self.holidays_names.get(day, "Праздник / выходной"))
        elif day.weekday() >= 5: lines.append("Выходной")
        else: lines.append("Рабочий день")
        if row:
            activation, endt, duration, undertime, overtime, day_pay_cents, ot_pay_cents, notes = row
            lines.append(f"Вход: {activation or '-'}  Выход: {endt or '-'}")
            if duration is not None: lines.append(f"Длительность: {duration} мин")
            if undertime and undertime > 0: lines.append(f"Недоработка: {undertime} мин")
            if overtime and overtime > 0: lines.append(f"Переработка: {overtime} мин")
            base = cents_to_money(day_pay_cents or 0); lines.append(f"Оплата за день: {base} руб")
            if ot_pay_cents and ot_pay_cents > 0: lines.append(f"Доп Оплата: {cents_to_money(ot_pay_cents)} руб")
            total = cents_to_money((day_pay_cents or 0) + (ot_pay_cents or 0)); lines.append(f"Итого за день: {total} руб")
            if notes:
                note_preview = str(notes).strip().splitlines()[-6:]
                for ln in note_preview: lines.append(ln)
        else: lines.append("(нет записей)")
        x = self.winfo_pointerx() + 12; y = self.winfo_pointery() + 12
        self.tooltip = Tooltip(self, lines, edit_callback=lambda d=day: self._edit_day(d))
        self.tooltip.show_at(x, y)

    def _on_day_leave(self, event, day):
        if hasattr(self, "tooltip") and self.tooltip: self.tooltip.close(); self.tooltip = None

    def _edit_day(self, day):
        cur = self.conn.cursor(); cur.execute("SELECT activation, end, duration_min, undertime_min, overtime_min, day_pay_cents, overtime_pay_cents, notes FROM shifts WHERE day=?", (day.isoformat(),)); row = cur.fetchone()
        existing = {}
        if row: existing = {"activation": row[0], "end": row[1], "duration_min": row[2], "undertime_min": row[3], "overtime_min": row[4], "notes": row[7], "overtime_pay_cents": row[6]}
        dlg = EditShiftDialog(self, day, existing, self.conn); self.wait_window(dlg)
        if getattr(dlg, "result", None) is None: return
        if dlg.result.get("deleted"): self._draw_calendar(); return
        activation = dlg.result.get("activation"); endt = dlg.result.get("end"); notes = dlg.result.get("notes") or ""
        duration = None; undertime = 0; overtime = 0; day_pay_cents = 0; ot_pay_cents = 0
        if activation and endt:
            try:
                fmt = "%H:%M"
                a_dt = datetime.combine(day, datetime.strptime(activation, fmt).time())
                b_dt = datetime.combine(day, datetime.strptime(endt, fmt).time())
                if b_dt < a_dt: b_dt += timedelta(days=1)
                duration = int((b_dt - a_dt).total_seconds() // 60)
                is_weekend = (day.weekday() >= 5 or day in self.holidays_set)
                if is_weekend:
                    undertime = 0
                    overtime = 0
                    hrate = calculations.hourly_rate_for_month(day.year, day.month, self.holidays_set)
                    total_pay = calculations.weekend_pay_for_duration(duration, hrate)
                    database.save_shift(self.conn, day.isoformat(), activation, endt, duration, undertime, overtime, total_pay, 0, notes)
                    self._draw_calendar()
                    return
                undertime = max(0, REQUIRED_MINUTES - duration); overtime = max(0, duration - REQUIRED_MINUTES)
                hrate = calculations.hourly_rate_for_month(day.year, day.month, self.holidays_set); day_pay_cents = calculations.day_base_pay(hrate); ot_pay_cents = 0
            except Exception as ex:
                messagebox.showerror("Ошибка", f"Ошибка расчёта: {ex}"); return
        database.save_shift(self.conn, day.isoformat(), activation, endt, duration, undertime, overtime, day_pay_cents, ot_pay_cents, notes)
        self._draw_calendar()

    def _start_shift(self):
        day = self.today; start_str = datetime.now().strftime("%H:%M"); cur = self.conn.cursor()
        cur.execute("SELECT activation FROM shifts WHERE day=?", (day.isoformat(),)); row = cur.fetchone()
        if row and row[0]: messagebox.showinfo("Смена уже начата", "Для сегодняшнего дня уже задано начало смены."); return
        cur.execute("SELECT day FROM shifts WHERE day=?", (day.isoformat(),))
        if cur.fetchone():
            cur.execute("UPDATE shifts SET activation=? WHERE day=?", (start_str, day.isoformat()))
        else:
            hrate = calculations.hourly_rate_for_month(day.year, day.month, self.holidays_set); day_pay = calculations.day_base_pay(hrate)
            cur.execute("INSERT INTO shifts(day, activation, end, duration_min, undertime_min, overtime_min, day_pay_cents, overtime_pay_cents, notes) VALUES(?,?,?,?,?,?,?,?,?)", (day.isoformat(), start_str, None, None, 0, 0, day_pay, 0, ""))
        self.conn.commit(); self._update_shift_end_widget(); self._draw_calendar(); messagebox.showinfo("Смена начата", f"Смена начата в {start_str}")

    def _finish_shift(self):
        day = self.today
        cur = self.conn.cursor()
        cur.execute("SELECT activation, end, duration_min FROM shifts WHERE day=?", (day.isoformat(),))
        row = cur.fetchone()
        if row and row[1] and row[2] is not None:
            messagebox.showinfo("Смена уже завершена", "Для сегодняшнего дня смена уже завершена.")
            return
        if not row or not row[0]:
            if not messagebox.askyesno("Нет активации", "Для сегодняшнего дня не задано время активации. Ввести сейчас?"):
                return
            self._input_activation_for_date(day)
            cur.execute("SELECT activation FROM shifts WHERE day=?", (day.isoformat(),))
            row = cur.fetchone()
            if not row or not row[0]:
                return
        activation = row[0]
        if not messagebox.askyesno("Подтверждение", "Закончить смену сейчас (будет использовано фактическое текущее время)?"):
            return
        end_dt = datetime.now()
        end_str = end_dt.strftime("%H:%M")
        fmt = "%H:%M"
        try:
            a_dt = datetime.combine(day, datetime.strptime(activation, fmt).time())
            b_dt = datetime.combine(day, datetime.strptime(end_str, fmt).time())
            if b_dt < a_dt:
                b_dt += timedelta(days=1)
            duration = int((b_dt - a_dt).total_seconds() // 60)
        except Exception as ex:
            messagebox.showerror("Ошибка", f"Неправильный формат времени активации: {ex}")
            return
        is_weekend = (day.weekday() >= 5 or day in self.holidays_set)
        if is_weekend:
            undertime = 0
            overtime = 0
            hrate = calculations.hourly_rate_for_month(day.year, day.month, self.holidays_set)
            work_minutes = duration or 0
            if work_minutes > 240:
                work_minutes -= 60
            total_pay = calculations.calc_overtime_pay_minutes(work_minutes, hrate, is_weekend=True)
            database.save_shift(self.conn, day.isoformat(), activation, end_str, duration, undertime, overtime, total_pay, 0, "")
            messagebox.showinfo("Выходной/праздник","Работа в выходной учтена: оплачивается по коэффициенту x2, день отмечен золотым.")
            self._draw_calendar()
            return
        undertime = max(0, REQUIRED_MINUTES - duration)
        overtime = max(0, duration - REQUIRED_MINUTES)
        hrate = calculations.hourly_rate_for_month(day.year, day.month, self.holidays_set)
        day_pay_cents = calculations.day_base_pay(hrate)
        ot_pay_cents = 0
        if overtime > 30:
            include_overtime_in_pay = messagebox.askyesno("Учитываем переработку?",
                                                          f"Обнаружена переработка {overtime} мин. Учитываем переработку к выплатам?")
            if include_overtime_in_pay:
                ot_pay_cents = calculations.calc_overtime_pay_minutes(overtime, hrate, is_weekend=False)
        database.save_shift(self.conn, day.isoformat(), activation, end_str, duration, undertime, overtime, day_pay_cents, ot_pay_cents, "")
        half = 1 if day.day <= 15 else 2
        leftover, used_map = events.distribute_overtime_minutes(self.conn, day.year, day.month, half, day.isoformat(), overtime)
        if used_map:
            details = "; ".join([f"{k}:{v}min" for k, v in used_map.items()])
            messagebox.showinfo("Распределение переработки", f"Переработка {overtime} мин распределена: {details}. Осталось {leftover} мин.")
        self._draw_calendar()

    def _process_pending_overtimes(self):
        rows = database.find_pending_overtimes(self.conn, self.cur_year, self.cur_month)
        if not rows:
            messagebox.showinfo("Нет переработок", "Нет переработок, требующих обработки в текущем месяце.")
            return
        total_added = 0; processed = 0
        for r in rows:
            try:
                day_iso, overtime_min = r[0], r[1] or 0
                if overtime_min <= 0: continue
                d = datetime.strptime(day_iso, "%Y-%m-%d").date()
                include = False
                if overtime_min > 30:
                    include = messagebox.askyesno("Учитываем переработку?", f"Дата {day_iso}: обнаружена переработка {overtime_min} минут. Учитываем переработку к выплатам?")
                else:
                    is_weekend = (d.weekday() >= 5 or d in self.holidays_set)
                    include = True if (is_weekend and overtime_min > 0) else False
                if include:
                    hrate = calculations.hourly_rate_for_month(d.year, d.month, self.holidays_set)
                    is_weekend = (d.weekday() >= 5 or d in self.holidays_set)
                    ot_cents = calculations.calc_overtime_pay_minutes(overtime_min, hrate, is_weekend)
                    if ot_cents > 0:
                        events.add_overtime_pay(self.conn, day_iso, ot_cents); total_added += ot_cents
                half = 1 if d.day <= 15 else 2
                leftover, used_map = events.distribute_overtime_minutes(self.conn, d.year, d.month, half, day_iso, overtime_min)
                processed += 1
            except Exception:
                traceback.print_exc(); continue
        self._draw_calendar()
        messagebox.showinfo("Обработка завершена", f"Обработано {processed} дней. Добавлено доплаты: {cents_to_money(total_added)} руб")

    def _input_activation_for_date(self, day):
        dlg = EditShiftDialog(self, day, {}, self.conn); self.wait_window(dlg)
        if getattr(dlg, "result", None) is None: return
        if dlg.result.get("deleted"): self._draw_calendar(); return
        activation = dlg.result.get("activation"); endt = dlg.result.get("end"); notes = dlg.result.get("notes") or ""
        duration = None; undertime = 0; overtime = 0; day_pay_cents = 0; ot_pay_cents = 0
        if activation and endt:
            try:
                fmt = "%H:%M"
                a_dt = datetime.combine(day, datetime.strptime(activation, fmt).time())
                b_dt = datetime.combine(day, datetime.strptime(endt, fmt).time())
                if b_dt < a_dt: b_dt += timedelta(days=1)
                duration = int((b_dt - a_dt).total_seconds() // 60)
                is_weekend = (day.weekday() >= 5 or day in self.holidays_set)
                if is_weekend:
                    undertime = 0
                    overtime = 0
                    hrate = calculations.hourly_rate_for_month(day.year, day.month, self.holidays_set)
                    total_pay = calculations.weekend_pay_for_duration(duration, hrate)
                    database.save_shift(self.conn, day.isoformat(), activation, endt, duration, undertime, overtime, total_pay, 0, notes)
                    self._draw_calendar()
                    return
                undertime = max(0, REQUIRED_MINUTES - duration); overtime = max(0, duration - REQUIRED_MINUTES)
                hrate = calculations.hourly_rate_for_month(day.year, day.month, self.holidays_set); day_pay_cents = calculations.day_base_pay(hrate); ot_pay_cents = 0
            except Exception as ex:
                messagebox.showerror("Ошибка", f"Ошибка расчёта: {ex}"); return
        database.save_shift(self.conn, day.isoformat(), activation, endt, duration, undertime, overtime, day_pay_cents, ot_pay_cents, notes); self._draw_calendar()

    def _update_shift_end_widget(self):
        cur = self.conn.cursor(); today_iso = self.today.isoformat()
        cur.execute("SELECT activation, overtime_pay_cents, duration_min FROM shifts WHERE day=?", (today_iso,))
        row = cur.fetchone()
        if not row or not row[0]:
            self.shift_end_widget.config(text="Ожидаемое окончание смены: —", bg=COLOR_HEADER_BG)
            self.overtime_earnings_widget.config(text="", bg=COLOR_HEADER_BG)
            return
        activation = row[0]; ot_pay_cents = row[1] or 0; duration_min = row[2]
        fmt = "%H:%M"
        try:
            act_dt = datetime.strptime(activation, fmt).replace(year=self.today.year, month=self.today.month, day=self.today.day)
        except Exception:
            self.shift_end_widget.config(text="Ожидаемое окончание смены: —", bg=COLOR_HEADER_BG); return
        shift_end = act_dt + timedelta(hours=9); now = datetime.now()
        if now < shift_end:
            self.shift_end_widget.config(text=f"Ожидаемое окончание смены: {shift_end.strftime(fmt)}", bg=COLOR_HEADER_BG); self.overtime_earnings_widget.config(text="", bg=COLOR_HEADER_BG); return
        delta = now - shift_end; overtime_minutes = int(delta.total_seconds() // 60)
        hrate = calculations.hourly_rate_for_month(self.today.year, self.today.month, self.holidays_set)
        extra_pay = calculations.calc_overtime_pay_minutes(overtime_minutes, hrate, is_weekend=False)
        self.shift_end_widget.config(text=f"Смена окончена {shift_end.strftime(fmt)}  (+{format_minutes_hhmm(overtime_minutes)})", bg=COLOR_GOLD)
        self.overtime_earnings_widget.config(text=f"Потенц. доп: {cents_to_money(extra_pay)} руб", bg=COLOR_GOLD)

    def _update_salary_boxes(self):
        prev_month = self.cur_month - 1 if self.cur_month > 1 else 12
        prev_year = self.cur_year if self.cur_month > 1 else self.cur_year - 1
        last_prev = calendar.monthrange(prev_year, prev_month)[1]
        start_prev = date(prev_year, prev_month, 16); end_prev = date(prev_year, prev_month, last_prev)
        cur = self.conn.cursor(); cur.execute("SELECT day_pay_cents, overtime_pay_cents FROM shifts WHERE day BETWEEN ? AND ?", (start_prev.isoformat(), end_prev.isoformat()))
        rows = cur.fetchall(); total14 = sum((r[0] or 0) + (r[1] or 0) for r in rows)
        self.lbl_salary_14.config(text=f"Зарплата 14 (16..{last_prev} {calendar.month_name[prev_month]} {prev_year}): {cents_to_money(total14)} руб")
        start_cur = date(self.cur_year, self.cur_month, 1); end_cur = date(self.cur_year, self.cur_month, 15)
        cur.execute("SELECT day_pay_cents, overtime_pay_cents FROM shifts WHERE day BETWEEN ? AND ?", (start_cur.isoformat(), end_cur.isoformat()))
        rows = cur.fetchall(); total29 = sum((r[0] or 0) + (r[1] or 0) for r in rows)
        self.lbl_salary_29.config(text=f"Зарплата 29 (1..15 {calendar.month_name[self.cur_month]} {self.cur_year}): {cents_to_money(total29)} руб")

    def _export_csv(self):
        try:
            fname = export.export_shifts(self.conn)
            messagebox.showinfo("Экспорт", f"CSV сохранён: {fname}")
        except Exception as ex:
            messagebox.showerror("Ошибка экспорта", str(ex))

def main():
    try:
        app = CalendarApp(); app.mainloop()
    except Exception:
        traceback.print_exc(); messagebox.showerror("Критическая ошибка", "Произошла ошибка, см. консоль.")

if __name__ == "__main__": main()
