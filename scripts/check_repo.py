"""CI check for this repository: its documents' links resolve and its data files parse.

This repo is a benchmark (JSONL data, Markdown write-ups and one stdlib-only scoring script), so
what can silently break is: a relative link or in-page anchor that no longer points anywhere, an
external link that has gone dead, a data file that no longer parses, and the scoring script failing
to start.

    python scripts/check_repo.py            # everything
    python scripts/check_repo.py --offline  # skip external links (no network)

Exit 1 on any failure, listing each one. Stdlib only, so CI needs no install step.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
BARE_URL = re.compile(r"https?://[^\s)>\]`\"']+")
HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*#*\s*$")
_RETRIES = 3
_TIMEOUT_SECONDS = 20


def _tracked(pattern: str) -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", pattern], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return [ROOT / p for p in out.stdout.splitlines() if p]


def _anchors(md: Path) -> set[str]:
    """GitHub's heading slugs: lowercase, punctuation dropped, spaces to hyphens, repeats -1, -2."""
    seen: dict[str, int] = {}
    slugs: set[str] = set()
    in_fence = False
    for line in md.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        m = None if in_fence else HEADING.match(line)
        if not m:
            continue
        text = re.sub(r"[`*_]|\[([^\]]*)\]\([^)]*\)", r"\1", m.group(1)).strip().lower()
        slug = re.sub(r"[^\w\- ]", "", text).replace(" ", "-")
        n = seen.get(slug, 0)
        seen[slug] = n + 1
        slugs.add(slug if n == 0 else f"{slug}-{n}")
    return slugs


def check_local_links(docs: list[Path]) -> tuple[list[str], set[str]]:
    errors: list[str] = []
    external: set[str] = set()
    for md in docs:
        text = md.read_text(encoding="utf-8")
        for target in LINK.findall(text):
            if target.startswith(("http://", "https://")):
                external.add(target)
                continue
            if target.startswith("mailto:"):
                continue
            path_part, _, anchor = target.partition("#")
            dest = md if not path_part else (md.parent / path_part).resolve()
            rel = md.relative_to(ROOT)
            if not dest.exists():
                errors.append(f"{rel}: link target does not exist: {target}")
            elif anchor and dest.suffix == ".md" and anchor.lower() not in _anchors(dest):
                errors.append(f"{rel}: no heading for anchor #{anchor} in {dest.relative_to(ROOT)}")
        external.update(u.rstrip(".,;:") for u in BARE_URL.findall(text))
    return errors, external


def _status(url: str) -> int | str:
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "eval-defect-bench-ci"})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:  # noqa: S310
            return int(resp.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return f"{type(exc).__name__}: {exc}"


def check_external_links(urls: set[str]) -> tuple[list[str], list[str]]:
    """A 404/410 (or an unreachable host after retries) fails. A 429 or 5xx after every retry is a
    warning, not a failure: it says the host is busy, not that the link is dead."""
    errors: list[str] = []
    warnings: list[str] = []
    for url in sorted(urls):
        result: int | str = ""
        for attempt in range(_RETRIES):
            result = _status(url)
            if isinstance(result, int) and (result < 400 or result in (404, 410)):
                break
            time.sleep(2 * (attempt + 1))
        if isinstance(result, int) and result < 400:
            continue
        if isinstance(result, int) and (result == 429 or result >= 500):
            warnings.append(f"{url}: HTTP {result} after {_RETRIES} tries (not counted as dead)")
        else:
            errors.append(f"{url}: {'HTTP ' + str(result) if isinstance(result, int) else result}")
    return errors, warnings


def check_data() -> list[str]:
    errors: list[str] = []
    for path in _tracked("*.json"):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            errors.append(f"{path.relative_to(ROOT)}: not valid JSON: {exc}")
    for path in _tracked("*.jsonl"):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                json.loads(line)
            except ValueError as exc:
                errors.append(f"{path.relative_to(ROOT)}:{n}: not valid JSON: {exc}")
    return errors


def check_score_script() -> list[str]:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "score.py"), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return [f"scripts/score.py --help exited {result.returncode}: {result.stderr.strip()}"]
    return []


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--offline", action="store_true", help="skip the external link check")
    args = ap.parse_args()

    docs = _tracked("*.md")
    link_errors, external = check_local_links(docs)
    errors = link_errors + check_data() + check_score_script()
    warnings: list[str] = []
    if not args.offline:
        ext_errors, warnings = check_external_links(external)
        errors += ext_errors

    for w in warnings:
        print(f"WARNING {w}")
    for e in errors:
        print(f"FAIL {e}")
    checked = f"{len(docs)} Markdown files, {len(external)} external links"
    checked += " (skipped, --offline)" if args.offline else ""
    if errors:
        print(f"FAILED: {len(errors)} problem(s); checked {checked}")
        return 1
    print(f"OK: checked {checked}, every JSON/JSONL file, and scripts/score.py --help")
    return 0


if __name__ == "__main__":
    sys.exit(main())
