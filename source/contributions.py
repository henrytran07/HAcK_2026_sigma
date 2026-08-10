import collections
import json
import os
import subprocess
import threading
import time
from pathlib import Path

from fastapi import APIRouter

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_FILE = BASE_DIR / "contributions.json"
CACHE_TTL = 300

TEXT_SKIP_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg",
    ".stl", ".step", ".pdf", ".pyc", ".swp",
    ".kicad_pcb", ".kicad_prl", ".kicad_pro", ".kicad_sch", ".kicad_sym",
}

SKIP_DIRS = ("__pycache__", ".vscode", "node_modules")

# Git usernames that belong to the same person — merged inside the tracker
# so the page is right even where .mailmap doesn't reach.
ALIASES = {
    "LoadingSomething": "Bertrand Wickam",
    "24bnguyen18-hue": "Bao Nguyen",
}


def _canonical(name):
    return ALIASES.get(name, name)

AREAS = [
    ("Firmware", ("circuit/code.py", "circuit/boot.py")),
    ("Circuit design", ("circuit/HAcK2026_instrument_kicad",)),
    ("3D model", ("model/",)),
    ("Backend", ("source/",)),
    ("Front end", ("templates/", "css/")),
]

# Work done in pairs at the bench doesn't show up in git — only whoever
# happened to run the commit does. Declare those collaborations here and
# credit for the matching files is split evenly between everyone listed.
CO_AUTHORS = {
    "circuit/HAcK2026_instrument_kicad": ["Dominic Agoncillo", "Bertrand Wickam"],
    "model/": ["Bao Nguyen"],
}

# Code written at the bench by one person and committed by another. Lines in
# these files are credited to the names listed instead of to git blame.
CODE_CREDIT = {
    "circuit/code.py": ["Bertrand Wickam"],
    "circuit/boot.py": ["Bertrand Wickam"],
}

_lock = threading.Lock()
_cache = {"at": 0.0, "data": None}


def _git(args):
    result = subprocess.run(
        ["git"] + args, cwd=BASE_DIR, capture_output=True,
        text=True, errors="replace", timeout=30
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git failed")
    return result.stdout


def _area_for(path):
    for name, prefixes in AREAS:
        if any(path == p or path.startswith(p) for p in prefixes):
            return name
    return "Other"


def _tracked_files():
    for path in _git(["ls-files"]).split("\n"):
        if not path or not (BASE_DIR / path).exists():
            continue
        if any(part in SKIP_DIRS for part in path.split("/")):
            continue
        yield path


def _blame(path):
    output = _git(["blame", "--line-porcelain", "-w", "-M", "-C", "--", path])
    counts = collections.Counter()
    for line in output.split("\n"):
        if line.startswith("author "):
            counts[_canonical(line[7:].strip())] += 1
    return counts


def _code_credit_for(path):
    for prefix, names in CODE_CREDIT.items():
        if path == prefix or path.startswith(prefix):
            return names
    return None


def _declared_for(path):
    for prefix, names in CO_AUTHORS.items():
        if path == prefix or path.startswith(prefix):
            return names
    return None


def _added_by(path):
    declared = _declared_for(path)
    if declared:
        return list(declared)
    output = _git(["log", "--diff-filter=A", "--format=%aN", "--", path])
    names = [_canonical(n) for n in output.split("\n") if n]
    return [names[-1]] if names else []


def compute():
    lines = collections.Counter()
    artifacts = collections.Counter()
    areas = collections.defaultdict(collections.Counter)
    area_kinds = collections.defaultdict(collections.Counter)
    area_totals = collections.Counter()
    files = []

    for path in _tracked_files():
        area = _area_for(path)
        extension = os.path.splitext(path)[1].lower()
        declared = _declared_for(path)

        if declared or extension in TEXT_SKIP_EXT:
            names = declared or _added_by(path)
            if names:
                for author in names:
                    artifacts[author] += 1
                    areas[area][author] += 1
                files.append({
                    "path": path,
                    "kind": "artifact",
                    "shared": len(names) > 1,
                    "authors": {a: 1 for a in names},
                })
                area_totals[area] += 1
                area_kinds[area]["artifact"] += 1
            continue

        counts = _blame(path)
        if not counts:
            continue

        credited = _code_credit_for(path)
        if credited:
            total = sum(counts.values())
            counts = collections.Counter({n: total // len(credited) for n in credited})
        lines.update(counts)
        areas[area].update(counts)
        area_totals[area] += sum(counts.values())
        area_kinds[area]["code"] += sum(counts.values())
        files.append({"path": path, "kind": "code", "authors": dict(counts)})

    commits = collections.Counter(
        _canonical(n) for n in _git(["log", "--format=%aN"]).split("\n") if n
    )

    authors = []
    for name in set(lines) | set(artifacts) | set(commits):
        if name == "Not Committed Yet":
            continue
        authors.append({
            "name": name,
            "lines": lines.get(name, 0),
            "artifacts": artifacts.get(name, 0),
            "commits": commits.get(name, 0),
        })
    authors.sort(key=lambda a: (-a["lines"], -a["artifacts"]))

    area_rows = []
    for name, _ in AREAS:
        counts = areas.get(name)
        if not counts:
            continue
        counts.pop("Not Committed Yet", None)
        if not counts:
            continue
        kinds = area_kinds.get(name, collections.Counter())
        if kinds["artifact"] and kinds["code"]:
            unit = "items"
        elif kinds["artifact"]:
            unit = "files"
        else:
            unit = "lines"

        area_rows.append({
            "area": name,
            "total": area_totals[name] if kinds["artifact"] else sum(counts.values()),
            "unit": unit,
            "shared": kinds["artifact"] > 0 and len(counts) > 1,
            "authors": {a: c for a, c in counts.most_common()},
        })

    return {
        "authors": authors,
        "areas": area_rows,
        "files": sorted(files, key=lambda f: f["path"]),
        "total_lines": sum(lines.values()),
        "total_artifacts": sum(artifacts.values()),
        "generated_at": time.time(),
        "source": "git",
    }


def _fallback():
    if CACHE_FILE.exists():
        try:
            data = json.loads(CACHE_FILE.read_text())
            data["source"] = "snapshot"
            return data
        except ValueError:
            pass
    return {
        "authors": [], "areas": [], "files": [],
        "total_lines": 0, "total_artifacts": 0,
        "generated_at": time.time(), "source": "unavailable",
    }


@router.get("/api/contributions")
def contributions():
    now = time.time()
    with _lock:
        if _cache["data"] and now - _cache["at"] < CACHE_TTL:
            return _cache["data"]

    try:
        data = compute()
        CACHE_FILE.write_text(json.dumps(data, indent=2))
    except (RuntimeError, OSError, subprocess.SubprocessError):
        data = _fallback()

    with _lock:
        _cache["at"] = now
        _cache["data"] = data
    return data