"""
Reporting Agent - Reports all phases results to Telegram bot

This agent is responsible for:
1. Sending status updates to Telegram bot for operators
2. Sending notifications to clients
3. Aggregating pipeline results
4. Creating summary reports
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from enum import Enum

from app.agents.base_agent import BaseAgent, AgentContext, AgentResult, AgentType
from models import PartRequest, EventType, OutboundMessage, RequestState
from sqlmodel import select

logger = logging.getLogger("agents.reporting")


class ReportType(str, Enum):
    """Types of reports"""
    OPERATOR_NOTIFICATION = "operator_notification"  # To internal team
    CLIENT_NOTIFICATION = "client_notification"  # To customer
    PIPELINE_SUMMARY = "pipeline_summary"  # Full pipeline report
    ERROR_ALERT = "error_alert"  # Error notifications


class ReportingAgent(BaseAgent):
    """
    Reporting Agent - Sends notifications and reports to Telegram and other channels.
    
    Reports on:
    - New order received
    - Processing completed
    - Document ready for approval
    - Approval status changes
    - Delivery confirmations
    - Errors and warnings
    """
    
    def __init__(self, tenant_id: str = "default", config: Optional[Dict[str, Any]] = None):
        super().__init__(AgentType.REPORTING, tenant_id, config)
        self.operator_chat_ids = self.config.get("operator_chat_ids", [])
        self.notify_on_success = self.config.get("notify_on_success", True)
        self.notify_on_error = self.config.get("notify_on_error", True)
        self.notify_on_approval_needed = self.config.get("notify_on_approval_needed", True)
    
    def execute(self, context: AgentContext) -> AgentResult:
        """Generate and send reports for the completed pipeline"""
        
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
        
        # Collect all phase results
        intake_result = context.previous_results.get("intake", {})
        processing_result = context.previous_results.get("processing", {})
        gates_result = context.previous_results.get("gates", {})
        document_result = context.previous_results.get("document", {})
        delivery_result = context.previous_results.get("delivery", {})
        
        # Determine what type of report to send
        reports_sent = []
        
        # 1. Send operator notification (internal team)
        if self.operator_chat_ids:
            operator_report = self._build_operator_report(
                request, intake_result, processing_result, 
                gates_result, document_result, delivery_result
            )
            
            for chat_id in self.operator_chat_ids:
                self._send_telegram_report(chat_id, operator_report, request.request_id)
                reports_sent.append(f"operator:{chat_id}")
        
        # 2. Send client notification if delivery was successful
        if delivery_result.get("success") and request.source == "telegram":
            client_report = self._build_client_report(request, document_result, delivery_result)
            chat_id = self._extract_chat_id(request)
            if chat_id:
                self._send_telegram_report(chat_id, client_report, request.request_id, is_client=True)
                reports_sent.append(f"client:{chat_id}")
        
        # 3. Log pipeline summary event
        self._log_pipeline_summary(request, context)
        
        # 4. If there were errors, send error alert
        all_errors = []
        for phase, result in context.previous_results.items():
            if isinstance(result, dict) and result.get("errors"):
                all_errors.extend(result["errors"])
        
        if all_errors and self.notify_on_error:
            error_report = self._build_error_report(request, all_errors, context)
            for chat_id in self.operator_chat_ids:
                self._send_telegram_report(chat_id, error_report, request.request_id)
                reports_sent.append(f"error:{chat_id}")
        
        # Final status update
        self._update_final_status(request, delivery_result)
        
        return AgentResult(
            success=True,
            agent_type=self.agent_type,
            data={
                "request_id": request.request_id,
                "reports_sent": reports_sent,
                "operator_notified": len([r for r in reports_sent if r.startswith("operator:")]),
                "client_notified": len([r for r in reports_sent if r.startswith("client:")]),
                "errors_reported": len([r for r in reports_sent if r.startswith("error:")]),
            },
            next_agent=None,  # End of pipeline
            correlation_id=context.correlation_id
        )
    
    def _build_operator_report(
        self,
        request: PartRequest,
        intake: Dict[str, Any],
        processing: Dict[str, Any],
        gates: Dict[str, Any],
        document: Dict[str, Any],
        delivery: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build detailed report for operators"""
        
        # Status emoji
        status_emoji = {
            "NEW": "🆕",
            "MATCHING": "🔍",
            "PRICING_REVIEW": "💰",
            "READY_FOR_APPROVAL": "⏳",
            "APPROVED": "✅",
            "SENT_TO_CLIENT": "📤",
            "PAID": "💵",
            "FULFILLED": "📦",
            "CLOSED": "🏁",
            "FAILED": "❌",
            "MANUAL_REVIEW": "👀",
        }.get(request.status, "📋")
        
        # Processing summary
        matched_count = len([p for p in processing.get("matched_parts", []) if p.get("best_match")])
        total_parts = len(processing.get("matched_parts", []))
        
        pricing = processing.get("pricing_evidence", {})
        total_amount = pricing.get("total", 0)
        
        # Gates status
        gates_passed = gates.get("all_gates_passed", False)
        auto_advance = gates.get("auto_advance_allowed", False)
        
        text = (
            f"{status_emoji} *Заказ #{request.request_id}*\n\n"
            f"📊 *Статус:* {request.status}\n"
            f"📥 *Источник:* {request.source}\n"
            f"👤 *Клиент:* {request.customer_name or 'Не указан'}\n"
            f"🚗 *Авто:* {request.vehicle_make or ''} {request.vehicle_model or ''}"
            f"{f' ({request.vehicle_year})' if request.vehicle_year else ''}\n"
            f"🔢 *VIN:* {request.vehicle_vin_masked or 'Не указан'}\n\n"
            f"🔧 *Детали:* {matched_count}/{total_parts} найдено\n"
            f"💰 *Сумма:* {total_amount:.2f} руб.\n\n"
            f"🛡 *Защитные ворота:* {'✅ Пройдены' if gates_passed else '❌ Не пройдены'}\n"
            f"⚡ *Авто-продвижение:* {'Да' if auto_advance else 'Нет (требуется одобрение)'}\n\n"
            f"📄 *Документ:* {document.get('document_id', 'N/A')}\n"
            f"📤 *Доставка:* {delivery.get('channel', 'N/A')} — {delivery.get('status', 'N/A')}\n"
            f"🔗 *Оригинал:* {request.raw_input_ref or 'N/A'}\n\n"
            f"⏱ *Pipeline ID:* {request.request_id}"
        )
        
        return {
            "type": ReportType.OPERATOR_NOTIFICATION,
            "text": text,
            "structured": {
                "request_id": request.request_id,
                "status": request.status,
                "source": request.source,
                "matched_parts": matched_count,
                "total_parts": total_parts,
                "total_amount": total_amount,
                "gates_passed": gates_passed,
                "auto_advance": auto_advance,
                "document_id": document.get("document_id"),
                "delivery_status": delivery.get("status"),
                "original_ref": request.raw_input_ref,
            }
        }
    
    def _build_client_report(
        self,
        request: PartRequest,
        document: Dict[str, Any],
        delivery: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build client-friendly notification"""
        
        text = (
            f"📋 *Ваш заказ #{request.request_id} обработан*\n\n"
            f"Статус: {'Отправлен на согласование' if delivery.get('status') == 'queued' else 'Обработан'}\n\n"
            f"Сумма заказа: {document.get('totals', {}).get('total', 0):.2f} руб.\n\n"
            f"Мы свяжемся с вами для подтверждения деталей.\n"
            f"Ссылка на заказ: {request.raw_input_ref or 'N/A'}"
        )
        
        return {
            "type": ReportType.CLIENT_NOTIFICATION,
            "text": text,
            "structured": {
                "request_id": request.request_id,
                "total_amount": document.get("totals", {}).get("total", 0),
                "delivery_status": delivery.get("status"),
            }
        }
    
    def _build_error_report(
        self,
        request: PartRequest,
        errors: List[str],
        context: AgentContext
    ) -> Dict[str, Any]:
        """Build error alert for operators"""
        
        text = (
            f"🚨 *ОШИБКА В ПАЙПЛАЙНЕ* #{request.request_id}\n\n"
            f"Статус: {request.status}\n"
            f"Источник: {request.source}\n\n"
            f"Ошибки:\n" + "\n".join(f"• {e}" for e in errors[:5]) + 
            (f"\n... и еще {len(errors) - 5} ошибок" if len(errors) > 5 else "") +
            f"\n\nPipeline ID: {context.correlation_id}"
        )
        
        return {
            "type": ReportType.ERROR_ALERT,
            "text": text,
            "structured": {
                "request_id": request.request_id,
                "errors": errors,
                "correlation_id": context.correlation_id,
                "current_agent": context.current_agent,
            }
        }
    
    def _send_telegram_report(
        self, 
        chat_id: int, 
        report: Dict[str, Any], 
        request_id: str,
        is_client: bool = False
    ):
        """Queue a Telegram message via outbox"""
        
        delivery_id = f"report_{uuid.uuid4().hex[:12]}"
        
        outbound = self.create_outbound_message(
            channel="telegram",
            recipient=str(chat_id),
            body_text=report["text"],
            subject=f"Report: {report['type'].value}",
            request_id=request_id,
            payload={
                "delivery_id": delivery_id,
                "report_type": report["type"].value,
                "is_client": is_client,
                "structured": report["structured"],
            }
        )
        
        self.logger.info(f"Queued {report['type'].value} report for chat_id={chat_id}, outbound_id={outbound.id}")
    
    def _extract_chat_id(self, request: PartRequest) -> Optional[int]:
        """Extract Telegram chat_id from original reference"""
        if request.raw_input_ref and request.raw_input_ref.startswith("tg:msg:"):
            parts = request.raw_input_ref.split(":")
            if len(parts) >= 3:
                try:
                    return int(parts[2])
                except ValueError:
                    pass
        return None
    
    def _log_pipeline_summary(self, request: PartRequest, context: AgentContext):
        """Log complete pipeline summary as event"""
        
        summary = {
            "request_id": request.request_id,
            "source": request.source,
            "status": request.status,
            "phases": list(context.previous_results.keys()),
            "correlation_id": context.correlation_id,
            "total_agents": len(context.previous_results),
            "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        }
        
        self.emit_event(
            request_id=request.request_id,
            event_type=EventType.STATE_CHANGED,
            actor_type="agent",
            actor_id="reporting_agent",
            payload={
                "action": "pipeline_complete",
                "summary": summary,
            }
        )
    
    def _update_final_status(self, request: PartRequest, delivery: Dict[str, Any]):
        """Update final status based on delivery result"""
        
        if delivery.get("status") in ("queued", "sent", "available"):
            # Already SENT_TO_CLIENT from delivery agent
            pass
        elif request.status == "READY_FOR_APPROVAL":
            # Still waiting for approval
            pass
        else:
            # Default
            pass
    
    def _get_order(self, request_id: str) -> Optional[PartRequest]:
        """Get existing PartRequest"""
        return self.session.exec(
            select(PartRequest).where(
                PartRequest.request_id == request_id,
                PartRequest.tenant_id == self.tenant_id
            )
        ).first()


def create_reporting_agent(tenant_id: str = "default", config: Optional[Dict] = None) -> ReportingAgent:
    """Create a reporting agent instance"""
    return ReportingAgent(tenant_id=tenant_id, config=config)