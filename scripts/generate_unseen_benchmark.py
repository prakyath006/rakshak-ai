"""Generate 100 Unseen Benchmark Disputes with Hidden Ground Truth and Adversarial Noise."""

import json
import random
from pathlib import Path
from datetime import datetime, timedelta

# Set fixed seed for reproducibility
random.seed(42)

MERCHANTS = [
    {
        "merchant_id": "MERCH-001",
        "name": "Apex Electronics India",
        "industry": "Electronics",
        "refund_policy": "Returns accepted within 7 days in original packaging.",
        "cancellation_policy": "Cancellations permitted prior to shipment dispatch.",
        "terms_url": "https://apexelectronics.in/terms",
    },
    {
        "merchant_id": "MERCH-002",
        "name": "StyleHub Fashion",
        "industry": "Apparel",
        "refund_policy": "Full refund upon receipt of returned goods.",
        "cancellation_policy": "Free cancellation before fulfillment.",
        "terms_url": "https://stylehub.in/terms",
    },
    {
        "merchant_id": "MERCH-003",
        "name": "Veda Health & Wellness",
        "industry": "Health",
        "refund_policy": "30-day money back guarantee on unopened supplements.",
        "cancellation_policy": "Cancellations within 12 hours of order.",
        "terms_url": "https://vedahealth.in/terms",
    },
]

PRODUCTS = [
    {"name": "Wireless Noise Cancelling Earbuds", "cat": "goods_not_received", "price": 4500.0, "pcat": "Audio"},
    {"name": "Smart Fitness Watch Ultra", "cat": "goods_not_received", "price": 12000.0, "pcat": "Wearables"},
    {"name": "Ergonomic Office Chair Pro", "cat": "goods_not_received", "price": 18500.0, "pcat": "Furniture"},
    {"name": "4K Ultra HD Dash Camera", "cat": "goods_not_received", "price": 8900.0, "pcat": "Auto"},
    {"name": "Organic Whey Protein 2kg", "cat": "credit_not_processed", "price": 5400.0, "pcat": "Supplements"},
    {"name": "Designer Leather Laptop Bag", "cat": "credit_not_processed", "price": 7200.0, "pcat": "Accessories"},
    {"name": "Mechanical Keyboard RGB 75%", "cat": "not_as_described", "price": 9500.0, "pcat": "Accessories"},
    {"name": "Studio Monitor Speakers Pair", "cat": "not_as_described", "price": 28000.0, "pcat": "Audio"},
    {"name": "Handcrafted Silk Kurta Set", "cat": "cancelled_merchandise", "price": 6500.0, "pcat": "Apparel"},
    {"name": "Smart Home Hub Gateway", "cat": "unauthorized_fraud", "price": 14000.0, "pcat": "Smart Home"},
    {"name": "Flagship 5G Smartphone 256GB", "cat": "unauthorized_fraud", "price": 52000.0, "pcat": "Mobiles"},
]

CITIES = ["Bengaluru", "Mumbai", "Delhi", "Hyderabad", "Chennai", "Pune", "Kolkata", "Ahmedabad", "Jaipur", "Kochi"]
FIRST_NAMES = ["Aarav", "Vihaan", "Aditya", "Sai", "Reyansh", "Ananya", "Diya", "Isha", "Riya", "Kavya", "Pooja", "Rahul", "Nikhil", "Tarun"]
LAST_NAMES = ["Sharma", "Verma", "Patel", "Reddy", "Nair", "Iyer", "Mehta", "Singh", "Gupta", "Deshmukh", "Choudhury", "Bose"]

REASON_CODES = {
    "goods_not_received": [("13.1", "Visa"), ("1064", "UPI"), ("C08", "AmEx")],
    "credit_not_processed": [("13.6", "Visa"), ("1061", "UPI")],
    "not_as_described": [("13.3", "Visa")],
    "cancelled_merchandise": [("13.7", "Visa")],
    "unauthorized_fraud": [("10.4", "Visa")],
}


