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
print("🔍 ДИАГНОСТИКА: ПРОВЕРКА ВХОДЯЩИХ СООБЩЕНИЙ")
print("=" * 50)
print(f"📱 Инстанс: {ID_INSTANCE}")
print(f"🎯 Ожидаемый чат: {MAX_CHAT_ID}")
print("=" * 50)
print("🟢 Запущено. Отправьте ЛЮБОЕ сообщение в ЛЮБОЙ чат Max...\n")

# ===== ВЕБ-СЕРВЕР ДЛЯ RENDER =====
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
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔔 ПОЛУЧЕНО СООБЩЕНИЕ!")
                print("=" * 60)
                
                # Показываем всю структуру
                print("📦 ПОЛНЫЕ ДАННЫЕ:")
                print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])  # Первые 1000 символов
                
                # Извлекаем ID чата
                body = data.get('body', {})
                sender_data = body.get('senderData', {})
                chat_id = sender_data.get('chatId')
                
                print("\n📌 САМОЕ ВАЖНОЕ:")
                print(f"ID чата отправителя: {chat_id}")
                print(f"Ожидаемый ID: {MAX_CHAT_ID}")
                print(f"Совпадают: {chat_id == MAX_CHAT_ID}")
                
                # Показываем тип сообщения
                message_data = body.get('messageData', {})
                msg_type = message_data.get('typeMessage')
                print(f"Тип сообщения: {msg_type}")
                
                # Удаляем уведомление
                delete_url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/deleteNotification/{API_TOKEN}/{receipt_id}"
                requests.delete(delete_url)
                print("=" * 60 + "\n")
        else:
            print(".", end="", flush=True)
            
    except requests.exceptions.Timeout:
        print("t", end="", flush=True)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        time.sleep(5)
    
    time.sleep(1)
