import os
import requests

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
RENDER_URL = "https://test-tys3.onrender.com"  # твой URL на Render

url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
data = {"url": f"{RENDER_URL}/"}

response = requests.post(url, json=data)
print("✅ Вебхук настроен:", response.json())
