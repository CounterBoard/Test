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
deleted_messages_cache = {}  # кэш для удалённых сообщений: id -> текст
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
        
        # Сохраняем текст в кэш для возможного удаления
        if msg.get('typeMessage') == 'textMessage':
            deleted_messages_cache[msg_id] = msg.get('textMessage', '')
        
        if msg.get('typeMessage') in ['deletedMessage']:
            continue
            
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
        
        # 👇 ПУСТАЯ СТРОКА ПОСЛЕ ИМЕНИ
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
        
        if len(text) > 100:
            text = text[:100] + '...'
        
        messages.append(f"{arrow} [{time_str}] {sender}{edit_mark}:\n\n{reply_prefix}{text}")
    
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
    """Отправляет текстовое сообщение в Telegram"""
    if is_edit and edit_id and edit_id in sent_edits:
        print(f"⏭️ Редактирование {edit_id} уже отправлено, пропускаем")
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
    """Отправляет уведомление об удалении сообщения в Telegram"""
    if delete_id and delete_id in sent_deletes:
        print(f"⏭️ Уведомление об удалении {delete_id} уже отправлено")
        return False
    
    full_message = f"🗑️ {sender_name} удалил сообщение:\n\n{deleted_text}"
    
    try:
        response = requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                                json={"chat_id": TELEGRAM_CHAT_ID, "text": full_message}, timeout=10)
        if response.status_code == 200:
            if delete_id:
                sent_deletes.add(delete_id)
            print(f"✅ Уведомление об удалении отправлено")
            return True
        return False
    except Exception as e:
        print(f"❌ Ошибка при отправке уведомления об удалении: {e}")
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
                webhook_type = update.get('typeWebhook')
                
                # Обработка команд /h
                if 'message' in update and 'text' in update['message']:
                    text = update['message']['text']
                    chat_id = update['message']['chat']['id']
                    if str(chat_id) == str(TELEGRAM_CHAT_ID) and text.startswith('/h'):
                        parts = text.split()
                        count = 10
                        if len(parts) > 1 and parts[1].isdigit():
                            count = int(parts[1])
                        send_history_to_telegram(chat_id, count)
                
                # Обработка редактирования сообщений
                elif webhook_type == 'editedMessageWebhook':
                    print(f"\n✏️ ПОЛУЧЕНО УВЕДОМЛЕНИЕ О РЕДАКТИРОВАНИИ!")
                    
                    body = update.get('body', {})
                    message_data = body.get('messageData', {})
                    sender_data = body.get('senderData', {})
                    
                    edited_data = message_data.get('editedMessageData', {})
                    
                    stanza_id = edited_data.get('stanzaId')
                    new_text = edited_data.get('textMessage', '')
                    sender_name = sender_data.get('senderName', 'Неизвестно')
                    
                    print(f"📎 Оригинальное сообщение ID: {stanza_id}")
                    print(f"👤 От: {sender_name}")
                    print(f"📝 Новый текст: {new_text[:50]}...")
                    
                    if stanza_id and new_text:
                        edit_id = f"edit_{stanza_id}"
                        if edit_id not in sent_edits:
                            # Пытаемся найти информацию об ответе для редактируемого сообщения
                            reply_info = ""
                            history = get_chat_history(50)
                            for msg in history:
                                if msg.get('idMessage') == stanza_id:
                                    if 'quotedMessage' in msg:
                                        quoted = msg['quotedMessage']
                                        quoted_text = quoted.get('textMessage', '')
                                        quoted_sender = quoted.get('senderName', '')
                                        if quoted_text:
                                            if quoted_sender:
                                                reply_info = f"↪️ В ответ на {quoted_sender}:\n\n> {quoted_text}\n\n"
                                            else:
                                                reply_info = f"↪️ В ответ на сообщение:\n\n> {quoted_text}\n\n"
                                    break
                            
                            send_text_to_telegram(new_text, sender_name, reply_info, is_edit=True, edit_id=edit_id)
                
                # 👇 ОБНОВЛЁННАЯ ОБРАБОТКА УДАЛЕНИЯ
                elif webhook_type == 'incomingMessageReceived' or webhook_type == 'outgoingMessageReceived':
                    # Проверяем, не является ли это сообщением об удалении
                    message_data = update.get('body', {}).get('messageData', {})
                    if message_data.get('typeMessage') == 'deletedMessage':
                        print(f"\n🗑️ ПОЛУЧЕНО УВЕДОМЛЕНИЕ ОБ УДАЛЕНИИ!")
                        
                        body = update.get('body', {})
                        sender_data = body.get('senderData', {})
                        message_data = body.get('messageData', {})
                        deleted_data = message_data.get('deletedMessageData', {})
                        
                        # ID удалённого сообщения
                        stanza_id = deleted_data.get('stanzaId')
                        sender_name = sender_data.get('senderName', 'Неизвестно')
                        
                        print(f"📎 Удалено сообщение ID: {stanza_id}")
                        print(f"👤 От: {sender_name}")
                        
                        # Пытаемся найти текст удалённого сообщения
                        deleted_text = "Текст сообщения недоступен"
                        if stanza_id:
                            delete_id = f"delete_{stanza_id}"
                            if delete_id not in sent_deletes:
                                # Сначала проверяем кэш
                                if stanza_id in deleted_messages_cache:
                                    deleted_text = deleted_messages_cache[stanza_id]
                                else:
                                    # Если нет в кэше, ищем в истории
                                    history = get_chat_history(50)
                                    for msg in history:
                                        if msg.get('idMessage') == stanza_id:
                                            deleted_text = msg.get('textMessage', 'Текст сообщения недоступен')
                                            # Сохраняем в кэш на будущее
                                            deleted_messages_cache[stanza_id] = deleted_text
                                            break
                                
                                send_deleted_notification(sender_name, deleted_text, delete_id)
            except Exception as e:
                print(f"❌ Ошибка обработки: {e}")
        
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
print("🚀 МОСТ MAX → TELEGRAM (С УДАЛЕНИЕМ)")
print("=" * 50)
print(f"📱 Инстанс: {ID_INSTANCE}")
print(f"💬 Чат MAX: {MAX_CHAT_ID}")
print(f"📬 Чат Telegram: {TELEGRAM_CHAT_ID}")
print("=" * 50)
print("🟢 Запущено. Опрос истории каждую секунду...")
print("📝 Команда /h - последние 10 сообщений")
print("👤 Твои сообщения: @scul_k")
print("✏️ Редактирование поддерживается")
print("🗑️ Удаление поддерживается")
print("💬 Цитирование поддерживается\n")

