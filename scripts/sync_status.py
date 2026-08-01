import re
import sys
from datetime import datetime, timezone
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent


def sync_status(root: Path = REPOSITORY_ROOT) -> int:
    """Synchronize the Obsidian status files for the checked-out repository."""
    manifest_path = root / "partsops_agent_os_devpack/00_SYSTEM/SYSTEM_MANIFEST.yaml"
    overview_path = root / "DM obs/00-overview.md"
    log_path = root / "DM obs/obsidian_sync.log"
    
    # 1. Get Current Stage
    stage = "discovery"
    try:
        with manifest_path.open('r', encoding='utf-8') as f:
            content = f.read()
            match = re.search(r'current_stage:\s*(\S+)', content)
            if match:
                stage = match.group(1).strip()
    except OSError as error:
        print(f"Error reading manifest: {error}", file=sys.stderr)
        return 1

    # 2. Current Time
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 3. Update Overview File
    try:
        with overview_path.open('r', encoding='utf-8') as f:
            lines = f.readlines()

        # Update Last Sync
        sync_found = False
        for i, line in enumerate(lines):
            if "- Last Sync:" in line:
                lines[i] = f"- Last Sync: `{now}`\n"
                sync_found = True
                break
        
        if not sync_found:
            # Try to insert after Current Stage
            for i, line in enumerate(lines):
                if "- Current Stage:" in line:
                    lines.insert(i + 1, f"- Last Sync: `{now}`\n")
                    break

        # Update Current Stage
        for i, line in enumerate(lines):
            if "- Current Stage:" in line:
                lines[i] = f"- Current Stage: `{stage}`\n"
                break

        with overview_path.open('w', encoding='utf-8') as f:
            f.writelines(lines)
            
    except OSError as error:
        print(f"Error updating overview: {error}", file=sys.stderr)
        return 1

    # 4. Log the sync
    try:
        with log_path.open('a', encoding='utf-8') as f:
            f.write(f"[{now}] Sync: set current_stage={stage}\n")
    except OSError as error:
        print(f"Error writing log: {error}", file=sys.stderr)
        return 1

    print(f"Sync completed. Current stage: {stage}, timestamp: {now}")
    return 0

if __name__ == "__main__":
    raise SystemExit(sync_status())
