
import tkinter as tk
from tkinter import ttk, messagebox

class Tooltip(tk.Toplevel):
    def __init__(self, parent, lines, edit_callback):
        super().__init__(parent)
        self.wm_overrideredirect(True)
        self.attributes("-topmost", True)
        frm = ttk.Frame(self, relief="solid", borderwidth=1)
        frm.pack(fill="both", expand=True)
        for ln in lines:
            ttk.Label(frm, text=ln).pack(anchor="w", padx=6, pady=0)
        ttk.Button(frm, text="Редактировать", command=edit_callback).pack(padx=6, pady=6)
    def show_at(self, x, y):
        try:
            sw = self.winfo_screenwidth(); sh = self.winfo_screenheight()
            w = 320; h = 200
            if x + w > sw: x = max(0, sw - w - 10)
            if y + h > sh: y = max(0, sh - h - 10)
        except Exception:
            pass
        self.wm_geometry(f"+{x}+{y}")
    def close(self):
        try: self.destroy()
        except: pass

class EditShiftDialog(tk.Toplevel):
    def __init__(self, parent, day, existing, conn):
        super().__init__(parent)
        self.title(f"Редактирование {day.isoformat()}")
        self.resizable(False, False)
        self.result = None
        self.conn = conn
        frm = ttk.Frame(self, padding=10); frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="Время активации (HH:MM):").grid(row=0, column=0, sticky="w")
        self.ent_act = ttk.Entry(frm, width=10); self.ent_act.grid(row=0, column=1, padx=6, pady=4)
        ttk.Label(frm, text="Время окончания (HH:MM):").grid(row=1, column=0, sticky="w")
        self.ent_end = ttk.Entry(frm, width=10); self.ent_end.grid(row=1, column=1, padx=6, pady=4)
        ttk.Label(frm, text="Примечание:").grid(row=2, column=0, sticky="nw")
        self.txt_note = tk.Text(frm, width=40, height=6); self.txt_note.grid(row=2, column=1, padx=6, pady=4)
        if existing.get("activation"): self.ent_act.insert(0, existing.get("activation"))
        if existing.get("end"): self.ent_end.insert(0, existing.get("end"))
        if existing.get("notes"): self.txt_note.insert("1.0", existing.get("notes"))
        btns = ttk.Frame(frm); btns.grid(row=3, column=0, columnspan=2, pady=(8,0))
        ttk.Button(btns, text="Сохранить", command=self._on_save).pack(side="left", padx=6)
        ttk.Button(btns, text="Удалить запись", command=self._on_delete).pack(side="left", padx=6)
        ttk.Button(btns, text="Отмена", command=lambda: self.destroy()).pack(side="left", padx=6)
        self.day = day
        self.grab_set()
    def _on_delete(self):
        from . import database
        if not messagebox.askyesno("Подтвердить", "Удалить запись?"): return
        database.delete_shift(self.conn, self.day.isoformat())
        self.result = {"deleted": True}; self.destroy()
    def _on_save(self):
        act = self.ent_act.get().strip(); endt = self.ent_end.get().strip(); notes = self.txt_note.get("1.0", "end").strip()
        def ok_time(s):
            if not s: return True
            try:
                import datetime as _dt
                _dt.datetime.strptime(s, "%H:%M"); return True
            except: return False
        if not ok_time(act) or not ok_time(endt):
            messagebox.showerror("Ошибка", "Время в формате HH:MM или пусто"); return
        self.result = {"activation": act or None, "end": endt or None, "notes": notes}
        self.destroy()
