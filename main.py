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

# ===== СИСТЕМА ЛОГИРОВАНИЯ =====
stats = {
    'received': 0,
    'sent_text': 0,
    'sent_media': 0,
    'skipped': 0,
    'errors': 0,
    'types': {}
}

def log_message_stats(msg_type, status, details=""):
    """Логирует статистику по сообщениям"""
    stats['received'] += 1
    stats['types'][msg_type] = stats['types'].get(msg_type, 0) + 1
    
    if status == 'sent':
        if msg_type == 'textMessage':
            stats['sent_text'] += 1
        else:
            stats['sent_media'] += 1
    elif status == 'skipped':
        stats['skipped'] += 1
    elif status == 'error':
        stats['errors'] += 1
    
    if stats['received'] % 50 == 0:
        print("\n" + "="*50)
        print("📊 СТАТИСТИКА:")
        print(f"📥 Всего получено: {stats['received']}")
        print(f"📝 Текстов отправлено: {stats['sent_text']}")
        print(f"🖼️ Медиа отправлено: {stats['sent_media']}")
        print(f"⏭️ Пропущено: {stats['skipped']}")
        print(f"❌ Ошибок: {stats['errors']}")
        print("📌 Типы сообщений:")
        for t, count in stats['types'].items():
            print(f"   {t}: {count}")
        print("="*50 + "\n")
# ===============================

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
    """Отправляет историю сообщений в Telegram (новые сообщения внизу)"""
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
    for msg in reversed(history[:count]):
        msg_type = msg.get('type', '')
        sender = msg.get('senderName', 'Неизвестно')
        text = msg.get('textMessage', '')
        timestamp = msg.get('timestamp', 0)
        
        time_str = datetime.fromtimestamp(timestamp).strftime('%H:%M %d.%m')
        arrow = '📥' if msg_type == 'incoming' else '📤'
        
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

print("=" * 50)
print("🚀 МОСТ MAX → TELEGRAM (С РУЧНЫМИ ID)")
print("=" * 50)
print(f"📱 Инстанс: {ID_INSTANCE}")
print(f"💬 Чат MAX: {MAX_CHAT_ID}")
print(f"📬 Чат Telegram: {TELEGRAM_CHAT_ID}")
print("=" * 50)
print("🟢 Запущено. Жду сообщения...")
print("📝 Команды: /h - последние 10 сообщений, /h 5 - последние 5 сообщений\n")

receive_url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/receiveNotification/{API_TOKEN}"

