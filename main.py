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

# ===== ХРАНИЛИЩА =====
processed_ids = set()        # обработанные сообщения
sent_edits = set()           # отправленные редактирования
sent_deletes = set()         # отправленные удаления
message_cache = {}           # кэш текстов сообщений
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
    except Exception as e:
        print(f"Ошибка получения истории: {e}")
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
                message_cache[msg_id] = text

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
        
        # Информация об ответе
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
        full_message = f"{reply_info}✏️ {sender_name} отредактировал сообщение:\n\n{text}"
    else:
        full_message = f"{reply_info}📨 MAX от {sender_name}:\n\n{text}"
    
    try:
        response = requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                                json={"chat_id": TELEGRAM_CHAT_ID, "text": full_message}, timeout=10)
        if response.status_code == 200:
            if is_edit and edit_id:
                sent_edits.add(edit_id)
            return True
        return False
    except Exception as e:
        print(f"Ошибка отправки текста: {e}")
        return False

# 👇 НОВАЯ ФУНКЦИЯ ДЛЯ ФОТО В НУЖНОМ ФОРМАТЕ
def send_photo_to_telegram(photo_url, sender_name, caption="", reply_info=""):
    """Отправляет фото в формате: 📨 MAX от @scul_k или с подписью"""
    try:
        print(f"📸 Отправка фото от {sender_name}")
        
        # Скачиваем фото
        photo_response = requests.get(photo_url, timeout=30)
        if photo_response.status_code != 200:
            print(f"❌ Ошибка скачивания фото")
            return False
        
        # Формируем подпись
        if reply_info:
            if caption:
                full_caption = f"{reply_info}📨 MAX от {sender_name}:\n\n{caption}"
            else:
                full_caption = f"{reply_info}📨 MAX от {sender_name}"
        else:
            if caption:
                full_caption = f"📨 MAX от {sender_name}:\n\n{caption}"
            else:
                full_caption = f"📨 MAX от {sender_name}"
        
        # Отправляем фото
        tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        files = {'photo': ('photo.webp', photo_response.content)}
        data = {
            'chat_id': TELEGRAM_CHAT_ID,
            'caption': full_caption[:1024]
        }
        
        response = requests.post(tg_url, data=data, files=files, timeout=30)
        
        if response.status_code == 200:
            print(f"✅ Фото отправлено")
            return True
        else:
            print(f"❌ Ошибка Telegram: {response.status_code}")
            return False
        
    except Exception as e:
        print(f"❌ Ошибка отправки фото: {e}")
        return False

def send_extended_text_to_telegram(extended_data, sender_name, reply_info=""):
    text = extended_data.get('text', '')
    title = extended_data.get('title', '')
    description = extended_data.get('description', '')
    
    full_message = f"{reply_info}📨 MAX от {sender_name}:"
    if text:
        full_message += f"\n\n{text}"
    if title:
        full_message += f"\n\n🔗 **{title}**"
    if description:
        full_message += f"\n{description}"
    
    try:
        response = requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                                json={"chat_id": TELEGRAM_CHAT_ID, "text": full_message}, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Ошибка отправки extendedText: {e}")
        return False

def send_deleted_notification(sender_name, deleted_text, delete_id):
    """Отправляет уведомление об удалении в твоём формате"""
    if delete_id and delete_id in sent_deletes:
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
        print(f"Ошибка отправки уведомления об удалении: {e}")
        return False

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
                
                body = update.get('body', {})
                message_data = body.get('messageData', {})
                webhook_type = update.get('typeWebhook')
                
                if message_data.get('typeMessage') == 'deletedMessage':
                    print(f"\n🗑️ ПОЛУЧЕНО УВЕДОМЛЕНИЕ ОБ УДАЛЕНИИ в {webhook_type}")
                    
                    sender_data = body.get('senderData', {})
                    deleted_data = message_data.get('deletedMessageData', {})
                    
                    stanza_id = deleted_data.get('stanzaId')
                    sender_name = sender_data.get('senderName', 'Неизвестно')
                    
                    if stanza_id and stanza_id not in sent_deletes:
                        deleted_text = message_cache.get(stanza_id, "Текст сообщения недоступен")
                        send_deleted_notification(sender_name, deleted_text, stanza_id)
                
                elif webhook_type == 'editedMessageWebhook':
                    print(f"\n✏️ ПОЛУЧЕНО РЕДАКТИРОВАНИЕ")
                    
                    edited_data = message_data.get('editedMessageData', {})
                    stanza_id = edited_data.get('stanzaId')
                    new_text = edited_data.get('textMessage', '')
                    sender_name = body.get('senderData', {}).get('senderName', 'Неизвестно')
                    
                    if stanza_id and new_text:
                        edit_id = f"edit_{stanza_id}"
                        if edit_id not in sent_edits:
                            reply_info = ""
                            history = get_chat_history(20)
                            for msg in history:
                                if msg.get('idMessage') == stanza_id and 'quotedMessage' in msg:
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
                
            except Exception as e:
                print(f"❌ Ошибка обработки вебхука: {e}")
        
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
print("🚀 МОСТ MAX → TELEGRAM (С ФОТО)")
print("=" * 50)
print(f"📱 Инстанс: {ID_INSTANCE}")
print(f"💬 Чат MAX: {MAX_CHAT_ID}")
print(f"📬 Чат Telegram: {TELEGRAM_CHAT_ID}")
print("=" * 50)
print("🟢 Запущено. Опрос истории каждую секунду...")
print("📝 Команда /h - последние 10 сообщений")
print("👤 Твои сообщения: @scul_k")
print("🖼️ Фото поддерживаются в формате: 📨 MAX от @scul_k")
print("✏️ Редактирование поддерживается")
print("🗑️ Удаление поддерживается")
print("💬 Цитирование поддерживается\n")

