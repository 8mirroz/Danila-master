"""
PartsOps AI Manager - Multi-Agent Order Processing System

This package contains the multi-agent system for order processing:
- IntakeAgent: Collects orders from Telegram, CRM, Email
- ProcessingAgent: Executes core matching/pricing and generates approval documents
- DeliveryAgent: Handles invoice download and client delivery via TG/Email
- ReportingAgent: Reports all phases results to Telegram bot
"""

from app.agents.base_agent import BaseAgent, AgentContext, AgentResult, AgentType, AgentStatus
from app.agents.intake_agent import IntakeAgent, create_intake_agent
from app.agents.intake_facade import parse_intake_text, process_intake_request
from app.agents.processing_agent import ProcessingAgent, create_processing_agent
from app.agents.delivery_agent import DeliveryAgent, create_delivery_agent
from app.agents.reporting_agent import ReportingAgent, create_reporting_agent
from app.agents.orchestrator import AgentOrchestrator, PipelineResult, create_orchestrator

__all__ = [
    "BaseAgent",
    "AgentContext",
    "AgentResult",
    "AgentType",
    "AgentStatus",
    "IntakeAgent",
    "create_intake_agent",
    "parse_intake_text",
    "process_intake_request",
    "ProcessingAgent",
    "create_processing_agent",
    "DeliveryAgent",
    "create_delivery_agent",
    "ReportingAgent",
    "create_reporting_agent",
    "AgentOrchestrator",
    "PipelineResult",
    "create_orchestrator",
]