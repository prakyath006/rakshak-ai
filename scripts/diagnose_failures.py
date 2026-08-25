"""Diagnostic script to inspect missed contestable cases (GT: CONTEST -> Pred: DO_NOT_CONTEST / REVIEW)."""

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
    benchmark_path = Path(__file__).parent.parent / "data" / "unseen_benchmark_100.json"
    with open(benchmark_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    pipeline = DisputePipeline()

    missed_as_dnc = []
    missed_as_review = []

    for case in cases:
        if case["expected_decision"] == "CONTEST":
            res = pipeline.run(case)
            pred = res["decision"]["recommendation"]
            if pred == "DO_NOT_CONTEST":
                missed_as_dnc.append((case, res))
            elif pred == "REVIEW":
                missed_as_review.append((case, res))

    print("=" * 90)
    print(f"DIAGNOSTIC REPORT: 19 MISSED CONTESTABLE CASES (GT = CONTEST)")
    print(f"  • Missed as DO_NOT_CONTEST (Severe Under-Defense): {len(missed_as_dnc)} cases")
    print(f"  • Missed as REVIEW (Over-Cautious Escalation)   : {len(missed_as_review)} cases")
    print("=" * 90)

    print("\n" + "#" * 90)
    print(f"PART 1: THE {len(missed_as_dnc)} FALSE 'DO_NOT_CONTEST' CASES (Crucial Fix)")
    print("#" * 90)

    for case, res in missed_as_dnc:
        print(f"\n[CASE {case['case_id']}] | Category: {case['category']} | Reason Code: {case['reason_code']}")
        print(f"  • Title: {case['title']}")
        print(f"  • Amount: ₹{case['dispute']['amount']:,.2f}")
        print(f"  • Predicted: {res['decision']['recommendation']} (Confidence: {res['decision']['confidence']*100:.1f}%)")
        print(f"  • Reasoning: {res['decision']['reasoning']}")
        v = res["verification"]
        print(f"  • 4D Scores: Comp={v['completeness_score']*100:.1f}%, Rel={v['reliability_score']*100:.1f}%, Cons={v['consistency_score']*100:.1f}%, Relev={v['relevance_score']*100:.1f}%")
        print(f"  • Missing Critical : {v['missing_critical']}")
        print(f"  • Missing Optional : {v['missing_optional']}")
        print(f"  • Contradictions    : {v['contradictions']}")
        print(f"  • Relevance Warnings: {v['relevance_warnings']}")
        print(f"  • Available Types   : {v['available_evidence']}")
        print("  " + "-" * 80)

    print("\n" + "#" * 90)
    print(f"PART 2: THE {len(missed_as_review)} FALSE 'REVIEW' CASES (Over-Cautious Escalation)")
    print("#" * 90)

    for case, res in missed_as_review:
        print(f"\n[CASE {case['case_id']}] | Category: {case['category']} | Reason Code: {case['reason_code']}")
        print(f"  • Title: {case['title']}")
        print(f"  • Amount: ₹{case['dispute']['amount']:,.2f}")
        print(f"  • Predicted: {res['decision']['recommendation']} (Confidence: {res['decision']['confidence']*100:.1f}%)")
        print(f"  • Reasoning: {res['decision']['reasoning']}")
        v = res["verification"]
        print(f"  • 4D Scores: Comp={v['completeness_score']*100:.1f}%, Rel={v['reliability_score']*100:.1f}%, Cons={v['consistency_score']*100:.1f}%, Relev={v['relevance_score']*100:.1f}%")
        print(f"  • Missing Critical : {v['missing_critical']}")
        print(f"  • Missing Optional : {v['missing_optional']}")
        print(f"  • Contradictions    : {v['contradictions']}")
        print("  " + "-" * 80)


if __name__ == "__main__":
    main()
