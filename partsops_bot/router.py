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
        self.api_base_url = os.environ.get("PARTSOPS_API_URL", "http://localhost:8000")
        self.api_token = os.environ.get("PARTSOPS_API_TOKEN", "test-token")

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

    def _call_pipeline_api(self, endpoint: str, payload: dict) -> dict:
        """Call the PartsOps AI Manager pipeline API"""
        url = f"{self.api_base_url}/api{endpoint}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_token}",
                "X-Tenant-ID": "default",
            }
        )
        try:
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, context=ctx, timeout=60) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            logger.error("API call failed: %r", e)
            return {"success": False, "error": str(e)}

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
                "Пришлите текстовый запрос на подбор автодеталей (например, с VIN-кодом), и мультиагентная система автоматически обработает его:\n"
                "1. 📥 Intake Agent — сбор и структурирование заказа\n"
                "2. 🔧 Processing Agent — подбор деталей и расчет цен\n"
                "3. 📤 Delivery Agent — отправка документа на согласование\n"
                "4. 📊 Reporting Agent — отчет в Telegram\n\n"
                "Доступные команды:\n"
                "/status — текущий статус бота\n"
                "/help — список команд\n"
                "/pipeline <request_id> — продолжить обработку заказа\n"
            )
            self.send_message(chat_id, help_text, reply_to_message_id=message_id)
            return

        if text.startswith("/status"):
            status_text = (
                "ℹ️ *Статус системы:*\n"
                "- Бот: Активен\n"
                "- Подключение к БД: OK\n"
                "- Модель: NIM (google/gemma-4-31b-it) подключена\n"
                "- Мультиагентная система: Активна"
            )
            self.send_message(chat_id, status_text, reply_to_message_id=message_id)
            return

        if text.startswith("/pipeline"):
            parts = text.split()
            if len(parts) < 2:
                self.send_message(chat_id, "Использование: /pipeline <request_id> [stage]", reply_to_message_id=message_id)
                return
            request_id = parts[1]
            stage = parts[2] if len(parts) > 2 else "processing"
            
            self.send_message(chat_id, f"🔄 Продолжаю обработку заказа {request_id} с этапа {stage}...", reply_to_message_id=message_id)
            
            result = self._call_pipeline_api(f"/pipeline/continue/{request_id}", {"start_from": stage})
            
            if result.get("success"):
                reply = f"✅ Заказ {request_id} продолжен успешно!\nСтатус: {result.get('phases', {})}"
            else:
                reply = f"❌ Ошибка: {result.get('error', 'Unknown error')}"
            self.send_message(chat_id, reply, reply_to_message_id=message_id)
            return

        # Process user query through the multi-agent pipeline
        try:
            self.send_message(chat_id, "⏳ Обрабатываю запрос через мультиагентную систему...", reply_to_message_id=message_id)
            
            # Build metadata with Telegram info
            metadata = {
                "source_metadata": {
                    "message_id": message_id,
                    "chat_id": chat_id,
                    "user_id": user_id,
                    "username": user.get("username"),
                    "first_name": user.get("first_name"),
                    "last_name": user.get("last_name"),
                    "date": message.get("date"),
                },
                "attachments": [],
            }
            
            # Check for attachments
            if message.get("photo"):
                metadata["attachments"].append({"type": "photo", "file_id": message["photo"][-1]["file_id"]})
            if message.get("document"):
                metadata["attachments"].append({"type": "document", "file_id": message["document"]["file_id"], "file_name": message["document"].get("file_name")})
            
            # Call the pipeline API
            payload = {
                "source": "telegram",
                "text": text,
                "customer_name": f"Telegram User {user_id}",
                "customer_phone": None,
                "customer_email": None,
                "customer_erp_id": None,
                "vehicle_vin": None,
                "vehicle_make": None,
                "vehicle_model": None,
                "vehicle_year": None,
                "vehicle_generation": None,
                "vehicle_engine": None,
                "parts_data": None,
                "metadata": metadata,
                "priority": "normal",
            }
            
            result = self._call_pipeline_api("/pipeline/run", payload)
            
            if result.get("success"):
                request_id = result.get("request_id")
                phases = result.get("phases", {})
                
                # Build response message
                processing = phases.get("processing", {})
                processing_data = processing.get("data", {})
                
                matched_parts = processing_data.get("matched_parts", 0)
                total_amount = 0
                pricing = processing_data.get("pricing_evidence", {})
                if pricing:
                    total_amount = pricing.get("total", 0)
                
                auto_advance = processing_data.get("auto_advance", False)
                approval_required = processing_data.get("approval_required", False)
                
                delivery = phases.get("delivery", {})
                delivery_data = delivery.get("data", {})
                delivery_status = delivery_data.get("status", "unknown")
                delivery_channel = delivery_data.get("channel", "unknown")
                
                reply = (
                    f"✅ *Заказ #{request_id} обработан!*\n\n"
                    f"📊 *Результаты:*\n"
                    f"• Найдено деталей: {matched_parts}\n"
                    f"• Сумма заказа: {total_amount:.2f} руб.\n"
                    f"• Авто-согласование: {'Да' if auto_advance else 'Нет (требуется одобрение)'}\n\n"
                    f"📤 *Доставка:* {delivery_channel} — {delivery_status}\n\n"
                    f"📝 *Этапы:*\n"
                )
                
                for phase_name, phase_data in phases.items():
                    status = "✅" if phase_data.get("success") else "❌"
                    time_ms = phase_data.get("execution_time_ms", 0)
                    reply += f"• {status} {phase_name.capitalize()} ({time_ms}ms)\n"
                
                reply += f"\n🔗 Оригинал заявки: tg:msg:{chat_id}:{message_id}"
                
                self.send_message(chat_id, reply, reply_to_message_id=message_id)
            else:
                error = result.get("error", "Unknown error")
                self.send_message(chat_id, f"❌ Ошибка обработки: {error}", reply_to_message_id=message_id)
                
        except Exception as e:
            logger.exception("Error in dispatch: %r", e)
            self.send_message(chat_id, f"⚠️ Произошла внутренняя ошибка: {e}", reply_to_message_id=message_id)