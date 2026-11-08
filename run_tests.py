#!/usr/bin/env python3
"""
Test Runner Script
Runs all automated test suites across the project:
1. Integration Test (tests/test_integration.py)
2. Audio Studio Test (tests/test_audio_studio.py)
3. Network Dashboard Test (tests/test_dashboard_monitoring.py)
"""

import os
import sys
import subprocess
import time

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

def run_suite(name, script_path):
    print("=" * 66)
    print(f" RUNNING SUITE: {name}")
    print("=" * 66)
    t0 = time.time()
    res = subprocess.run([sys.executable, script_path], cwd=ROOT_DIR)
    elapsed = time.time() - t0
    if res.returncode == 0:
        print(f"\n[OK] {name} passed successfully in {elapsed:.2f}s.\n")
        return True
    else:
        print(f"\n[FAIL] {name} failed with exit code {res.returncode}.\n")
        return False

def main():
    suites = [
        ("Base Integration Suite", os.path.join(ROOT_DIR, "tests", "test_integration.py")),
        ("Audio Studio FFmpeg Suite", os.path.join(ROOT_DIR, "tests", "test_audio_studio.py")),
        ("Network Dashboard & Monitoring Suite", os.path.join(ROOT_DIR, "tests", "test_dashboard_monitoring.py")),
    ]

    all_passed = True
    for name, path in suites:
        if not run_suite(name, path):
            all_passed = False
            break

    if all_passed:
        print("*" * 66)
        print("  ALL TEST SUITES PASSED 100% ACROSS THE ORGANIZED CODEBASE!")
        print("*" * 66)
        sys.exit(0)
    else:
        print("One or more test suites failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
