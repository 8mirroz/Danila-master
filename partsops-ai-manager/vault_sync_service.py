"""
Background vault sync service for PartsOps.
Can run as a standalone process or be integrated into FastAPI as a background task.
"""

import os
import logging
import asyncio
import json
from datetime import datetime

logger = logging.getLogger(__name__)
from typing import Dict, Any
from pathlib import Path

# Add project to path
import sys
sys.path.insert(0, "/Users/user/projects/Danila master/partsops-ai-manager")

from vault_sync import sync_pipeline_run, sync_agent_config, sync_session_summary, get_vault_status
from database import engine
from models import LLMUsageLog
from sqlmodel import Session, select, desc


class VaultSyncService:
    """Service to automatically sync pipeline runs and configs to Obsidian vault."""
    
    def __init__(self, tenant_id: str = "default", poll_interval: int = 30):
        self.tenant_id = tenant_id
        self.poll_interval = poll_interval
        self.running = False
        self.seen_correlations: set[str] = set()
        self.last_sync_time = datetime.now()
        
    def sync_new_pipeline_runs(self) -> int:
        """Check for new pipeline runs and sync them to vault."""
        synced = 0
        
        with Session(engine) as session:
            # Get all LLM usage logs for this tenant, ordered by creation time
            logs = session.exec(
                select(LLMUsageLog)
                .where(LLMUsageLog.tenant_id == self.tenant_id)
                .order_by(desc(LLMUsageLog.created_at))
                .limit(100)
            ).all()
            
            # Group by correlation_id
            by_correlation: Dict[str, list] = {}
            for log in logs:
                if log.correlation_id:
                    if log.correlation_id not in by_correlation:
                        by_correlation[log.correlation_id] = []
                    by_correlation[log.correlation_id].append(log)
            
            # Process each correlation
            for corr_id, corr_logs in by_correlation.items():
                # Create a unique key for this run state
                latest_log = corr_logs[0]
                run_key = f"{corr_id}:{latest_log.status}:{latest_log.id}"
                
                if run_key in self.seen_correlations:
                    continue
                    
                # Build phase data
                phases = {}
                for log in corr_logs:
                    key = log.provider
                    phases[key] = {
                        "agent_type": log.provider,
                        "provider": log.provider,
                        "model": log.model,
                        "success": (log.status or "").lower() == "success",
                        "latency_ms": log.latency_ms,
                        "total_tokens": log.total_tokens,
                        "cost_usd": log.cost_usd,
                        "errors": [] if (log.status or "").lower() == "success" else [log.status or "unknown"],
                    }
                
                # Determine overall status
                all_success = all(p["success"] for p in phases.values())
                run_status = "completed" if all_success else "in_progress"
                
                # Only sync completed or failed runs
                if run_status in ("completed", "failed"):
                    run_data = {
                        "correlation_id": corr_id,
                        "status": run_status,
                        "phases": phases,
                        "synced_at": datetime.now().isoformat(),
                    }
                    
                    try:
                        result = sync_pipeline_run(corr_id, run_data)
                        logger.info("Synced pipeline %s -> %s", corr_id[:16], result)
                        synced += 1
                        self.seen_correlations.add(run_key)
                    except Exception as e:
                        logger.error("Failed to sync %s: %s", corr_id, e)
        
        return synced
    
    def sync_agent_os_config(self, config: Dict[str, Any]) -> str:
        """Sync AgentOSPanel configuration."""
        return sync_agent_config("agent-os-panel", config)
    
    def sync_session(self, session_data: Dict[str, Any]) -> str:
        """Sync a general session summary."""
        return sync_session_summary(session_data)
    
    async def run_forever(self):
        """Run the sync service indefinitely."""
        self.running = True
        logger.info("Starting service for tenant %s, polling every %ds", self.tenant_id, self.poll_interval)
        
        # Initial status check
        status = get_vault_status()
        logger.debug("Vault status: %s", json.dumps(status, indent=2))
        
        while self.running:
            try:
                count = self.sync_new_pipeline_runs()
                if count > 0:
                    logger.info("Synced %d new pipeline runs", count)
                    
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in sync loop: %s", e)
                await asyncio.sleep(self.poll_interval)
        
        logger.info("Service stopped")
    
    def stop(self):
        self.running = False


async def main():
    """Entry point for running as a standalone service."""
    service = VaultSyncService(tenant_id="default", poll_interval=30)
    
    try:
        await service.run_forever()
    except KeyboardInterrupt:
        service.stop()
        logger.info("Shutdown requested")


if __name__ == "__main__":
    asyncio.run(main())