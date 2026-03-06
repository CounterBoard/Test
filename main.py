import os
import requests
import time
import threading
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
print("🚀 МОСТ MAX → TELEGRAM (УЛЬТРА-УПРОЩЁННЫЙ)")
print("=" * 50)

processed_ids = set()

def get_chat_history(count=5):
    url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/GetChatHistory/{API_TOKEN}"
    try:
        r = requests.post(url, json={"chatId": MAX_CHAT_ID, "count": count}, timeout=10)
        return r.json() if r.status_code == 200 else []
    except: return []

def send_telegram(text):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                     json={"chat_id": TELEGRAM_CHAT_ID, "text": text})
    except: pass

def send_photo_force(photo_url, caption):
    try:
        print(f"📸 Скачиваю фото...")
        photo_data = requests.get(photo_url, timeout=30).content
        print(f"📦 Размер: {len(photo_data)} байт")
        
        files = {'photo': ('photo.jpg', photo_data)}
        data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': caption[:1024]}
        
        r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
                         data=data, files=files, timeout=30)
        
        if r.status_code == 200:
            print("✅ Фото отправлено!")
            return True
        else:
            print(f"❌ Ошибка: {r.status_code}")
            print(r.text)
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

# ===== ВЕБ-СЕРВЕР =====
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bridge")
    def log_message(self, *args): pass

def run_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"🌐 Сервер на порту {port}")

run_server()

print("🟢 Запущено. Жду сообщения...\n")

while True:
    try:
        history = get_chat_history(10)
        
        for msg in history:
            msg_id = msg.get('idMessage')
            if not msg_id or msg_id in processed_ids:
                continue
            
            msg_type = msg.get('typeMessage')
            
            # Определяем отправителя
            if msg.get('type') == 'incoming':
                sender = msg.get('senderName', 'Неизвестно')
            else:
                sender = "@scul_k"
            
            print(f"\n📨 Тип: {msg_type} от {sender}")
            
            # ТЕКСТ
            if msg_type == 'textMessage':
                text = msg.get('textMessage', '')
                if text:
                    send_telegram(f"📨 MAX от {sender}:\n\n{text}")
                    processed_ids.add(msg_id)
                    print(f"✅ Текст отправлен")
            
            # ФОТО
            elif msg_type == 'imageMessage':
                photo_url = msg.get('downloadUrl')
                caption = msg.get('caption', '')
                if photo_url:
                    if caption:
                        cap = f"📨 MAX от {sender}:\n\n{caption}"
                    else:
                        cap = f"📨 MAX от {sender}"
                    
                    if send_photo_force(photo_url, cap):
                        processed_ids.add(msg_id)
            
            # ВСЁ ОСТАЛЬНОЕ
            else:
                processed_ids.add(msg_id)
                print(f"⏭️ Пропущен")
        
        time.sleep(1)
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        time.sleep(5)
