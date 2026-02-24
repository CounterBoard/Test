import os
import requests
import json

# Берём данные из переменных окружения Render
ID_INSTANCE = os.environ.get('ID_INSTANCE')
API_TOKEN = os.environ.get('API_TOKEN')
MAX_CHAT_ID = os.environ.get('MAX_CHAT_ID')

print(f"🔍 Проверка истории для чата: {MAX_CHAT_ID}")
print("=" * 50)

# Проверяем, есть ли вообще сообщения в чате
url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/GetChatHistory/{API_TOKEN}"
payload = {
    "chatId": MAX_CHAT_ID,
    "count": 5
}

try:
    response = requests.post(url, json=payload, timeout=10)
    
    print(f"📊 Статус ответа: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"📨 Получено сообщений: {len(data)}")
        
        if len(data) > 0:
            print("\n📌 Первое сообщение в истории:")
            print(json.dumps(data[0], indent=2, ensure_ascii=False))
        else:
            print("\n⚠️ История пуста!")
            print("Возможные причины:")
            print("  • В чате нет сообщений за последние 14 дней")
            print("  • Неправильный ID чата")
            print("  • Нет доступа к истории этого чата")
    else:
        print(f"❌ Ошибка API: {response.text}")
        
except Exception as e:
    print(f"❌ Ошибка при запросе: {e}")