last_cleanup = time.time()
last_message_time = 0

while True:
    try:
        history = get_chat_history(20)
        
        if history and isinstance(history, list):
            update_message_cache(history)
            
            # 👇 ОТПРАВКА УДАЛЕНИЙ ИЗ ИСТОРИИ (подстраховка)
            for msg in history:
                if msg.get('isDeleted') and msg.get('idMessage'):
                    msg_id = msg.get('idMessage')
                    if msg_id not in sent_deletes:
                        print(f"\n🔍 Найдено удалённое сообщение в истории: {msg_id}")
                        
                        sender_name = get_sender_name(msg)
                        deleted_text = msg.get('textMessage', 'Текст сообщения недоступен')
                        send_deleted_notification(sender_name, deleted_text, msg_id)
            
            # 👇 ОБРАБОТКА СООБЩЕНИЙ ИЗ ИСТОРИИ
            for msg in reversed(history):
                msg_id = msg.get('idMessage')
                is_edited = msg.get('isEdited', False)
                
                if not msg_id:
                    continue
                
                # ПРОПУСК УЖЕ ОБРАБОТАННЫХ (с учётом редактирований)
                if msg_id in processed_ids and not is_edited:
                    continue
                if is_edited:
                    edit_key = f"edit_{msg_id}"
                    if edit_key in sent_edits:
                        continue
                
                msg_type = msg.get('typeMessage')
                sender_name = get_sender_name(msg)

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
                
                sent = False
                
                # ТЕКСТ
                if msg_type == 'textMessage':
                    text = msg.get('textMessage', '')
                    if text:
                        sent = send_text_to_telegram(text, sender_name, reply_info, is_edit=is_edited, 
                                                    edit_id=f"edit_{msg_id}" if is_edited else None)
                
                # РАСШИРЕННЫЙ ТЕКСТ (ссылки)
                elif msg_type == 'extendedTextMessage':
                    extended_data = msg.get('extendedTextMessageData', {})
                    if extended_data:
                        sent = send_extended_text_to_telegram(extended_data, sender_name, reply_info)
                
                # 👇 ФОТО В НУЖНОМ ФОРМАТЕ
                elif msg_type == 'imageMessage':
                    file_data = msg.get('fileMessageData', {})
                    download_url = file_data.get('downloadUrl')
                    caption = file_data.get('caption', '')
                    
                    if download_url:
                        sent = send_photo_to_telegram(download_url, sender_name, caption, reply_info)
                
                # ДРУГИЕ МЕДИА (видео, документы, аудио) - пока игнорируем
                elif msg_type in ['videoMessage', 'documentMessage', 'audioMessage']:
                    if not is_edited:
                        processed_ids.add(msg_id)
                    continue
                
                # ВСЁ ОСТАЛЬНОЕ
                else:
                    if not is_edited:
                        processed_ids.add(msg_id)
                    continue
                
                # ОБНОВЛЯЕМ СТАТИСТИКУ И ХРАНИЛИЩА
                if sent:
                    stats['sent'] += 1
                    if is_edited:
                        sent_edits.add(f"edit_{msg_id}")
                    else:
                        processed_ids.add(msg_id)
                    last_message_time = time.time()
                else:
                    stats['skipped'] += 1
                
                stats['total'] += 1
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
            if len(message_cache) > 500:
                cache_items = list(message_cache.items())[-500:]
                message_cache = dict(cache_items)
            last_cleanup = time.time()
        
        time.sleep(1)
        
    except KeyboardInterrupt:
        print("\n\n👋 Скрипт остановлен")
        break
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        time.sleep(5)
