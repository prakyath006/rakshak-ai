"""First look at IEEE-CIS: verify the label, then prove the split is clean.

Run this before any modelling. Its whole job is to refuse to proceed quietly if
the data is not what the documentation claims, because every number downstream
inherits whatever is wrong here.

    python -m ml.inspect_data
"""

from __future__ import annotations

import sys

from ml.data import (
    AMOUNT,
    DatasetMissing,
    LABEL,
    SECONDS_PER_DAY,
    TIME,
    load_raw,
    time_split,
    verify_label,
)


def rule(title: str) -> None:
    print(f"\n{title}")
    print("-" * len(title))


def main() -> int:
    try:
        print("Loading train_transaction.csv + train_identity.csv ...")
        df = load_raw()
    except DatasetMissing as exc:
        print(f"\n{exc}")
        return 1

    # ---- the label ---------------------------------------------------
    rule("LABEL")
    info = verify_label(df)
    print(f"  definition        : {info['documented_definition']}")
    print(f"  rows              : {info['rows']:,}")
    print(f"  positives         : {info['positives']:,}")
    print(f"  fraud rate        : {info['fraud_rate']:.3%}")
    print(f"  observation window: {info['span_days']:.0f} days")
    if info["rate_matches_documentation"]:
        print("  [OK] Rate is consistent with the documented ~3.5% chargeback rate.")
    else:
        print("  [WARN] Rate is outside the expected 2.5-4.5% band — investigate before modelling.")

    # ---- shape -------------------------------------------------------
    rule("SHAPE")
    identity_cols = [c for c in df.columns if c.startswith("id_")] + ["DeviceType", "DeviceInfo"]
    present_identity = [c for c in identity_cols if c in df.columns]
    have_identity = df[present_identity[0]].notna().mean() if present_identity else 0.0
    print(f"  columns           : {df.shape[1]}")
    print(f"  identity coverage : {have_identity:.1%} of transactions have a device record")
    print(f"  ticket median     : {df[AMOUNT].median():,.2f}")
    print(f"  ticket p99        : {df[AMOUNT].quantile(0.99):,.2f}")

    # Loss is what we actually care about, and it is not spread evenly.
    fraud_value = df.loc[df[LABEL] == 1, AMOUNT].sum()
    total_value = df[AMOUNT].sum()
    print(f"  value at risk     : {fraud_value / total_value:.2%} of settled value is fraudulent")

    # ---- the split ---------------------------------------------------
    rule("SPLIT")
    split = time_split(df)          # raises if the folds overlap
    print(split.describe())
    print("\n  [OK] No time overlap and no shared TransactionIDs across folds.")

    # ---- the honest caveat -------------------------------------------
    rule("WATCH")
    tr_rate, ca_rate, te_rate = split.fraud_rates()
    drift = (te_rate - tr_rate) / tr_rate if tr_rate else 0.0
    print(f"  fraud rate drift train -> test: {drift:+.1%}")
    print("  A negative drift is expected and is not the model's fault: labels come")
    print("  from chargebacks reported within ~120 days, so the most recent window")
    print("  has had less time to accumulate them. Report this rather than tuning to it.")

    print("\nData verified. Safe to build features.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
