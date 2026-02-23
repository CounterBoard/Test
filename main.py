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
processed_messages = set()  # ID сообщений, которые уже отправили
stats = {'total': 0, 'sent': 0, 'skipped': 0}

# ===== ВЕБ-СЕРВЕР ДЛЯ RENDER =====
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bridge is running (history mode)")
    
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
# =================================

def get_chat_history(count=5):
    """Получает последние сообщения из истории чата"""
    url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/GetChatHistory/{API_TOKEN}"
    payload = {
        "chatId": MAX_CHAT_ID,
        "count": count
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Ошибка получения истории: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Ошибка при запросе истории: {e}")
        return None

def send_text_to_telegram(text, sender_name, timestamp):
    """Отправляет текстовое сообщение в Telegram в нужном формате"""
    # Убираем время, оставляем только имя и сообщение с отступом
    full_message = f"📨 **MAX от {sender_name}:**\n\n{text}"
    
    tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    tg_data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": full_message,
        "parse_mode": "Markdown"  # Используем Markdown для жирного текста
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
print("🚀 МОСТ MAX → TELEGRAM (РЕЖИМ ИСТОРИИ)")
print("=" * 50)
print(f"📱 Инстанс: {ID_INSTANCE}")
print(f"💬 Чат MAX: {MAX_CHAT_ID}")
print(f"📬 Чат Telegram: {TELEGRAM_CHAT_ID}")
print("=" * 50)
print("🟢 Запущено. Опрос истории каждую секунду...")
print("⏱️ Максимальная задержка: 1 секунда")
print("📊 Статистика будет каждые 50 сообщений\n")

while True:
    try:
        # Получаем последние 5 сообщений из истории
        history = get_chat_history(5)
        
        if history and isinstance(history, list):
            for msg in history:
                msg_id = msg.get('idMessage')
                timestamp = msg.get('timestamp', 0)
                
                # Пропускаем уже обработанные
                if not msg_id or msg_id in processed_messages:
                    continue
                
                # Определяем отправителя (имя и фамилия берутся из senderName)
                sender_name = msg.get('senderName', 'Неизвестно')
                
                # Если сообщение отправлено тобой, добавляем пометку
                if msg.get('type') != 'incoming':
                    sender_name = f"{sender_name} (я)"
                
                # Текстовые сообщения
                if msg.get('typeMessage') == 'textMessage':
                    text = msg.get('textMessage', '')
                    if text:
                        stats['total'] += 1
                        
                        print(f"\n📥 [{datetime.now().strftime('%H:%M:%S')}] НОВОЕ СООБЩЕНИЕ:")
                        print(f"👤 От: {sender_name}")
                        print(f"📝 Текст: {text[:50]}{'...' if len(text) > 50 else ''}")
                        
                        if send_text_to_telegram(text, sender_name, timestamp):
                            stats['sent'] += 1
                            processed_messages.add(msg_id)
                        else:
                            stats['skipped'] += 1
                
                # Медиа сообщения (пока просто логируем)
                elif msg.get('typeMessage') in ['imageMessage', 'videoMessage', 'documentMessage', 'audioMessage']:
                    print(f"\n📥 МЕДИА от {sender_name} (пока не обрабатывается)")
                    processed_messages.add(msg_id)
                    stats['skipped'] += 1
                
                # Ограничиваем размер хранилища
                if len(processed_messages) > 1000:
                    processed_messages = set(list(processed_messages)[-500:])
                
                # Статистика каждые 50 сообщений
                if stats['total'] > 0 and stats['total'] % 50 == 0:
                    print("\n" + "="*50)
                    print("📊 СТАТИСТИКА:")
                    print(f"📥 Всего новых: {stats['total']}")
                    print(f"✅ Отправлено: {stats['sent']}")
                    print(f"⏭️ Пропущено: {stats['skipped']}")
                    print("="*50)
        
        # Ждём 1 секунду (соблюдаем лимит API)
        time.sleep(1)
        
    except KeyboardInterrupt:
        print("\n\n👋 Скрипт остановлен")
        break
    except Exception as e:
        print(f"\n❌ Ошибка в основном цикле: {e}")
        time.sleep(5)
