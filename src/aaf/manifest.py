"""Run manifests: what data, code, config, and environment produced an artifact."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def tree_hash(root: Path, patterns: tuple[str, ...] = ("src/**/*.py", "scripts/*.py")) -> str:
    """Hash of source files (path + content) so results can be tied to the exact code."""
    h = hashlib.sha256()
    root = Path(root)
    files = sorted({p for pat in patterns for p in root.glob(pat) if p.is_file()})
    for p in files:
        h.update(str(p.relative_to(root)).encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def git_commit(root: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    if out.returncode != 0:
        return None  # not a git repository yet: never fabricate a commit
    return out.stdout.strip() or None


def environment(packages: tuple[str, ...]) -> dict:
    versions = {}
    for p in packages:
        try:
            versions[p] = metadata.version(p)
        except metadata.PackageNotFoundError:
            versions[p] = None
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "packages": versions,
    }


def write_manifest(path: Path, record: dict, outputs: list[Path]) -> dict:
    record = dict(record)
    record["written_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    record["outputs"] = {str(p.name): sha256_file(p) for p in outputs if Path(p).exists()}
    tmp = Path(path).with_suffix(".tmp")
    tmp.write_text(json.dumps(record, indent=1, sort_keys=True, default=str))
    tmp.replace(path)
    return record
