"""Generate a 200-Case Adversarial Benchmark Suite designed to stress-test guardrails and consistency engines."""

import json
import random
from pathlib import Path
from datetime import datetime, timedelta

# Set fixed seed for reproducibility
random.seed(999)

MERCHANTS = [
    {
        "merchant_id": "MERCH-ADV-001",
        "name": "Apex Electronics India",
        "industry": "Electronics",
        "refund_policy": "Returns accepted within 7 days in original packaging.",
        "cancellation_policy": "Cancellations permitted prior to shipment dispatch.",
        "terms_url": "https://apexelectronics.in/terms",
    },
    {
        "merchant_id": "MERCH-ADV-002",
        "name": "StyleHub Fashion",
        "industry": "Apparel",
        "refund_policy": "Full refund upon receipt of returned goods.",
        "cancellation_policy": "Free cancellation before fulfillment.",
        "terms_url": "https://stylehub.in/terms",
    },
]

PRODUCTS = [
    {"name": "Gaming Laptop 16-inch RTX 4080", "cat": "goods_not_received", "price": 50000.0, "pcat": "Laptops"},
    {"name": "Smart Fitness Band", "cat": "goods_not_received", "price": 5000.0, "pcat": "Wearables"},
    {"name": "Wireless Noise-Cancelling Headphones", "cat": "credit_not_processed", "price": 18000.0, "pcat": "Audio"},
    {"name": "4K Ultra-Wide Curved Monitor", "cat": "not_as_described", "price": 42000.0, "pcat": "Monitors"},
    {"name": "Designer Silk Anarkali Suit", "cat": "cancelled_merchandise", "price": 12000.0, "pcat": "Clothing"},
    {"name": "Flagship 5G Smartphone 512GB", "cat": "unauthorized_fraud", "price": 65000.0, "pcat": "Mobiles"},
]

CITIES = ["Bengaluru", "Mumbai", "Delhi", "Hyderabad", "Pune", "Kolkata", "Chennai"]