while True:
    try:
        response = requests.get(receive_url, timeout=30)
        
        if response.status_code == 200 and response.text and response.text != "null":
            data = response.json()
            receipt_id = data.get('receiptId')
            
            if receipt_id:
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔔 Получено уведомление!")
                
                body = data.get('body', {})
                sender_data = body.get('senderData', {})
                message_data = body.get('messageData', {})
                
                chat_id = sender_data.get('chatId')
                msg_type = message_data.get('typeMessage', 'unknown')
                print(f"📨 Чат: {chat_id}, Тип: {msg_type}")
                
                log_message_stats(msg_type, 'received')
                
                if chat_id == MAX_CHAT_ID:
                    print("✅ Сообщение из нужного чата!")
                    
                    reply_info = ""
                    if 'quotedMessage' in message_data:
                        quoted = message_data['quotedMessage']
                        quoted_text = quoted.get('textMessage', '')
                        quoted_sender = quoted.get('senderName', '')
                        if quoted_text:
                            if quoted_sender:
                                reply_info = f"↪️ В ответ на {quoted_sender}:\n> {quoted_text}\n\n"
                            else:
                                reply_info = f"↪️ В ответ на сообщение:\n> {quoted_text}\n\n"
                    
                    sender_name = sender_data.get('senderName', 'Неизвестно')
                    
                    # 📝 ТЕКСТОВЫЕ СООБЩЕНИЯ (С ИСПРАВЛЕНИЕМ ID)
                    if msg_type == 'textMessage' and 'textMessageData' in message_data:
                        text = message_data['textMessageData'].get('textMessage')
                        if text:
                            # 👇 ПОЛУЧАЕМ ID СООБЩЕНИЯ ИЛИ СОЗДАЁМ СВОЙ
                            message_id = data.get('idMessage')
                            if not message_id:
                                # Создаём свой ID на основе времени
                                message_id = f"manual_{int(time.time() * 1000)}_{hash(text) % 10000}"
                                print(f"⚠️ ID сообщения отсутствовал, создан ручной: {message_id}")
                            
                            print(f"👤 От: {sender_name}")
                            print(f"📝 Текст: {text[:50]}...")
                            print(f"🆔 ID: {message_id}")
                            
                            full_message = f"{reply_info}📨 MAX от {sender_name}:\n{text}"
                            
                            # Отправляем в Telegram с повторными попытками
                            max_retries = 3
                            sent = False
                            for attempt in range(max_retries):
                                try:
                                    tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                                    tg_data = {
                                        "chat_id": TELEGRAM_CHAT_ID,
                                        "text": full_message
                                    }
                                    tg_response = requests.post(tg_url, json=tg_data, timeout=10)
                                    
                                    if tg_response.status_code == 200:
                                        print(f"✅ Текст отправлен в Telegram (попытка {attempt+1})")
                                        log_message_stats(msg_type, 'sent')
                                        sent = True
                                        break
                                    else:
                                        print(f"❌ Попытка {attempt+1}: ошибка {tg_response.status_code}")
                                        if attempt < max_retries - 1:
                                            time.sleep(2)
                                except Exception as e:
                                    print(f"❌ Попытка {attempt+1}: ошибка {e}")
                                    if attempt < max_retries - 1:
                                        time.sleep(2)
                            
                            if not sent:
                                log_message_stats(msg_type, 'error', 'max retries exceeded')
                    
                    # 🖼️ МЕДИА СООБЩЕНИЯ
                    elif msg_type in ['imageMessage', 'videoMessage', 'documentMessage', 'audioMessage']:
                        file_data = message_data.get('fileMessageData', {})
                        download_url = file_data.get('downloadUrl')
                        caption = file_data.get('caption', '')
                        file_name = file_data.get('fileName', 'media')
                        
                        if download_url:
                            file_type = {
                                'imageMessage': '🖼️ Фото',
                                'videoMessage': '🎥 Видео',
                                'documentMessage': '📄 Документ',
                                'audioMessage': '🎵 Аудио'
                            }.get(msg_type, '📎 Медиа')
                            
                            print(f"👤 От: {sender_name}")
                            print(f"{file_type}: {file_name}")
                            
                            # 👇 ПОЛУЧАЕМ ID ДЛЯ МЕДИА
                            message_id = data.get('idMessage')
                            if not message_id:
                                message_id = f"media_{int(time.time() * 1000)}"
                            
                            try:
                                # Скачиваем файл
                                file_response = requests.get(download_url, timeout=30)
                                
                                if file_response.status_code == 200:
                                    file_size = len(file_response.content)
                                    print(f"📦 Размер файла: {file_size/1024:.1f} KB")
                                    
                                    if file_size > 50 * 1024 * 1024:  # 50 MB
                                        print(f"⚠️ Файл слишком большой ({file_size/1024/1024:.1f} MB), пропускаем")
                                        tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                                        data = {
                                            "chat_id": TELEGRAM_CHAT_ID,
                                            "text": f"⚠️ {sender_name} отправил {file_type}, но файл слишком большой для Telegram ({file_size/1024/1024:.1f} MB)"
                                        }
                                        requests.post(tg_url, json=data, timeout=10)
                                        log_message_stats(msg_type, 'skipped', 'file too large')
                                    else:
                                        full_caption = f"{reply_info}📨 MAX от {sender_name}"
                                        if caption:
                                            full_caption += f"\n{caption}"
                                        
                                        max_retries = 3
                                        sent = False
                                        for attempt in range(max_retries):
                                            try:
                                                if msg_type == 'imageMessage':
                                                    tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
                                                    files = {'photo': (file_name, file_response.content)}
                                                    data = {
                                                        'chat_id': TELEGRAM_CHAT_ID,
                                                        'caption': full_caption
                                                    }
                                                    tg_response = requests.post(tg_url, data=data, files=files, timeout=30)
                                                else:
                                                    tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
                                                    files = {'document': (file_name, file_response.content)}
                                                    data = {
                                                        'chat_id': TELEGRAM_CHAT_ID,
                                                        'caption': full_caption
                                                    }
                                                    tg_response = requests.post(tg_url, data=data, files=files, timeout=30)
                                                
                                                if tg_response.status_code == 200:
                                                    print(f"✅ {file_type} отправлен в Telegram (попытка {attempt+1})")
                                                    log_message_stats(msg_type, 'sent')
                                                    sent = True
                                                    break
                                                else:
                                                    print(f"❌ Попытка {attempt+1}: ошибка {tg_response.status_code}")
                                                    if attempt < max_retries - 1:
                                                        time.sleep(2)
                                            except Exception as e:
                                                print(f"❌ Попытка {attempt+1}: ошибка {e}")
                                                if attempt < max_retries - 1:
                                                    time.sleep(2)
                                        
                                        if not sent:
                                            log_message_stats(msg_type, 'error', 'max retries exceeded')
                                else:
                                    print(f"❌ Не удалось скачать файл: {file_response.status_code}")
                                    log_message_stats(msg_type, 'error', f'download failed {file_response.status_code}')
                            except Exception as e:
                                print(f"❌ Ошибка обработки медиа: {e}")
                                log_message_stats(msg_type, 'error', str(e))
                        else:
                            print("⏭️ Нет ссылки на файл")
                            log_message_stats(msg_type, 'skipped', 'no download URL')
                    else:
                        print(f"⏭️ Неподдерживаемый тип: {msg_type}")
                        log_message_stats(msg_type, 'skipped', 'unsupported type')
                else:
                    print(f"⏭️ Не тот чат (жду {MAX_CHAT_ID})")
                    log_message_stats(msg_type, 'skipped', 'wrong chat')
                
                # Удаляем уведомление
                delete_url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/deleteNotification/{API_TOKEN}/{receipt_id}"
                requests.delete(delete_url)
                print("🗑️ Уведомление удалено")
        else:
            print(".", end="", flush=True)
            
    except requests.exceptions.Timeout:
        print("t", end="", flush=True)
    except Exception as e:
        print(f"\n❌ Ошибка в основном цикле: {e}")
        time.sleep(5)
    
    time.sleep(1)
