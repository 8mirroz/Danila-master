"""
Intake Agent - Collects and structures orders from multiple sources (Telegram, CRM, Email)

This agent is responsible for:
1. Receiving raw input from multiple channels (TG, CRM, Email, Web, API)
2. Extracting and structuring order data
3. Storing original request reference for traceability
4. Creating the initial PartRequest record
5. Passing structured context to the processing agent
"""

from __future__ import annotations

import re
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from dataclasses import dataclass, field

from app.agents.base_agent import BaseAgent, AgentContext, AgentResult, AgentType, AgentStatus
from models import PartRequest, EventType
from pii import secure_pre_parse
from event_store import emit_event

logger = logging.getLogger("agents.intake")


@dataclass
class SourceInput:
    """Standardized input from any source"""
    source: str  # telegram, email, crm, web, manual, api
    raw_text: str
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    customer_erp_id: Optional[str] = None
    source_metadata: Dict[str, Any] = field(default_factory=dict)  # Original message ID, thread ID, etc.
    attachments: List[str] = field(default_factory=list)  # File references
    priority: str = "normal"
    
    def __post_init__(self):
        if self.source_metadata is None:
            self.source_metadata = {}
        if self.attachments is None:
            self.attachments = []


class IntakeAgent(BaseAgent):
    """
    Intake Agent - Entry point for all orders.
    
    Handles multiple input channels:
    - Telegram Bot messages (text, photos, documents)
    - Email (parsed from inbox)
    - CRM (webhook or API integration)
    - Web forms
    - Manual entry
    - API calls
    """
    
    def __init__(self, tenant_id: str = "default", config: Optional[Dict[str, Any]] = None):
        super().__init__(AgentType.INTAKE, tenant_id, config)
        self.supported_sources = self.config.get("supported_sources", [
            "telegram", "email", "crm", "web", "manual", "api"
        ])
    
    def execute(self, context: AgentContext) -> AgentResult:
        """Process incoming order from any source"""
        
        # If context already has structured data, just validate and pass through
        if context.raw_input is None and context.parts_data:
            return self._validate_and_forward(context)
        
        # Otherwise, parse the raw input
        source_input = self._parse_raw_input(context)
        if not source_input:
            return AgentResult(
                success=False,
                agent_type=self.agent_type,
                errors=["Failed to parse input"],
                next_agent=None
            )
        
        # Apply PII masking
        pii_result = self.mask_pii(source_input.raw_text)
        masked_text = pii_result.get("masked_text", source_input.raw_text)
        vehicle_context = pii_result.get("vehicle_context", {})
        
        # Extract structured data via single public intake facade
        from app.agents.intake_facade import parse_intake_text
        intake_result = parse_intake_text(
            masked_text,
            priority=source_input.priority,
            vehicle_context=vehicle_context,
            tenant_id=context.tenant_id,
        )
        
        # Create PartRequest record with original reference
        request = self._create_order_record(context, source_input, intake_result)
        
        # Update context with structured data
        context.request_id = request.request_id
        context.order_id = request.request_id  # Same for now
        context.source = source_input.source
        context.raw_input = source_input.raw_text
        context.original_request_ref = self._build_original_ref(source_input)
        context.customer_data = {
            "name": source_input.customer_name,
            "phone_masked": pii_result.get("phone_masked"),
            "email_masked": pii_result.get("email_masked"),
            "erp_id": source_input.customer_erp_id,
        }
        context.vehicle_data = {
            "vin_masked": intake_result.get("vehicle_vin"),
            "make": intake_result.get("vehicle_make"),
            "model": intake_result.get("vehicle_model"),
            "generation": intake_result.get("vehicle_generation"),
            "year": intake_result.get("vehicle_year"),
            "engine": intake_result.get("vehicle_engine"),
            "confidence": intake_result.get("vehicle_confidence"),
            "vin_validity": intake_result.get("vin_validity"),
        }
        context.parts_data = intake_result.get("extracted_parts", [])
        context.priority = source_input.priority
        context.metadata = {
            "source_metadata": source_input.source_metadata,
            "attachments": source_input.attachments,
            "intake_trace": intake_result.get("agent_trace", []),
            "validation_status": intake_result.get("validation_status"),
            "is_spam": intake_result.get("is_spam", False),
        }
        
        # Emit event with original reference
        self.emit_event(
            request_id=request.request_id,
            event_type=EventType.REQUEST_RECEIVED,
            actor_type="agent",
            actor_id="intake_agent",
            payload={
                "source": source_input.source,
                "original_ref": context.original_request_ref,
                "customer": context.customer_data,
                "vehicle": context.vehicle_data,
                "parts_count": len(context.parts_data),
            },
            evidence_refs=[context.original_request_ref] if context.original_request_ref else None
        )
        
        return AgentResult(
            success=True,
            agent_type=self.agent_type,
            data={
                "request_id": request.request_id,
                "order_id": request.request_id,
                "parts_count": len(context.parts_data),
                "vehicle_identified": bool(context.vehicle_data.get("make")),
            },
            next_agent=AgentType.PROCESSING,
            correlation_id=context.correlation_id
        )
    
    def _parse_raw_input(self, context: AgentContext) -> Optional[SourceInput]:
        """Parse raw input based on source type"""
        
        source = context.source or "manual"
        raw_text = context.raw_input or ""
        
        if not raw_text and not context.customer_data:
            self.logger.warning(f"No raw input or customer data for source: {source}")
            return None
        
        # Build SourceInput based on source type
        if source == "telegram":
            return self._parse_telegram(context)
        elif source == "email":
            return self._parse_email(context)
        elif source == "crm":
            return self._parse_crm(context)
        elif source == "web":
            return self._parse_web(context)
        elif source == "api":
            return self._parse_api(context)
        else:
            # Manual/fallback
            return SourceInput(
                source=source,
                raw_text=raw_text,
                customer_name=context.customer_data.get("name"),
                customer_phone=context.customer_data.get("phone"),
                customer_email=context.customer_data.get("email"),
                customer_erp_id=context.customer_data.get("erp_id"),
                source_metadata=context.metadata.get("source_metadata", {}),
                attachments=context.metadata.get("attachments", []),
                priority=context.priority,
            )
    
    def _parse_telegram(self, context: AgentContext) -> SourceInput:
        """Parse Telegram message input"""
        meta = context.metadata.get("source_metadata", {})
        
        # Extract text from message or caption
        raw_text = context.raw_input or ""
        if not raw_text and "caption" in meta:
            raw_text = meta["caption"]
        
        # Use customer data from context if available
        customer_data = context.customer_data or {}
        
        return SourceInput(
            source="telegram",
            raw_text=raw_text,
            customer_name=meta.get("user_name") or meta.get("first_name") or customer_data.get("name"),
            customer_phone=customer_data.get("phone"),
            customer_email=customer_data.get("email"),
            customer_erp_id=customer_data.get("erp_id"),
            source_metadata={
                "message_id": meta.get("message_id"),
                "chat_id": meta.get("chat_id"),
                "user_id": meta.get("user_id"),
                "username": meta.get("username"),
                "date": meta.get("date"),
                "has_photo": meta.get("has_photo", False),
                "has_document": meta.get("has_document", False),
            },
            attachments=context.metadata.get("attachments", []),
            priority=context.priority,
        )
    
    def _parse_email(self, context: AgentContext) -> SourceInput:
        """Parse email input"""
        meta = context.metadata.get("source_metadata", {})
        
        # Email body as raw text
        raw_text = context.raw_input or meta.get("body_text", "") or meta.get("body_html", "")
        
        return SourceInput(
            source="email",
            raw_text=raw_text,
            customer_name=meta.get("from_name"),
            customer_phone=None,
            customer_email=meta.get("from_email"),
            customer_erp_id=None,
            source_metadata={
                "message_id": meta.get("message_id"),
                "subject": meta.get("subject"),
                "from_email": meta.get("from_email"),
                "to_email": meta.get("to_email"),
                "date": meta.get("date"),
                "thread_id": meta.get("thread_id"),
                "has_attachments": meta.get("has_attachments", False),
            },
            attachments=context.metadata.get("attachments", []),
            priority=context.priority,
        )
    
    def _parse_crm(self, context: AgentContext) -> SourceInput:
        """Parse CRM webhook/input"""
        meta = context.metadata.get("source_metadata", {})
        
        return SourceInput(
            source="crm",
            raw_text=context.raw_input or meta.get("description", "") or meta.get("notes", ""),
            customer_name=meta.get("customer_name") or context.customer_data.get("name"),
            customer_phone=meta.get("customer_phone") or context.customer_data.get("phone"),
            customer_email=meta.get("customer_email") or context.customer_data.get("email"),
            customer_erp_id=meta.get("customer_erp_id") or context.customer_data.get("erp_id"),
            source_metadata={
                "ticket_id": meta.get("ticket_id"),
                "deal_id": meta.get("deal_id"),
                "contact_id": meta.get("contact_id"),
                "company_id": meta.get("company_id"),
                "pipeline_stage": meta.get("pipeline_stage"),
                "assigned_to": meta.get("assigned_to"),
                "created_at": meta.get("created_at"),
                "custom_fields": meta.get("custom_fields", {}),
            },
            attachments=context.metadata.get("attachments", []),
            priority=meta.get("priority", context.priority),
        )
    
    def _parse_web(self, context: AgentContext) -> SourceInput:
        """Parse web form input"""
        meta = context.metadata.get("source_metadata", {})
        
        return SourceInput(
            source="web",
            raw_text=context.raw_input or meta.get("message", ""),
            customer_name=meta.get("name") or context.customer_data.get("name"),
            customer_phone=meta.get("phone") or context.customer_data.get("phone"),
            customer_email=meta.get("email") or context.customer_data.get("email"),
            customer_erp_id=None,
            source_metadata={
                "form_id": meta.get("form_id"),
                "page_url": meta.get("page_url"),
                "user_agent": meta.get("user_agent"),
                "ip_hash": meta.get("ip_hash"),
                "submitted_at": meta.get("submitted_at"),
                "recaptcha_score": meta.get("recaptcha_score"),
            },
            attachments=context.metadata.get("attachments", []),
            priority=context.priority,
        )
    
    def _parse_api(self, context: AgentContext) -> SourceInput:
        """Parse direct API input"""
        meta = context.metadata.get("source_metadata", {})
        
        return SourceInput(
            source="api",
            raw_text=context.raw_input or meta.get("description", ""),
            customer_name=meta.get("customer_name") or context.customer_data.get("name"),
            customer_phone=meta.get("customer_phone") or context.customer_data.get("phone"),
            customer_email=meta.get("customer_email") or context.customer_data.get("email"),
            customer_erp_id=meta.get("customer_erp_id") or context.customer_data.get("erp_id"),
            source_metadata={
                "api_key_id": meta.get("api_key_id"),
                "endpoint": meta.get("endpoint"),
                "request_id": meta.get("request_id"),
                "idempotency_key": meta.get("idempotency_key"),
            },
            attachments=context.metadata.get("attachments", []),
            priority=meta.get("priority", context.priority),
        )
    
    def _create_order_record(
        self, 
        context: AgentContext, 
        source_input: SourceInput, 
        intake_result: Dict[str, Any]
    ) -> PartRequest:
        """Create PartRequest record in database"""
        
        import json
        import uuid
        
        request_id = context.request_id or f"req_{uuid.uuid4().hex[:12]}"
        
        request = PartRequest(
            tenant_id=self.tenant_id,
            request_id=request_id,
            source=source_input.source,
            status="NEW",
            priority=source_input.priority,
            customer_name=source_input.customer_name,
            customer_phone_masked=source_input.customer_phone,
            customer_email_masked=source_input.customer_email,
            customer_erp_id=source_input.customer_erp_id,
            vehicle_vin_masked=intake_result.get("vehicle_vin"),
            vehicle_make=intake_result.get("vehicle_make"),
            vehicle_model=intake_result.get("vehicle_model"),
            vehicle_generation=intake_result.get("vehicle_generation"),
            vehicle_year=intake_result.get("vehicle_year"),
            vehicle_engine=intake_result.get("vehicle_engine"),
            vehicle_confidence=intake_result.get("vehicle_confidence"),
            vin_validity=intake_result.get("vin_validity"),
            parts_json=json.dumps(intake_result.get("extracted_parts", [])),
            raw_input_ref=self._build_original_ref(source_input),
        )
        
        self.session.add(request)
        self.session.commit()
        self.session.refresh(request)
        
        return request
    
    def _build_original_ref(self, source_input: SourceInput) -> str:
        """Build a reference string to the original request for traceability"""
        meta = source_input.source_metadata
        
        if source_input.source == "telegram":
            return f"tg:msg:{meta.get('chat_id')}:{meta.get('message_id')}"
        elif source_input.source == "email":
            return f"email:{meta.get('message_id')}"
        elif source_input.source == "crm":
            ticket = meta.get("ticket_id") or meta.get("deal_id")
            return f"crm:{ticket}" if ticket else f"crm:contact:{meta.get('contact_id')}"
        elif source_input.source == "web":
            return f"web:form:{meta.get('form_id')}:{meta.get('submitted_at')}"
        elif source_input.source == "api":
            return f"api:req:{meta.get('request_id')}"
        else:
            return f"manual:{datetime.now(timezone.utc).replace(tzinfo=None).isoformat()}"
    
    def _validate_and_forward(self, context: AgentContext) -> AgentResult:
        """Validate existing context and forward to processing"""
        if not context.request_id:
            return AgentResult(
                success=False,
                agent_type=self.agent_type,
                errors=["No request_id in context"],
                next_agent=None
            )
        
        # Verify request exists
        request = self._get_order(context.request_id)
        if not request:
            return AgentResult(
                success=False,
                agent_type=self.agent_type,
                errors=[f"Request {context.request_id} not found"],
                next_agent=None
            )
        
        # Load parts data from request
        import json
        if request.parts_json:
            context.parts_data = json.loads(request.parts_json)
        
        context.order_id = request.request_id
        
        return AgentResult(
            success=True,
            agent_type=self.agent_type,
            data={"request_id": request.request_id, "validated": True},
            next_agent=AgentType.PROCESSING,
            correlation_id=context.correlation_id
        )
    
    def _get_order(self, request_id: str) -> Optional[PartRequest]:
        """Get existing PartRequest"""
        from sqlmodel import select
        return self.session.exec(
            select(PartRequest).where(
                PartRequest.request_id == request_id,
                PartRequest.tenant_id == self.tenant_id
            )
        ).first()


# Convenience function for direct usage
def create_intake_agent(tenant_id: str = "default", config: Optional[Dict] = None) -> IntakeAgent:
    """Create an intake agent instance"""
    return IntakeAgent(tenant_id=tenant_id, config=config)
