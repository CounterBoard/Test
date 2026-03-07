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
processed_ids = set()
sent_deletes = set()
sent_edits = set()
message_cache = {}
stats = {'total': 0, 'sent': 0}

# ===== ФУНКЦИЯ ДЛЯ ПОЛУЧЕНИЯ ИСТОРИИ =====
def get_chat_history(count=20):
    url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/GetChatHistory/{API_TOKEN}"
    payload = {"chatId": MAX_CHAT_ID, "count": min(count, 100)}
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        print(f"Ошибка истории: {e}")
        return []

def update_cache(history):
    """Обновляет кэш сообщений"""
    for msg in history:
        msg_id = msg.get('idMessage')
        if msg_id and msg.get('typeMessage') == 'textMessage':
            message_cache[msg_id] = msg.get('textMessage', '')

# ===== ОТПРАВКА В TELEGRAM =====
def send_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
        response = requests.post(url, json=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Ошибка отправки: {e}")
        return False

def send_photo(photo_url, caption):
    try:
        photo_response = requests.get(photo_url, timeout=30)
        if photo_response.status_code != 200:
            return False
        
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        files = {'photo': ('photo.jpg', photo_response.content)}
        data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': caption[:1024]}
        response = requests.post(url, data=data, files=files, timeout=30)
        return response.status_code == 200
    except Exception as e:
        print(f"Ошибка фото: {e}")
        return False

def send_history_to_telegram(chat_id, count=10):
    """Отправляет историю сообщений"""
    history = get_chat_history(count)
    if not history:
        send_telegram("📭 Нет сообщений в истории")
        return
    
    messages = []
    for msg in history[-count:]:
        if msg.get('typeMessage') != 'textMessage':
            continue
        sender = get_sender_name(msg)
        text = msg.get('textMessage', '')
        if text:
            time_str = datetime.fromtimestamp(msg.get('timestamp', 0)).strftime('%H:%M')
            messages.append(f"[{time_str}] {sender}:\n{text[:100]}")
    
    if messages:
        full_text = "📜 История чата:\n\n" + "\n\n---\n\n".join(messages)
        send_telegram(full_text[:4000])
    else:
        send_telegram("📭 В истории нет текстовых сообщений")

def get_sender_name(msg):
    if msg.get('type') == 'incoming':
        return msg.get('senderName', 'Неизвестно')
    else:
        return "@scul_k"

def get_quoted_text(msg):
    """Извлекает текст цитируемого сообщения"""
    if 'quotedMessage' in msg:
        quoted = msg['quotedMessage']
        quoted_text = quoted.get('textMessage', '')
        quoted_sender = quoted.get('senderName', '')
        if quoted_text:
            if quoted_sender:
                return f"↪️ В ответ на {quoted_sender}:\n> {quoted_text}\n\n"
            else:
                return f"↪️ В ответ на сообщение:\n> {quoted_text}\n\n"
    return ""

def send_edit_notification(sender_name, new_text, quoted=""):
    """Отправляет уведомление о редактировании (для текста или подписи)"""
    full_text = f"{quoted}✏️ {sender_name} отредактировал(а) сообщение:\n\n{new_text}"
    return send_telegram(full_text)

# ===== ВЕБ-СЕРВЕР =====
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bridge is running")
    
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
                
                # Обработка редактирования из вебхука
                webhook_type = update.get('typeWebhook')
                if webhook_type == 'editedMessageWebhook':
                    body = update.get('body', {})
                    message_data = body.get('messageData', {})
                    sender_data = body.get('senderData', {})
                    edited_data = message_data.get('editedMessageData', {})
                    
                    stanza_id = edited_data.get('stanzaId')
                    new_text = edited_data.get('textMessage', '')
                    sender_name = sender_data.get('senderName', 'Неизвестно')
                    
                    if stanza_id and new_text:
                        edit_id = f"edit_{stanza_id}"
                        if edit_id not in sent_edits:
                            # Ищем информацию об ответе
                            quoted = ""
                            history = get_chat_history(20)
                            for msg in history:
                                if msg.get('idMessage') == stanza_id and 'quotedMessage' in msg:
                                    q = msg['quotedMessage']
                                    q_text = q.get('textMessage', '')
                                    q_sender = q.get('senderName', '')
                                    if q_text:
                                        if q_sender:
                                            quoted = f"↪️ В ответ на {q_sender}:\n> {q_text}\n\n"
                                        else:
                                            quoted = f"↪️ В ответ на сообщение:\n> {q_text}\n\n"
                                    break
                            
                            send_edit_notification(sender_name, new_text, quoted)
                            sent_edits.add(edit_id)
            except Exception as e:
                print(f"❌ Ошибка обработки вебхука: {e}")
        
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    
    def log_message(self, *args): pass

def run_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"🌐 Веб-сервер запущен на порту {port}")

