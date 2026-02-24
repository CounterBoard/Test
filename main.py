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
        else:
            print(f"❌ Ошибка получения истории: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Ошибка получения истории: {e}")
        return None

def send_history_to_telegram(chat_id, count=10):
    """Отправляет историю сообщений в Telegram"""
    history = get_chat_history(count)
    
    if not history or len(history) == 0:
        tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": "📭 Нет сообщений в истории"
        }
        requests.post(tg_url, json=data)
        return
    
    messages = []
    for msg in reversed(history[:count]):  # новые внизу
        msg_type = msg.get('type', '')
        sender = msg.get('senderName', 'Неизвестно')
        text = msg.get('textMessage', '')
        timestamp = msg.get('timestamp', 0)
        
        time_str = datetime.fromtimestamp(timestamp).strftime('%H:%M %d.%m')
        
        # Определяем тип сообщения и отправителя
        if msg_type == 'incoming':
            arrow = '📥'
        else:
            arrow = '📤'
            sender = 'ымел осла'  # твоё имя для исходящих
        
        if len(text) > 100:
            text = text[:100] + '...'
        
        messages.append(f"{arrow} [{time_str}] {sender}:\n{text}")
    
    full_text = f"📜 **История чата (последние {len(messages)}):**\n\n" + "\n\n".join(messages)
    
    if len(full_text) > 4000:
        full_text = full_text[:4000] + "...\n\n(сообщение обрезано)"
    
    tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": full_text,
        "parse_mode": "Markdown"
    }
    requests.post(tg_url, json=data)
    print(f"📜 История из {count} сообщений отправлена в Telegram")

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
        
        try:
            update = json.loads(post_data)
            
            if 'message' in update and 'text' in update['message']:
                text = update['message']['text']
                chat_id = update['message']['chat']['id']
                
                if str(chat_id) == str(TELEGRAM_CHAT_ID):
                    if text.startswith('/h'):
                        parts = text.split()
                        count = 10
                        if len(parts) > 1 and parts[1].isdigit():
                            count = int(parts[1])
                        
                        print(f"📨 Получена команда /h с параметром {count}")
                        send_history_to_telegram(chat_id, count)
        except Exception as e:
            print(f"❌ Ошибка обработки команды: {e}")
        
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

def send_text_to_telegram(text, sender_name):
    """Отправляет текстовое сообщение в Telegram в нужном формате"""
    full_message = f"📨 **MAX от {sender_name}:**\n \n{text}"
    
    tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    tg_data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": full_message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(tg_url, json=tg_data, timeout=10)
        if response.status_code == 200:
            return True
        else:
            print(f"❌ Ошибка Telegram: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")
        return False

print("=" * 50)
print("🚀 МОСТ MAX → TELEGRAM (С ИСТОРИЕЙ И КОМАНДОЙ /h)")
print("=" * 50)
print(f"📱 Инстанс: {ID_INSTANCE}")
print(f"💬 Чат MAX: {MAX_CHAT_ID}")
print(f"📬 Чат Telegram: {TELEGRAM_CHAT_ID}")
print("=" * 50)
print("🟢 Запущено. Опрос истории каждую секунду...")
print("📝 Команда /h - последние 10 сообщений, /h 5 - последние 5")
print("📊 Статистика каждые 10 сообщений\n")

receive_url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/receiveNotification/{API_TOKEN}"

while True:
    try:
        # Получаем последние 5 сообщений из истории
        history = get_chat_history(5)
        
        if history and isinstance(history, list):
            for msg in history:
                msg_id = msg.get('idMessage')
                timestamp = msg.get('timestamp', 0)
                
                if not msg_id or msg_id in processed_messages:
                    continue
                
                if msg.get('type') == 'incoming':
                    sender_name = msg.get('senderName', 'Неизвестно')
                else:
                    sender_name = "ымел осла"
                
                if msg.get('typeMessage') == 'textMessage':
                    text = msg.get('textMessage', '')
                    if text:
                        stats['total'] += 1
                        
                        print(f"\n📥 [{datetime.now().strftime('%H:%M:%S')}] НОВОЕ СООБЩЕНИЕ:")
                        print(f"👤 От: {sender_name}")
                        print(f"📝 Текст: {text[:50]}{'...' if len(text) > 50 else ''}")
                        
                        if send_text_to_telegram(text, sender_name):
                            stats['sent'] += 1
                            processed_messages.add(msg_id)
                        else:
                            stats['skipped'] += 1
                
                elif msg.get('typeMessage') in ['imageMessage', 'videoMessage', 'documentMessage', 'audioMessage']:
                    print(f"\n📥 МЕДИА от {sender_name} (пока не обрабатывается)")
                    processed_messages.add(msg_id)
                    stats['skipped'] += 1
                
                if len(processed_messages) > 1000:
                    processed_messages = set(list(processed_messages)[-500:])
                
                if stats['total'] > 0 and stats['total'] % 10 == 0:
                    print("\n" + "="*50)
                    print("📊 СТАТИСТИКА:")
                    print(f"📥 Всего новых: {stats['total']}")
                    print(f"✅ Отправлено: {stats['sent']}")
                    print(f"⏭️ Пропущено: {stats['skipped']}")
                    print("="*50)
        
        time.sleep(1)
        
    except KeyboardInterrupt:
        print("\n\n👋 Скрипт остановлен")
        break
    except Exception as e:
        print(f"\n❌ Ошибка в основном цикле: {e}")
        time.sleep(5)
