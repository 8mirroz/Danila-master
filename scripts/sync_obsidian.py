#!/usr/bin/env python3
import sys
import argparse
from pathlib import Path

# Add antigravity-core scripts/obsidian to sys.path
sys.path.append("/Users/user/antigravity-core/scripts/obsidian")
try:
    from obsidian_project import ProjectContext, ensure_structure, sync_project, load_obsidian_config
except ImportError as e:
    print(f"Error importing obsidian_project: {e}")
    print("Please make sure you run this script using the virtualenv python: /Users/user/zera/.venv/bin/python3")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VAULT_PATH = PROJECT_ROOT / "DM obs"

def main():
    parser = argparse.ArgumentParser(description="Sync Danila Master project artifacts with Obsidian Vault.")
    parser.add_argument("--stage", default="discovery")
    parser.add_argument("--status", default="in-progress")
    parser.add_argument("--plan-file")
    parser.add_argument("--report-file")
    parser.add_argument("--research-note")
    parser.add_argument("--decision-note")
    parser.add_argument("--handoff-note")
    parser.add_argument("--agent-role", choices=["orchestrator", "engineer", "reviewer", "council"])
    args = parser.parse_args()

    # Empty slug means write directly to DM obs root
    context = ProjectContext(
        vault_path=VAULT_PATH,
        project_slug="",
        project_title="Danila Master",
        project_root=str(PROJECT_ROOT),
        status=args.status,
        stage=args.stage,
        project_root_rel=""
    )

    # Automatically find plan/report files if not provided
    plan_file = args.plan_file
    if not plan_file:
        for p in ["task.md", "implementation_plan.md", "roadmap.md"]:
            path = PROJECT_ROOT / p
            if path.exists():
                plan_file = str(path)
                break

    report_file = args.report_file
    if not report_file:
        for p in ["walkthrough.md", "report.md", "retrospective.md"]:
            path = PROJECT_ROOT / p
            if path.exists():
                report_file = str(path)
                break

    print(f"Syncing to Obsidian Vault: {VAULT_PATH}")
    print(f"Plan file: {plan_file}")
    print(f"Report file: {report_file}")

    ensure_structure(context, "TBD", "TBD", "TBD", "TBD")
    sync_project(
        context=context,
        plan_file=plan_file,
        report_file=report_file,
        research_note=args.research_note,
        decision_note=args.decision_note,
        handoff_note=args.handoff_note,
        agent_role=args.agent_role
    )
    print("Sync completed successfully.")

if __name__ == "__main__":
    main()
