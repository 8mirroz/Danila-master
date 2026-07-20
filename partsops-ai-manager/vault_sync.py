"""
Vault sync service for PartsOps - persists agent sessions and pipeline runs to Obsidian vault.
Uses the existing obsidian_sync_bridge.py approach for consistency.
"""

import os
import subprocess
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

VAULT_PATH = Path(os.environ.get("OBSIDIAN_VAULT_PATH", os.path.expanduser("~/antigravity-vault")))
SESSIONS_DIR = VAULT_PATH / "04_Sessions" / "Zera"
SYNC_SCRIPT = Path("/Users/user/.hermes/profiles/zera/skills/zera/zera-vault-bridge/scripts/obsidian_sync_bridge.py")


def ensure_dirs():
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def create_session_note(session_id: str, content: str, tags: Optional[List[str]] = None) -> str:
    """Create a session note in the vault using the bridge script."""
    ensure_dirs()
    
    if not SYNC_SCRIPT.exists():
        raise FileNotFoundError(f"Bridge script not found at {SYNC_SCRIPT}")
    
    # Prepare tags
    tag_list = ["zera", "partsops", "vault-sync"]
    if tags:
        tag_list.extend(tags)
    
    # Call the bridge script
    cmd = [
        "python3",
        str(SYNC_SCRIPT),
        session_id,
        content
    ]
    
    env = os.environ.copy()
    env["OBSIDIAN_VAULT_PATH"] = str(VAULT_PATH)
    
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    
    if result.returncode != 0:
        raise RuntimeError(f"Vault sync failed: {result.stderr}")
    
    # Extract the file path from output
    output = result.stdout.strip()
    if "SUCCESS: Session synced to " in output:
        return output.replace("SUCCESS: Session synced to ", "")
    
    return "unknown"


def sync_pipeline_run(correlation_id: str, run_data: Dict[str, Any]) -> str:
    """Sync a pipeline run to the vault."""
    session_id = f"pipeline-{correlation_id[:16]}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    content = f"""# Pipeline Run: {correlation_id}

## Overview
- **Correlation ID**: {correlation_id}
- **Status**: {run_data.get('status', 'unknown')}
- **Timestamp**: {datetime.now().isoformat()}
- **Total Phases**: {len(run_data.get('phases', {}))}

## Phase Details
"""
    
    for phase_key, phase in run_data.get('phases', {}).items():
        content += f"""
### {phase.get('agent_type', phase_key)}
- **Provider**: {phase.get('provider', 'N/A')}
- **Model**: {phase.get('model', 'N/A')}
- **Status**: {'✅ Success' if phase.get('success') else '❌ Failed'}
- **Latency**: {phase.get('latency_ms', 0)}ms
- **Tokens**: {phase.get('total_tokens', 0)}
- **Cost**: ${phase.get('cost_usd', 0):.6f}
"""
        if phase.get('errors'):
            content += f"- **Errors**: {', '.join(phase['errors'])}\n"
    
    content += f"""

## Raw Data
```json
{json.dumps(run_data, indent=2, default=str)}
```

## Tags
#zera #partsops #pipeline-run #vault-sync
"""
    
    return create_session_note(session_id, content, tags=["pipeline-run", "partsops"])


def sync_agent_config(config_name: str, config_data: Dict[str, Any]) -> str:
    """Sync AgentOSPanel configuration to the vault."""
    session_id = f"config-{config_name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    content = f"""# Agent OS Configuration: {config_name}

## Configuration Snapshot
- **Timestamp**: {datetime.now().isoformat()}
- **Config Name**: {config_name}

## Settings
```json
{json.dumps(config_data, indent=2, default=str)}
```

## Tags
#zera #partsops #agent-config #vault-sync
"""
    
    return create_session_note(session_id, content, tags=["agent-config", "partsops"])


def sync_session_summary(summary: Dict[str, Any]) -> str:
    """Sync a general session summary to the vault."""
    session_id = f"session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    content = f"""# Session Summary

## Overview
- **Timestamp**: {datetime.now().isoformat()}
- **Session Type**: {summary.get('type', 'general')}

## Data
```json
{json.dumps(summary, indent=2, default=str)}
```

## Tags
#zera #partsops #session-summary #vault-sync
"""
    
    return create_session_note(session_id, content, tags=["session-summary", "partsops"])


def get_vault_status() -> Dict[str, Any]:
    """Check vault connectivity and status."""
    try:
        ensure_dirs()
        return {
            "vault_path": str(VAULT_PATH),
            "vault_exists": VAULT_PATH.exists(),
            "sessions_dir": str(SESSIONS_DIR),
            "sessions_dir_exists": SESSIONS_DIR.exists(),
            "bridge_script": str(SYNC_SCRIPT),
            "bridge_script_exists": SYNC_SCRIPT.exists(),
            "session_count": len(list(SESSIONS_DIR.glob("*.md"))) if SESSIONS_DIR.exists() else 0,
        }
    except Exception as e:
        return {
            "error": str(e),
            "vault_path": str(VAULT_PATH),
        }


if __name__ == "__main__":
    # Test the vault sync
    status = get_vault_status()
    print("Vault Status:", json.dumps(status, indent=2))
    
    if status.get("vault_exists") and status.get("bridge_script_exists"):
        test_result = sync_session_summary({
            "type": "test",
            "message": "Vault sync service test",
            "data": {"test": True}
        })
        print(f"Test sync result: {test_result}")