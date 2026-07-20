"""
Delivery Agent - Handles invoice download and client delivery via Telegram/Email

This agent is responsible for:
1. Managing document download (PDF generation, etc.)
2. Sending documents to clients via their preferred channel
3. Tracking delivery status
4. Handling retries and confirmations
"""

from __future__ import annotations

import logging
import uuid
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

from app.agents.base_agent import BaseAgent, AgentContext, AgentResult, AgentType
from models import PartRequest, EventType, OutboundMessage, RequestState
from sqlmodel import select

logger = logging.getLogger("agents.delivery")


class DeliveryChannel(str, Enum):
    """Delivery channels"""
    TELEGRAM = "telegram"
    EMAIL = "email"
    DOWNLOAD = "download"  # Direct download link
    WEBHOOK = "webhook"  # Push to external system


class DeliveryStatus(str, Enum):
    """Delivery status"""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"
    CONFIRMED = "confirmed"  # Client confirmed receipt


class DeliveryAgent(BaseAgent):
    """
    Delivery Agent - Handles document delivery to clients.
    
    Supports multiple channels:
    - Telegram Bot (using existing bot infrastructure)
    - Email (SMTP)
    - Direct download link
    - Webhook to external systems
    """
    
    def __init__(self, tenant_id: str = "default", config: Optional[Dict[str, Any]] = None):
        super().__init__(AgentType.DELIVERY, tenant_id, config)
        self.default_channel = self.config.get("default_channel", DeliveryChannel.TELEGRAM)
        self.enable_retry = self.config.get("enable_retry", True)
        self.max_retries = self.config.get("max_retries", 3)
        self.retry_delay_seconds = self.config.get("retry_delay_seconds", 60)
    
    def execute(self, context: AgentContext) -> AgentResult:
        """Execute delivery of approval document"""
        
        if not context.request_id:
            return AgentResult(
                success=False,
                agent_type=self.agent_type,
                errors=["No request_id in context"],
                next_agent=None
            )
        
        request = self._get_order(context.request_id)
        if not request:
            return AgentResult(
                success=False,
                agent_type=self.agent_type,
                errors=[f"Request {context.request_id} not found"],
                next_agent=None
            )
        
        # Get document info from processing results
        processing_result = context.previous_results.get("processing", {})
        document_result = context.previous_results.get("document", {})
        gates_result = context.previous_results.get("gates", {})
        
        document_id = document_result.get("document_id") or request.erp_quotation_ref
        if not document_id:
            return AgentResult(
                success=False,
                agent_type=self.agent_type,
                errors=["No document to deliver"],
                next_agent=None
            )
        
        # Check if request requires approval first
        auto_advance = gates_result.get("auto_advance_allowed", False)
        if not auto_advance and request.status == RequestState.READY_FOR_APPROVAL:
            # Request is waiting for approval - don't send yet
            return AgentResult(
                success=True,
                agent_type=self.agent_type,
                data={
                    "request_id": request.request_id,
                    "status": "awaiting_approval",
                    "message": "Request requires manual approval before delivery",
                },
                next_agent=AgentType.REPORTING,
                correlation_id=context.correlation_id
            )
        
        # Determine delivery channel based on source
        channel = self._determine_channel(request, context)
        
        # Build delivery content
        content = self._build_delivery_content(request, document_result, processing_result)
        
        # Send via appropriate channel with retry
        delivery_result = self._deliver_with_retry(channel, request, content, document_id)
        
        if not delivery_result["success"]:
            return AgentResult(
                success=False,
                agent_type=self.agent_type,
                errors=delivery_result["errors"],
                next_agent=None
            )
        
        # Update request status
        self._update_status(request, RequestState.SENT_TO_CLIENT)
        
        # Store delivery info in context
        context.previous_results["delivery"] = delivery_result
        
        # Next agent: Reporting
        return AgentResult(
            success=True,
            agent_type=self.agent_type,
            data={
                "request_id": request.request_id,
                "channel": channel.value,
                "delivery_id": delivery_result.get("delivery_id"),
                "status": delivery_result.get("status"),
                "recipient": delivery_result.get("recipient"),
            },
            next_agent=AgentType.REPORTING,
            correlation_id=context.correlation_id
        )
    
    def _determine_channel(
        self, 
        request: PartRequest, 
        context: AgentContext
    ) -> DeliveryChannel:
        """Determine the best delivery channel based on source and customer data"""
        
        # Check context for explicit channel preference
        if context.metadata.get("delivery_channel"):
            try:
                return DeliveryChannel(context.metadata["delivery_channel"])
            except ValueError:
                pass
        
        # Default based on source - but only if valid recipient exists
        if request.source == "telegram":
            return DeliveryChannel.TELEGRAM
        elif request.source == "email":
            if request.customer_email_masked:
                return DeliveryChannel.EMAIL
            else:
                # Fallback to download if no email
                return DeliveryChannel.DOWNLOAD
        elif request.customer_email_masked:
            return DeliveryChannel.EMAIL
        else:
            return DeliveryChannel.DOWNLOAD
    
    def _build_delivery_content(
        self, 
        request: PartRequest, 
        document: Dict[str, Any],
        processing: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build the delivery message/content"""
        
        pricing = processing.get("pricing_evidence", {})
        line_items = pricing.get("line_items", [])
        
        # Build line items text
        lines_text = []
        for item in line_items:
            lines_text.append(
                f"• {item.get('part_name', 'Деталь')} — "
                f"{item.get('quantity', 1)} шт. × {item.get('sale_price', 0):.2f} = "
                f"{item.get('line_total', 0):.2f} руб."
            )
        
        lines_str = "\n".join(lines_text) if lines_text else "Детали не указаны"
        
        # Vehicle info
        vehicle_info = ""
        if request.vehicle_make or request.vehicle_model:
            vehicle_info = f"\n🚗 Автомобиль: {request.vehicle_make or ''} {request.vehicle_model or ''}"
            if request.vehicle_year:
                vehicle_info += f" ({request.vehicle_year})"
            if request.vehicle_vin_masked:
                vehicle_info += f" VIN: {request.vehicle_vin_masked}"
        
        # Build message
        message = (
            f"📋 *Заказ на согласование* #{request.request_id}\n\n"
            f"👤 Клиент: {request.customer_name or 'Не указан'}"
            f"{vehicle_info}\n\n"
            f"🔧 *Позиции заказа:*\n{lines_str}\n\n"
            f"💰 *Итого:*\n"
            f"• Подытог: {pricing.get('subtotal', 0):.2f} руб.\n"
            f"• НДС (20%): {pricing.get('tax', 0):.2f} руб.\n"
            f"• **Всего к оплате: {pricing.get('total', 0):.2f} руб.**\n\n"
            f"📎 Документ: {document.get('document_id', 'N/A')}\n"
            f"🔗 Ссылка на оригинал заявки: {request.raw_input_ref or 'N/A'}\n\n"
            f"Для подтверждения заказа, пожалуйста, ответьте на это сообщение или перейдите по ссылке."
        )
        
        # Also create structured data for API/webhook delivery
        structured = {
            "request_id": request.request_id,
            "document_id": document.get("document_id"),
            "customer": {
                "name": request.customer_name,
                "phone": request.customer_phone_masked,
                "email": request.customer_email_masked,
            },
            "vehicle": {
                "make": request.vehicle_make,
                "model": request.vehicle_model,
                "year": request.vehicle_year,
                "vin": request.vehicle_vin_masked,
            },
            "line_items": line_items,
            "totals": {
                "subtotal": pricing.get("subtotal", 0),
                "tax": pricing.get("tax", 0),
                "total": pricing.get("total", 0),
            },
            "original_ref": request.raw_input_ref,
            "message_text": message,
        }
        
        return {
            "text": message,
            "structured": structured,
            "subject": f"Заказ #{request.request_id} на согласование",
        }
    
    def _deliver(
        self, 
        request: PartRequest, 
        channel: DeliveryChannel, 
        content: Dict[str, Any],
        document_id: str
    ) -> Dict[str, Any]:
        """Deliver via the specified channel"""
        
        if channel == DeliveryChannel.TELEGRAM:
            return self._deliver_telegram(request, content, document_id)
        elif channel == DeliveryChannel.EMAIL:
            return self._deliver_email(request, content, document_id)
        elif channel == DeliveryChannel.DOWNLOAD:
            return self._deliver_download(request, content, document_id)
        elif channel == DeliveryChannel.WEBHOOK:
            return self._deliver_webhook(request, content, document_id)
        else:
            return {"success": False, "errors": [f"Unknown channel: {channel}"]}
    
    def _deliver_telegram(
        self, 
        request: PartRequest, 
        content: Dict[str, Any], 
        document_id: str
    ) -> Dict[str, Any]:
        """Deliver via Telegram bot"""
        
        # Try to get chat_id from original reference
        chat_id = None
        if request.raw_input_ref and request.raw_input_ref.startswith("tg:msg:"):
            parts = request.raw_input_ref.split(":")
            if len(parts) >= 3:
                try:
                    chat_id = int(parts[2])
                except ValueError:
                    pass
        
        # Create outbound message for Telegram
        # The actual sending will be handled by the Telegram bot polling
        # We just queue it in the outbox
        delivery_id = f"del_{uuid.uuid4().hex[:12]}"
        
        outbound = self.create_outbound_message(
            channel="telegram",
            recipient=str(chat_id) if chat_id else "unknown",
            body_text=content["text"],
            subject=content["subject"],
            request_id=request.request_id,
            payload={
                "document_id": document_id,
                "delivery_id": delivery_id,
                "structured": content["structured"],
            }
        )
        
        # In a real implementation, we'd trigger the bot to send immediately
        # For now, we return the queued message
        
        return {
            "success": True,
            "delivery_id": delivery_id,
            "channel": "telegram",
            "status": "queued",
            "recipient": str(chat_id) if chat_id else "unknown",
            "outbound_id": outbound.id,
        }
    
    def _deliver_with_retry(
        self,
        channel: DeliveryChannel,
        request: PartRequest,
        content: Dict[str, Any],
        document_id: str,
        max_retries: Optional[int] = None
    ) -> Dict[str, Any]:
        """Deliver with retry logic"""
        max_retries = max_retries if max_retries is not None else self.max_retries
        
        for attempt in range(max_retries + 1):
            if channel == DeliveryChannel.TELEGRAM:
                result = self._deliver_telegram(request, content, document_id)
            elif channel == DeliveryChannel.EMAIL:
                result = self._deliver_email(request, content, document_id)
            elif channel == DeliveryChannel.DOWNLOAD:
                result = self._deliver_download(request, content, document_id)
            elif channel == DeliveryChannel.WEBHOOK:
                result = self._deliver_webhook(request, content, document_id)
            else:
                return {"success": False, "errors": [f"Unknown channel: {channel}"]}
            
            if result["success"]:
                return result
            
            # If failed and not last attempt, wait and retry
            if attempt < max_retries:
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s...
                self.logger.warning(f"Delivery attempt {attempt + 1} failed for {request.request_id}, retrying in {wait_time}s...")
                time.sleep(wait_time)
        
        return {"success": False, "errors": [f"Delivery failed after {max_retries + 1} attempts"]}

    def _deliver_email(
        self, 
        request: PartRequest, 
        content: Dict[str, Any], 
        document_id: str
    ) -> Dict[str, Any]:
        """Deliver via Email"""
        
        recipient = request.customer_email_masked
        if not recipient:
            return {"success": False, "errors": ["No email address for customer"]}
        
        delivery_id = f"del_{uuid.uuid4().hex[:12]}"
        
        outbound = self.create_outbound_message(
            channel="email",
            recipient=recipient,
            body_text=content["text"],
            subject=content["subject"],
            request_id=request.request_id,
            payload={
                "document_id": document_id,
                "delivery_id": delivery_id,
                "structured": content["structured"],
            }
        )
        
        return {
            "success": True,
            "delivery_id": delivery_id,
            "channel": "email",
            "status": "queued",
            "recipient": recipient,
            "outbound_id": outbound.id,
        }
    
    def _deliver_download(
        self, 
        request: PartRequest, 
        content: Dict[str, Any], 
        document_id: str
    ) -> Dict[str, Any]:
        """Provide direct download link"""
        
        # Generate a tracking token for client portal
        from client_portal import create_tracking_token
        
        token = create_tracking_token(
            request_id=request.request_id,
            tenant_id=self.tenant_id,
            expires_hours=72,
        )
        
        download_url = f"https://partsops.example.com/client/track/{token}"
        
        return {
            "success": True,
            "delivery_id": f"del_{uuid.uuid4().hex[:12]}",
            "channel": "download",
            "status": "available",
            "recipient": "client_portal",
            "download_url": download_url,
            "tracking_token": token,
        }
    
    def _deliver_webhook(
        self, 
        request: PartRequest, 
        content: Dict[str, Any], 
        document_id: str
    ) -> Dict[str, Any]:
        """Deliver via webhook to external system"""
        
        webhook_url = self.config.get("webhook_url")
        if not webhook_url:
            return {"success": False, "errors": ["Webhook URL not configured"]}
        
        delivery_id = f"del_{uuid.uuid4().hex[:12]}"
        
        outbound = self.create_outbound_message(
            channel="webhook",
            recipient=webhook_url,
            body_text=content["text"],
            subject=content["subject"],
            request_id=request.request_id,
            payload={
                "document_id": document_id,
                "delivery_id": delivery_id,
                "structured": content["structured"],
                "webhook_url": webhook_url,
            }
        )
        
        return {
            "success": True,
            "delivery_id": delivery_id,
            "channel": "webhook",
            "status": "queued",
            "recipient": webhook_url,
            "outbound_id": outbound.id,
        }
    
    def _update_status(self, request: PartRequest, status: RequestState):
        """Update request status"""
        request.status = status.value
        request.updated_at = datetime.utcnow()
        self.session.add(request)
        self.session.commit()
        
        self.emit_event(
            request_id=request.request_id,
            event_type=EventType.STATE_CHANGED,
            actor_type="agent",
            actor_id="delivery_agent",
            payload={"new_state": status.value}
        )
    
    def _get_order(self, request_id: str) -> Optional[PartRequest]:
        """Get existing PartRequest"""
        return self.session.exec(
            select(PartRequest).where(
                PartRequest.request_id == request_id,
                PartRequest.tenant_id == self.tenant_id
            )
        ).first()


def create_delivery_agent(tenant_id: str = "default", config: Optional[Dict] = None) -> DeliveryAgent:
    """Create a delivery agent instance"""
    return DeliveryAgent(tenant_id=tenant_id, config=config)