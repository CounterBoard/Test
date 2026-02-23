import requests

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
RENDER_URL = "https://akuxfafueruirffuax.onrender.com"  # замени на свой URL

url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
data = {"url": f"{RENDER_URL}/"}

response = requests.post(url, json=data)
print("✅ Вебхук настроен:", response.json())
