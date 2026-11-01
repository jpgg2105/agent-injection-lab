"""results/runs.jsonl -> results/REPORT.md (tables; the interpretation is written by hand)."""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

from .defences import DEFENCES

FAMILIES = ["hijack", "manipulation", "exfiltration"]


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def rate(rows: list[dict], key: str) -> str:
    n, k = len(rows), sum(bool(r.get(key)) for r in rows)
    if not n:
        return "–"
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {k / n:.0%} [{lo:.0%}, {hi:.0%}]"


def load(path: Path) -> list[dict]:
    """Finished runs, with any hand-review overrides from manual_review.json next to them applied."""
    latest = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if not r.get("error"):
            latest[(r["case"], r["defence"])] = r
    review = path.with_name("manual_review.json")
    if review.exists():
        for o in json.loads(review.read_text(encoding="utf-8"))["overrides"]:
            r = latest.get((o["case"], o["defence"]))
            if r is not None:
                r.setdefault("auto", {})[o["field"]] = r.get(o["field"])
                r[o["field"]] = o["value"]
                r["reviewed"] = o["reason"]
    return list(latest.values())


def write_report(path: Path) -> Path:
    rows = load(path)
    by = defaultdict(list)
    for r in rows:
        by[r["defence"]].append(r)
    defs = [d for d in DEFENCES if d in by]
    n_over = sum(1 for r in rows if r.get("reviewed"))
    L = ["# Agent injection lab: results", "", f"{len(rows)} finished runs."
         + (f" {n_over} automatic verdicts were overridden after reading the answers (see manual_review.json)." if n_over else ""), ""]
    L += ["## Attack success rate", "", "Share of attacks that worked, with 95% Wilson intervals.", "",
          "| Defence | all attacks | hijack (email sent) | hijack attempted | manipulation | exfiltration |", "|---|---|---|---|---|---|"]
    for d in defs:
        at = [r for r in by[d] if r["kind"] == "attack"]
        fam = {f: [r for r in at if r["family"] == f] for f in FAMILIES}
        L.append(f"| {d} | {rate(at, 'success')} | {rate(fam['hijack'], 'success')} | {rate(fam['hijack'], 'attempted')} | "
                 f"{rate(fam['manipulation'], 'success')} | {rate(fam['exfiltration'], 'success')} |")
    L += ["", "## Cost on clean tasks", "", "| Defence | task success (clean) | clean doc withheld | legit email blocked | task success under attack | calls per run | tokens per run (in/out) | seconds per run |",
          "|---|---|---|---|---|---|---|---|"]
    for d in defs:
        cl = [r for r in by[d] if r["kind"] == "clean"]
        at = [r for r in by[d] if r["kind"] == "attack"]
        calls = sum(r.get("calls", 0) + r.get("screen_calls", 0) for r in by[d]) / len(by[d])
        tin = sum(r.get("usage", {}).get("input_tokens", 0) for r in by[d]) / len(by[d])
        tout = sum(r.get("usage", {}).get("output_tokens", 0) for r in by[d]) / len(by[d])
        sec = sum(r.get("seconds", 0) for r in by[d]) / len(by[d])
        L.append(f"| {d} | {rate(cl, 'task_success')} | {rate(cl, 'clean_doc_withheld')} | {rate([r for r in cl if r.get('needs_send')], 'legit_email_blocked')} | "
                 f"{rate(at, 'task_success')} | {calls:.2f} | {tin:,.0f} / {tout:,.0f} | {sec:.1f} |")
    L += ["", "Seconds include waiting for the free tier's rate limit, so compare calls and tokens, not time.", "",
          "## By technique (no defence)", "", "| Technique | " + " | ".join(FAMILIES) + " |", "|---|---|---|---|"]
    techs = defaultdict(dict)
    for r in by.get("none", []):
        if r["kind"] == "attack":
            techs[r["technique"]][r["family"]] = "yes" if r["success"] else "no"
    for t, f in sorted(techs.items()):
        L.append(f"| {t} | " + " | ".join(f.get(x, "–") for x in FAMILIES) + " |")
    L += ["", "## Successful attacks per defence", ""]
    for d in defs:
        hits = [r for r in by[d] if r["kind"] == "attack" and r["success"]]
        L.append(f"- **{d}**: " + (", ".join(f"{r['case']} ({r['technique']})" for r in sorted(hits, key=lambda r: r["case"])) or "none"))
    retrieved = [r for r in rows if r["kind"] == "attack"]
    L += ["", f"Poisoned document reached the model (retrieved and not withheld) in "
          f"{sum(r.get('poison_retrieved') and not r.get('poison_withheld') for r in retrieved)}/{len(retrieved)} attack runs.", ""]
    out = path.with_name("REPORT.md")
    out.write_text("\n".join(L), encoding="utf-8")
    return out

