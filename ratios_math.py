import tkinter as tk
from tkinter import ttk, filedialog
import math
import csv
import re

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
        self.root.geometry("1100x850")
        
        self.spring_data = []
        
        # --- Variables ---
        self.var_r_ext = tk.DoubleVar(value=10.0)
        self.var_R_large = tk.DoubleVar(value=40.0)
        self.var_r_spring = tk.DoubleVar(value=5.0)
        
        # --- UI Layout ---
        control_frame = ttk.Frame(root, padding=20)
        control_frame.pack(side=tk.TOP, fill=tk.X)

        self.create_slider(control_frame, "Driven Shaft Radius (r_ext) [mm]", self.var_r_ext, 2.1, 50)
        self.create_slider(control_frame, "Large Wheel Radius (R_large) [mm]", self.var_R_large, 5, 150)
        self.create_slider(control_frame, "Wheel Shaft Radius (r_spring) [mm]", self.var_r_spring, 1, 30)
        
        ttk.Separator(control_frame, orient="horizontal").pack(fill="x", pady=10)
        
        self.lbl_results = ttk.Label(control_frame, font=("Arial", 11, "bold"), justify="center", foreground="#b71c1c")
        self.lbl_results.pack()
        
        btn_load = ttk.Button(control_frame, text="Load Spring CSV", command=self.load_csv)
        btn_load.pack(pady=5)

        # --- Table ---
        table_frame = ttk.Frame(root, padding=10)
        table_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Added columns for Quantity and Total System Force
        cols = ("PartNum", "Qty Needed", "Single End Force", "Total Sys Force", "Max Deflect", "Total Price")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120, anchor="center")
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        for var in [self.var_r_ext, self.var_R_large, self.var_r_spring]:
            var.trace_add("write", self.calculate)

    def create_slider(self, parent, label, var, start, end):
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=2)
        ttk.Label(frame, text=label, width=35).pack(side=tk.LEFT)
        ttk.Scale(frame, from_=start, to=end, variable=var, orient=tk.HORIZONTAL, command=self.calculate).pack(side=tk.LEFT, fill="x", expand=True)
        ttk.Label(frame, textvariable=var, width=8).pack(side=tk.RIGHT)

    def load_csv(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
        if not file_path: return
        
        self.spring_data = []
        try:
            with open(file_path, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    lg = parse_inch_string(row['Length'])
                    ext_lg = parse_inch_string(row['Extended Lg @ Max Load'])
                    max_f_lb = float(row['Max.'] if 'Max.' in row else row['Max Load (lb)']) 
                    rate_lb_in = parse_rate_string(row['Spring Rate'])
                    price = parse_price(row['Price'])
                    pkg_qty = float(row['Pkg Qty'] if 'Pkg Qty' in row else 1)
                    
                    self.spring_data.append({
                        'part': row['Part Number'],
                        'max_f_n': max_f_lb * 4.44822,
                        'rate_n_mm': rate_lb_in * 0.175126,
                        'max_def_mm': (ext_lg - lg) * 25.4,
                        'unit_price': price / pkg_qty,
                        'pkg_qty': pkg_qty
                    })
            self.calculate()
        except Exception as e:
            print(f"Error loading CSV: {e}")

    def calculate(self, *args):
        try:
            # Requirements
            L_rope = 600.0  
            r_int = 2.0     
            T_req_Nmm = 6.0 
            
            r_ext = self.var_r_ext.get()
            R_large = self.var_R_large.get()
            r_spring = self.var_r_spring.get()
            
            theta1 = L_rope / r_int
            theta2 = theta1 * (r_ext / R_large)
            
            req_travel_mm = theta2 * r_spring
            req_force_n = (T_req_Nmm * R_large) / (r_ext * r_spring)
            
            self.lbl_results.config(text=f"TARGET: {req_force_n:.3f} N Force at {req_travel_mm:.1f} mm Extension")
            
            for item in self.tree.get_children():
                self.tree.delete(item)
                
            for s in self.spring_data:
                # 1. Travel Check (Physical limit)
                if s['max_def_mm'] < req_travel_mm:
                    continue
                
                # 2. Force at the weakest point (fully retracted) for ONE spring
                f_retracted_single = s['max_f_n'] - (s['rate_n_mm'] * req_travel_mm)
                
                if f_retracted_single <= 0:
                    continue # Spring goes slack, parallel won't help
                
                # 3. How many springs in parallel to reach req_force_n?
                qty_needed = math.ceil(req_force_n / f_retracted_single)
                
                # Limit to 10 springs for sanity
                if qty_needed > 10:
                    continue
                
                total_sys_force = qty_needed * f_retracted_single
                total_cost = qty_needed * s['unit_price']

                self.tree.insert("", tk.END, values=(
                    s['part'],
                    f"{qty_needed}x",
                    f"{f_retracted_single:.2f} N",
                    f"{total_sys_force:.2f} N",
                    f"{s['max_def_mm']:.1f} mm",
                    f"${total_cost:.2f}"
                ))
                    
        except Exception:
            pass

if __name__ == "__main__":
    root = tk.Tk()
    app = ParallelSpringApp(root)
    root.mainloop()