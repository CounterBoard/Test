import os
import requests
import time
import threading
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

# ===== ПЕРЕМЕННЫЕ ИЗ ОКРУЖЕНИЯ =====
ID_INSTANCE = os.environ.get('ID_INSTANCE')
API_TOKEN = os.environ.get('API_TOKEN')
MAX_CHAT_ID = os.environ.get('MAX_CHAT_ID')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
# ===================================

print("=" * 50)
print("🔍 ДИАГНОСТИКА СТИКЕРОВ")
print("=" * 50)
print("🟢 Запущено. Отправьте СТИКЕР в чат...\n")

# ===== ВЕБ-СЕРВЕР =====
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Diagnostic mode")
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()
    def log_message(self, format, *args): pass

def run_http_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), Handler)
    server.serve_forever()

web_thread = threading.Thread(target=run_http_server, daemon=True)
web_thread.start()
# =================================

receive_url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/receiveNotification/{API_TOKEN}"

while True:
    try:
        response = requests.get(receive_url, timeout=30)
        
        if response.status_code == 200 and response.text and response.text != "null":
            data = response.json()
            receipt_id = data.get('receiptId')
            
            if receipt_id:
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔔 ПОЛУЧЕНО!")
                print("📦 ВСЕ ДАННЫЕ:")
                print(json.dumps(data, indent=2, ensure_ascii=False))
                print("=" * 60)
                
                # Удаляем уведомление
                delete_url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/deleteNotification/{API_TOKEN}/{receipt_id}"
                requests.delete(delete_url)
                print("🗑️ Удалено\n")
        else:
            print(".", end="", flush=True)
            
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        time.sleep(5)
    
    time.sleep(1)
