import os
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

# ===== ПЕРЕМЕННЫЕ ИЗ ОКРУЖЕНИЯ =====
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
# ===================================

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Test server is running")
    
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        print("\n📥 ПОЛУЧЕН POST ЗАПРОС!")
        print(f"Данные: {post_data.decode('utf-8')}")
        
        # Отправляем ответ
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), Handler)
    print(f"🚀 Тестовый сервер запущен на порту {port}")
    print("Жду POST запросы от Telegram...")
    server.serve_forever()

if __name__ == "__main__":
    run()
