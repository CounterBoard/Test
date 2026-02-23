import os
import requests
import time
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

# ===== МИНИМАЛЬНЫЙ ВЕБ-СЕРВЕР ДЛЯ RENDER =====
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Diagnostic mode")
    def log_message(self, format, *args): pass

def run_http_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    print(f"🌐 Веб-сервер запущен на порту {port}")
    server.serve_forever()

web_thread = threading.Thread(target=run_http_server, daemon=True)
web_thread.start()
# ==============================================

ID_INSTANCE = os.environ.get('ID_INSTANCE')
API_TOKEN = os.environ.get('API_TOKEN')

print("🔍 МОНИТОРИНГ ВСЕХ УВЕДОМЛЕНИЙ GREEN-API")
print("=" * 60)

receive_url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/receiveNotification/{API_TOKEN}"
stats = {'total': 0, 'types': {}}

while True:
    try:
        response = requests.get(receive_url, timeout=30)
        
        if response.status_code == 200 and response.text and response.text != "null":
            data = response.json()
            receipt_id = data.get('receiptId')
            
            if receipt_id:
                # Получаем тип вебхука
                webhook_type = data.get('body', {}).get('typeWebhook', 'unknown')
                
                stats['total'] += 1
                stats['types'][webhook_type] = stats['types'].get(webhook_type, 0) + 1
                
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔔 УВЕДОМЛЕНИЕ #{stats['total']}")
                print(f"📌 Тип: {webhook_type}")
                
                # Для исходящих сообщений покажем больше деталей
                if webhook_type in ['outgoingMessageReceived', 'outgoingMessageStatus']:
                    body = data.get('body', {})
                    msg_data = body.get('messageData', {})
                    sender = body.get('senderData', {})
                    print(f"📨 Чат: {sender.get('chatId')}")
                    print(f"📝 Тип сообщения: {msg_data.get('typeMessage')}")
                    print(f"🆔 ID сообщения: {data.get('idMessage')}")
                
                # Удаляем уведомление
                delete_url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/deleteNotification/{API_TOKEN}/{receipt_id}"
                requests.delete(delete_url)
                
                # Каждые 10 сообщений показываем статистику
                if stats['total'] % 10 == 0:
                    print("\n" + "="*60)
                    print("📊 СТАТИСТИКА ТИПОВ УВЕДОМЛЕНИЙ:")
                    for t, count in stats['types'].items():
                        print(f"   {t}: {count}")
                    print("="*60)
        else:
            print(".", end="", flush=True)
            
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        time.sleep(5)
    
    time.sleep(1)
