"""IEEE-CIS loading and the time-ordered split.

WHY THE SPLIT IS THE MOST IMPORTANT FUNCTION HERE
-------------------------------------------------
`isFraud` in this dataset is defined by Vesta as *"reported chargeback on the
card"*, with the label propagated to later transactions sharing a user account,
email or billing address. That makes it the closest thing to a real, labelled
chargeback outcome that exists publicly — and it also makes a random split
actively misleading:

  * Fraud arrives in bursts and rings. Randomly splitting puts members of the
    same ring on both sides, so the model is scored on cards and addresses it
    has already seen commit fraud. That is leakage, and it inflates every metric.
  * The label is assigned retrospectively, with a 120-day observation window.
    Transactions near the end of the recorded period have had less time to be
    reported, so late labels are relatively under-reported. A random split hides
    that; a time split makes it visible.
  * Deployment is chronological. A model trained today scores tomorrow's traffic.
    Any evaluation that shuffles time is measuring a task nobody has.

So the split here is strictly by `TransactionDT` — train on the earliest window,
calibrate on the middle, evaluate on the most recent — and the folds are checked
for overlap rather than assumed to be disjoint.

`TransactionDT` is a seconds offset from an undisclosed reference datetime, not
a timestamp. Only its ordering and its differences carry meaning; it is never
converted to a wall-clock date here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "ieee"

LABEL = "isFraud"
TIME = "TransactionDT"
AMOUNT = "TransactionAmt"
ID = "TransactionID"

SECONDS_PER_DAY = 86_400


class DatasetMissing(FileNotFoundError):
    """Raised with the exact command needed, rather than a bare path error."""

    def __init__(self, path: Path):
        super().__init__(
            f"Expected {path}.\n"
            f"Download it with:\n"
            f"    python -m kaggle competitions download -c ieee-fraud-detection -p data/ieee\n"
            f"    cd data/ieee && unzip -o ieee-fraud-detection.zip"
        )


def load_raw(
    data_dir: Path = DEFAULT_DATA_DIR,
    with_identity: bool = True,
    nrows: Optional[int] = None,
) -> pd.DataFrame:
    """Load the labelled training data, optionally joined to the identity table.

    Only the *train* files are usable: the competition's test labels were never
    released, so `test_transaction.csv` cannot score anything. Our held-out set
    is carved out of the labelled data by time, below.

    `nrows` reads a prefix for quick iteration. Note that because the file is
    time-ordered, a prefix is an *early* sample, not a random one — fine for
    plumbing checks, useless for measurement.
    """
    txn_path = data_dir / "train_transaction.csv"
    if not txn_path.exists():
        raise DatasetMissing(txn_path)

    txn = pd.read_csv(txn_path, nrows=nrows)

    if with_identity:
        id_path = data_dir / "train_identity.csv"
        if id_path.exists():
            identity = pd.read_csv(id_path)
            # Left join: most transactions have no identity record, and their
            # absence is itself signal. Dropping them would discard 75% of rows.
            txn = txn.merge(identity, on=ID, how="left")

    return txn


@dataclass(frozen=True)
class Split:
    """A time-ordered three-way split.

    train      fit the model
    calib      fit the probability calibrator — must not be the test set, or the
               calibration is scored on data it was tuned on
    test       held out; touched once, at the end
    """

    train: pd.DataFrame
    calib: pd.DataFrame
    test: pd.DataFrame

    @property
    def sizes(self) -> Tuple[int, int, int]:
        return len(self.train), len(self.calib), len(self.test)

    def fraud_rates(self) -> Tuple[float, float, float]:
        return tuple(float(f[LABEL].mean()) for f in (self.train, self.calib, self.test))

    def time_ranges(self) -> Tuple[Tuple[float, float], ...]:
        return tuple((float(f[TIME].min()), float(f[TIME].max())) for f in (self.train, self.calib, self.test))

    def assert_no_leakage(self) -> None:
        """Fail loudly if the folds overlap in time or share transactions.

        Called by `time_split` on every construction. A silent overlap here would
        invalidate every number downstream, so it is checked rather than trusted.
        """
        (tr_lo, tr_hi), (ca_lo, ca_hi), (te_lo, te_hi) = self.time_ranges()
        if not tr_hi <= ca_lo:
            raise AssertionError(f"train overlaps calib in time: {tr_hi} > {ca_lo}")
        if not ca_hi <= te_lo:
            raise AssertionError(f"calib overlaps test in time: {ca_hi} > {te_lo}")

        ids = [set(f[ID]) for f in (self.train, self.calib, self.test)]
        if ids[0] & ids[1] or ids[1] & ids[2] or ids[0] & ids[2]:
            raise AssertionError("folds share TransactionIDs")

    def describe(self) -> str:
        """The provenance block that belongs in the write-up."""
        names = ("train", "calib", "test")
        sizes = self.sizes
        rates = self.fraud_rates()
        ranges = self.time_ranges()
        total = sum(sizes)

        lines = [
            "Time-ordered split (no shuffling; folds are contiguous in TransactionDT)",
            f"{'fold':<8}{'rows':>10}{'share':>9}{'fraud':>9}{'day range':>20}",
        ]
        for name, n, rate, (lo, hi) in zip(names, sizes, rates, ranges):
            lines.append(
                f"{name:<8}{n:>10,}{n / total:>8.1%}{rate:>9.2%}"
                f"{f'{lo / SECONDS_PER_DAY:.0f} - {hi / SECONDS_PER_DAY:.0f}':>20}"
            )
        lines.append(f"{'total':<8}{total:>10,}{'':>9}{sum(sizes[i] * rates[i] for i in range(3)) / total:>9.2%}")
        return "\n".join(lines)


def time_split(
    df: pd.DataFrame,
    train_frac: float = 0.70,
    calib_frac: float = 0.15,
) -> Split:
    """Split chronologically into train / calibration / held-out test.

    Cuts on the *time* axis rather than by row index so that the boundary is a
    moment, not a position — transactions sharing a second are never divided
    across folds.
    """
    if not 0 < train_frac < 1 or not 0 < calib_frac < 1:
        raise ValueError("fractions must lie in (0, 1)")
    if train_frac + calib_frac >= 1.0:
        raise ValueError("train_frac + calib_frac must leave room for a test fold")
    if TIME not in df.columns:
        raise KeyError(f"{TIME} column is required for a time split")

    ordered = df.sort_values(TIME, kind="mergesort").reset_index(drop=True)
    t = ordered[TIME].to_numpy()

    cut_train = float(pd.Series(t).quantile(train_frac))
    cut_calib = float(pd.Series(t).quantile(train_frac + calib_frac))

    split = Split(
        train=ordered[ordered[TIME] <= cut_train].copy(),
        calib=ordered[(ordered[TIME] > cut_train) & (ordered[TIME] <= cut_calib)].copy(),
        test=ordered[ordered[TIME] > cut_calib].copy(),
    )
    split.assert_no_leakage()
    return split


def verify_label(df: pd.DataFrame) -> dict:
    """Check the label is what the documentation says before trusting it.

    Vesta documents `isFraud` as a reported chargeback on the card. We cannot
    verify that claim from the data itself, but we can verify the label's
    *shape* — binary, heavily imbalanced, roughly 3.5% positive — and refuse to
    proceed quietly if the file is not what we expect.
    """
    if LABEL not in df.columns:
        raise KeyError(f"{LABEL} not found; columns start with {list(df.columns)[:8]}")

    values = set(pd.unique(df[LABEL].dropna()))
    if not values <= {0, 1}:
        raise ValueError(f"{LABEL} is not binary: found {sorted(values)[:8]}")

    rate = float(df[LABEL].mean())
    span_days = float(df[TIME].max() - df[TIME].min()) / SECONDS_PER_DAY

    return {
        "rows": len(df),
        "positives": int(df[LABEL].sum()),
        "fraud_rate": rate,
        "span_days": span_days,
        "documented_definition": "reported chargeback on the card (Vesta / IEEE-CIS)",
        "rate_matches_documentation": 0.025 <= rate <= 0.045,
    }
