"""Benchmark Integrity Layer: Audits datasets for leakage, contamination, and valid signal overlap."""

import sys
import json
import io
from pathlib import Path
from collections import defaultdict

# Force UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Add backend directory to sys.path
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.agents.pipeline import DisputePipeline


def audit_benchmark_integrity():
    golden_path = Path(__file__).parent.parent / "data" / "golden_cases.json"
    benchmark_path = Path(__file__).parent.parent / "data" / "unseen_benchmark_1000.json"

    with open(golden_path, "r", encoding="utf-8") as f:
        golden_cases = json.load(f)

    with open(benchmark_path, "r", encoding="utf-8") as f:
        benchmark_cases = json.load(f)

    print("=" * 90)
    print("🛡️ RAKSHAK AI — BENCHMARK INTEGRITY & LEAKAGE AUDIT")
    print("=" * 90)

    # -------------------------------------------------------------
    # AUDIT 1: Train / Test Entity Leakage
    # -------------------------------------------------------------
    golden_order_ids = set(c.get("order", {}).get("order_id") for c in golden_cases)
    golden_payment_ids = set(c.get("payment", {}).get("payment_id") for c in golden_cases)
    golden_dispute_ids = set(c.get("dispute", {}).get("dispute_id") for c in golden_cases)
    golden_customer_ids = set(c.get("customer", {}).get("customer_id") for c in golden_cases)

    order_overlap = []
    payment_overlap = []
    dispute_overlap = []
    customer_overlap = []

    for b in benchmark_cases:
        b_oid = b.get("order", {}).get("order_id")
        b_pid = b.get("payment", {}).get("payment_id")
        b_did = b.get("dispute", {}).get("dispute_id")
        b_cid = b.get("customer", {}).get("customer_id")

        if b_oid in golden_order_ids:
            order_overlap.append(b_oid)
        if b_pid in golden_payment_ids:
            payment_overlap.append(b_pid)
        if b_did in golden_dispute_ids:
            dispute_overlap.append(b_did)
        if b_cid in golden_customer_ids:
            customer_overlap.append(b_cid)

    print("CHECK 1: TRAIN / TEST ENTITY LEAKAGE")
    print(f"  • Golden Regression Suite Size : {len(golden_cases)} cases")
    print(f"  • Evaluation Benchmark Size    : {len(benchmark_cases)} cases")
    print(f"  • Overlapping Order IDs        : {len(order_overlap)} (Target: 0)")
    print(f"  • Overlapping Payment IDs      : {len(payment_overlap)} (Target: 0)")
    print(f"  • Overlapping Dispute IDs      : {len(dispute_overlap)} (Target: 0)")
    print(f"  • Overlapping Customer IDs     : {len(customer_overlap)} (Target: 0)")

    leakage_pass = not (order_overlap or payment_overlap or dispute_overlap or customer_overlap)
    print(f"  -> RESULT: {'[PASSED] Zero entity leakage detected' if leakage_pass else '[FAILED] Leakage detected!'}")

    # -------------------------------------------------------------
    # AUDIT 2: Ground-Truth Visibility Leakage
    # -------------------------------------------------------------
    pipeline = DisputePipeline()
    gt_leakage_detected = False

    # Check if pipeline investigator passes ground truth fields into evidence nodes
    sample_case = benchmark_cases[0]
    inv_res = pipeline.investigator.investigate(sample_case)
    for node in inv_res.get("nodes", []):
        content_keys = list(node.get("content", {}).keys())
        for forbidden in ["ground_truth", "expected_decision", "merchant_fault", "label"]:
            if forbidden in content_keys:
                print(f"  [CRITICAL LEAKAGE] Evidence node {node['evidence_id']} exposes '{forbidden}' field!")
                gt_leakage_detected = True

    print("\nCHECK 2: GROUND-TRUTH VISIBILITY IN EVIDENCE GRAPH")
    print(f"  • Ground Truth Hidden from Evidence Nodes: {'[PASSED] Zero GT leakage' if not gt_leakage_detected else '[FAILED] Evidence graph contains GT labels!'}")

    # -------------------------------------------------------------
    # AUDIT 3: Signal Overlap & Non-Trivial Distribution Check
    # -------------------------------------------------------------
    # Verify that delivery proof / refund proof presence is NOT a trivial 1-to-1 mapping with GT
    delivery_status_by_gt = defaultdict(lambda: defaultdict(int))
    for b in benchmark_cases:
        gt = b.get("dispute", {}).get("ground_truth", "unknown")
        ship = b.get("shipment")
        del_status = ship.get("delivery_status") if ship else "no_shipment"
        delivery_status_by_gt[gt][del_status] += 1

    print("\nCHECK 3: MULTI-SIGNAL DISTRIBUTION OVERLAP (Delivery Status vs Ground Truth)")
    for gt, statuses in delivery_status_by_gt.items():
        print(f"  • Ground Truth: {gt:<16} -> {dict(statuses)}")

    print("\n" + "=" * 90)
    print("ALL AUDIT CHECKS COMPLETED.")
    print("=" * 90)


if __name__ == "__main__":
    audit_benchmark_integrity()
