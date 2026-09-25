"""Datasets for the AAF study.

1. Archival: the course-supplied five-asset workbook (``HW3_dataset.xlsx``), monthly
   1983-08..2023-01, decimal returns, RF in decimal per month. Imported locally; its
   redistribution rights are not established, so it is never committed.
2. Transfer: Kenneth French Data Library, "5 Industry Portfolios" (value-weighted, monthly)
   and the Fama/French factors file for RF. Published in PERCENT; -99.99 / -999 mark missing.
   Industry portfolios are research return series, not executable quotes.
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

HW3_ASSETS = ["Equity", "Bonds", "Credits", "HY", "Comm"]
HW3_FEATURES = [
    "US_Earnings_yield",
    "US_DIV_Yield",
    "Equity Volatility",
    "TED",
    "Credit Subindex",
    "Leverage Subindex",
    "Risk Subindex",
    "Non Financial Leverage Subindex",
    "Credit Spread",
    "Inflation",
    "IP YoY",
    "yields 10Y",
    "Term Spread",
    "CAPE",
]
FRENCH_BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
FRENCH_FILES = {
    "industries": "5_Industry_Portfolios_CSV.zip",
    "factors": "F-F_Research_Data_Factors_CSV.zip",
}


def load_hw3(path: Path) -> pd.DataFrame:
    if not Path(path).exists():
        raise FileNotFoundError(
            f"{path} not found. The archival study needs the course-supplied workbook "
            "HW3_dataset.xlsx, which is not redistributed (docs/data.md). The public French "
            "study does not need it: make data-public reproduce-public."
        )
    df = pd.read_excel(path, sheet_name="Sheet1")
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").set_index("Date")
    missing = [c for c in HW3_ASSETS + HW3_FEATURES + ["RF"] if c not in df]
    if missing:
        raise ValueError(f"HW3 workbook lacks columns {missing}")
    return df


def hw3_design(df: pd.DataFrame, feature_lag: int = 1):
    """Pairs (Z_{t-lag}, r_t - rf_t). A one-month lag is the notebook/paper convention; it does
    NOT establish that each macro series was published (or unrevised) by month end."""
    Z = df[HW3_FEATURES].shift(feature_lag)
    X = df[HW3_ASSETS].sub(df["RF"], axis=0)
    ok = Z.notna().all(axis=1) & X.notna().all(axis=1)
    return Z[ok], X[ok], df.loc[ok, "RF"]


def download_french(out_dir: Path) -> dict:
    """Download the two library files and compare them with the recorded snapshot.

    The library revises history occasionally: a download that differs from the snapshot in
    ``french_manifest.json`` is reported (the published results used the recorded one)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    man = out_dir / "french_manifest.json"
    recorded = json.loads(man.read_text()) if man.exists() else {}
    rec = {}
    for key, name in FRENCH_FILES.items():
        r = requests.get(FRENCH_BASE + name, timeout=60)
        r.raise_for_status()
        if not r.content.startswith(b"PK"):
            raise RuntimeError(f"{name}: response is not a zip archive")
        (out_dir / name).write_bytes(r.content)
        rec[key] = {
            "url": FRENCH_BASE + name,
            "sha256": hashlib.sha256(r.content).hexdigest(),
            "bytes": len(r.content),
            "last_modified": r.headers.get("Last-Modified"),
            "retrieved_utc": datetime.now(timezone.utc).isoformat(),
        }
    for key, r in rec.items():
        old = recorded.get(key, {}).get("sha256")
        if old and old != r["sha256"]:
            print(
                f"WARNING {FRENCH_FILES[key]}: differs from the recorded snapshot (sha256 "
                f"{old[:12]}..., last modified {recorded[key].get('last_modified')}); the library "
                "has been revised, so reruns will not match the published numbers exactly."
            )
    man.write_text(json.dumps(rec, indent=1))
    return rec


def _read_zip_text(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".csv")]
        if len(names) != 1:
            raise ValueError(f"expected one CSV in {path}, found {names}")
        return z.read(names[0]).decode("latin-1")


def parse_french_monthly(text: str, section_title: str | None = None) -> pd.DataFrame:
    """First monthly (YYYYMM) table after ``section_title`` (or the first table).

    Values are percent; -99.99 and -999 are missing-data sentinels and become NaN.
    """
    lines = text.splitlines()
    start = 0
    if section_title is not None:
        hits = [i for i, ln in enumerate(lines) if section_title.lower() in ln.lower()]
        if not hits:
            raise ValueError(f"section '{section_title}' not found")
        start = hits[0]
    header_idx = None
    for i in range(start, len(lines)):
        if (
            re.match(r"^\s*,", lines[i])
            and i + 1 < len(lines)
            and re.match(r"^\s*\d{6}\s*,", lines[i + 1])
        ):
            header_idx = i
            break
    if header_idx is None:
        raise ValueError("no monthly table found")
    cols = [c.strip() for c in lines[header_idx].split(",")[1:]]
    rows = []
    for ln in lines[header_idx + 1 :]:
        m = re.match(r"^\s*(\d{6})\s*,(.*)$", ln)
        if not m:
            break
        vals = [float(v) for v in m.group(2).split(",")]
        rows.append([m.group(1)] + vals)
    df = pd.DataFrame(rows, columns=["yyyymm"] + cols)
    df.index = pd.to_datetime(df.pop("yyyymm"), format="%Y%m") + pd.offsets.MonthEnd(0)
    df = df.replace([-99.99, -999.0], np.nan)
    return df


def load_french(data_dir: Path) -> tuple[pd.DataFrame, pd.Series]:
    """Industry total returns and RF, both in DECIMAL per month, on common months."""
    for name in FRENCH_FILES.values():
        if not (Path(data_dir) / name).exists():
            raise FileNotFoundError(
                f"{Path(data_dir) / name} not found: download the public Kenneth French "
                "library files with `make data-public`."
            )
    ind = parse_french_monthly(
        _read_zip_text(Path(data_dir) / FRENCH_FILES["industries"]),
        "Average Value Weighted Returns -- Monthly",
    )
    fac = parse_french_monthly(_read_zip_text(Path(data_dir) / FRENCH_FILES["factors"]))
    ind, rf = ind / 100.0, fac["RF"] / 100.0
    common = ind.index.intersection(rf.index)
    return ind.loc[common], rf.loc[common]


def french_design(ind: pd.DataFrame, rf: pd.Series):
    """Return-derived features known at the end of month t-1, paired with excess r_t.

    Per industry: 12-month and 1-month total return, 12-month volatility. Market level
    (equal-weight of the five): 12-month return, 3-month volatility, cross-industry dispersion
    of 12-month returns. 18 features; all computed from data up to t-1.
    """
    feats = {}
    lr = np.log1p(ind)
    for c in ind.columns:
        feats[f"{c}_mom12"] = lr[c].rolling(12).sum()
        feats[f"{c}_ret1"] = ind[c]
        feats[f"{c}_vol12"] = ind[c].rolling(12).std()
    mkt = ind.mean(axis=1)
    feats["mkt_mom12"] = np.log1p(mkt).rolling(12).sum()
    feats["mkt_vol3"] = mkt.rolling(3).std()
    feats["disp_mom12"] = pd.DataFrame({c: feats[f"{c}_mom12"] for c in ind.columns}).std(axis=1)
    Z = pd.DataFrame(feats).shift(1)
    X = ind.sub(rf, axis=0)
    ok = Z.notna().all(axis=1) & X.notna().all(axis=1)
    return Z[ok], X[ok], rf[ok]
