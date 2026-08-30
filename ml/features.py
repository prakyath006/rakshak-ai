"""Feature engineering, including entity resolution.

THE HONEST-EVALUATION RULE THAT SHAPES THIS FILE
------------------------------------------------
Public solutions to this dataset routinely concatenate train and test before
computing frequency encodings and group aggregates. That wins Kaggle points and
would be fraud in production: it lets a training-time feature depend on
transactions that had not happened yet.

Every encoder here is therefore *fitted on train only* and applied to the later
folds, exactly as a deployed model would see them. Values that appear for the
first time in the test window map to a missing indicator rather than being
silently learned. This costs measurable performance versus the leaky version,
and reporting the honest number is the point.

ENTITY RESOLUTION — THE RING SIGNAL
-----------------------------------
IEEE-CIS has no user column, but one can be reconstructed. `D1` is documented as
days since the card began, so for a given card

    account_day = floor(TransactionDT / 86400) - D1

is approximately constant across that card's transactions. Combining it with
`card1` and `addr1` yields a latent account identifier. Once transactions are
grouped under it, ring behaviour becomes visible — velocity, how many distinct
cards or addresses an account touches, how much it spends relative to its own
history. This is what the brief calls an abuse ring, and it is the single most
valuable feature family in this dataset.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from ml.data import AMOUNT, ID, LABEL, SECONDS_PER_DAY, TIME

# Categoricals worth frequency-encoding. Raw cardinality is high, so the count of
# a value is more useful to a tree than the value itself.
FREQUENCY_COLUMNS: Sequence[str] = (
    "card1", "card2", "card3", "card5",
    "addr1", "addr2",
    "P_emaildomain", "R_emaildomain",
    "DeviceInfo", "id_30", "id_31", "id_33",
)

# Low-cardinality categoricals passed through as pandas categories for LightGBM.
CATEGORICAL_COLUMNS: Sequence[str] = (
    "ProductCD", "card4", "card6", "M1", "M2", "M3", "M4",
    "M5", "M6", "M7", "M8", "M9", "DeviceType",
)

UID_PARTS: Sequence[str] = ("card1", "addr1", "account_day")


def _account_day(df: pd.DataFrame) -> pd.Series:
    """Approximate day the card/account was opened.

    D1 is days-since-card-began, so subtracting it from the transaction day gives
    a value that stays put for one account and differs between accounts.
    """
    day = np.floor(df[TIME] / SECONDS_PER_DAY)
    if "D1" not in df.columns:
        return pd.Series(np.nan, index=df.index)
    return day - df["D1"]


def add_base_features(df: pd.DataFrame) -> pd.DataFrame:
    """Row-local features. No fitting, so these are safe to compute anywhere."""
    out = df.copy()

    day = np.floor(out[TIME] / SECONDS_PER_DAY)
    seconds_into_day = out[TIME] - day * SECONDS_PER_DAY
    out["hour"] = np.floor(seconds_into_day / 3600).astype("float32")
    out["weekday"] = (day % 7).astype("float32")
    out["day"] = day.astype("float32")

    # Card-testing and bot traffic cluster on round amounts; the cents portion of
    # a converted foreign amount is unusually uniform. Both are visible here.
    out["amt_log"] = np.log1p(out[AMOUNT]).astype("float32")
    cents = (out[AMOUNT] - np.floor(out[AMOUNT])).round(4)
    out["amt_cents"] = cents.astype("float32")
    out["amt_is_round"] = (cents == 0).astype("int8")

    out["account_day"] = _account_day(out).astype("float32")

    # A single string key for the latent account. Missing parts propagate, so an
    # unidentifiable transaction is not grouped with unrelated ones.
    parts = [out[c].astype("string") for c in UID_PARTS if c in out.columns]
    if parts:
        uid = parts[0]
        for p in parts[1:]:
            uid = uid.str.cat(p, sep="_", na_rep="?")
        out["uid"] = uid.where(~uid.str.contains(r"\?", na=True), other=pd.NA)
    else:
        out["uid"] = pd.NA

    for col in ("P_emaildomain", "R_emaildomain"):
        if col in out.columns:
            out[f"{col}_suffix"] = out[col].astype("string").str.split(".").str[-1]
    if {"P_emaildomain", "R_emaildomain"} <= set(out.columns):
        out["email_mismatch"] = (
            (out["P_emaildomain"] != out["R_emaildomain"])
            & out["P_emaildomain"].notna()
            & out["R_emaildomain"].notna()
        ).astype("int8")

    return out


@dataclass
class FeatureEncoder:
    """Fitted on train, applied to later folds. Never refitted on test.

    Holding the fitted state in an object — rather than computing encodings
    inline over a concatenated frame — is what makes the no-leakage rule
    enforceable instead of aspirational.
    """

    frequency_maps: Dict[str, pd.Series] = field(default_factory=dict)
    uid_stats: Optional[pd.DataFrame] = None
    fitted: bool = False

    # ------------------------------------------------------------------
    def fit(self, train: pd.DataFrame) -> "FeatureEncoder":
        base = add_base_features(train)

        for col in FREQUENCY_COLUMNS:
            if col in base.columns:
                self.frequency_maps[col] = base[col].value_counts(dropna=True)

        if base["uid"].notna().any():
            grouped = base.dropna(subset=["uid"]).groupby("uid", observed=True)
            self.uid_stats = pd.DataFrame({
                "uid_txn_count": grouped[ID].size(),
                "uid_amt_mean": grouped[AMOUNT].mean(),
                "uid_amt_std": grouped[AMOUNT].std(),
                "uid_day_span": grouped["day"].max() - grouped["day"].min(),
                "uid_n_cards": grouped["card1"].nunique() if "card1" in base.columns else 0,
                "uid_n_addr": grouped["addr1"].nunique() if "addr1" in base.columns else 0,
            })
            # Transactions per active day: the velocity signal that separates a
            # busy legitimate account from a card-testing burst.
            span = self.uid_stats["uid_day_span"].clip(lower=1)
            self.uid_stats["uid_velocity"] = self.uid_stats["uid_txn_count"] / span

        self.fitted = True
        return self

    # ------------------------------------------------------------------
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self.fitted:
            raise RuntimeError("FeatureEncoder.fit must be called on the train fold first")

        out = add_base_features(df)

        for col, counts in self.frequency_maps.items():
            if col in out.columns:
                # Unseen values get NaN, not zero: "never observed in training" and
                # "observed zero times" are different facts and a tree can use the
                # distinction.
                out[f"{col}_freq"] = out[col].map(counts).astype("float32")

        if self.uid_stats is not None:
            out = out.merge(self.uid_stats, left_on="uid", right_index=True, how="left")
            # How far this transaction sits from the account's own normal spend.
            std = out["uid_amt_std"].replace(0, np.nan)
            out["amt_vs_uid_mean"] = (out[AMOUNT] / out["uid_amt_mean"]).astype("float32")
            out["amt_zscore_in_uid"] = ((out[AMOUNT] - out["uid_amt_mean"]) / std).astype("float32")
            out["uid_is_new"] = out["uid_txn_count"].isna().astype("int8")

        # Text columns LightGBM cannot consume: keep the low-cardinality ones as
        # categories, and drop the rest — those are already represented by their
        # frequency encoding, which is the useful part of a high-cardinality key.
        for col in out.columns:
            if col in ("uid",) or not _is_text(out[col]):
                continue
            if col in CATEGORICAL_COLUMNS or out[col].nunique(dropna=True) <= MAX_CATEGORY_LEVELS:
                out[col] = out[col].astype("category")

        return out


MAX_CATEGORY_LEVELS = 64
"""Above this, a raw category is noise to a tree; its frequency encoding carries
the signal instead."""


def _is_text(series: pd.Series) -> bool:
    """True for object/string dtypes across pandas 2.x and 3.x.

    pandas 3.0 made `str` the default dtype for text, so a check for `object`
    alone silently lets string columns through to LightGBM, which rejects them.
    """
    return series.dtype == object or str(series.dtype) in ("string", "str")


def feature_columns(df: pd.DataFrame) -> List[str]:
    """Model inputs: numeric and categorical columns only.

    Selected by what the learner accepts rather than by listing exclusions — an
    exclusion list silently breaks whenever a dtype default changes upstream.

    `TransactionDT` is excluded deliberately. It is a position on the timeline,
    and because the split is chronological a tree would happily use it to
    memorise "late transactions are test transactions".
    """
    drop = {LABEL, ID, TIME, "uid"}
    keep: List[str] = []
    for col in df.columns:
        if col in drop:
            continue
        dtype = df[col].dtype
        if isinstance(dtype, pd.CategoricalDtype) or pd.api.types.is_numeric_dtype(dtype):
            keep.append(col)
    return keep


def build(train: pd.DataFrame, *later: pd.DataFrame):
    """Fit on train, transform every fold, return them with the column list."""
    encoder = FeatureEncoder().fit(train)
    frames = [encoder.transform(f) for f in (train, *later)]
    return encoder, frames, feature_columns(frames[0])
