"""
Test script for AutoDoc Agent.
Sends both test cases to the API and displays results.

Usage:
    1. Start the server:  uvicorn main:app --reload
    2. Run this script:   python tests/test_agent.py
"""

import httpx
import json
import sys
import time

BASE_URL = "http://localhost:8000"

# ── Test Cases ──────────────────────────────────────────────────────────────

TEST_CASES = [
    {
        "name": "Test 1: Standard Request (Meeting Minutes)",
        "request": (
            "Create meeting minutes for a project kickoff meeting between "
            "engineering and the client for a new CRM system."
        ),
    },
    {
        "name": "Test 2: Ambiguous/Complex Request (Status Report)",
        "request": (
            "I need something for my manager about how the project is going, "
            "not sure what format, just make it look professional."
        ),
    },
]


def print_separator(char="═", length=70):
    print(char * length)


def print_header(text):
    print()
    print_separator()
    print(f"  {text}")
    print_separator()


def run_test(test_case: dict):
    """Run a single test case against the API."""
    print_header(test_case["name"])
    print(f"\n  Request: \"{test_case['request'][:80]}...\"")
    print(f"\n  Sending to {BASE_URL}/agent ...")
    print()

    start_time = time.time()

    try:
        with httpx.Client(timeout=600) as client:  # 10 min timeout for local LLM calls
            response = client.post(
                f"{BASE_URL}/agent",
                json={"request": test_case["request"]},
            )

        elapsed = time.time() - start_time

        if response.status_code == 200:
            data = response.json()

            print(f"  ✅ SUCCESS (took {elapsed:.1f}s)")
            print()
            print(f"  Document Type : {data['document_type']}")
            print()
            print(f"  Plan:")
            for i, step in enumerate(data["plan"], 1):
                print(f"    {i}. {step}")
            print()

            if data["assumptions"]:
                print(f"  Assumptions:")
                for assumption in data["assumptions"]:
                    print(f"    • {assumption}")
                print()

            print(f"  File Path: {data['file_path']}")
            print()

            return True
        else:
            print(f"  ❌ FAILED — HTTP {response.status_code}")
            print(f"  Response: {response.text}")
            return False

    except httpx.ConnectError:
        print(f"  ❌ CONNECTION ERROR — Is the server running?")
        print(f"     Start it with: uvicorn main:app --reload")
        return False

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"  ❌ ERROR after {elapsed:.1f}s: {e}")
        return False


def check_health():
    """Check if the server is running."""
    try:
        with httpx.Client(timeout=5) as client:
            response = client.get(BASE_URL)
            if response.status_code == 200:
                data = response.json()
                print(f"  Server status : {data.get('status', 'unknown')}")
                print(f"  LLM provider  : {data.get('llm_provider', 'unknown')}")
                return True
    except httpx.ConnectError:
        return False
    return False


# ── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print_header("AutoDoc Agent — Test Suite")

    # Health check
    print("\n  Checking server health...")
    if not check_health():
        print("\n  ❌ Server is not running!")
        print("     Start it with:")
        print("       cd 'd:\\Desktop File\\Autonomous Document Generation Agent'")
        print("       uvicorn main:app --reload")
        print()
        sys.exit(1)

    print()

    # Run tests
    results = []
    for test_case in TEST_CASES:
        success = run_test(test_case)
        results.append((test_case["name"], success))

    # Summary
    print_header("Test Summary")
    print()
    for name, success in results:
        icon = "✅" if success else "❌"
        print(f"  {icon}  {name}")
    print()

    passed = sum(1 for _, s in results if s)
    total = len(results)
    print(f"  Result: {passed}/{total} tests passed")
    print_separator()
