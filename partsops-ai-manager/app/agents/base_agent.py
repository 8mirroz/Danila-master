"""
Base Agent Class for PartsOps Multi-Agent System

All agents inherit from this base class to ensure consistent interface
and shared functionality.
"""

from __future__ import annotations

import uuid
import time
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from sqlmodel import Session, select

from database import engine
from models import PartRequest, RequestEvent, EventType, OutboundMessage
from event_store import emit_event
from pii import secure_pre_parse


logger = logging.getLogger("agents")


class AgentStatus(str, Enum):
    """Agent execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class AgentType(str, Enum):
    """Agent types in the system"""
    INTAKE = "intake"
    PROCESSING = "processing"
    DELIVERY = "delivery"
    REPORTING = "reporting"


@dataclass
class AgentContext:
    """Context passed between agents in the pipeline"""
    tenant_id: str = "default"
    request_id: Optional[str] = None
    order_id: Optional[str] = None
    source: str = "unknown"  # telegram, email, crm, web, manual, api
    raw_input: Optional[str] = None
    customer_data: Dict[str, Any] = field(default_factory=dict)
    vehicle_data: Dict[str, Any] = field(default_factory=dict)
    parts_data: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    original_request_ref: Optional[str] = None  # Reference to original request (TG msg, email, CRM ticket)
    priority: str = "normal"
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Pipeline state
    current_agent: Optional[str] = None
    previous_results: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


@dataclass
class AgentResult:
    """Result returned by an agent after execution"""
    success: bool
    agent_type: AgentType
    data: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    next_agent: Optional[AgentType] = None
    execution_time_ms: int = 0
    correlation_id: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "agent_type": self.agent_type.value,
            "data": self.data,
            "errors": self.errors,
            "warnings": self.warnings,
            "next_agent": self.next_agent.value if self.next_agent else None,
            "execution_time_ms": self.execution_time_ms,
            "correlation_id": self.correlation_id,
        }


class BaseAgent(ABC):
    """Base class for all agents in the PartsOps multi-agent system"""
    
    def __init__(
        self,
        agent_type: AgentType,
        tenant_id: str = "default",
        config: Optional[Dict[str, Any]] = None
    ):
        self.agent_type = agent_type
        self.tenant_id = tenant_id
        self.config = config or {}
        self.logger = logging.getLogger(f"agents.{agent_type.value}")
        self._session: Optional[Session] = None
    
    @property
    def session(self) -> Session:
        """Get or create database session"""
        if self._session is None:
            self._session = Session(engine)
        return self._session
    
    def close_session(self):
        """Close database session"""
        if self._session:
            self._session.close()
            self._session = None
    
    def emit_event(
        self,
        request_id: str,
        event_type: EventType,
        actor_type: str = "agent",
        actor_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        evidence_refs: Optional[List[str]] = None
    ):
        """Emit an event to the event store"""
        return emit_event(
            session=self.session,
            request_id=request_id,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id or self.agent_type.value,
            payload=payload,
            evidence_refs=evidence_refs,
            tenant_id=self.tenant_id
        )
    
    def mask_pii(self, text: str) -> Dict[str, Any]:
        """Apply PII masking to input text"""
        return secure_pre_parse(text)
    
    def create_outbound_message(
        self,
        channel: str,
        recipient: str,
        body_text: str,
        subject: Optional[str] = None,
        request_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None
    ) -> OutboundMessage:
        """Create an outbound message in the outbox"""
        import uuid as uuid_lib
        message = OutboundMessage(
            tenant_id=self.tenant_id,
            request_id=request_id,
            channel=channel,
            recipient=recipient,
            subject=subject,
            body_text=body_text,
            payload_json=str(payload) if payload else None,
            idempotency_key=f"{self.agent_type.value}_{uuid_lib.uuid4().hex[:16]}",
            status="pending",
            attempts=0,
        )
        self.session.add(message)
        self.session.commit()
        return message
    
    @abstractmethod
    def execute(self, context: AgentContext) -> AgentResult:
        """
        Execute the agent's main logic.
        
        Args:
            context: The agent context containing all pipeline data
            
        Returns:
            AgentResult with execution outcome and next agent to run
        """
        pass
    
    def run(self, context: AgentContext) -> AgentResult:
        """
        Run the agent with timing and error handling.
        
        Args:
            context: The agent context
            
        Returns:
            AgentResult
        """
        start_time = time.time()
        context.current_agent = self.agent_type.value
        
        self.logger.info(
            f"[{self.agent_type.value}] Starting execution for request_id={context.request_id}, "
            f"order_id={context.order_id}, correlation_id={context.correlation_id}"
        )
        
        try:
            result = self.execute(context)
            result.execution_time_ms = int((time.time() - start_time) * 1000)
            result.correlation_id = context.correlation_id
            
            if result.success:
                self.logger.info(
                    f"[{self.agent_type.value}] Completed successfully in {result.execution_time_ms}ms. "
                    f"Next agent: {result.next_agent.value if result.next_agent else 'none'}"
                )
            else:
                self.logger.error(
                    f"[{self.agent_type.value}] Failed after {result.execution_time_ms}ms. "
                    f"Errors: {result.errors}"
                )
            
            return result
            
        except Exception as e:
            self.logger.exception(f"[{self.agent_type.value}] Unexpected error")
            return AgentResult(
                success=False,
                agent_type=self.agent_type,
                errors=[f"Unexpected error: {str(e)}"],
                execution_time_ms=int((time.time() - start_time) * 1000),
                correlation_id=context.correlation_id,
            )
        finally:
            # Session will be closed by orchestrator
            pass
    
    def _create_order_record(self, context: AgentContext) -> PartRequest:
        """Create a PartRequest record from context"""
        import json
        request = PartRequest(
            tenant_id=context.tenant_id,
            request_id=context.request_id or f"req_{uuid.uuid4().hex[:12]}",
            source=context.source,
            status="NEW",
            priority=context.priority,
            customer_name=context.customer_data.get("name"),
            customer_phone_masked=context.customer_data.get("phone_masked"),
            customer_email_masked=context.customer_data.get("email_masked"),
            customer_erp_id=context.customer_data.get("erp_id"),
            vehicle_vin_masked=context.vehicle_data.get("vin_masked"),
            vehicle_make=context.vehicle_data.get("make"),
            vehicle_model=context.vehicle_data.get("model"),
            vehicle_generation=context.vehicle_data.get("generation"),
            vehicle_year=context.vehicle_data.get("year"),
            vehicle_engine=context.vehicle_data.get("engine"),
            vehicle_confidence=context.vehicle_data.get("confidence"),
            vin_validity=context.vehicle_data.get("vin_validity"),
            parts_json=json.dumps(context.parts_data) if context.parts_data else None,
            raw_input_ref=context.original_request_ref,
        )
        self.session.add(request)
        self.session.commit()
        self.session.refresh(request)
        
        # Emit event
        self.emit_event(
            request_id=request.request_id,
            event_type=EventType.REQUEST_RECEIVED,
            actor_type="agent",
            actor_id=self.agent_type.value,
            payload={"source": context.source, "original_ref": context.original_request_ref}
        )
        
        return request
    
    def _update_order(self, request_id: str, updates: Dict[str, Any]) -> Optional[PartRequest]:
        """Update an existing PartRequest"""
        request = self.session.exec(
            select(PartRequest).where(
                PartRequest.request_id == request_id,
                PartRequest.tenant_id == self.tenant_id
            )
        ).first()
        
        if not request:
            return None
        
        for key, value in updates.items():
            if hasattr(request, key):
                setattr(request, key, value)
        
        request.updated_at = datetime.utcnow()
        self.session.add(request)
        self.session.commit()
        self.session.refresh(request)
        
        return request
    
    def _get_order(self, request_id: str) -> Optional[PartRequest]:
        """Get an existing PartRequest"""
        return self.session.exec(
            select(PartRequest).where(
                PartRequest.request_id == request_id,
                PartRequest.tenant_id == self.tenant_id
            )
        ).first()