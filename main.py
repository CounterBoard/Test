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

# ===== ХРАНИЛИЩЕ ОБРАБОТАННЫХ СООБЩЕНИЙ =====
processed_messages = set()

def get_chat_history(count=5):
    """Получает последние count сообщений из чата Max"""
    url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/GetChatHistory/{API_TOKEN}"
    payload = {
        "chatId": MAX_CHAT_ID,
        "count": count
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            return response.json()
        return []
    except:
        return []

def send_text_to_telegram(text):
    """Отправляет текстовое сообщение в Telegram"""
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                     json={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=10)
    except:
        pass

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
    print(f"🌐 Веб-сервер запущен на порту {port}")
    server.serve_forever()

web_thread = threading.Thread(target=run_http_server, daemon=True)
web_thread.start()
# =====================

print("=" * 50)
print("🔍 ДИАГНОСТИКА: ПРОВЕРКА СТРУКТУРЫ СООБЩЕНИЙ")
print("=" * 50)
print("🟢 Запущено. Отправьте СООБЩЕНИЕ С ОТВЕТОМ в чат\n")

while True:
    try:
        history = get_chat_history(5)
        
        if history and isinstance(history, list):
            for msg in history:
                msg_id = msg.get('idMessage')
                
                if not msg_id or msg_id in processed_messages:
                    continue
                
                # Выводим полную структуру сообщения
                print("\n" + "="*60)
                print(f"📦 СООБЩЕНИЕ ID: {msg_id}")
                print(f"📌 Тип: {msg.get('typeMessage', 'unknown')}")
                print("📄 Полные данные:")
                print(json.dumps(msg, indent=2, ensure_ascii=False))
                print("="*60 + "\n")
                
                processed_messages.add(msg_id)
                
                # Если это текстовое сообщение, отправляем в Telegram для наглядности
                if msg.get('typeMessage') == 'textMessage':
                    text = msg.get('textMessage', '')
                    if text:
                        send_text_to_telegram(f"📨 {msg.get('senderName', 'Unknown')}: {text[:50]}...")
        
        time.sleep(2)
        
    except KeyboardInterrupt:
        print("\n\n👋 Скрипт остановлен")
        break
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        time.sleep(5)
