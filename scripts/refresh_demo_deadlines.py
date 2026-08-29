"""Refresh the synthetic response deadlines in data/golden_cases.json.

`respond_by` is display-only — no rule reads it — but a fixture whose deadline
has already elapsed makes every case render as "Deadline passed / CRITICAL",
which hides the urgency tiers entirely. Re-run this whenever the fixtures age out:

    python scripts/refresh_demo_deadlines.py

Deliberately spreads cases across all three tiers (<6h critical, <24h high,
else normal) so the deadline treatment is actually visible in a demo.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA = Path(__file__).parent.parent / "data" / "golden_cases.json"

# Hours from now, cycled across the case list.
OFFSETS = [3, 5, 14, 20, 40, 62, 86, 110]


def main() -> None:
    cases = json.loads(DATA.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)

    for idx, case in enumerate(cases):
        deadline = now + timedelta(hours=OFFSETS[idx % len(OFFSETS)])
        case.setdefault("dispute", {})["respond_by"] = (
            deadline.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        )

    DATA.write_text(json.dumps(cases, indent=2) + "\n", encoding="utf-8")

    tiers = {"critical": 0, "high": 0, "normal": 0}
    for case in cases:
        hours = (
            datetime.fromisoformat(case["dispute"]["respond_by"].replace("Z", "+00:00")) - now
        ).total_seconds() / 3600
        tiers["critical" if hours < 6 else "high" if hours < 24 else "normal"] += 1

    print(f"Refreshed {len(cases)} deadlines in {DATA.name}")
    print(f"  critical (<6h): {tiers['critical']}   high (<24h): {tiers['high']}   normal: {tiers['normal']}")


if __name__ == "__main__":
    main()
