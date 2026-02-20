import os
import requests
import time
import json
from datetime import datetime

# ===== ПЕРЕМЕННЫЕ ИЗ ОКРУЖЕНИЯ =====
ID_INSTANCE = os.environ.get('ID_INSTANCE')
API_TOKEN = os.environ.get('API_TOKEN')
MAX_CHAT_ID = os.environ.get('MAX_CHAT_ID')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
# ===================================

print("=" * 50)
print("🔍 ЭКСТРЕННАЯ ДИАГНОСТИКА")
print("=" * 50)
print(f"📱 Инстанс: {ID_INSTANCE}")
print(f"🎯 Ожидаемый чат: {MAX_CHAT_ID}")
print("=" * 50)

receive_url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/receiveNotification/{API_TOKEN}"

while True:
    try:
        response = requests.get(receive_url, timeout=30)
        
        if response.status_code == 200 and response.text and response.text != "null":
            data = response.json()
            receipt_id = data.get('receiptId')
            
            if receipt_id:
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔔 ПОЛУЧЕНО!")
                
                # Просто выводим ID чата
                body = data.get('body', {})
                sender_data = body.get('senderData', {})
                chat_id = sender_data.get('chatId')
                
                print(f"ID чата: {chat_id}")
                print(f"Совпадает с ожидаемым: {chat_id == MAX_CHAT_ID}")
                
                # Удаляем уведомление
                delete_url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/deleteNotification/{API_TOKEN}/{receipt_id}"
                requests.delete(delete_url)
        else:
            print(".", end="", flush=True)
            
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        time.sleep(5)
    
    time.sleep(1)
