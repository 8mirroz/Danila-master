import os
import re
from datetime import datetime, timezone

def sync_status():
    # Configuration
    root = "/Users/user/projects/Danila master"
    manifest_path = os.path.join(root, "partsops_agent_os_devpack/00_SYSTEM/SYSTEM_MANIFEST.yaml")
    overview_path = os.path.join(root, "DM obs/00-overview.md")
    log_path = os.path.join(root, "DM obs/obsidian_sync.log")
    
    # 1. Get Current Stage
    stage = "discovery"
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
            match = re.search(r'current_stage:\s*(\S+)', content)
            if match:
                stage = match.group(1).strip()
    except Exception as e:
        print(f"Error reading manifest: {e}")

    # 2. Current Time
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 3. Update Overview File
    try:
        with open(overview_path, 'r', encoding='utf-8') as f:
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

        with open(overview_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
            
    except Exception as e:
        print(f"Error updating overview: {e}")
        return

    # 4. Log the sync
    try:
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"[{now}] Sync: set current_stage={stage}\n")
    except Exception as e:
        print(f"Error writing log: {e}")

    print(f"Sync completed. Current stage: {stage}, timestamp: {now}")

if __name__ == "__main__":
    sync_status()
