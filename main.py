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

# Проверка наличия переменных
if not all([ID_INSTANCE, API_TOKEN, MAX_CHAT_ID, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
    missing = [v for v in ['ID_INSTANCE', 'API_TOKEN', 'MAX_CHAT_ID', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID'] 
               if not os.environ.get(v)]
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
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            return r.json()
        return []
    except: return []

# ===== ОТПРАВКА В TELEGRAM =====
def send_text(text):
    try:
        r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                         json={"chat_id": TELEGRAM_CHAT_ID, "text": text})
        return r.status_code == 200
    except: return False

def send_photo(photo_url, caption):
    try:
        print(f"📸 Скачиваю фото...")
        photo_data = requests.get(photo_url, timeout=30).content
        print(f"📦 Размер: {len(photo_data)} байт")
        
        files = {'photo': ('photo.jpg', photo_data)}
        data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': caption[:1024]}
        
        r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
                         data=data, files=files, timeout=30)
        
        if r.status_code == 200:
            print("✅ Фото отправлено")
            return True
        else:
            print(f"❌ Ошибка: {r.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

# ===== ФОРМАТИРОВАНИЕ С УЧЁТОМ ПОЛА =====
def get_name_with_gender(sender_name, msg):
    """Добавляет окончание в зависимости от пола отправителя"""
    # По умолчанию мужской род
    gender = "мужской"
    
    # Здесь можно добавить определение пола по имени
    # Например, если имя заканчивается на "а" или "я" - женский род
    if sender_name and sender_name[-1] in ['а', 'я', 'А', 'Я']:
        gender = "женский"
    
    return sender_name, gender

def format_edit(sender_name, gender):
    """Форматирует сообщение о редактировании"""
    if gender == "женский":
        return f"✏️ {sender_name} отредактировала сообщение"
    else:
        return f"✏️ {sender_name} отредактировал сообщение"

def format_delete(sender_name, gender):
    """Форматирует сообщение об удалении"""
    if gender == "женский":
        return f"🗑️ {sender_name} удалила сообщение"
    else:
        return f"🗑️ {sender_name} удалил сообщение"

def get_sender_name(msg):
    if msg.get('type') == 'incoming':
        return msg.get('senderName', 'Неизвестно')
    else:
        return "@scul_k"

# ===== ВЕБ-СЕРВЕР =====
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bridge running")
    def log_message(self, *args): pass

def run_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"🌐 Сервер на порту {port}")

run_server()

print("=" * 50)
print("🚀 МОСТ MAX → TELEGRAM")
print("=" * 50)
print(f"📱 Инстанс: {ID_INSTANCE}")
print(f"💬 Чат MAX: {MAX_CHAT_ID}")
print("=" * 50)
print("🟢 Запущено. Жду сообщения...\n")

while True:
    try:
        history = get_chat_history(20)
        
        if history:
            for msg in history:
                msg_id = msg.get('idMessage')
                if not msg_id or msg_id in processed_ids:
                    continue
                
                msg_type = msg.get('typeMessage')
                sender = get_sender_name(msg)
                sender_name, gender = get_name_with_gender(sender, msg)
                
                # УДАЛЕНИЯ
                if msg.get('isDeleted'):
                    if msg_id not in sent_deletes:
                        deleted_text = msg.get('textMessage', 'Текст сообщения недоступен')
                        delete_text = format_delete(sender, gender)
                        full_text = f"{delete_text}:\n\n{deleted_text}"
                        if send_text(full_text):
                            sent_deletes.add(msg_id)
                            processed_ids.add(msg_id)
                            print(f"🗑️ Удаление от {sender}")
                    continue
                
                # РЕДАКТИРОВАНИЯ
                if msg.get('isEdited'):
                    text = msg.get('textMessage', '')
                    if text:
                        edit_text = format_edit(sender, gender)
                        full_text = f"{edit_text}:\n\n{text}"
                        if send_text(full_text):
                            processed_ids.add(msg_id)
                            stats['sent'] += 1
                            print(f"✏️ Редактирование от {sender}")
                    continue
                
                # ТЕКСТ
                if msg_type == 'textMessage':
                    text = msg.get('textMessage', '')
                    if text:
                        if send_text(f"📨 MAX от {sender}:\n\n{text}"):
                            processed_ids.add(msg_id)
                            stats['sent'] += 1
                            print(f"📨 Текст от {sender}")
                
                # ССЫЛКИ
                elif msg_type == 'extendedTextMessage':
                    ext_data = msg.get('extendedTextMessageData', {})
                    text = ext_data.get('text', '')
                    title = ext_data.get('title', '')
                    desc = ext_data.get('description', '')
                    
                    full_text = f"📨 MAX от {sender}:"
                    if text:
                        full_text += f"\n\n{text}"
                    if title:
                        full_text += f"\n\n🔗 {title}"
                    if desc:
                        full_text += f"\n{desc}"
                    
                    if send_text(full_text):
                        processed_ids.add(msg_id)
                        stats['sent'] += 1
                        print(f"🔗 Ссылка от {sender}")
                
                # ФОТО
                elif msg_type == 'imageMessage':
                    photo_url = msg.get('downloadUrl')
                    caption = msg.get('caption', '')
                    if photo_url:
                        if caption:
                            cap = f"📨 MAX от {sender}:\n\n{caption}"
                        else:
                            cap = f"📨 MAX от {sender}"
                        
                        if send_photo(photo_url, cap):
                            processed_ids.add(msg_id)
                            stats['sent'] += 1
                            print(f"📸 Фото от {sender}")
                        else:
                            print(f"❌ Не удалось отправить фото от {sender}")
                
                # ВСЁ ОСТАЛЬНОЕ
                else:
                    processed_ids.add(msg_id)
                    print(f"⏭️ Пропущен тип: {msg_type}")
        
        # Очистка хранилищ
        if len(processed_ids) > 500:
            processed_ids = set(list(processed_ids)[-500:])
        if len(sent_deletes) > 100:
            sent_deletes = set(list(sent_deletes)[-100:])
        
        time.sleep(1)
        
    except KeyboardInterrupt:
        print("\n👋 Скрипт остановлен")
        break
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        time.sleep(5)
