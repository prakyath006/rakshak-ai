"""Generate 1,000 Unseen Benchmark Disputes with Hidden Ground Truth and Adversarial Noise."""

import json
import random
from pathlib import Path
from datetime import datetime, timedelta

import sys
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.generate_unseen_benchmark import generate_unseen_dataset


def main():
    random.seed(1337)  # Independent seed for 1,000-case evaluation
    cases = generate_unseen_dataset(1000)
    out_dir = Path(__file__).parent.parent / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "unseen_benchmark_1000.json"
    
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(cases, f, indent=2)

    print(f"Generated 1,000 unseen benchmark cases at {out_file}")


if __name__ == "__main__":
    main()
