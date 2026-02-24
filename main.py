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
processed_ids = set()
stats = {'total': 0, 'sent': 0, 'skipped': 0}

# ===== ФУНКЦИЯ ДЛЯ ПОЛУЧЕНИЯ ИСТОРИИ =====
def get_chat_history(count=10):
    """Получает последние count сообщений из чата Max"""
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

def send_history_to_telegram(chat_id, count=10):
    """Отправляет историю сообщений в Telegram"""
    history = get_chat_history(count)
    if not history or len(history) == 0:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", 
                     json={"chat_id": chat_id, "text": "📭 Нет сообщений в истории"})
        return
    
    messages = []
    seen_ids = set()
    
    for msg in reversed(history[:count]):
        msg_id = msg.get('idMessage')
        if not msg_id or msg_id in seen_ids:
            continue
        seen_ids.add(msg_id)
        
        if msg.get('typeMessage') != 'textMessage':
            continue
        
        text = msg.get('textMessage', '')
        if not text:
            continue
            
        timestamp = msg.get('timestamp', 0)
        time_str = datetime.fromtimestamp(timestamp).strftime('%H:%M %d.%m')
        
        if msg.get('type') == 'incoming':
            sender = msg.get('senderName', 'Неизвестно')
            arrow = '📥'
        else:
            sender = "@scul_k"
            arrow = '📤'
        
        # Проверяем, есть ли ответ (цитирование)
        reply_prefix = ""
        if 'quotedMessage' in msg:
            quoted = msg['quotedMessage']
            quoted_text = quoted.get('textMessage', '')
            quoted_sender = quoted.get('senderName', '')
            if quoted_text:
                if quoted_sender:
                    reply_prefix = f"↪️ В ответ на {quoted_sender}:\n> {quoted_text}\n\n"
                else:
                    reply_prefix = f"↪️ В ответ на сообщение:\n> {quoted_text}\n\n"
        
        if len(text) > 100:
            text = text[:100] + '...'
        
        messages.append(f"{arrow} [{time_str}] {sender}:\n{reply_prefix}{text}")
    
    if not messages:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", 
                     json={"chat_id": chat_id, "text": "📭 В истории нет текстовых сообщений"})
        return
    
    full_text = f"📜 История чата (последние {len(messages)}):\n\n" + "\n\n".join(messages)
    if len(full_text) > 4000:
        full_text = full_text[:4000] + "...\n\n(сообщение обрезано)"
    
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", 
                 json={"chat_id": chat_id, "text": full_text})

def send_text_to_telegram(text, sender_name, reply_info=""):
    """Отправляет текстовое сообщение в Telegram с поддержкой ответов"""
    if reply_info:
        full_message = f"{reply_info}📨 MAX от {sender_name}:\n{text}"
    else:
        full_message = f"📨 MAX от {sender_name}:\n{text}"
    
    try:
        response = requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                                json={"chat_id": TELEGRAM_CHAT_ID, "text": full_message}, timeout=10)
        return response.status_code == 200
    except:
        return False

# ===== ВЕБ-СЕРВЕР =====
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bridge is running")
    
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()
    
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        if content_length > 0:
            try:
                update = json.loads(post_data)
                if 'message' in update and 'text' in update['message']:
                    text = update['message']['text']
                    chat_id = update['message']['chat']['id']
                    if str(chat_id) == str(TELEGRAM_CHAT_ID) and text.startswith('/h'):
                        parts = text.split()
                        count = 10
                        if len(parts) > 1 and parts[1].isdigit():
                            count = int(parts[1])
                        send_history_to_telegram(chat_id, count)
            except:
                pass
        
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
print("🚀 МОСТ MAX → TELEGRAM (С ЦИТИРОВАНИЕМ)")
print("=" * 50)
print(f"📱 Инстанс: {ID_INSTANCE}")
print(f"💬 Чат MAX: {MAX_CHAT_ID}")
print(f"📬 Чат Telegram: {TELEGRAM_CHAT_ID}")
print("=" * 50)
print("🟢 Запущено. Опрос истории каждую секунду...")
print("📝 Команда /h - последние 10 сообщений")
print("👤 Твои сообщения: @scul_k")
print("💬 Цитирование поддерживается\n")

last_cleanup = time.time()

while True:
    try:
        history = get_chat_history(15)
        
        if history and isinstance(history, list):
            for msg in reversed(history):
                msg_id = msg.get('idMessage')
                
                if not msg_id or msg_id in processed_ids:
                    continue
                
                if msg.get('typeMessage') != 'textMessage':
                    processed_ids.add(msg_id)
                    continue
                
                timestamp = msg.get('timestamp', 0)
                if time.time() - timestamp > 30:
                    processed_ids.add(msg_id)
                    continue
                
                text = msg.get('textMessage', '')
                if not text:
                    processed_ids.add(msg_id)
                    continue
                
                # 👇 ПОЛУЧАЕМ ИНФОРМАЦИЮ ОБ ОТВЕТЕ
                reply_info = ""
                if 'quotedMessage' in msg:
                    quoted = msg['quotedMessage']
                    quoted_text = quoted.get('textMessage', '')
                    quoted_sender = quoted.get('senderName', '')
                    if quoted_text:
                        if quoted_sender:
                            reply_info = f"↪️ В ответ на {quoted_sender}:\n> {quoted_text}\n\n"
                        else:
                            reply_info = f"↪️ В ответ на сообщение:\n> {quoted_text}\n\n"
                        print(f"📎 Найден ответ на: {quoted_text[:30]}...")
                
                if msg.get('type') == 'incoming':
                    sender_name = msg.get('senderName', 'Неизвестно')
                else:
                    sender_name = "@scul_k"
                
                stats['total'] += 1
                if send_text_to_telegram(text, sender_name, reply_info):
                    stats['sent'] += 1
                    processed_ids.add(msg_id)
                else:
                    stats['skipped'] += 1
                
                if stats['total'] % 10 == 0:
                    print(f"📊 Статистика: всего {stats['total']}, отправлено {stats['sent']}")
        
        # Очистка старых ID раз в минуту
        if time.time() - last_cleanup > 60:
            if len(processed_ids) > 500:
                processed_ids = set(list(processed_ids)[-500:])
            last_cleanup = time.time()
        
        time.sleep(1)
        
    except KeyboardInterrupt:
        print("\n\n👋 Скрипт остановлен")
        break
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        time.sleep(5)
