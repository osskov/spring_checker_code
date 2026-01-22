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
        self.root.geometry("1000x850")
        
        self.spring_data = []
        
        # --- Variables ---
        self.var_r_ext = tk.DoubleVar(value=2.0)
        self.var_R_large = tk.DoubleVar(value=25.0)
        self.var_r_spring = tk.DoubleVar(value=2.0)
        
        # --- UI Layout ---
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

        # --- Table ---
        table_frame = ttk.Frame(root, padding=10)
        table_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Updated Columns: Net Rate, Min Operating Length, Total Price
        cols = ("PartNum", "Qty Needed", "Net Rate (N/mm)", "Min Length (Retracted)", "Total Price")
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
        default_filename = "springs.csv"
        if os.path.exists(default_filename):
            self.process_csv(default_filename)
            self.lbl_status.config(text=f"Automatically loaded: {default_filename}")
        else:
            self.lbl_status.config(text=f"Ready ('{default_filename}' not found)")

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
                    lg_in = parse_inch_string(row.get('Length', '0'))
                    ext_lg_in = parse_inch_string(row.get('Extended Lg @ Max Load', '0'))
                    max_f_str = row.get('Max Load (lb)', row.get('Max.', '0'))
                    max_f_lb = float(max_f_str) if max_f_str else 0.0
                    rate_lb_in = parse_rate_string(row.get('Spring Rate', '0'))
                    price_pkg = parse_price(row.get('Price', '0'))
                    pkg_qty = float(row.get('Pkg Qty', 1))
                    
                    self.spring_data.append({
                        'part': row.get('Part Number', 'Unknown'),
                        'free_len_mm': lg_in * 25.4,
                        'max_f_n': max_f_lb * 4.44822,
                        'rate_n_mm': rate_lb_in * 0.175126,
                        'max_def_mm': (ext_lg_in - lg_in) * 25.4,
                        'pkg_price': price_pkg,
                        'pkg_qty': pkg_qty
                    })
            self.calculate()
        except Exception as e:
            messagebox.showerror("Error", f"Could not parse CSV: {e}")

    def calculate(self, *args):
        try:
            # Mechanical Constant Assumptions
            L_rope = 600.0  
            r_int = 2.0     
            T_req_Nmm = 6.0 
            
            r_ext = self.var_r_ext.get()
            R_large = self.var_R_large.get()
            r_spring = self.var_r_spring.get()
            
            if R_large <= 0 or r_ext <= 0 or r_spring <= 0:
                self.lbl_results.config(text="TARGET: Invalid Radii")
                for item in self.tree.get_children(): self.tree.delete(item)
                return

            # Geometry logic
            theta1 = L_rope / r_int
            theta2 = theta1 * (r_ext / R_large)
            req_travel_mm = theta2 * r_spring
            req_force_n_total = (T_req_Nmm * R_large) / (r_ext * r_spring)
            
            self.lbl_results.config(text=f"TARGET: {req_force_n_total:.3f} N Force at {req_travel_mm:.1f} mm Extension")
            
            valid_configs = []
                
            for s in self.spring_data:
                # 1. Check if spring can even handle the stroke (Travel Check)
                if s['max_def_mm'] < req_travel_mm:
                    continue
                
                # 2. Find force at max usable retraction for 1 spring
                # Initial Tension (approximate) = Max Load - (Rate * Max Deflection)
                it_n = s['max_f_n'] - (s['rate_n_mm'] * s['max_def_mm'])
                
                # The spring is strongest when fully extended. At the retracted state (min length), 
                # we must have enough headroom to travel 'req_travel_mm' without exceeding max_def_mm.
                # Therefore, the maximum force we can have at the retracted state is:
                f_max_at_retracted = s['max_f_n'] - (s['rate_n_mm'] * req_travel_mm)
                
                if f_max_at_retracted <= 0:
                    continue # Spring too weak or goes slack during stroke
                
                # 3. Determine Qty
                qty_needed = math.ceil(req_force_n_total / f_max_at_retracted)
                if qty_needed > 10:
                    continue
                
                # 4. Calculate Minimum Length to hit necessary force
                # We need req_force_n_total / qty_needed per spring at retracted state.
                f_target_per_spring = req_force_n_total / qty_needed
                
                # Pre-load extension required = (Force - Initial Tension) / Rate
                # If force is less than initial tension, x is 0 (it hits the force instantly).
                x_preload = max(0.0, (f_target_per_spring - it_n) / s['rate_n_mm'])
                
                # The minimum length required is the Free Length + Pre-load
                min_oper_length_mm = s['free_len_mm'] + x_preload
                
                # 5. Total Price Calculation (Purchase price of packages)
                num_packages = math.ceil(qty_needed / s['pkg_qty'])
                total_purchase_price = num_packages * s['pkg_price']

                valid_configs.append({
                    'part': s['part'],
                    'qty': qty_needed,
                    'net_rate': qty_needed * s['rate_n_mm'],
                    'min_len': min_oper_length_mm,
                    'cost': total_purchase_price
                })
            
            # Sort by Net Rate (stiffness)
            valid_configs.sort(key=lambda x: x['net_rate'])

            for item in self.tree.get_children(): self.tree.delete(item)

            for config in valid_configs:
                self.tree.insert("", tk.END, values=(
                    config['part'],
                    f"{config['qty']}x",
                    f"{config['net_rate']:.3f} N/mm",
                    f"{config['min_len']:.2f} mm",
                    f"${config['cost']:.2f}"
                ))
                    
        except Exception:
            pass

if __name__ == "__main__":
    root = tk.Tk()
    app = ParallelSpringApp(root)
    root.mainloop()