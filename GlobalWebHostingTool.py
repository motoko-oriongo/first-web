import tkinter as tk
from tkinter import filedialog, messagebox
import os
import threading
import http.server
import ctypes
import sys
import ssl
import urllib.request
import json

# 檢查是否擁有系統管理員權限
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

# 取得真實公網 IP，用於設定 M365 DNS
def get_public_ip():
    try:
        req = urllib.request.Request('https://api.ipify.org?format=json', headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data.get('ip', '無法取得')
    except:
        return "無法取得 (請確認網路連線)"

class GlobalWebHostingTool:
    def __init__(self, root):
        self.root = root
        self.root.title("OrionGO 對外 HTTPS 伺服器 (全球公開版)")
        self.root.geometry("480x520")
        
        self.server_thread = None
        self.httpd = None
        self.hosting_dir = tk.StringVar()
        self.cert_file = tk.StringVar()
        self.key_file = tk.StringVar()
        
        self.public_ip = get_public_ip()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # --- 介面設計 ---
        ip_frame = tk.Frame(root, bg="#f0f8ff", pady=10)
        ip_frame.pack(fill="x")
        tk.Label(ip_frame, text="🌍 您的實體公網 IP 為:", font=("Arial", 10, "bold"), bg="#f0f8ff", fg="darkblue").pack()
        tk.Entry(ip_frame, textvariable=tk.StringVar(value=self.public_ip), state='readonly', width=20, justify='center', font=("Arial", 14, "bold")).pack()
        tk.Label(ip_frame, text="(請將此 IP 填入 Microsoft 365 DNS 的「A 記錄」中)", bg="#f0f8ff", fg="gray", font=("Arial", 9)).pack()

        tk.Label(root, text="1. 選擇網頁根目錄:", font=("Arial", 10, "bold")).pack(pady=(15, 0))
        tk.Button(root, text="📂 瀏覽資料夾", command=self.select_directory).pack()
        tk.Label(root, textvariable=self.hosting_dir, fg="blue").pack()

        tk.Label(root, text="2. 憑證設定 (對外公開請務必使用真實 SSL 憑證):", font=("Arial", 10, "bold")).pack(pady=(15, 0))
        tk.Label(root, text="※ 請勿使用 mkcert 自簽憑證，外部訪客會看到不安全紅色警告\n※ 請使用 Let's Encrypt 等機構核發的正式 .pem 憑證檔案", fg="red", font=("Arial", 9)).pack()
        
        cert_frame = tk.Frame(root)
        cert_frame.pack(pady=10)
        tk.Button(cert_frame, text="手動選擇正式憑證 (.pem/.crt)", command=self.select_cert).grid(row=0, column=0, padx=5)
        tk.Button(cert_frame, text="手動選擇私鑰 (.key/.pem)", command=self.select_key).grid(row=0, column=1, padx=5)
        
        tk.Label(root, textvariable=self.cert_file, fg="purple", font=("Arial", 8)).pack()
        tk.Label(root, textvariable=self.key_file, fg="purple", font=("Arial", 8)).pack()

        self.start_btn = tk.Button(root, text="🚀 啟動全球 HTTPS 伺服器", bg="green", fg="white", font=("Arial", 12, "bold"), command=self.start_server)
        self.start_btn.pack(pady=20)

    def select_directory(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.hosting_dir.set(folder_selected)

    def select_cert(self):
        file_selected = filedialog.askopenfilename(filetypes=[("Certificate Files", "*.pem *.crt"), ("All Files", "*.*")])
        if file_selected:
            self.cert_file.set(file_selected)

    def select_key(self):
        file_selected = filedialog.askopenfilename(filetypes=[("Key Files", "*.pem *.key"), ("All Files", "*.*")])
        if file_selected:
            self.key_file.set(file_selected)

    def run_server(self, directory, cert_path, key_path):
        os.chdir(directory)
        handler = http.server.SimpleHTTPRequestHandler
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certfile=cert_path, keyfile=key_path)
            
            # 使用 ThreadingHTTPServer 支援多執行緒，確保全球多人連線不會卡頓
            # 綁定 "0.0.0.0" 確保能接收來自外網的請求
            self.httpd = http.server.ThreadingHTTPServer(("0.0.0.0", 443), handler)
            self.httpd.socket = context.wrap_socket(self.httpd.socket, server_side=True)
            self.httpd.serve_forever()
        except OSError as e:
            messagebox.showerror("Port 錯誤", f"Port 443 被佔用。請確保沒有其他伺服器 (如 IIS、Apache、Skype) 運行。\n\n詳細錯誤: {e}")
        except Exception as e:
            messagebox.showerror("憑證錯誤", f"載入憑證失敗，請確認檔案是否為真實有效的憑證與私鑰。\n\n詳細錯誤: {e}")

    def start_server(self):
        directory = self.hosting_dir.get()
        cert_path = self.cert_file.get()
        key_path = self.key_file.get()

        if not directory or not cert_path or not key_path:
            messagebox.showwarning("警告", "請確保已選擇資料夾、正式憑證與私鑰！")
            return

        if self.server_thread is None or not self.server_thread.is_alive():
            self.server_thread = threading.Thread(target=self.run_server, args=(directory, cert_path, key_path), daemon=True)
            self.server_thread.start()
            
            self.start_btn.config(text=f"伺服器對外運行中", state=tk.DISABLED, bg="gray")
            messagebox.showinfo("成功", "HTTPS 伺服器已成功啟動！\n\n確保您已完成：\n1. M365 DNS 已設定 A 記錄\n2. 路由器已設定 Port Forwarding\n\n全球訪客即可透過 https://oriongo.com.tw 瀏覽！")

    def on_closing(self):
        if self.httpd:
            self.httpd.shutdown()
        self.root.destroy()
        sys.exit()

if __name__ == "__main__":
    if is_admin():
        root = tk.Tk()
        app = GlobalWebHostingTool(root)
        root.mainloop()
    else:
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)