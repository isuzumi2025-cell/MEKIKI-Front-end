"""
ParagraphMatcher latency benchmark harness.

Measures first-run and rerun latency on synthetic N x M candidates.
Can enforce SLO thresholds and emit a JSON report.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import io
import json
import random
import statistics
import string
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.paragraph_matcher import ParagraphEntry, ParagraphMatcher


WORDS = [
    "alpha",
    "beta",
    "gamma",
    "delta",
    "epsilon",
    "zeta",
    "eta",
    "theta",
    "iota",
    "kappa",
    "lambda",
    "mu",
    "nu",
    "xi",
    "omicron",
    "pi",
    "rho",
    "sigma",
    "tau",
    "upsilon",
]

DEFAULT_KYUSHU_METADATA_CSV = ROOT / "exports" / "metadata_20260206_031356.csv"
DATASET_SYNTHETIC = "synthetic"
DATASET_KYUSHU_TEMPLE = "kyushu-temple"


def _make_text(seed: int) -> str:
    rnd = random.Random(seed)
    words = WORDS[:]
    rnd.shuffle(words)
    pick = rnd.randint(8, 14)
    suffix = "".join(rnd.choices(string.ascii_lowercase, k=rnd.randint(6, 20)))
    return " ".join(words[:pick]) + " " + suffix


def _make_entries(count: int, source: str, seed_offset: int) -> List[ParagraphEntry]:
    entries: List[ParagraphEntry] = []
    prefix = "W" if source == "web" else "P"
    for i in range(count):
        y = i * 12
        entries.append(
            ParagraphEntry(
                id=f"{prefix}-{i:03d}",
                source=source,
                text=_make_text(seed_offset + i),
                rect=[0, y, 100, y + 10],
            )
        )
    return entries


def _load_entries_from_metadata_csv(
    csv_path: Path,
    web_count: int,
    pdf_count: int,
) -> Tuple[List[ParagraphEntry], List[ParagraphEntry]]:
    if web_count <= 0 or pdf_count <= 0:
        raise ValueError("web_count and pdf_count must be positive integers.")
    if not csv_path.exists():
        raise FileNotFoundError(f"Kyushu dataset CSV not found: {csv_path}")

    web_entries: List[ParagraphEntry] = []
    pdf_entries: List[ParagraphEntry] = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            source = (row.get("Source") or "").strip().lower()
            if source not in {"web", "pdf"}:
                continue
            if source == "web" and len(web_entries) >= web_count:
                continue
            if source == "pdf" and len(pdf_entries) >= pdf_count:
                continue

            try:
                rect = [
                    int(row["X1"]),
                    int(row["Y1"]),
                    int(row["X2"]),
                    int(row["Y2"]),
                ]
            except (TypeError, ValueError, KeyError):
                continue

            entry = ParagraphEntry(
                id=(row.get("ID") or "").strip(),
                source=source,
                text=row.get("Text") or "",
                rect=rect,
            )
            if source == "web":
                web_entries.append(entry)
            else:
                pdf_entries.append(entry)

            if len(web_entries) >= web_count and len(pdf_entries) >= pdf_count:
                break

    if len(web_entries) < web_count or len(pdf_entries) < pdf_count:
        raise ValueError(
            f"Insufficient entries in {csv_path}: "
            f"web={len(web_entries)}/{web_count}, pdf={len(pdf_entries)}/{pdf_count}"
        )

    return web_entries, pdf_entries


def _percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = int(round((len(ordered) - 1) * pct))
    idx = max(0, min(len(ordered) - 1, idx))
    return ordered[idx]


def _measure_once(matcher: ParagraphMatcher, web: List[ParagraphEntry], pdf: List[ParagraphEntry]) -> float:
    start = time.perf_counter()
    # Benchmark core matching cost without stdout overhead.
    with contextlib.redirect_stdout(io.StringIO()):
        matcher.match_paragraphs(web, pdf)
    return time.perf_counter() - start


def _summarize(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"avg": 0.0, "min": 0.0, "max": 0.0, "p95": 0.0}
    return {
        "avg": statistics.mean(values),
        "min": min(values),
        "max": max(values),
        "p95": _percentile(values, 0.95),
    }


def run_benchmark(
    web_count: int,
    pdf_count: int,
    repeats: int,
    first_slo_sec: float,
    rerun_slo_sec: float,
    dataset: str = DATASET_KYUSHU_TEMPLE,
    kyushu_csv: Path = DEFAULT_KYUSHU_METADATA_CSV,
) -> Dict[str, object]:
    first_runs: List[float] = []
    reruns: List[float] = []
    samples: List[Dict[str, float]] = []

    web_fixture: List[ParagraphEntry] = []
    pdf_fixture: List[ParagraphEntry] = []
    if dataset == DATASET_KYUSHU_TEMPLE:
        web_fixture, pdf_fixture = _load_entries_from_metadata_csv(
            csv_path=kyushu_csv,
            web_count=web_count,
            pdf_count=pdf_count,
        )

    for i in range(repeats):
        matcher = ParagraphMatcher()
        if dataset == DATASET_SYNTHETIC:
            web = _make_entries(web_count, "web", seed_offset=i * 101)
            pdf = _make_entries(pdf_count, "pdf", seed_offset=i * 101 + 7)
        else:
            web = list(web_fixture)
            pdf = list(pdf_fixture)

        t_first = _measure_once(matcher, web, pdf)
        t_rerun = _measure_once(matcher, web, pdf)

        first_runs.append(t_first)
        reruns.append(t_rerun)
        samples.append(
            {
                "iteration": i + 1,
                "first_sec": t_first,
                "rerun_sec": t_rerun,
            }
        )

    first_summary = _summarize(first_runs)
    rerun_summary = _summarize(reruns)

    passed = first_summary["avg"] <= first_slo_sec and rerun_summary["avg"] <= rerun_slo_sec
    return {
        "config": {
            "dataset": dataset,
            "web_count": web_count,
            "pdf_count": pdf_count,
            "repeats": repeats,
            "slo_first_sec": first_slo_sec,
            "slo_rerun_sec": rerun_slo_sec,
            "dataset_path": str(kyushu_csv) if dataset == DATASET_KYUSHU_TEMPLE else "",
        },
        "samples": samples,
        "first_run": first_summary,
        "rerun": rerun_summary,
        "slo_passed": passed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark ParagraphMatcher latency.")
    parser.add_argument(
        "--dataset",
        choices=[DATASET_KYUSHU_TEMPLE, DATASET_SYNTHETIC],
        default=DATASET_KYUSHU_TEMPLE,
    )
    parser.add_argument("--web-count", type=int, default=100)
    parser.add_argument("--pdf-count", type=int, default=100)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--slo-first-sec", type=float, default=2.0)
    parser.add_argument("--slo-rerun-sec", type=float, default=0.5)
    parser.add_argument("--kyushu-csv", type=str, default=str(DEFAULT_KYUSHU_METADATA_CSV))
    parser.add_argument("--output-json", type=str, default="")
    parser.add_argument("--enforce-slo", action="store_true")
    args = parser.parse_args()

    result = run_benchmark(
        web_count=args.web_count,
        pdf_count=args.pdf_count,
        repeats=args.repeats,
        first_slo_sec=args.slo_first_sec,
        rerun_slo_sec=args.slo_rerun_sec,
        dataset=args.dataset,
        kyushu_csv=Path(args.kyushu_csv),
    )

    print("ParagraphMatcher latency benchmark")
    print(f"- dataset: {args.dataset}")
    if args.dataset == DATASET_KYUSHU_TEMPLE:
        print(f"- dataset_path: {Path(args.kyushu_csv)}")
    print(
        f"- size: {args.web_count} x {args.pdf_count}, repeats: {args.repeats}"
    )
    print(
        f"- first avg: {result['first_run']['avg']:.4f}s (SLO <= {args.slo_first_sec:.4f}s)"
    )
    print(
        f"- rerun avg: {result['rerun']['avg']:.4f}s (SLO <= {args.slo_rerun_sec:.4f}s)"
    )
    print(f"- slo_passed: {result['slo_passed']}")

    if args.output_json:
        out = Path(args.output_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"- wrote report: {out}")

    if args.enforce_slo and not result["slo_passed"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
