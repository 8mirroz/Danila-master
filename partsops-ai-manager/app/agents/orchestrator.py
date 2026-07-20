"""
Agent Orchestrator - Coordinates the multi-agent pipeline

This orchestrator manages the execution flow between agents:
Intake → Processing → Delivery → Reporting
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from app.agents.base_agent import BaseAgent, AgentContext, AgentResult, AgentType
from app.agents.intake_agent import IntakeAgent
from app.agents.processing_agent import ProcessingAgent
from app.agents.delivery_agent import DeliveryAgent
from app.agents.reporting_agent import ReportingAgent
from models import PartRequest
from sqlmodel import select
from database import engine
from sqlmodel import Session

logger = logging.getLogger("agents.orchestrator")


@dataclass
class PipelineResult:
    """Result of the complete pipeline execution"""
    success: bool
    request_id: Optional[str] = None
    order_id: Optional[str] = None
    phases: Dict[str, AgentResult] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    correlation_id: str = ""
    total_time_ms: int = 0


class AgentOrchestrator:
    """
    Orchestrates the multi-agent order processing pipeline.
    
    Flow:
    1. Intake Agent - Collects and structures order from source
    2. Processing Agent - Matches parts, calculates pricing, generates document
    3. Delivery Agent - Sends document to client via appropriate channel
    4. Reporting Agent - Notifies operators and client
    """
    
    def __init__(
        self,
        tenant_id: str = "default",
        config: Optional[Dict[str, Any]] = None
    ):
        self.tenant_id = tenant_id
        self.config = config or {}
        
        # Initialize agents
        self.intake_agent = IntakeAgent(tenant_id=tenant_id, config=self.config.get("intake", {}))
        self.processing_agent = ProcessingAgent(tenant_id=tenant_id, config=self.config.get("processing", {}))
        self.delivery_agent = DeliveryAgent(tenant_id=tenant_id, config=self.config.get("delivery", {}))
        self.reporting_agent = ReportingAgent(tenant_id=tenant_id, config=self.config.get("reporting", {}))
        
        # Agent execution order
        self.pipeline = [
            (AgentType.INTAKE, self.intake_agent),
            (AgentType.PROCESSING, self.processing_agent),
            (AgentType.DELIVERY, self.delivery_agent),
            (AgentType.REPORTING, self.reporting_agent),
        ]
    
    def run_pipeline(
        self,
        source: str,
        raw_input: str,
        customer_data: Optional[Dict[str, Any]] = None,
        vehicle_data: Optional[Dict[str, Any]] = None,
        parts_data: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        priority: str = "normal",
        request_id: Optional[str] = None,
    ) -> PipelineResult:
        """
        Run the complete multi-agent pipeline.
        
        Args:
            source: Source of the order (telegram, email, crm, web, manual, api)
            raw_input: Raw text input from the source
            customer_data: Customer information (name, phone, email, erp_id)
            vehicle_data: Vehicle information (vin, make, model, year, etc.)
            parts_data: Pre-extracted parts (if available)
            metadata: Source-specific metadata (message_id, chat_id, etc.)
            priority: Request priority (low, normal, urgent, vip)
            request_id: Existing request ID (for continuing pipeline)
            
        Returns:
            PipelineResult with execution outcome
        """
        
        import time
        start_time = time.time()
        
        # Create initial context
        context = AgentContext(
            tenant_id=self.tenant_id,
            request_id=request_id,
            source=source,
            raw_input=raw_input,
            customer_data=customer_data or {},
            vehicle_data=vehicle_data or {},
            parts_data=parts_data or [],
            metadata=metadata or {},
            priority=priority,
        )
        
        logger.info(
            f"Starting pipeline for source={source}, request_id={request_id}, "
            f"correlation_id={context.correlation_id}"
        )
        
        result = PipelineResult(
            success=False,
            correlation_id=context.correlation_id,
        )
        
        try:
            # Execute each agent in sequence
            for agent_type, agent in self.pipeline:
                logger.info(f"Executing {agent_type.value} agent")
                
                agent_result = agent.run(context)
                result.phases[agent_type.value] = agent_result
                
                if not agent_result.success:
                    result.errors.extend(agent_result.errors)
                    logger.error(f"{agent_type.value} agent failed: {agent_result.errors}")
                    break
                
                # Update context with results
                if agent_result.data:
                    context.previous_results[agent_type.value] = agent_result.data
                
                # Check for next agent
                if agent_result.next_agent is None:
                    logger.info(f"{agent_type.value} agent indicated end of pipeline")
                    break
                
                # Verify next agent matches expected
                next_agent_type = agent_result.next_agent
                expected_next = self._get_next_agent_type(agent_type)
                if next_agent_type != expected_next:
                    logger.warning(
                        f"Agent {agent_type.value} requested {next_agent_type.value}, "
                        f"but expected {expected_next.value}. Continuing with requested."
                    )
            
            # Check if all phases completed
            completed_phases = [k for k, v in result.phases.items() if v.success]
            result.success = len(completed_phases) == len(self.pipeline) or (
                # Allow early termination if delivery/reporting not needed
                len(completed_phases) >= 2 and all(p in completed_phases for p in ["intake", "processing"])
            )
            
            if result.success:
                result.request_id = context.request_id
                result.order_id = context.order_id
                logger.info(f"Pipeline completed successfully for {context.request_id}")
            else:
                logger.error(f"Pipeline failed for {context.request_id}: {result.errors}")
                
        except Exception as e:
            logger.exception("Unexpected error in pipeline")
            result.errors.append(f"Pipeline error: {str(e)}")
            result.success = False
        
        finally:
            # Close all agent sessions
            for _, agent in self.pipeline:
                agent.close_session()
            
            result.total_time_ms = int((time.time() - start_time) * 1000)
        
        return result
    
    def _get_next_agent_type(self, current: AgentType) -> AgentType:
        """Get the expected next agent type in the pipeline"""
        order = [AgentType.INTAKE, AgentType.PROCESSING, AgentType.DELIVERY, AgentType.REPORTING]
        try:
            idx = order.index(current)
            if idx + 1 < len(order):
                return order[idx + 1]
        except ValueError:
            pass
        return AgentType.REPORTING  # Default to end
    
    def continue_pipeline(
        self,
        request_id: str,
        start_from: AgentType = AgentType.PROCESSING,
    ) -> PipelineResult:
        """Continue pipeline from a specific agent (for retries)"""
        
        # Get existing request to rebuild context
        with Session(engine) as session:
            request = session.exec(
                select(PartRequest).where(
                    PartRequest.request_id == request_id,
                    PartRequest.tenant_id == self.tenant_id
                )
            ).first()
            
            if not request:
                return PipelineResult(
                    success=False,
                    errors=[f"Request {request_id} not found"],
                )
            
            # Rebuild context from request
            import json
            context = AgentContext(
                tenant_id=self.tenant_id,
                request_id=request.request_id,
                order_id=request.request_id,
                source=request.source,
                raw_input=None,  # Already processed
                customer_data={
                    "name": request.customer_name or "",
                    "phone_masked": request.customer_phone_masked or "",
                    "email_masked": request.customer_email_masked or "",
                    "erp_id": request.customer_erp_id or "",
                },
                vehicle_data={
                    "vin_masked": request.vehicle_vin_masked or "",
                    "make": request.vehicle_make or "",
                    "model": request.vehicle_model or "",
                    "generation": request.vehicle_generation or "",
                    "year": request.vehicle_year or 0,
                    "engine": request.vehicle_engine or "",
                    "confidence": request.vehicle_confidence or 0.0,
                    "vin_validity": request.vin_validity or "",
                },
                parts_data=json.loads(request.parts_json) if request.parts_json else [],
                metadata={"original_ref": request.raw_input_ref or ""},
                priority=request.priority,
            )
        
        # Run from specified agent
        import time
        start_time = time.time()
        
        result = PipelineResult(
            success=False,
            correlation_id=context.correlation_id,
        )
        
        # Find starting index
        start_idx = next(
            (i for i, (at, _) in enumerate(self.pipeline) if at == start_from),
            1  # Default to processing
        )
        
        try:
            for agent_type, agent in self.pipeline[start_idx:]:
                logger.info(f"Continuing pipeline with {agent_type.value} agent")
                
                agent_result = agent.run(context)
                result.phases[agent_type.value] = agent_result
                
                if not agent_result.success:
                    result.errors.extend(agent_result.errors)
                    break
                
                if agent_result.data:
                    context.previous_results[agent_type.value] = agent_result.data
                
                if agent_result.next_agent is None:
                    break
            
            result.success = all(v.success for v in result.phases.values())
            result.request_id = context.request_id
            result.order_id = context.order_id
            
        except Exception as e:
            logger.exception("Error continuing pipeline")
            result.errors.append(f"Pipeline error: {str(e)}")
        
        finally:
            for _, agent in self.pipeline:
                agent.close_session()
            
            result.total_time_ms = int((time.time() - start_time) * 1000)
        
        return result


# Convenience function
def create_orchestrator(tenant_id: str = "default", config: Optional[Dict] = None) -> AgentOrchestrator:
    """Create an agent orchestrator instance"""
    return AgentOrchestrator(tenant_id=tenant_id, config=config)