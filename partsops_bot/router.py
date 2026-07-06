import urllib.request
import json
import logging
import sys
import os
from config import CFG

logger = logging.getLogger("router")

class Router:
    def __init__(self, token: str, operators: set[int]):
        self.token = token
        self.operators = operators

    def send_message(self, chat_id: int, text: str, reply_to_message_id: int = None):
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
        }
        if reply_to_message_id:
            payload["reply_to_message_id"] = reply_to_message_id

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}
        )
        try:
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, context=ctx) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            logger.error("Failed to send message: %r", e)

    def dispatch(self, update: dict):
        message = update.get("message")
        if not message:
            return

        chat = message.get("chat", {})
        chat_id = chat.get("id")
        user = message.get("from", {})
        user_id = user.get("id")
        text = message.get("text", "")
        message_id = message.get("message_id")

        logger.info(f"Received message from user_id={user_id} (chat_id={chat_id}): {text}")

        # Check whitelist
        if user_id not in self.operators:
            self.send_message(chat_id, f"🚫 Доступ запрещен. Ваш Telegram ID: {user_id}", reply_to_message_id=message_id)
            return

        if not text:
            return

        if text.startswith("/start") or text.startswith("/help"):
            help_text = (
                "🤖 *PartsOps AI Bot* готов к работе!\n\n"
                "Пришлите текстовый запрос на подбор автодеталей (например, с VIN-кодом), и AI-агент автоматически обработает его.\n\n"
                "Доступные команды:\n"
                "/status — текущий статус бота\n"
                "/help — список команд\n"
            )
            self.send_message(chat_id, help_text, reply_to_message_id=message_id)
            return

        if text.startswith("/status"):
            status_text = (
                "ℹ️ *Статус системы:*\n"
                "- Бот: Активен\n"
                "- Подключение к БД: OK\n"
                "- Модель: NIM (google/gemma-4-31b-it) подключена"
            )
            self.send_message(chat_id, status_text, reply_to_message_id=message_id)
            return

        # Fallback: process user query through the agent orchestrator
        try:
            # Add backend path
            backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../partsops-ai-manager"))
            if backend_path not in sys.path:
                sys.path.append(backend_path)
            
            from agent_orchestrator import process_request
            
            self.send_message(chat_id, "⏳ Обрабатываю запрос с помощью AI...", reply_to_message_id=message_id)
            
            # Run orchestrator
            response = process_request(
                raw_request=text,
                customer_name=f"Telegram User {user_id}",
            )
            
            if response.status == "processed" and response.result:
                res = response.result
                parts_str = "\n".join([
                    f"- {p.get('name', 'Деталь')} (Кол-во: {p.get('quantity', 1)})"
                    for p in res.get("extracted_parts", [])
                ])
                vin_info = f"VIN: {res.get('vehicle_vin', 'Не найден')}"
                if res.get('vehicle_make'):
                    vin_info += f" ({res.get('vehicle_make')} {res.get('vehicle_model', '')})"
                
                reply = (
                    f"✅ *Запрос обработан!*\n\n"
                    f"🚗 *Автомобиль:* {vin_info}\n"
                    f"🔧 *Найденные детали:*\n{parts_str}\n\n"
                    f"📝 *Лог трассировки агента:*\n" + "\n".join([f"• {t}" for t in response.trace[:5]])
                )
                self.send_message(chat_id, reply, reply_to_message_id=message_id)
            else:
                self.send_message(chat_id, f"❌ Ошибка обработки запроса: {response.error or 'Неизвестная ошибка'}", reply_to_message_id=message_id)
                
        except Exception as e:
            logger.exception("Error in dispatch: %r", e)
            self.send_message(chat_id, f"⚠️ Произошла внутренняя ошибка: {e}", reply_to_message_id=message_id)
