import requests
import json

ID_INSTANCE = "3100522242"
API_TOKEN = "ff2c2e1b33094666ad55ad03b4741240618374a110e34efd82"

print("🔍 ПРОВЕРКА ИНСТАНСА GREEN-API")
print("=" * 50)

# Проверка статуса
url_state = f"https://api.green-api.com/waInstance{ID_INSTANCE}/getStateInstance/{API_TOKEN}"
response_state = requests.get(url_state)
print("📌 Статус инстанса:", response_state.json())

# Проверка настроек
url_settings = f"https://api.green-api.com/waInstance{ID_INSTANCE}/getSettings/{API_TOKEN}"
response_settings = requests.get(url_settings)
settings = response_settings.json()
print("\n📌 Настройки вебхуков:")
print(f"incomingWebhook (входящие): {settings.get('incomingWebhook')}")
print(f"outgoingWebhook (исходящие): {settings.get('outgoingWebhook')}")
print(f"webhookUrl: {settings.get('webhookUrl')}")

# Проверка очереди
url_q = f"https://api.green-api.com/waInstance{ID_INSTANCE}/getLastIncomingMessages/{API_TOKEN}"
response_q = requests.get(url_q)
print(f"\n📌 Последние входящие сообщения: {len(response_q.json()) if response_q.status_code == 200 else 'ошибка'}")
