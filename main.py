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

# Проверка наличия переменных
if not all([ID_INSTANCE, API_TOKEN, MAX_CHAT_ID, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
    missing = [v for v in ['ID_INSTANCE', 'API_TOKEN', 'MAX_CHAT_ID', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID'] 
               if not os.environ.get(v)]
    raise ValueError(f"❌ Отсутствуют: {', '.join(missing)}")

# ===== ХРАНИЛИЩЕ =====
processed_ids = set()
sent_deletes = set()
message_cache = {}

# ===== ФУНКЦИИ =====
def get_chat_history(count=10):
    url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/GetChatHistory/{API_TOKEN}"
    payload = {
        "chatId": MAX_CHAT_ID,
        "count": min(count, 100)
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            return response.json()
        return []
    except:
        return []

def update_message_cache(history):
    if not history:
        return
    for msg in history:
        msg_id = msg.get('idMessage')
        if msg_id and msg.get('typeMessage') == 'textMessage':
            text = msg.get('textMessage', '')
            if text:
                message_cache[msg_id] = text

def send_deleted_notification(sender_name, deleted_text):
    full_message = f"🗑️ {sender_name} удалил сообщение:\n\n{deleted_text}"
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                     json={"chat_id": TELEGRAM_CHAT_ID, "text": full_message}, timeout=10)
        print(f"✅ Уведомление об удалении отправлено")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

# ===== ВЕБ-СЕРВЕР =====
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bridge is running")
    
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        if content_length > 0:
            try:
                update = json.loads(post_data)
                
                # 👇 ПРОСТАЯ ПРОВЕРКА НА УДАЛЕНИЕ
                body = update.get('body', {})
                message_data = body.get('messageData', {})
                
                if message_data.get('typeMessage') == 'deletedMessage':
                    print(f"\n🗑️ ОБНАРУЖЕНО УДАЛЕНИЕ!")
                    
                    sender_data = body.get('senderData', {})
                    deleted_data = message_data.get('deletedMessageData', {})
                    
                    stanza_id = deleted_data.get('stanzaId')
                    sender_name = sender_data.get('senderName', 'Неизвестно')
                    
                    if stanza_id and stanza_id not in sent_deletes:
                        deleted_text = message_cache.get(stanza_id, "Текст сообщения недоступен")
                        send_deleted_notification(sender_name, deleted_text)
                        sent_deletes.add(stanza_id)
                        
            except Exception as e:
                print(f"❌ Ошибка: {e}")
        
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    
    def log_message(self, format, *args): pass

def run_http_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), Handler)
    print(f"🌐 Веб-сервер запущен на порту {port}")
    server.serve_forever()

web_thread = threading.Thread(target=run_http_server, daemon=True)
web_thread.start()
# =====================

print("=" * 50)
print("🚀 МОСТ MAX → TELEGRAM")
print("=" * 50)
print("🟢 Запущено. Жду удалений...\n")

while True:
    try:
        history = get_chat_history(20)
        update_message_cache(history)
        time.sleep(1)
    except KeyboardInterrupt:
        break
    except:
        time.sleep(5)
