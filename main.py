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

# Простая проверка
print("🟢 Запуск диагностической версии...")

# Хранилище ID обработанных сообщений
processed_ids = set()

def get_chat_history(count=10):
    url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/GetChatHistory/{API_TOKEN}"
    payload = {"chatId": MAX_CHAT_ID, "count": count}
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.json() if r.status_code == 200 else []
    except: return []

def send_telegram(text):
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                  json={"chat_id": TELEGRAM_CHAT_ID, "text": text})

def send_photo(photo_url, caption):
    # Скачиваем фото
    photo_data = requests.get(photo_url).content
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
                  data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption},
                  files={"photo": ("photo.webp", photo_data)})

# ===== ВЕБ-СЕРВЕР =====
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Diagnostic mode")
    def log_message(self, *args): pass

def run_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"🌐 Сервер на порту {port}")

run_server()

# ===== ОСНОВНОЙ ЦИКЛ =====
print("🟢 Начинаю мониторинг...")
while True:
    try:
        history = get_chat_history(5)
        
        for msg in history:
            msg_id = msg.get('idMessage')
            if not msg_id or msg_id in processed_ids:
                continue
            
            msg_type = msg.get('typeMessage')
            sender = "@scul_k" if msg.get('type') == 'outgoing' else msg.get('senderName', 'Неизвестно')
            
            print(f"\n📨 Найдено {msg_type} от {sender} (ID: {msg_id})")
            
            # ТЕКСТ
            if msg_type == 'textMessage':
                text = msg.get('textMessage', '')
                if text:
                    send_telegram(f"📨 {sender}:\n{text}")
                    print(f"✅ Текст отправлен")
                    processed_ids.add(msg_id)
            
            # ФОТО
            elif msg_type == 'imageMessage':
                photo_url = msg.get('downloadUrl')
                caption = msg.get('caption', '')
                if photo_url:
                    try:
                        send_photo(photo_url, f"📷 {sender}\n{caption}")
                        print(f"✅ Фото отправлено")
                        processed_ids.add(msg_id)
                    except Exception as e:
                        print(f"❌ Ошибка фото: {e}")
            
            # ВСЁ ОСТАЛЬНОЕ
            else:
                print(f"⏭️ Пропущен тип: {msg_type}")
                processed_ids.add(msg_id)
        
        time.sleep(2)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        time.sleep(5)
