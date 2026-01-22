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
        self.root.geometry("1150x850") # Slightly wider for new column
        
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
        
        # Added "Net Rate" column to display the sorting criteria
        cols = ("PartNum", "Qty Needed", "Net Spring Rate", "Single End Force", "Total Sys Force", "Max Deflect", "Total Price")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        for col in cols:
            self.tree.heading(col, text=col)
            # Make Net Rate column stand out slightly
            self.tree.column(col, width=130, anchor="center")
        
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
                           command=lambda s: var.set(round(float(s))))
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
                    lg = parse_inch_string(row.get('Length', '0'))
                    ext_lg = parse_inch_string(row.get('Extended Lg @ Max Load', '0'))
                    max_f_str = row.get('Max Load (lb)', row.get('Max.', '0'))
                    max_f_lb = float(max_f_str) if max_f_str else 0.0
                    rate_lb_in = parse_rate_string(row.get('Spring Rate', '0'))
                    price = parse_price(row.get('Price', '0'))
                    pkg_qty = float(row.get('Pkg Qty', 1))
                    
                    self.spring_data.append({
                        'part': row.get('Part Number', 'Unknown'),
                        'max_f_n': max_f_lb * 4.44822,
                        'rate_n_mm': rate_lb_in * 0.175126,
                        'max_def_mm': (ext_lg - lg) * 25.4,
                        'unit_price': price / pkg_qty,
                        'pkg_qty': pkg_qty
                    })
            self.calculate()
        except Exception as e:
            messagebox.showerror("Error", f"Could not parse CSV: {e}")

    def calculate(self, *args):
        try:
            # Requirements
            L_rope = 600.0  
            r_int = 2.0     
            T_req_Nmm = 6.0 
            
            r_ext = self.var_r_ext.get()
            R_large = self.var_R_large.get()
            r_spring = self.var_r_spring.get()
            
            if R_large <= 0 or r_ext <= 0 or r_spring <= 0:
                self.lbl_results.config(text="TARGET: Invalid Radii (Must be > 0)")
                for item in self.tree.get_children(): self.tree.delete(item)
                return

            theta1 = L_rope / r_int
            theta2 = theta1 * (r_ext / R_large)
            req_travel_mm = theta2 * r_spring
            req_force_n = (T_req_Nmm * R_large) / (r_ext * r_spring)
            
            self.lbl_results.config(text=f"TARGET: {req_force_n:.3f} N Force at {req_travel_mm:.1f} mm Extension")
            
            # Temporary list to store valid configurations for sorting
            valid_configs = []
                
            for s in self.spring_data:
                if s['max_def_mm'] < req_travel_mm:
                    continue
                
                f_retracted_single = s['max_f_n'] - (s['rate_n_mm'] * req_travel_mm)
                if f_retracted_single <= 0:
                    continue 
                
                qty_needed = math.ceil(req_force_n / f_retracted_single)
                if qty_needed > 10:
                    continue
                
                # Calculation of Net Spring Rate (Total K)
                net_spring_rate = qty_needed * s['rate_n_mm']
                
                total_sys_force = qty_needed * f_retracted_single
                total_cost = qty_needed * s['unit_price']

                # Store result in a dictionary for easy sorting
                valid_configs.append({
                    'part': s['part'],
                    'qty': qty_needed,
                    'net_rate': net_spring_rate,
                    'single_f': f_retracted_single,
                    'total_f': total_sys_force,
                    'max_def': s['max_def_mm'],
                    'cost': total_cost
                })
            
            # --- SORTING LOGIC ---
            # Sort the list by net_rate in increasing order
            valid_configs.sort(key=lambda x: x['net_rate'])

            # Clear and Re-populate the table
            for item in self.tree.get_children():
                self.tree.delete(item)

            for config in valid_configs:
                self.tree.insert("", tk.END, values=(
                    config['part'],
                    f"{config['qty']}x",
                    f"{config['net_rate']:.3f} N/mm", # Display net rate
                    f"{config['single_f']:.2f} N",
                    f"{config['total_f']:.2f} N",
                    f"{config['max_def']:.1f} mm",
                    f"${config['cost']:.2f}"
                ))
                    
        except Exception:
            pass

if __name__ == "__main__":
    root = tk.Tk()
    app = ParallelSpringApp(root)
    root.mainloop()