run_server()

print("=" * 50)
print("🚀 МОСТ MAX → TELEGRAM (ФИНАЛЬНАЯ ВЕРСИЯ)")
print("=" * 50)
print(f"📱 Инстанс: {ID_INSTANCE}")
print(f"💬 Чат MAX: {MAX_CHAT_ID}")
print("=" * 50)
print("🟢 Запущено. Жду сообщения...\n")
print("📝 Команда /h - последние 10 сообщений")
print("👤 Твои сообщения: @scul_k")
print("🖼️ Фото поддерживаются")
print("✏️ Редактирование: отредактировал(а)")
print("🗑️ Удаление: удалил(а)")
print("💬 Цитирование поддерживается")
print("📸 Редактирование подписей к фото поддерживается\n")

last_cleanup = time.time()

while True:
    try:
        history = get_chat_history(30)
        
        if history:
            update_cache(history)
            
            for msg in history:
                msg_id = msg.get('idMessage')
                if not msg_id:
                    continue
                
                # ===== УДАЛЕНИЯ =====
                if msg.get('isDeleted'):
                    if msg_id not in sent_deletes:
                        deleted_text = msg.get('textMessage', 'Текст сообщения недоступен')
                        quoted = get_quoted_text(msg)
                        sender = get_sender_name(msg)
                        full_text = f"{quoted}🗑️ {sender} удалил(а) сообщение:\n\n{deleted_text}"
                        if send_telegram(full_text):
                            sent_deletes.add(msg_id)
                            processed_ids.add(msg_id)
                            print(f"🗑️ Удаление от {sender}")
                    continue
                
                # ===== РЕДАКТИРОВАНИЯ =====
                if msg.get('isEdited'):
                    edit_key = f"edit_{msg_id}"
                    if edit_key not in sent_edits:
                        # Для фото - берём подпись, для текста - текст
                        if msg.get('typeMessage') == 'imageMessage':
                            new_text = msg.get('caption', 'Подпись отсутствует')
                        else:
                            new_text = msg.get('textMessage', '')
                        
                        if new_text:
                            quoted = get_quoted_text(msg)
                            sender = get_sender_name(msg)
                            full_text = f"{quoted}✏️ {sender} отредактировал(а) сообщение:\n\n{new_text}"
                            if send_telegram(full_text):
                                sent_edits.add(edit_key)
                                processed_ids.add(msg_id)
                                print(f"✏️ Редактирование от {sender}")
                    continue
                
                # ===== ВСЁ ОСТАЛЬНОЕ =====
                
                if msg_id in processed_ids:
                    continue
                
                if time.time() - msg.get('timestamp', 0) > 60:
                    processed_ids.add(msg_id)
                    continue
                
                msg_type = msg.get('typeMessage')
                sender = get_sender_name(msg)
                quoted = get_quoted_text(msg)
                
                # ТЕКСТ
                if msg_type == 'textMessage':
                    text = msg.get('textMessage', '')
                    if text:
                        full_text = f"{quoted}📨 MAX от {sender}:\n\n{text}"
                        if send_telegram(full_text):
                            processed_ids.add(msg_id)
                            stats['sent'] += 1
                            print(f"📨 Текст от {sender}")
                
                # ССЫЛКИ
                elif msg_type == 'extendedTextMessage':
                    text = msg.get('textMessage', '')
                    if text:
                        full_text = f"{quoted}📨 MAX от {sender}:\n\n{text}"
                        if send_telegram(full_text):
                            processed_ids.add(msg_id)
                            stats['sent'] += 1
                            print(f"🔗 Ссылка от {sender}")
                
                # ФОТО
                elif msg_type == 'imageMessage':
                    photo_url = msg.get('downloadUrl')
                    caption = msg.get('caption', '')
                    if photo_url:
                        cap = f"{quoted}📨 MAX от {sender}"
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
        
        # Очистка
        if time.time() - last_cleanup > 60:
            if len(processed_ids) > 500:
                processed_ids = set(list(processed_ids)[-500:])
            if len(sent_deletes) > 100:
                sent_deletes = set(list(sent_deletes)[-100:])
            if len(sent_edits) > 100:
                sent_edits = set(list(sent_edits)[-100:])
            if len(message_cache) > 500:
                message_cache = {k: v for k, v in list(message_cache.items())[-500:]}
            last_cleanup = time.time()
        
        time.sleep(1)
        
    except KeyboardInterrupt:
        print("\n\n👋 Скрипт остановлен")
        break
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        time.sleep(5)
