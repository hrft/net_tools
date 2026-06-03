import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import socket, ssl, subprocess, threading, os, time

class HRFT_VPN_ULTIMATE:
    def __init__(self, root):
        self.root = root
        self.root.title("HRFT VPN - Fixed & System-Wide")
        self.root.geometry("850x650")
        self.sudo_password = tk.StringVar()
        self.status_text = tk.StringVar(value="Status: Ready")

        # --- Password & Tools ---
        top_frame = tk.LabelFrame(root, text=" 1. System Access ", padx=10, pady=10)
        top_frame.pack(pady=10, padx=20, fill="x")
        tk.Label(top_frame, text="Sudo Password:").pack(side="left")
        tk.Entry(top_frame, textvariable=self.sudo_password, show="*", width=20).pack(side="left", padx=5)
        tk.Button(top_frame, text="Flush & Reset Network", bg="orange", command=self.flush_network).pack(side="right")

        # --- File & Scan ---
        mid_frame = tk.Frame(root)
        mid_frame.pack(pady=10)
        tk.Button(mid_frame, text="Load vpngate.csv", command=self.load_file, width=15).grid(row=0, column=0, padx=10)
        self.scan_btn = tk.Button(mid_frame, text="Scan Protocol", command=self.start_scan, state="disabled", width=15)
        self.scan_btn.grid(row=0, column=1, padx=10)

        # --- Table ---
        self.tree = ttk.Treeview(root, columns=("H", "C", "S"), show='headings')
        self.tree.heading("H", text="Server Address (IP/Host)")
        self.tree.heading("C", text="Country")
        self.tree.heading("S", text="Speed (MB/s)")
        self.tree.pack(pady=10, padx=20, fill="both", expand=True)

        # --- Control ---
        self.conn_btn = tk.Button(root, text="CONNECT (Full System Redirect)", bg="#27ae60", fg="white", 
                                  command=self.connect, state="disabled", height=2, width=30)
        self.conn_btn.pack(pady=10)
        tk.Button(root, text="STOP ALL CONNECTIONS", bg="#c0392b", fg="white", command=self.stop).pack(pady=5)
        
        tk.Label(root, textvariable=self.status_text, fg="blue", font=("Arial", 10, "bold")).pack()

    def load_file(self):
        f = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
        if f: self.file_path = f; self.scan_btn.config(state="normal")

    def flush_network(self):
        pw = self.sudo_password.get()
        if not pw: return messagebox.showerror("Error", "Enter Sudo Password")
        os.system(f"echo '{pw}' | sudo -S pkill sstpc")
        os.system(f"echo '{pw}' | sudo -S ip route flush cache")
        self.status_text.set("Network reset done.")

    def start_scan(self):
        self.tree.delete(*self.tree.get_children())
        self.status_text.set("Scanning... Please wait for list to fill.")
        threading.Thread(target=self.run_scan, daemon=True).start()

    def run_scan(self):
        try:
            with open(self.file_path, "r", encoding="utf-8", errors='ignore') as f:
                for line in f:
                    # نادیده گرفتن خطوط توضیحات و خالی
                    if line.startswith("*") or line.startswith("#") or len(line) < 50: continue
                    parts = line.split(",")
                    if len(parts) < 10: continue
                    
                    host = parts[0]
                    if self.quick_check(host):
                        try:
                            # تبدیل بیت بر ثانیه به مگابایت بر ثانیه
                            mbps = round(float(parts[4]) / 8 / 10**6, 2)
                        except: mbps = 0.0
                        self.tree.insert("", "end", values=(host, parts[6], f"{mbps} MB/s"))
            
            self.root.after(0, lambda: self.conn_btn.config(state="normal"))
            self.root.after(0, lambda: self.status_text.set("Scan complete. Choose a server."))
        except Exception as e:
            print(f"File Error: {e}")

    def quick_check(self, host):
        try:
            with socket.create_connection((host, 443), timeout=0.6) as s:
                ssl.create_default_context().wrap_socket(s, server_hostname=host)
                return True
        except: return False

    def connect(self):
        sel = self.tree.focus()
        if not sel: return
        host = self.tree.item(sel)['values'][0]
        pw = self.sudo_password.get()
        if not pw: return messagebox.showwarning("Pass", "Sudo Pass Required")

        self.status_text.set(f"Connecting to {host}...")
        
        def run_vpn():
            # ۱. اجرای دستور SSTP
            cmd = f"echo '{pw}' | sudo -S sstpc --cert-warn --user vpn --password vpn {host} -- defaultroute usepeerdns lock"
            subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # ۲. صبر برای ایجاد اینترفیس ppp0
            time.sleep(8)
            
            # ۳. اجبار سیستم به استفاده از ppp0 با Metric پایین (اولویت بالا)
            # این همان قطعه کدی است که باعث می‌شود کل سیستم VPN شود
            os.system(f"echo '{pw}' | sudo -S ip route add default dev ppp0 metric 1")
            
            self.root.after(0, lambda: self.status_text.set("VPN Connected! System-wide redirect active."))

        threading.Thread(target=run_vpn, daemon=True).start()

    def stop(self):
        self.flush_network()
        self.status_text.set("Disconnected.")

if __name__ == "__main__":
    root = tk.Tk(); app = HRFT_VPN_ULTIMATE(root); root.mainloop()