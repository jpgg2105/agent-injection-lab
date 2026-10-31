"""python -m injection_lab.cli run [--fake] [--limit N] [--defences none,warning] [--cases REGEX]
   python -m injection_lab.cli report
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from .defences import DEFENCES
from .llm import GullibleFake, gemini_factory, load_env
from .report import write_report
from .runner import ROOT


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="injection_lab")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--fake", action="store_true", help="scripted offline model, to test the plumbing")
    r.add_argument("--limit", type=int, default=0)
    r.add_argument("--defences", default=",".join(DEFENCES))
    r.add_argument("--cases", default="", help="regex on case ids, e.g. 'hij-0[1-3]|clean-t0[12]'")
    r.add_argument("--model", default="gemini-3.5-flash-lite")
    r.add_argument("--rpm", type=float, default=12)
    r.add_argument("--reasoning-effort", default="low")
    r.add_argument("--concurrency", type=int, default=3)
    r.add_argument("--out", default="")
    sub.add_parser("report").add_argument("--out", default="")
    a = ap.parse_args(argv)
    default = ROOT / "results" / ("runs-fake.jsonl" if getattr(a, "fake", False) else "runs.jsonl")
    out = Path(a.out) if a.out else default
    if a.cmd == "report":
        print(write_report(out))
        return
    load_env(ROOT / ".env")
    factory = GullibleFake if a.fake else gemini_factory(a.model, a.rpm, a.reasoning_effort or None)
    failures = asyncio.run(asyncio.wait_for(_run(factory, out, a), timeout=None))
    print(f"\nReport: {write_report(out)}")
    if failures:
        print(f"{failures} runs failed and will be retried next time.")


async def _run(factory, out, a):
    from .runner import run_all
    return await run_all(factory, out, defences=[d for d in a.defences.split(",") if d], limit=a.limit,
                         concurrency=a.concurrency, case_filter=a.cases)


if __name__ == "__main__":
    main()