def generate_adversarial_suite(count: int = 200):
    cases = []
    base_date = datetime(2026, 8, 1, 10, 0, 0)

    for i in range(1, count + 1):
        case_id = f"ADV-{i:03d}"
        trap_type = (i % 6) + 1  # 6 distinct adversarial trap archetypes
        merchant = random.choice(MERCHANTS)
        city = random.choice(CITIES)
        order_id = f"ORD-ADV-{i:04d}"
        payment_id = f"pay_adv_{i:04d}"
        disp_id = f"disp_adv_{i:04d}"

        order_dt = base_date + timedelta(days=random.randint(1, 20), hours=random.randint(1, 8))
        payment_dt = order_dt + timedelta(minutes=5)
        ship_dt = order_dt + timedelta(days=1)
        del_dt = ship_dt + timedelta(days=2)
        disp_dt = del_dt + timedelta(days=5)

        # Base case defaults
        prod = random.choice(PRODUCTS)
        amount = float(prod["price"])
        category = prod["cat"]
        reason_code = "13.1" if category == "goods_not_received" else "13.6" if category == "credit_not_processed" else "13.3" if category == "not_as_described" else "13.7" if category == "cancelled_merchandise" else "10.4"
        network = "visa"

        comms = []
        refunds = []
        delivery_status = "delivered"
        delivered_timestamp = del_dt.isoformat() + "Z"
        shipped_timestamp = ship_dt.isoformat() + "Z"
        cancelled_at = None
        address_match = True
        items_shipped = 1
        spec_text = "Standard factory configuration."

        # -------------------------------------------------------------
        # ADVERSARIAL TRAP ARTIFACTS
        # -------------------------------------------------------------
        if trap_type == 1:
            # Trap 1: Wrong-Order Contamination (customer message belongs to different order)
            title = f"Cross-Order Evidence Contamination (Msg from ORD-9999)"
            category = "goods_not_received"
            reason_code = "13.1"
            amount = 50000.0
            expected_decision = "REVIEW"
            ground_truth = "ambiguous"
            delivered_timestamp = None
            delivery_status = "in_transit"
            comms.append({
                "communication_id": f"COMM-ADV-{i}",
                "channel": "email",
                "direction": "inbound",
                "order_id": "ORD-9999",  # WRONG ORDER CONTAMINATION!
                "subject": "Received safely",
                "message": "Thanks, received it safely.",
                "timestamp": del_dt.isoformat() + "Z",
            })

        elif trap_type == 2:
            # Trap 2: Severe Amount Mismatch (₹5,000 invoice on ₹50,000 dispute)
            title = f"Severe Amount Mismatch (₹5K document on ₹50K dispute)"
            category = "goods_not_received"
            reason_code = "13.1"
            amount = 50000.0
            expected_decision = "REVIEW"
            ground_truth = "ambiguous"
            # Invoice is generated for 5000 in payment/order
            prod = {"name": "Budget Fitness Tracker", "cat": "goods_not_received", "price": 5000.0, "pcat": "Wearables"}

        elif trap_type == 3:
            # Trap 3: Temporally Impossible Delivery (Delivery date BEFORE order creation)
            title = f"Temporally Impossible Delivery (Delivered before Order Created)"
            category = "goods_not_received"
            reason_code = "13.1"
            amount = 25000.0
            expected_decision = "REVIEW"
            ground_truth = "ambiguous"
            shipped_timestamp = (order_dt - timedelta(days=5)).isoformat() + "Z"
            delivered_timestamp = (order_dt - timedelta(days=3)).isoformat() + "Z"

        elif trap_type == 4:
            # Trap 4: Partial Refund without Amount Settlement (₹20K refund on ₹50K dispute)
            title = f"Partial Refund Mismatch (₹20K refund on ₹50K dispute)"
            category = "credit_not_processed"
            reason_code = "13.6"
            amount = 50000.0
            expected_decision = "REVIEW"
            ground_truth = "ambiguous"
            refunds.append({
                "refund_id": f"rfnd_adv_{i}",
                "amount": 20000.0,  # PARTIAL REFUND MISMATCH!
                "status": "processed",
                "reason": "Partial restocking refund",
                "created_at": (order_dt + timedelta(days=1)).isoformat() + "Z",
            })

        elif trap_type == 5:
            # Trap 5: Conflicting Systems (Logistics says delivered, but merchant outbound confirmed lost)
            title = f"Conflicting Systems (Logistics delivered vs Merchant email lost)"
            category = "goods_not_received"
            reason_code = "13.1"
            amount = 35000.0
            expected_decision = "DO_NOT_CONTEST"
            ground_truth = "non_contestable"
            delivery_status = "delivered"
            delivered_timestamp = del_dt.isoformat() + "Z"
            comms.append({
                "communication_id": f"COMM-ADV-{i}",
                "channel": "email",
                "direction": "outbound",
                "subject": "Carrier update: lost package",
                "message": "We regret to confirm your package was lost by the courier.",
                "timestamp": (del_dt + timedelta(hours=2)).isoformat() + "Z",
            })

        else:
            # Trap 6: Strong legitimate merchant evidence with 0 customer communications
            title = f"Strong Legitimate Case (Missing Optional Comm Notes)"
            category = "goods_not_received"
            reason_code = "13.1"
            amount = 45000.0
            expected_decision = "CONTEST"
            ground_truth = "contestable"
            delivery_status = "delivered"
            delivered_timestamp = del_dt.isoformat() + "Z"

        case = {
            "case_id": case_id,
            "title": title,
            "category": category,
            "reason_code": reason_code,
            "reason_description": f"Adversarial Scenario #{i}",
            "expected_decision": expected_decision,
            "expected_strength": "HIGH" if expected_decision == "CONTEST" else "LOW" if expected_decision == "DO_NOT_CONTEST" else "MEDIUM",
            "merchant": merchant,
            "customer": {
                "customer_id": f"CUS-ADV-{i:04d}",
                "name": f"Adversarial Customer {i}",
                "email": f"adv.user.{i}@example.com",
                "phone": "+91-9811223344",
                "city": city,
                "country": "IN",
                "dispute_history_count": 1,
            },
            "product": {
                "product_id": f"PROD-ADV-{i:04d}",
                "name": prod["name"],
                "description": f"Catalog description for {prod['name']}",
                "specification": spec_text,
                "price": amount,
                "category": prod["pcat"],
            },
            "order": {
                "order_id": order_id,
                "quantity": 1,
                "order_amount": amount,
                "order_status": "delivered",
                "cancelled_at": cancelled_at,
                "created_at": order_dt.isoformat() + "Z",
            },
            "payment": {
                "payment_id": payment_id,
                "amount": amount,
                "payment_method": "card",
                "payment_status": "captured",
                "card_network": network,
                "payment_timestamp": payment_dt.isoformat() + "Z",
            },
            "shipment": {
                "shipment_id": f"SHIP-ADV-{i:04d}",
                "carrier": "BlueDart Express",
                "tracking_number": f"BD-{random.randint(1000000, 9999999)}",
                "shipped_at": shipped_timestamp,
                "delivered_at": delivered_timestamp,
                "delivery_status": delivery_status,
                "delivery_address_city": city if address_match else "Goa",
                "delivery_address_match": address_match,
                "items_shipped": items_shipped,
            } if delivery_status != "pending" else None,
            "communications": comms,
            "refunds": refunds,
            "dispute": {
                "dispute_id": disp_id,
                "amount": 50000.0 if trap_type == 2 else amount,  # Trap 2 amount mismatch
                "phase": "chargeback",
                "status": "open",
                "respond_by": (disp_dt + timedelta(days=7)).isoformat() + "Z",
                "customer_claim_text": f"Adversarial dispute filed for case {case_id}",
                "ground_truth": ground_truth,
            }
        }
        cases.append(case)

    return cases


def main():
    cases = generate_adversarial_suite(200)
    out_dir = Path(__file__).parent.parent / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "adversarial_suite_200.json"

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(cases, f, indent=2)

    print(f"Generated 200 adversarial test cases at {out_file}")


if __name__ == "__main__":
    main()
