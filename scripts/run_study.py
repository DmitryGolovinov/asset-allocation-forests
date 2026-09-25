"""Run an AAF study. The French transfer's `--mode final` is reserved for the final evaluation."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aaf.study import run  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=["archival_hw3", "transfer_french5"], required=True)
    ap.add_argument("--mode", choices=["dev", "final"], default="dev")
    ap.add_argument("--seeds", type=int, nargs="*", default=None)
    ap.add_argument("--leaf", choices=["equality", "relaxed"], default="equality")
    ap.add_argument("--compare-formulations", action="store_true")
    ap.add_argument(
        "--i-understand-this-is-the-final-evaluation", action="store_true", dest="confirm_final"
    )
    a = ap.parse_args()
    if a.mode == "final" and not a.confirm_final:
        sys.exit("final evaluation needs --i-understand-this-is-the-final-evaluation")
    if a.compare_formulations:
        import json

        from aaf.study import compare_formulations

        print(json.dumps(compare_formulations(ROOT, a.dataset, a.mode), indent=1))
        sys.exit(0)
    rec = run(ROOT, a.dataset, a.mode, a.seeds, leaf=a.leaf)
    print(rec["evaluation"], round(rec["runtime_seconds"], 1), "s")
