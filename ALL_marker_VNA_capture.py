import socket
import csv
import os
import re
import tkinter as tk
from tkinter import messagebox
from datetime import datetime

# ====================== CONFIG ======================
HOST = "127.0.0.1"
PORT = 5001
CSV_FILE = "cable_data.csv"
TIMEOUT = 8.0

TRACES = {
    1: {"name": "S11",   "markers": range(1, 7)},
    2: {"name": "S22",   "markers": range(1, 7)},
    3: {"name": "S21",   "markers": range(1, 7)},
    4: {"name": "Smith", "markers": [1]},
}
# ====================================================

def is_vna_connected() -> bool:
    """Check if ShockLine software is running and accepting SCPI"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2.0)
            s.connect((HOST, PORT))
            s.sendall(b"*IDN?\n")
            reply = s.recv(1024).decode(errors="ignore").strip()
            return len(reply) > 0          # any reply means connected
    except:
        return False

def send_scpi(cmd: str) -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(TIMEOUT)
            s.connect((HOST, PORT))
            s.sendall((cmd + "\n").encode())
            data = b""
            while True:
                chunk = s.recv(65536)
                if not chunk:
                    break
                data += chunk
                if b"\n" in chunk:
                    break
            return data.decode(errors="ignore").strip()
    except Exception as e:
        raise RuntimeError(f"SCPI error: {e}")

def get_marker_data():
    results = {}
    for tr_num, info in TRACES.items():
        for m in info["markers"]:
            y_raw = send_scpi(f":CALCulate1:PARameter{tr_num}:MARKer{m}:Y?")
            x_raw = send_scpi(f":CALCulate1:PARameter{tr_num}:MARKer{m}:X?")
            
            key = f"{info['name']}_M{m}"
            y_parts = [p.strip() for p in y_raw.split(",")]
            
            if len(y_parts) == 1:
                results[f"{key}_Y"] = y_parts[0]
            else:
                results[f"{key}_Y1"] = y_parts[0]
                results[f"{key}_Y2"] = y_parts[1]
            
            results[f"{key}_X"] = x_raw
    return results

def get_full_trace_data():
    sdata = {}
    for tr in range(1, 5):
        raw = send_scpi(f":CALCulate1:PARameter{tr}:DATA:SDATa?")
        values = [float(x) for x in raw.replace(" ", "").split(",") if x]
        sdata[tr] = values
    
    try:
        freq_raw = send_scpi(":SENSe1:FREQuency:DATA?")
        freqs = [float(x) for x in freq_raw.replace(" ", "").split(",") if x]
    except:
        start = float(send_scpi(":SENSe1:FREQuency:STARt?"))
        stop  = float(send_scpi(":SENSe1:FREQuency:STOP?"))
        points = len(sdata[1]) // 2
        freqs = [start + i * (stop - start) / max(points - 1, 1) for i in range(points)]
    
    points = len(sdata[1]) // 2
    rows = []
    for i in range(points):
        row = [
            freqs[i] if i < len(freqs) else 0.0,
            sdata[1][2*i], sdata[1][2*i+1],
            sdata[2][2*i], sdata[2][2*i+1],
            sdata[3][2*i], sdata[3][2*i+1],
            sdata[4][2*i], sdata[4][2*i+1],
        ]
        rows.append(row)
    return rows

def safe_filename(text: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", text).strip()

def write_all_files(part_no: str, serial: str, marker_data: dict, full_rows: list):
    fieldnames_marker = ["Product_Part_No", "Cable_Serial", "Timestamp"] + list(marker_data.keys())
    
    row_marker = {
        "Product_Part_No": part_no,
        "Cable_Serial": serial,
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    row_marker.update(marker_data)
    
    # 1. Main cumulative
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames_marker)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row_marker)
    
    base_dir = os.path.dirname(os.path.abspath(CSV_FILE)) or "."
    safe_part   = safe_filename(part_no)
    safe_serial = safe_filename(serial)
    
    # 2. Marker only file
    marker_file = os.path.join(base_dir, f"{safe_part}_{safe_serial}.csv")
    with open(marker_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames_marker)
        writer.writeheader()
        writer.writerow(row_marker)
    
    # 3. Full S2P-style file
    full_file = os.path.join(base_dir, f"{safe_part}_{safe_serial}_FULL.csv")
    headers_full = [
        "Frequency_Hz",
        "S11_Real", "S11_Imag",
        "S22_Real", "S22_Imag",
        "S21_Real", "S21_Imag",
        "Smith_Real", "Smith_Imag"
    ]
    with open(full_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers_full)
        writer.writerows(full_rows)
    
    return os.path.basename(marker_file), os.path.basename(full_file)

def get_last_serial_from_csv():
    if not os.path.isfile(CSV_FILE):
        return ""
    try:
        with open(CSV_FILE, newline="", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
            if reader:
                return reader[-1].get("Cable_Serial", "")
    except:
        pass
    return ""

def increment_serial(serial: str) -> str:
    match = re.search(r'(\d+)(?!.*\d)', serial)
    if match:
        num = match.group(1)
        new_num = str(int(num) + 1).zfill(len(num))
        return serial[:match.start()] + new_num + serial[match.end():]
    return serial

# ====================== GUI ======================
class CaptureApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ShockLine Cable Capture - Production")
        self.root.geometry("620x520")
        self.root.resizable(False, False)
        
        # Title
        tk.Label(root, text="RF Cable Data Capture", font=("Arial", 16, "bold")).pack(pady=8)
        
        # ===== VNA Connection Status =====
        status_frame = tk.Frame(root)
        status_frame.pack(pady=5)
        
        tk.Label(status_frame, text="VNA Status:", font=("Arial", 11, "bold")).pack(side="left")
        self.conn_label = tk.Label(status_frame, text="Checking...", font=("Arial", 11, "bold"), width=18)
        self.conn_label.pack(side="left", padx=8)
        
        tk.Button(status_frame, text="Test Connection", font=("Arial", 9),
                  command=self.update_connection_status).pack(side="left", padx=5)
        
        # Part No
        frame1 = tk.Frame(root)
        frame1.pack(pady=6, fill="x", padx=30)
        tk.Label(frame1, text="Product Part No.:", font=("Arial", 11), width=18, anchor="e").pack(side="left")
        self.part_var = tk.StringVar()
        self.part_entry = tk.Entry(frame1, textvariable=self.part_var, font=("Arial", 12), width=28)
        self.part_entry.pack(side="left", padx=5)
        
        # Serial
        frame2 = tk.Frame(root)
        frame2.pack(pady=6, fill="x", padx=30)
        tk.Label(frame2, text="Cable Serial No.:", font=("Arial", 11), width=18, anchor="e").pack(side="left")
        self.serial_var = tk.StringVar()
        self.serial_entry = tk.Entry(frame2, textvariable=self.serial_var, font=("Arial", 12), width=28)
        self.serial_entry.pack(side="left", padx=5)
        
        last = get_last_serial_from_csv()
        if last:
            self.serial_var.set(increment_serial(last))
        
        self.auto_inc = tk.BooleanVar(value=True)
        tk.Checkbutton(root, text="Auto-increment Serial after each capture",
                       variable=self.auto_inc, font=("Arial", 10)).pack(pady=6)
        
        # Capture button
        self.btn = tk.Button(root, text="CAPTURE DATA", font=("Arial", 14, "bold"),
                             bg="#4CAF50", fg="white", width=22, height=2,
                             command=self.on_capture)
        self.btn.pack(pady=12)
        
        # Status message
        self.status = tk.Label(root, text="Ready", font=("Arial", 9), fg="gray")
        self.status.pack(pady=4)
        
        # Info
        tk.Label(root, text=f"Main file: {os.path.abspath(CSV_FILE)}",
                 font=("Arial", 8), fg="#555").pack()
        
        tip = ("Each capture creates:\n"
               "• Main cumulative file\n"
               "• PartNo_Serial.csv          (markers)\n"
               "• PartNo_Serial_FULL.csv     (full S2P-style data)")
        tk.Label(root, text=tip, font=("Arial", 8), fg="#0066cc", justify="left").pack(pady=6)
        
        self.serial_entry.focus()
        self.root.bind("<Return>", lambda e: self.on_capture())
        
        # Initial connection check
        self.update_connection_status()
    
    def update_connection_status(self):
        connected = is_vna_connected()
        if connected:
            self.conn_label.config(text="● VNA Connected", fg="green")
        else:
            self.conn_label.config(text="● VNA Not Connected", fg="red")
        return connected
    
    def on_capture(self):
        # Always check connection first
        if not self.update_connection_status():
            messagebox.showerror("VNA Not Connected",
                                 "ShockLine software is not running or not listening on port 5001.\n\n"
                                 "Please start ShockLine software first.")
            return
        
        part_no = self.part_var.get().strip()
        serial  = self.serial_var.get().strip()
        
        if not part_no or not serial:
            messagebox.showwarning("Missing Data", "Please enter both Part No. and Serial No.")
            return
        
        self.btn.config(state="disabled", text="Capturing...")
        self.status.config(text="Reading markers + full trace data...", fg="blue")
        self.root.update()
        
        try:
            marker_data = get_marker_data()
            full_rows   = get_full_trace_data()
            
            m_file, f_file = write_all_files(part_no, serial, marker_data, full_rows)
            
            self.status.config(text=f"✓ Saved: {m_file}  +  {f_file}", fg="green")
            
            if self.auto_inc.get():
                self.serial_var.set(increment_serial(serial))
            
            self.serial_entry.focus()
            self.serial_entry.selection_range(0, tk.END)
            
        except Exception as e:
            self.status.config(text="Error – see message", fg="red")
            messagebox.showerror("Error", str(e))
        
        finally:
            self.btn.config(state="normal", text="CAPTURE DATA")
            self.update_connection_status()

if __name__ == "__main__":
    root = tk.Tk()
    app = CaptureApp(root)
    root.mainloop()