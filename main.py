import os
import requests
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# ===== ПЕРЕМЕННЫЕ ИЗ ОКРУЖЕНИЯ =====
ID_INSTANCE = os.environ.get('ID_INSTANCE')
API_TOKEN = os.environ.get('API_TOKEN')
MAX_CHAT_ID = os.environ.get('MAX_CHAT_ID')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
# ===================================

# Проверка наличия переменных
if not all([ID_INSTANCE, API_TOKEN, MAX_CHAT_ID, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
    missing = []
    if not ID_INSTANCE: missing.append('ID_INSTANCE')
    if not API_TOKEN: missing.append('API_TOKEN')
    if not MAX_CHAT_ID: missing.append('MAX_CHAT_ID')
    if not TELEGRAM_BOT_TOKEN: missing.append('TELEGRAM_BOT_TOKEN')
    if not TELEGRAM_CHAT_ID: missing.append('TELEGRAM_CHAT_ID')
    raise ValueError(f"❌ Отсутствуют: {', '.join(missing)}")

# ===== ХРАНИЛИЩА =====
processed_ids = set()
sent_deletes = set()
stats = {'total': 0, 'sent': 0}

# ===== ФУНКЦИЯ ДЛЯ ПОЛУЧЕНИЯ ИСТОРИИ =====
def get_chat_history(count=15):
    url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/GetChatHistory/{API_TOKEN}"
    payload = {"chatId": MAX_CHAT_ID, "count": min(count, 100)}
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            return response.json()
        return []
    except:
        return []

# ===== ОТПРАВКА В TELEGRAM =====
def send_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
        response = requests.post(url, json=data, timeout=10)
        return response.status_code == 200
    except:
        return False

def send_photo(photo_url, caption):
    try:
        # Скачиваем фото
        photo_response = requests.get(photo_url, timeout=30)
        if photo_response.status_code != 200:
            return False
        
        # Отправляем фото
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        files = {'photo': ('photo.jpg', photo_response.content)}
        data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': caption[:1024]}
        response = requests.post(url, data=data, files=files, timeout=30)
        return response.status_code == 200
    except:
        return False

def get_sender_name(msg):
    if msg.get('type') == 'incoming':
        return msg.get('senderName', 'Неизвестно')
    else:
        return "@scul_k"

def determine_gender(name):
    """Простое определение пола по окончанию имени"""
    if name and name[-1] in ['а', 'я', 'А', 'Я']:
        return "женский"
    return "мужской"

# ===== ВЕБ-СЕРВЕР =====
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bridge is running")
    def log_message(self, *args): pass

def run_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"🌐 Веб-сервер запущен на порту {port}")

run_server()

print("=" * 50)
print("🚀 МОСТ MAX → TELEGRAM")
print("=" * 50)
print(f"📱 Инстанс: {ID_INSTANCE}")
print(f"💬 Чат MAX: {MAX_CHAT_ID}")
print("=" * 50)
print("🟢 Запущено. Жду сообщения...\n")

last_cleanup = time.time()

while True:
    try:
        history = get_chat_history(20)
        
        if history and isinstance(history, list):
            for msg in history:
                msg_id = msg.get('idMessage')
                if not msg_id or msg_id in processed_ids:
                    continue
                
                msg_type = msg.get('typeMessage')
                sender = get_sender_name(msg)
                gender = determine_gender(sender)
                
                # УДАЛЕНИЯ
                if msg.get('isDeleted'):
                    if msg_id not in sent_deletes:
                        deleted_text = msg.get('textMessage', 'Текст сообщения недоступен')
                        delete_word = "удалила" if gender == "женский" else "удалил"
                        full_text = f"🗑️ {sender} {delete_word} сообщение:\n\n{deleted_text}"
                        
                        if send_telegram(full_text):
                            sent_deletes.add(msg_id)
                            processed_ids.add(msg_id)
                            stats['sent'] += 1
                            print(f"🗑️ Удаление от {sender}")
                    continue
                
                # РЕДАКТИРОВАНИЯ
                if msg.get('isEdited'):
                    text = msg.get('textMessage', '')
                    if text:
                        edit_word = "отредактировала" if gender == "женский" else "отредактировал"
                        full_text = f"✏️ {sender} {edit_word} сообщение:\n\n{text}"
                        
                        if send_telegram(full_text):
                            processed_ids.add(msg_id)
                            stats['sent'] += 1
                            print(f"✏️ Редактирование от {sender}")
                    continue
                
                # ОБЫЧНЫЙ ТЕКСТ
                if msg_type == 'textMessage':
                    text = msg.get('textMessage', '')
                    if text:
                        full_text = f"📨 MAX от {sender}:\n\n{text}"
                        if send_telegram(full_text):
                            processed_ids.add(msg_id)
                            stats['sent'] += 1
                            print(f"📨 Текст от {sender}")
                
                # ССЫЛКИ
                elif msg_type == 'extendedTextMessage':
                    ext = msg.get('extendedTextMessageData', {})
                    text = ext.get('text', '')
                    title = ext.get('title', '')
                    desc = ext.get('description', '')
                    
                    full_text = f"📨 MAX от {sender}:"
                    if text:
                        full_text += f"\n\n{text}"
                    if title:
                        full_text += f"\n\n🔗 {title}"
                    if desc:
                        full_text += f"\n{desc}"
                    
                    if send_telegram(full_text):
                        processed_ids.add(msg_id)
                        stats['sent'] += 1
                        print(f"🔗 Ссылка от {sender}")
                
                # ФОТО
                elif msg_type == 'imageMessage':
                    photo_url = msg.get('downloadUrl')
                    caption = msg.get('caption', '')
                    if photo_url:
                        cap = f"📨 MAX от {sender}"
                        if caption:
                            cap += f":\n\n{caption}"
                        
                        if send_photo(photo_url, cap):
                            processed_ids.add(msg_id)
                            stats['sent'] += 1
                            print(f"📸 Фото от {sender}")
                        else:
                            print(f"❌ Ошибка фото от {sender}")
                
                # ОСТАЛЬНОЕ
                else:
                    processed_ids.add(msg_id)
                    print(f"⏭️ Пропущен тип: {msg_type}")
        
        # Очистка старых данных
        if time.time() - last_cleanup > 60:
            if len(processed_ids) > 500:
                processed_ids = set(list(processed_ids)[-500:])
            if len(sent_deletes) > 100:
                sent_deletes = set(list(sent_deletes)[-100:])
            last_cleanup = time.time()
        
        time.sleep(1)
        
    except KeyboardInterrupt:
        print("\n\n👋 Скрипт остановлен")
        break
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        time.sleep(5)
