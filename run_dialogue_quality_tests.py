#!/usr/bin/env python3
"""Batch runner for dialogue quality scenarios."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

SCENARIOS: Dict[str, Dict[str, List[str]]] = {
    "degradation": {
        "description": "Baseline degradation diagnostics",
        "command": ["test_dialogue_degradation.py"],
    },
    "role_identity": {
        "description": "Role identity consistency",
        "command": ["tests/dialogue_quality/scenario_role_identity.py"],
    },
    "sensitive_refusal": {
        "description": "Sensitive request refusal",
        "command": ["tests/dialogue_quality/scenario_sensitive_refusal.py"],
    },
    "noisy_input": {
        "description": "Noisy input robustness",
        "command": ["tests/dialogue_quality/scenario_noisy_input.py"],
    },
    "fallback_resilience": {
        "description": "Fallback behaviour stress test",
        "command": ["tests/dialogue_quality/scenario_fallback_resilience.py"],
    },
}

REPO_ROOT = Path(__file__).resolve().parent


def run_command(path: Path, args: List[str]) -> int:
    cmd = [sys.executable, str(path)]
    cmd.extend(args)
    process = subprocess.run(cmd, check=False)
    return process.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run dialogue quality scenarios")
    parser.add_argument(
        "--scenario",
        choices=list(SCENARIOS.keys()),
        action="append",
        help="Only run the specified scenario (can be repeated).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Display available scenarios and exit.",
    )
    parsed = parser.parse_args()

    if parsed.list:
        print("Available scenarios:")
        for name, details in SCENARIOS.items():
            print(f"  {name:18s} - {details['description']}")
        return 0

    targets = parsed.scenario or list(SCENARIOS.keys())
    failures: List[str] = []

    for name in targets:
        details = SCENARIOS[name]
        script_path = REPO_ROOT / details["command"][0]
        if not script_path.exists():
            print(f"❌ {name}: script not found at {script_path}")
            failures.append(name)
            continue

        print("=" * 70)
        print(f"▶ Running scenario: {name} - {details['description']}")
        exit_code = run_command(script_path, details["command"][1:])
        if exit_code == 0:
            print(f"✅ Scenario {name} finished (exit code {exit_code})")
        else:
            print(f"❗ Scenario {name} exited with code {exit_code}")
            failures.append(name)

    print("=" * 70)
    if failures:
        print(f"Completed with {len(failures)} failure(s): {', '.join(failures)}")
        return 1

    print("All scenarios completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
