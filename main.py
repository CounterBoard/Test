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
sent_edits = set()
sent_deletes = set()
message_cache = {}
stats = {'total': 0, 'sent': 0, 'skipped': 0}

# ===== ФУНКЦИЯ ДЛЯ ПОЛУЧЕНИЯ ИСТОРИИ =====
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
        if not msg_id:
            continue
        if msg.get('typeMessage') == 'textMessage':
            text = msg.get('textMessage', '')
            if text:
                sender = msg.get('senderName', 'Неизвестно') if msg.get('type') == 'incoming' else "@scul_k"
                timestamp = msg.get('timestamp', 0)
                message_cache[msg_id] = {
                    'text': text,
                    'sender': sender,
                    'timestamp': timestamp
                }

def send_history_to_telegram(chat_id, count=10):
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
        
        reply_prefix = ""
        if 'quotedMessage' in msg:
            quoted = msg['quotedMessage']
            quoted_text = quoted.get('textMessage', '')
            quoted_sender = quoted.get('senderName', '')
            if quoted_text:
                if quoted_sender:
                    reply_prefix = f"↪️ В ответ на {quoted_sender}:\n\n> {quoted_text}\n\n"
                else:
                    reply_prefix = f"↪️ В ответ на сообщение:\n\n> {quoted_text}\n\n"
        
        edit_mark = " ✏️" if msg.get('isEdited') else ""
        delete_mark = " 🗑️" if msg.get('isDeleted') else ""
        
        if len(text) > 100:
            text = text[:100] + '...'
        
        messages.append(f"{arrow} [{time_str}] {sender}{edit_mark}{delete_mark}:\n\n{reply_prefix}{text}")
    
    if not messages:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", 
                     json={"chat_id": chat_id, "text": "📭 В истории нет текстовых сообщений"})
        return
    
    full_text = f"📜 История чата (последние {len(messages)}):\n\n" + "\n\n---\n\n".join(messages)
    if len(full_text) > 4000:
        full_text = full_text[:4000] + "...\n\n(сообщение обрезано)"
    
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", 
                 json={"chat_id": chat_id, "text": full_text})

def send_text_to_telegram(text, sender_name, reply_info="", is_edit=False, edit_id=None):
    if is_edit and edit_id and edit_id in sent_edits:
        return False
    
    if is_edit:
        if reply_info:
            full_message = f"{reply_info}✏️ {sender_name} отредактировал сообщение:\n\n{text}"
        else:
            full_message = f"✏️ {sender_name} отредактировал сообщение:\n\n{text}"
    elif reply_info:
        full_message = f"{reply_info}📨 MAX от {sender_name}:\n\n{text}"
    else:
        full_message = f"📨 MAX от {sender_name}:\n\n{text}"
    
    try:
        response = requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                                json={"chat_id": TELEGRAM_CHAT_ID, "text": full_message}, timeout=10)
        if response.status_code == 200:
            if is_edit and edit_id:
                sent_edits.add(edit_id)
            return True
        return False
    except:
        return False

def send_deleted_notification(sender_name, deleted_text, delete_id):
    if delete_id and delete_id in sent_deletes:
        return False
    
    full_message = f"🗑️ {sender_name} удалил сообщение:\n\n{deleted_text}"
    
    try:
        response = requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                                json={"chat_id": TELEGRAM_CHAT_ID, "text": full_message}, timeout=10)
        if response.status_code == 200:
            if delete_id:
                sent_deletes.add(delete_id)
            return True
        return False
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
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            if content_length > 0:
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
                
                # Обработка всех типов уведомлений
                webhook_type = update.get('typeWebhook')
                body = update.get('body', {})
                message_data = body.get('messageData', {})
                sender_data = body.get('senderData', {})
                
                # Проверяем, не является ли это удалением
                if message_data.get('typeMessage') == 'deletedMessage':
                    deleted_data = message_data.get('deletedMessageData', {})
                    stanza_id = deleted_data.get('stanzaId')
                    sender_name = sender_data.get('senderName', 'Неизвестно')
                    
                    if stanza_id:
                        delete_id = f"delete_{stanza_id}"
                        if delete_id not in sent_deletes:
                            deleted_text = "Текст сообщения недоступен"
                            if stanza_id in message_cache:
                                deleted_text = message_cache[stanza_id]['text']
                            send_deleted_notification(sender_name, deleted_text, delete_id)
                
                # Проверяем, не является ли это редактированием
                elif webhook_type == 'editedMessageWebhook':
                    edited_data = message_data.get('editedMessageData', {})
                    stanza_id = edited_data.get('stanzaId')
                    new_text = edited_data.get('textMessage', '')
                    sender_name = sender_data.get('senderName', 'Неизвестно')
                    
                    if stanza_id and new_text:
                        edit_id = f"edit_{stanza_id}"
                        if edit_id not in sent_edits:
                            send_text_to_telegram(new_text, sender_name, is_edit=True, edit_id=edit_id)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
        
        # Всегда отвечаем 200 OK
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
print(f"📱 Инстанс: {ID_INSTANCE}")
print(f"💬 Чат MAX: {MAX_CHAT_ID}")
print(f"📬 Чат Telegram: {TELEGRAM_CHAT_ID}")
print("=" * 50)
print("🟢 Запущено\n")

last_cleanup = time.time()

while True:
    try:
        history = get_chat_history(15)
        
        if history and isinstance(history, list):
            update_message_cache(history)
            
            for msg in reversed(history):
                msg_id = msg.get('idMessage')
                is_edited = msg.get('isEdited', False)
                
                if not msg_id or msg_id in processed_ids:
                    continue
                
                if msg.get('typeMessage') != 'textMessage':
                    processed_ids.add(msg_id)
                    continue
                
                text = msg.get('textMessage', '')
                if not text:
                    processed_ids.add(msg_id)
                    continue
                
                # Получаем информацию об ответе
                reply_info = ""
                if 'quotedMessage' in msg:
                    quoted = msg['quotedMessage']
                    quoted_text = quoted.get('textMessage', '')
                    quoted_sender = quoted.get('senderName', '')
                    if quoted_text:
                        if quoted_sender:
                            reply_info = f"↪️ В ответ на {quoted_sender}:\n\n> {quoted_text}\n\n"
                        else:
                            reply_info = f"↪️ В ответ на сообщение:\n\n> {quoted_text}\n\n"
                
                if msg.get('type') == 'incoming':
                    sender_name = msg.get('senderName', 'Неизвестно')
                else:
                    sender_name = "@scul_k"
                
                if is_edited:
                    edit_id = f"edit_{msg_id}"
                    if edit_id not in sent_edits:
                        if send_text_to_telegram(text, sender_name, reply_info, is_edit=True, edit_id=edit_id):
                            sent_edits.add(edit_id)
                else:
                    if send_text_to_telegram(text, sender_name, reply_info):
                        processed_ids.add(msg_id)
        
        # Очистка
        if time.time() - last_cleanup > 60:
            if len(processed_ids) > 500:
                processed_ids = set(list(processed_ids)[-500:])
            if len(sent_edits) > 100:
                sent_edits = set(list(sent_edits)[-100:])
            if len(sent_deletes) > 100:
                sent_deletes = set(list(sent_deletes)[-100:])
            last_cleanup = time.time()
        
        time.sleep(1)
        
    except KeyboardInterrupt:
        break
    except:
        time.sleep(5)
