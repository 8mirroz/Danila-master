"""
Processing Agent - Executes core matching/pricing and generates approval documents

This agent is responsible for:
1. Running the supplier matching and pricing pipeline
2. Checking margin policies and protective gates
3. Generating the approval document (invoice/quotation)
4. Storing the document for review
5. Passing to delivery agent
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from app.agents.base_agent import BaseAgent, AgentContext, AgentResult, AgentType
from models import PartRequest, EventType, RequestState, ApprovalTicket
from agents import process_intake_request
from policy_engine import policy_engine
from pricing import compute_price, check_margin_guard, PricingContext
from intelligence import get_90d_median_price, assess_return_risk
from matcher import match_part_from_db
from database import engine
from sqlmodel import Session as SyncSession
from services.workflow_transitions import advance_request_state

logger = logging.getLogger("agents.processing")


class ProcessingAgent(BaseAgent):
    """
    Processing Agent - Core order processing engine.
    
    Performs:
    - Supplier matching (scatter-gather)
    - Pricing calculation with margin guards
    - Protective gates evaluation
    - Approval document generation
    - Creates approval tickets if needed
    """
    
    def __init__(self, tenant_id: str = "default", config: Optional[Dict[str, Any]] = None):
        super().__init__(AgentType.PROCESSING, tenant_id, config)
        self.auto_advance_enabled = self.config.get("auto_advance", True)
    
    def execute(self, context: AgentContext) -> AgentResult:
        """Execute the core processing pipeline"""
        
        if not context.request_id:
            return AgentResult(
                success=False,
                agent_type=self.agent_type,
                errors=["No request_id in context"],
                next_agent=None
            )
        
        # Get the existing request
        request = self._get_order(context.request_id)
        if not request:
            return AgentResult(
                success=False,
                agent_type=self.agent_type,
                errors=[f"Request {context.request_id} not found"],
                next_agent=None
            )
        
        # Update status to processing
        self._update_status(request, RequestState.MATCHING)
        
        # Load parts data
        import json as json_lib
        parts_data = context.parts_data
        if not parts_data and request.parts_json:
            parts_data = json_lib.loads(request.parts_json)
            context.parts_data = parts_data
        
        if not parts_data:
            return AgentResult(
                success=False,
                agent_type=self.agent_type,
                errors=["No parts data to process"],
                next_agent=None
            )
        
        # Run the full pipeline
        result = self._run_processing_pipeline(request, parts_data, context)
        
        if not result["success"]:
            self._update_status(request, RequestState.FAILED)
            return AgentResult(
                success=False,
                agent_type=self.agent_type,
                errors=result["errors"],
                next_agent=None
            )
        
        # Generate approval document
        doc_result = self._generate_approval_document(request, result)
        
        # Check protective gates
        gates_result = self._check_protective_gates(request, result)
        
        # Every commercial quote is explicitly approved by a finance/admin
        # operator.  Automatic matching may make a request eligible for a fast
        # decision, but it must never skip the immutable quote snapshot and
        # send a preliminary document directly to the customer.
        self._update_status(request, RequestState.READY_FOR_APPROVAL)
        self._create_approval_ticket(request, gates_result)
        gates_result["auto_advance_allowed"] = False
        next_agent = AgentType.DELIVERY
        
        # Store processing results in context
        context.previous_results["processing"] = result
        context.previous_results["gates"] = gates_result
        context.previous_results["document"] = doc_result

        selected_offers = {
            str(part["name"]): {
                "item": part["best_match"],
                "supplier": part.get("supplier"),
            }
            for part in result.get("matched_parts", [])
            if part.get("name") and part.get("best_match")
        }
        # Update request with pricing evidence
        self._update_order(request.request_id, {
            "match_evidence_json": json_lib.dumps(selected_offers),
            "pricing_evidence_json": json_lib.dumps(result.get("pricing_evidence", {})),
            "margin_policy_passed": result.get("margin_policy_passed", False),
        })
        
        return AgentResult(
            success=True,
            agent_type=self.agent_type,
            data={
                "request_id": request.request_id,
                "matched_parts": len(result.get("matched_parts", [])),
                "pricing_evidence": result.get("pricing_evidence", {}),
                "margin_policy_passed": result.get("margin_policy_passed", False),
                "auto_advance": gates_result["auto_advance_allowed"],
                "document_id": doc_result.get("document_id"),
                "approval_required": not gates_result["auto_advance_allowed"],
            },
            next_agent=next_agent,
            correlation_id=context.correlation_id
        )
    
    def _run_processing_pipeline(
        self, 
        request: PartRequest, 
        parts_data: List[Dict[str, Any]], 
        context: AgentContext
    ) -> Dict[str, Any]:
        """Run the complete matching and pricing pipeline"""
        
        trace = []
        matched_parts = []
        has_valid_match = False
        
        # Vehicle context for matching
        vehicle_make = request.vehicle_make
        vehicle_model = request.vehicle_model
        
        with SyncSession(engine) as session:
            for part in parts_data:
                part_name = part.get("name", "")
                qty = part.get("quantity", 1)
                
                if part_name == "Неизвестная деталь" or not part_name:
                    matched_parts.append({
                        "name": part_name,
                        "quantity": qty,
                        "best_match": None,
                        "match_score": 0.0,
                        "breakdown": {},
                        "error": "Unknown part name"
                    })
                    trace.append(f"Processing: Skipped unknown part '{part_name}'")
                    continue
                
                # Find matching supplier offers
                matches = match_part_from_db(
                    part_name, session, threshold=50.0, limit=3,
                    vehicle_context=vehicle_make, tenant_id=request.tenant_id
                )
                
                if matches:
                    best_match = matches[0]["item"]
                    score = matches[0]["score"]
                    breakdown = matches[0].get("breakdown", {})
                    
                    matched_parts.append({
                        "name": part_name,
                        "quantity": qty,
                        "best_match": best_match,
                        "match_score": score,
                        "breakdown": breakdown,
                        "supplier": matches[0]["supplier"]
                    })
                    has_valid_match = True
                    trace.append(f"Processing: Matched '{part_name}' to '{best_match['name']}' ({score}%)")
                else:
                    matched_parts.append({
                        "name": part_name,
                        "quantity": qty,
                        "best_match": None,
                        "match_score": 0.0,
                        "breakdown": {},
                        "error": "No matches found"
                    })
                    trace.append(f"Processing: No matches found for '{part_name}'")
        
        if not has_valid_match:
            return {
                "success": False,
                "errors": ["No valid supplier matches found for any parts"],
                "matched_parts": matched_parts,
                "trace": trace,
            }
        
        # Pricing Guard - calculate prices and check margins
        trace.append("Processing: Running pricing guard")
        pricing_result = self._run_pricing_guard(request, matched_parts)
        
        trace.extend(pricing_result.get("trace", []))
        
        return {
            "success": True,
            "matched_parts": matched_parts,
            "pricing_evidence": pricing_result.get("pricing_evidence"),
            "margin_policy_passed": pricing_result.get("margin_policy_passed", False),
            "price_anomaly_detected": pricing_result.get("price_anomaly_detected", False),
            "violations": pricing_result.get("violations", []),
            "trace": trace,
        }
    
    def _run_pricing_guard(
        self, 
        request: PartRequest, 
        matched_parts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Run pricing calculations and margin checks"""
        
        trace = []
        line_items = []
        subtotal = 0.0
        margin_policy_passed = True
        price_anomaly_detected = False
        violations = []
        
        with SyncSession(engine) as session:
            for part in matched_parts:
                if not part.get("best_match"):
                    continue
                
                qty = part.get("quantity", 1)
                purchase_price = part["best_match"]["price"]
                reliability = part["supplier"]["reliability_score"] if part.get("supplier") else 0.90
                catalog_id = part["best_match"]["catalog_id"]
                
                # Assess warranty/return risk
                risk_info = assess_return_risk(
                    part["best_match"]["name"], 
                    part["best_match"].get("brand", "")
                )
                
                # Fetch 90d historical median
                median_price = get_90d_median_price(catalog_id, session)
                
                # Context-based pricing
                ctx = PricingContext(
                    purchase_price=purchase_price,
                    logistics_cost=500.0 / len([p for p in matched_parts if p.get("best_match")]),
                    supplier_reliability_score=reliability,
                    is_non_returnable=risk_info["is_non_returnable"],
                    is_original="BMW" in part["best_match"]["name"].upper(),
                    brand_group="original_bmw" if "BMW" in part["best_match"]["name"].upper() else "default",
                    historical_median_price_90d=median_price
                )
                
                pricing_res = compute_price(ctx)
                
                line_total = pricing_res.client_price * qty
                subtotal += line_total
                
                if not pricing_res.margin_policy_passed:
                    margin_policy_passed = False
                    violations.extend(pricing_res.violations)
                if pricing_res.price_anomaly_detected:
                    price_anomaly_detected = True
                
                line_items.append({
                    "part_name": part["best_match"]["name"],
                    "purchase_price": purchase_price,
                    "sale_price": pricing_res.client_price,
                    "quantity": qty,
                    "line_total": line_total,
                    "margin_rate": pricing_res.margin_rate,
                    "is_non_returnable": risk_info["is_non_returnable"],
                    "risk_level": risk_info["risk_level"],
                    "violations": pricing_res.violations
                })
                
                trace.append(f"Pricing: {part['best_match']['name']} - "
                           f"purchase={purchase_price:.2f}, sale={pricing_res.client_price:.2f}, "
                           f"margin={pricing_res.margin_rate:.1%}")
        
        pricing_evidence = {
            "line_items": line_items,
            "subtotal": round(subtotal, 2),
            "tax": round(subtotal * 0.20, 2),
            "total": round(subtotal * 1.20, 2),
            "violations": violations
        }
        
        trace.append(f"Pricing Guard: margin_passed={margin_policy_passed}, "
                    f"anomalies={price_anomaly_detected}, total={pricing_evidence['total']:.2f}")
        
        return {
            "pricing_evidence": pricing_evidence,
            "margin_policy_passed": margin_policy_passed,
            "price_anomaly_detected": price_anomaly_detected,
            "violations": violations,
            "trace": trace,
        }
    
    def _check_protective_gates(
        self, 
        request: PartRequest, 
        processing_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check all 7 protective gates"""
        
        trace = []
        trace.append("Processing: Evaluating protective gates")
        
        # Update the actual request with processing results before checking gates
        import json as json_lib
        request.parts_json = json_lib.dumps(processing_result.get("matched_parts", []))
        request.pricing_evidence_json = json_lib.dumps(processing_result.get("pricing_evidence", {}))
        self.session.add(request)
        self.session.commit()
        
        # Now check gates using the updated request
        with SyncSession(engine) as session:
            auto_advance = policy_engine.auto_advance_policy(request, session)
        
        gate_results = {
            "gate_1_parts_matched": any(p.get("best_match") for p in processing_result.get("matched_parts", [])),
            "gate_2_margin_policy": processing_result.get("margin_policy_passed", False),
            "gate_3_no_price_anomaly": not processing_result.get("price_anomaly_detected", False),
            "gate_4_vehicle_identified": bool(request.vehicle_make),
            "gate_5_customer_complete": bool(request.customer_name and request.customer_phone_masked),
            "gate_6_no_violations": len(processing_result.get("violations", [])) == 0,
            "gate_7_supplier_reliable": all(
                p.get("supplier", {}).get("reliability_score", 0) >= 0.7 
                for p in processing_result.get("matched_parts", []) if p.get("best_match")
            ),
        }
        
        all_gates_passed = all(gate_results.values())
        
        trace.append(f"Gates: {gate_results}")
        trace.append(f"Auto-advance allowed: {auto_advance} (all gates: {all_gates_passed})")
        
        return {
            "auto_advance_allowed": auto_advance and self.auto_advance_enabled,
            "all_gates_passed": all_gates_passed,
            "gate_results": gate_results,
            "trace": trace,
        }
    
    def _generate_approval_document(
        self, 
        request: PartRequest, 
        processing_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate approval document (invoice/quotation) and create Invoice record"""
        
        import json as json_lib
        
        document_id = f"doc_{uuid.uuid4().hex[:12]}"
        pricing = processing_result.get("pricing_evidence", {})
        line_items = pricing.get("line_items", [])
        
        # Create Invoice record in database
        from suppliers import Invoice
        
        invoice = Invoice(
            tenant_id=self.tenant_id,
            invoice_number=document_id,
            request_id=request.request_id,
            supplier_id=line_items[0].get("supplier_id", "SUP-001") if line_items else "SUP-001",
            customer_name=request.customer_name or "Unknown",
            items_json=json_lib.dumps(line_items),
            subtotal=pricing.get("subtotal", 0),
            tax=pricing.get("tax", 0),
            total=pricing.get("total", 0),
            status="DRAFT",
        )
        
        self.session.add(invoice)
        self.session.commit()
        self.session.refresh(invoice)
        
        document = {
            "document_id": document_id,
            "document_type": "approval_invoice",
            "request_id": request.request_id,
            "created_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
            "customer": {
                "name": request.customer_name,
                "phone": request.customer_phone_masked,
                "email": request.customer_email_masked,
            },
            "vehicle": {
                "vin": request.vehicle_vin_masked,
                "make": request.vehicle_make,
                "model": request.vehicle_model,
                "year": request.vehicle_year,
            },
            "line_items": line_items,
            "totals": {
                "subtotal": pricing.get("subtotal", 0),
                "tax": pricing.get("tax", 0),
                "total": pricing.get("total", 0),
            },
            "violations": pricing.get("violations", []),
            "status": "draft",
            "original_request_ref": request.raw_input_ref,
        }
        
        # Store document reference in request
        self._update_order(request.request_id, {
            "erp_quotation_ref": document_id,
            # The durable Invoice row above is the draft that delivery sends after
            # approval. Keep the request reference in sync before the state machine
            # advances through INVOICE_DRAFTED/SENT_TO_CLIENT.
            "erp_invoice_ref": document_id,
        })
        
        # Emit event
        self.emit_event(
            request_id=request.request_id,
            event_type=EventType.ERP_DOCUMENT_CREATED,
            actor_type="agent",
            actor_id="processing_agent",
            payload={
                "document_id": document_id,
                "document_type": "approval_invoice",
                "total": pricing.get("total", 0),
            }
        )
        
        return document
    
    def _create_approval_ticket(
        self, 
        request: PartRequest, 
        gates_result: Dict[str, Any]
    ) -> ApprovalTicket:
        """Create approval ticket for manual review"""
        
        import json as json_lib
        
        ticket = ApprovalTicket(
            tenant_id=self.tenant_id,
            ticket_id=f"appr_{uuid.uuid4().hex[:12]}",
            request_id=request.request_id,
            tool_name="processing_agent",
            reason=f"Protective gates check failed: {json_lib.dumps(gates_result['gate_results'])}",
            role_required="finance",
            requested_by="system",
            status="pending",
            payload_json=json_lib.dumps({
                "gate_results": gates_result["gate_results"],
                "all_gates_passed": gates_result["all_gates_passed"],
            })
        )
        
        self.session.add(ticket)
        self.session.commit()
        self.session.refresh(ticket)
        
        return ticket
    
    def _update_status(self, request: PartRequest, status: RequestState):
        """Advance through legal states and write an audit event for every step."""
        advance_request_state(
            self.session,
            request,
            status,
            actor_id="processing_agent",
            reason="Processing pipeline advanced request",
        )
    
    def _update_order(self, request_id: str, updates: Dict[str, Any]) -> Optional[PartRequest]:
        """Update order with new data"""
        from sqlmodel import select
        
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
        
        request.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.session.add(request)
        self.session.commit()
        self.session.refresh(request)
        
        return request
    
    def _get_order(self, request_id: str) -> Optional[PartRequest]:
        """Get existing PartRequest"""
        from sqlmodel import select
        return self.session.exec(
            select(PartRequest).where(
                PartRequest.request_id == request_id,
                PartRequest.tenant_id == self.tenant_id
            )
        ).first()


def create_processing_agent(tenant_id: str = "default", config: Optional[Dict] = None) -> ProcessingAgent:
    """Create a processing agent instance"""
    return ProcessingAgent(tenant_id=tenant_id, config=config)
