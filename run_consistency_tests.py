#!/usr/bin/env python3
"""
Lightweight runner for consistency checker tests without pytest dependency.
Runs unit and integration tests by importing their functions and executing them.
Aligned with CLAUDE.md container execution model.
"""

import sys
import traceback


def run_test(fn, name):
    try:
        fn()
        print(f"[PASS] {name}")
        return True
    except AssertionError as e:
        print(f"[FAIL] {name} - AssertionError: {e}")
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"[ERROR] {name} - {e}")
        traceback.print_exc()
        return False


def main():
    total = 0
    passed = 0

    # Unit tests
    try:
        from tests.dspy.test_consistency_checker import (
            test_bootstrap_noop,
            test_fever_state_flip,
            test_self_introduction_detection,
            test_generic_response_detection,
            test_timeline_inconsistency_detection,
        )

        tests = [
            (test_bootstrap_noop, "checker::bootstrap_noop"),
            (test_fever_state_flip, "checker::fever_state_flip"),
            (test_self_introduction_detection, "checker::self_introduction"),
            (test_generic_response_detection, "checker::generic_response"),
            (test_timeline_inconsistency_detection, "checker::timeline_inconsistency"),
        ]

        for fn, name in tests:
            total += 1
            if run_test(fn, name):
                passed += 1
    except Exception as e:
        print(f"[ERROR] Import unit tests failed: {e}")
        traceback.print_exc()

    # Integration test
    try:
        from tests.dspy.test_consistency_integration_unified import (
            test_unified_with_consistency_filtering,
        )
        total += 1
        if run_test(test_unified_with_consistency_filtering, "integration::unified_filtering"):
            passed += 1
    except Exception as e:
        print(f"[ERROR] Import integration test failed: {e}")
        traceback.print_exc()

    print(f"\nSummary: {passed}/{total} tests passed")
    sys.exit(0 if passed == total and total > 0 else 1)


if __name__ == "__main__":
    main()