last_cleanup = time.time()
last_message_time = 0

while True:
    try:
        history = get_chat_history(15)
        
        if history and isinstance(history, list):
            for msg in reversed(history):
                msg_id = msg.get('idMessage')
                is_edited = msg.get('isEdited', False)
                
                # Сохраняем текст в кэш для возможного удаления
                if msg.get('typeMessage') == 'textMessage' and msg_id:
                    deleted_messages_cache[msg_id] = msg.get('textMessage', '')
                
                if not msg_id:
                    continue
                
                if msg_id in processed_ids and not is_edited:
                    continue
                
                if is_edited:
                    edit_key = f"edit_{msg_id}"
                    if edit_key in sent_edits:
                        continue
                
                if msg.get('typeMessage') != 'textMessage':
                    if not is_edited:
                        processed_ids.add(msg_id)
                    continue
                
                timestamp = msg.get('timestamp', 0)
                text = msg.get('textMessage', '')
                if not text:
                    if not is_edited:
                        processed_ids.add(msg_id)
                    continue
                
                if time.time() - last_message_time < 0.5:
                    time.sleep(0.5)
                
                # 👇 ПУСТАЯ СТРОКА В ОТВЕТАХ
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
                        print(f"📎 Найден ответ на: {quoted_text[:30]}...")
                
                if msg.get('type') == 'incoming':
                    sender_name = msg.get('senderName', 'Неизвестно')
                else:
                    sender_name = "@scul_k"
                
                stats['total'] += 1
                
                if is_edited:
                    edit_id = f"edit_{msg_id}"
                    if send_text_to_telegram(text, sender_name, reply_info, is_edit=True, edit_id=edit_id):
                        stats['sent'] += 1
                        last_message_time = time.time()
                    else:
                        stats['skipped'] += 1
                else:
                    if send_text_to_telegram(text, sender_name, reply_info):
                        stats['sent'] += 1
                        processed_ids.add(msg_id)
                        last_message_time = time.time()
                    else:
                        stats['skipped'] += 1
                
                if stats['total'] % 10 == 0:
                    print(f"📊 Статистика: всего {stats['total']}, отправлено {stats['sent']}")
        
        # Очистка старых данных
        if time.time() - last_cleanup > 60:
            if len(processed_ids) > 500:
                processed_ids = set(list(processed_ids)[-500:])
            if len(sent_edits) > 100:
                sent_edits = set(list(sent_edits)[-100:])
            if len(sent_deletes) > 100:
                sent_deletes = set(list(sent_deletes)[-100:])
            if len(deleted_messages_cache) > 200:
                # Оставляем только последние 200 записей в кэше
                cache_items = list(deleted_messages_cache.items())[-200:]
                deleted_messages_cache = dict(cache_items)
            last_cleanup = time.time()
        
        time.sleep(1)
        
    except KeyboardInterrupt:
        print("\n\n👋 Скрипт остановлен")
        break
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        time.sleep(5)
