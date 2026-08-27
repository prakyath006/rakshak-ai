import sys
import json
import io
from pathlib import Path

# Force UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Add backend directory to sys.path
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.agents.pipeline import DisputePipeline


def main():
    golden_path = Path(__file__).parent.parent / "data" / "golden_cases.json"
    with open(golden_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    pipeline = DisputePipeline(use_llm=False)

    passed = 0
    total = len(cases)

    print("=" * 80)
    print(f"RAKSHAK AI - GOLDEN CASES REGRESSION EVALUATION ({total} Cases)")
    print("=" * 80)

    for case in cases:
        case_id = case["case_id"]
        expected_dec = case["expected_decision"]
        expected_str = case.get("expected_strength")

        result = pipeline.run(case)
        actual_dec = result["decision"]["recommendation"]
        actual_str = result["decision"]["evidence_strength"]
        completeness = result["verification"]["completeness_score"] * 100

        match = (actual_dec == expected_dec)
        if match:
            passed += 1
            status_icon = "[PASS]"
        else:
            status_icon = "[FAIL]"

        print(
            f"{status_icon} {case_id} | {case['category']:<22} | "
            f"Exp: {expected_dec:<14} -> Act: {actual_dec:<14} | "
            f"Comp: {completeness:>5.1f}% | Str: {actual_str:<6} | {case['title'][:32]}"
        )
        if not match:
            print(f"      Reason: {result['decision']['reasoning']}")
            print(f"      Contradictions: {result['verification']['contradictions']}")

    accuracy = (passed / total) * 100
    print("=" * 80)
    print(f"RESULTS: {passed}/{total} PASSED ({accuracy:.1f}% accuracy)")
    print("=" * 80)

    if passed == total:
        print("ALL 20 GOLDEN TEST CASES PASSED PERFECTLY.")
        sys.exit(0)
    else:
        print(f"FAILED {total - passed} cases. Please calibrate decision logic.")
        sys.exit(1)


if __name__ == "__main__":
    main()