def generate_unseen_dataset(count: int = 100):
    cases = []
    base_date = datetime(2026, 7, 1, 10, 0, 0)

    # Categories distribution proportional weights:
    # 30% GNR, 20% CNP, 20% NAD, 15% CANC, 15% FRAUD
    base_pool = (
        ["goods_not_received"] * 30
        + ["credit_not_processed"] * 20
        + ["not_as_described"] * 20
        + ["cancelled_merchandise"] * 15
        + ["unauthorized_fraud"] * 15
    )
    multiplier = (count // len(base_pool)) + 1
    cat_distribution = (base_pool * multiplier)[:count]
    random.shuffle(cat_distribution)

    for i in range(1, count + 1):
        case_id = f"UNSEEN-{i:03d}"
        cat = cat_distribution[i - 1]
        merchant = random.choice(MERCHANTS)
        
        # Deep copy product dictionary to prevent mutation leakage
        raw_prod = random.choice([p for p in PRODUCTS if p["cat"] == cat] or PRODUCTS)
        prod = {
            "name": raw_prod["name"],
            "cat": raw_prod["cat"],
            "price": raw_prod["price"],
            "pcat": raw_prod["pcat"],
            "specification": "Standard manufacturer configuration and technical specifications.",
        }
        
        city = random.choice(CITIES)
        cust_name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        cust_id = f"CUS-UNS-{i:04d}"
        order_id = f"ORD-UNS-{i:04d}"
        payment_id = f"pay_uns_{i:04d}"
        disp_id = f"disp_uns_{i:04d}"
        
        rc_info = random.choice(REASON_CODES[cat])
        reason_code, network = rc_info

        amount = float(prod["price"])
        order_dt = base_date + timedelta(days=random.randint(1, 45), hours=random.randint(1, 12))
        payment_dt = order_dt + timedelta(minutes=5)
        ship_dt = order_dt + timedelta(days=random.randint(1, 2))
        del_dt = ship_dt + timedelta(days=random.randint(1, 3))
        disp_dt = del_dt + timedelta(days=random.randint(3, 10))

        # Deliberately sample scenario archetype
        scenario_roll = random.random()
        
        order_status = "delivered"
        cancelled_at = None
        delivery_status = "delivered"
        delivered_timestamp = del_dt.isoformat() + "Z"
        address_match = True
        items_shipped = 1
        refunds = []
        comms = []
        is_adversarial_trap = False

        # --- Scenario Archetypes ---
        if cat == "goods_not_received":
            if scenario_roll < 0.40:
                # Strong contestable case
                expected_decision = "CONTEST"
                ground_truth = "contestable"
                comms.append({
                    "communication_id": f"COMM-UNS-{i}",
                    "channel": "email",
                    "direction": "inbound",
                    "subject": "Delivery confirmed",
                    "message": "Thanks, received it safely.",
                    "timestamp": (del_dt + timedelta(hours=4)).isoformat() + "Z",
                })
            elif scenario_roll < 0.65:
                # Missing proof / lost shipment
                expected_decision = "REVIEW"
                ground_truth = "ambiguous"
                delivered_timestamp = None
                delivery_status = "in_transit"
            elif scenario_roll < 0.80:
                # Clearly merchant fault (lost confirmed by merchant)
                expected_decision = "DO_NOT_CONTEST"
                ground_truth = "non_contestable"
                delivered_timestamp = None
                delivery_status = "lost"
                comms.append({
                    "communication_id": f"COMM-UNS-{i}",
                    "channel": "email",
                    "direction": "outbound",
                    "subject": "Lost in transit",
                    "message": "Courier confirmed package was lost in transit.",
                    "timestamp": (del_dt).isoformat() + "Z",
                })
            elif scenario_roll < 0.90:
                # Address contradiction
                expected_decision = "REVIEW"
                ground_truth = "ambiguous"
                address_match = False
            else:
                # Adversarial Trap A: Cross-order contamination
                expected_decision = "REVIEW"
                ground_truth = "ambiguous"
                is_adversarial_trap = True
                comms.append({
                    "communication_id": f"COMM-UNS-{i}",
                    "channel": "email",
                    "direction": "inbound",
                    "order_id": f"ORD-UNS-9999",  # WRONG ORDER!
                    "subject": "Received",
                    "message": "Thanks, received it.",
                    "timestamp": del_dt.isoformat() + "Z",
                })

        elif cat == "credit_not_processed":
            if scenario_roll < 0.50:
                # Refund processed successfully
                expected_decision = "CONTEST"
                ground_truth = "contestable"
                refunds.append({
                    "refund_id": f"rfnd_uns_{i}",
                    "amount": amount,
                    "status": "processed",
                    "reason": "Customer cancellation",
                    "created_at": (order_dt + timedelta(days=1)).isoformat() + "Z",
                })
            elif scenario_roll < 0.75:
                # Promised in writing but not issued
                expected_decision = "DO_NOT_CONTEST"
                ground_truth = "non_contestable"
                comms.append({
                    "communication_id": f"COMM-UNS-{i}",
                    "channel": "email",
                    "direction": "outbound",
                    "subject": "Refund promise",
                    "message": f"We will process your refund of INR {amount:,.2f} within 2 business days.",
                    "timestamp": order_dt.isoformat() + "Z",
                })
            else:
                # Refund pending in rails
                expected_decision = "REVIEW"
                ground_truth = "ambiguous"
                refunds.append({
                    "refund_id": f"rfnd_uns_{i}",
                    "amount": amount,
                    "status": "pending",
                    "reason": "Return requested",
                    "created_at": (order_dt + timedelta(days=1)).isoformat() + "Z",
                })

        elif cat == "not_as_described":
            if scenario_roll < 0.50:
                # Delivered matches spec
                expected_decision = "CONTEST"
                ground_truth = "contestable"
            elif scenario_roll < 0.80:
                # Specification actually differs
                expected_decision = "DO_NOT_CONTEST"
                ground_truth = "non_contestable"
                prod["specification"] = "Advertised: 16GB. Fulfilled: 8GB model."
            else:
                # Ambiguous spec
                expected_decision = "REVIEW"
                ground_truth = "ambiguous"
                prod["specification"] = "Generic components (exact variant omitted in catalog)."

        elif cat == "cancelled_merchandise":
            if scenario_roll < 0.45:
                # Cancelled after shipment
                expected_decision = "REVIEW"
                ground_truth = "ambiguous"
                cancelled_at = (ship_dt + timedelta(hours=5)).isoformat() + "Z"
            elif scenario_roll < 0.80:
                # Cancelled before dispatch, merchant never shipped, never refunded
                expected_decision = "DO_NOT_CONTEST"
                ground_truth = "non_contestable"
                cancelled_at = (order_dt + timedelta(hours=2)).isoformat() + "Z"
                delivered_timestamp = None
                delivery_status = "pending"
            else:
                # Cancelled before dispatch, merchant shipped anyway
                expected_decision = "DO_NOT_CONTEST"
                ground_truth = "non_contestable"
                cancelled_at = (order_dt + timedelta(hours=2)).isoformat() + "Z"

        else:  # unauthorized_fraud
            # Fraud category is always human review in Track 02 defense mode
            expected_decision = "REVIEW"
            ground_truth = "ambiguous" if scenario_roll < 0.70 else "contestable"

        # Construct full case dictionary
        case = {
            "case_id": case_id,
            "title": f"{cat.replace('_', ' ').title()} Scenario #{i}",
            "category": cat,
            "reason_code": reason_code,
            "reason_description": f"Dispute Reason {reason_code}",
            "expected_decision": expected_decision,
            "expected_strength": "HIGH" if expected_decision == "CONTEST" else "LOW" if expected_decision == "DO_NOT_CONTEST" else "MEDIUM",
            "merchant": merchant,
            "customer": {
                "customer_id": cust_id,
                "name": cust_name,
                "email": f"{cust_name.lower().replace(' ', '.')}@example.com",
                "phone": "+91-98" + str(random.randint(10000000, 99999999)),
                "city": city,
                "country": "IN",
                "dispute_history_count": random.randint(0, 2),
            },
            "product": {
                "product_id": f"PROD-UNS-{i:04d}",
                "name": prod["name"],
                "description": f"Original catalog listing for {prod['name']}",
                "specification": prod.get("specification", "Standard manufacturer configuration"),
                "price": amount,
                "category": prod["pcat"],
            },
            "order": {
                "order_id": order_id,
                "quantity": 1,
                "order_amount": amount,
                "order_status": order_status,
                "cancelled_at": cancelled_at,
                "created_at": order_dt.isoformat() + "Z",
            },
            "payment": {
                "payment_id": payment_id,
                "amount": amount,
                "payment_method": "card" if network in ["Visa", "AmEx"] else "upi",
                "payment_status": "refunded" if refunds and refunds[0]["status"] == "processed" else "captured",
                "card_network": network.lower(),
                "payment_timestamp": payment_dt.isoformat() + "Z",
            },
            "shipment": {
                "shipment_id": f"SHIP-UNS-{i:04d}",
                "carrier": "BlueDart Express",
                "tracking_number": f"BD-{random.randint(1000000, 9999999)}",
                "shipped_at": ship_dt.isoformat() + "Z" if delivery_status != "pending" else None,
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
                "amount": amount,
                "phase": "chargeback" if cat != "unauthorized_fraud" else "fraud",
                "status": "open",
                "respond_by": (disp_dt + timedelta(days=7)).isoformat() + "Z",
                "customer_claim_text": f"Customer initiated dispute under code {reason_code}.",
                "ground_truth": ground_truth,
            }
        }
        cases.append(case)

    return cases


def main():
    cases = generate_unseen_dataset(100)
    out_dir = Path(__file__).parent.parent / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "unseen_benchmark_100.json"
    
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(cases, f, indent=2)

    print(f"Generated 100 unseen benchmark cases at {out_file}")


if __name__ == "__main__":
    main()
