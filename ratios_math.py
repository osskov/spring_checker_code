import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import math
import csv
import re
import os

def parse_inch_string(s):
    if not s: return 0.0
    s = s.replace('"', '').strip()
    try:
        if ' ' in s:
            parts = s.split(' ')
            whole = float(parts[0])
            frac = parts[1].split('/')
            return whole + (float(frac[0]) / float(frac[1]))
        elif '/' in s:
            frac = s.split('/')
            return float(frac[0]) / float(frac[1])
        else:
            return float(s)
    except:
        return 0.0

def parse_rate_string(s):
    try:
        match = re.search(r"(\d+\.?\d*)", s)
        return float(match.group(1)) if match else 0.0
    except:
        return 0.0

def parse_price(s):
    try:
        return float(re.sub(r'[^\d.]', '', s))
    except:
        return 0.0

class ParallelSpringApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Retraction Designer: Parallel Spring Optimizer")
        self.root.geometry("1250x850") # Widened slightly for new column
        
        self.spring_data = []
        self.var_r_ext = tk.DoubleVar(value=2.0)
        self.var_R_large = tk.DoubleVar(value=25.0)
        self.var_r_spring = tk.DoubleVar(value=2.0)
        
        control_frame = ttk.Frame(root, padding=20)
        control_frame.pack(side=tk.TOP, fill=tk.X)

        self.create_slider(control_frame, "Driven Shaft Radius (r_ext) [mm]", self.var_r_ext, 1, 10)
        self.create_slider(control_frame, "Large Wheel Radius (R_large) [mm]", self.var_R_large, 0, 50)
        self.create_slider(control_frame, "Wheel Shaft Radius (r_spring) [mm]", self.var_r_spring, 1, 10)
        
        ttk.Separator(control_frame, orient="horizontal").pack(fill="x", pady=10)
        self.lbl_results = ttk.Label(control_frame, font=("Arial", 11, "bold"), justify="center", foreground="#b71c1c")
        self.lbl_results.pack()
        self.lbl_status = ttk.Label(control_frame, text="No file loaded", font=("Arial", 9, "italic"))
        self.lbl_status.pack(pady=2)

        btn_load = ttk.Button(control_frame, text="Manually Load Spring CSV", command=self.manual_load_csv)
        btn_load.pack(pady=5)

        table_frame = ttk.Frame(root, padding=10)
        table_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # ADDED "Max Total Load (N)" to columns
        cols = ("PartNum", "Qty Needed", "Net Rate (N/mm)", "Min Length (Retracted)", "Max Total Load (N)", "Max Deflect", "Total Price")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=150, anchor="center")
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        for var in [self.var_r_ext, self.var_R_large, self.var_r_spring]:
            var.trace_add("write", self.calculate)

        self.auto_load_default_file()

    def create_slider(self, parent, label, var, start, end):
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=2)
        ttk.Label(frame, text=label, width=35).pack(side=tk.LEFT)
        slider = ttk.Scale(frame, from_=start, to=end, variable=var, orient=tk.HORIZONTAL, 
                           command=lambda s: var.set(round(float(s) * 2) / 2))
        slider.pack(side=tk.LEFT, fill="x", expand=True)
        ttk.Label(frame, textvariable=var, width=8).pack(side=tk.RIGHT)

    def auto_load_default_file(self):
        if os.path.exists("springs.csv"):
            self.process_csv("springs.csv")
            self.lbl_status.config(text="Automatically loaded: springs.csv")
        else:
            self.lbl_status.config(text="Ready ('springs.csv' not found)")

    def manual_load_csv(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
        if file_path:
            self.process_csv(file_path)
            self.lbl_status.config(text=f"Loaded: {os.path.basename(file_path)}")

    def process_csv(self, file_path):
        self.spring_data = []
        try:
            with open(file_path, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    l_free_in = parse_inch_string(row.get('Length', '0'))
                    l_max_in = parse_inch_string(row.get('Extended Lg @ Max Load', '0'))
                    rate_lb_in = parse_rate_string(row.get('Spring Rate', '0'))
                    price_pkg = parse_price(row.get('Price', '0'))
                    pkg_qty = float(row.get('Pkg Qty', 1))
                    
                    self.spring_data.append({
                        'part': row.get('Part Number', 'Unknown'),
                        'l_free_mm': l_free_in * 25.4,
                        'l_max_mm': l_max_in * 25.4,
                        'rate_n_mm': rate_lb_in * 0.175126,
                        'pkg_price': price_pkg,
                        'pkg_qty': pkg_qty
                    })
            self.calculate()
        except Exception as e:
            messagebox.showerror("Error", f"Could not parse CSV: {e}")

    def calculate(self, *args):
        try:
            rope_pull = 600.0
            r_int = 2.0
            t_req = 6.0
            r_ext = self.var_r_ext.get()
            R_large = self.var_R_large.get()
            r_spring = self.var_r_spring.get()

            if R_large <= 0: return

            delta_op = (rope_pull / r_int) * (r_ext / R_large) * r_spring
            f_target_total = (t_req * R_large) / (r_ext * r_spring)
            self.lbl_results.config(text=f"TARGET: {f_target_total:.2f}N @ {delta_op:.1f}mm travel")

            valid_configs = []
            for s in self.spring_data:
                delta_max = s['l_max_mm'] - s['l_free_mm']
                if delta_max <= delta_op: continue

                f_start_max_single = s['rate_n_mm'] * (delta_max - delta_op)
                if f_start_max_single <= 0: continue
                
                qty = math.ceil(f_target_total / f_start_max_single)
                if qty > 10: continue

                delta_preload = (f_target_total / qty) / s['rate_n_mm']
                l_min = s['l_free_mm'] + delta_preload
                
                if (delta_preload + delta_op) > delta_max: continue

                num_pkgs = math.ceil(qty / s['pkg_qty'])
                
                # NEW CALCULATION: Max Total Load
                max_total_load = qty * (s['rate_n_mm'] * delta_max)

                valid_configs.append({
                    'part': s['part'],
                    'qty': qty,
                    'net_rate': qty * s['rate_n_mm'],
                    'min_len': l_min,
                    'max_load': max_total_load, # Calculated above
                    'max_def': l_min+delta_op,
                    'cost': num_pkgs * s['pkg_price']
                })

            valid_configs.sort(key=lambda x: x['net_rate'])

            self.tree.delete(*self.tree.get_children())
            for c in valid_configs:
                self.tree.insert("", tk.END, values=(
                    c['part'], f"{c['qty']}x", f"{c['net_rate']:.3f}", 
                    f"{c['min_len']:.2f} mm", f"{c['max_load']:.2f} N", 
                    f"{c['max_def']:.1f} mm", f"${c['cost']:.2f}"
                ))
        except Exception:
            pass

if __name__ == "__main__":
    root = tk.Tk()
    app = ParallelSpringApp(root)
    root.mainloop()