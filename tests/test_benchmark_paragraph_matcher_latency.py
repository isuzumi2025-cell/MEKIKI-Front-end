import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "benchmark_paragraph_matcher_latency.py"
SPEC = importlib.util.spec_from_file_location("benchmark_paragraph_matcher_latency", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_load_entries_from_metadata_csv_extracts_requested_counts(tmp_path):
    csv_path = tmp_path / "metadata.csv"
    csv_path.write_text(
        "\n".join(
            [
                "ID,Source,Page,X1,Y1,X2,Y2,Width,Height,TextLength,Text",
                "W-001,web,1,10,20,110,120,100,100,5,web one",
                "P-001,pdf,1,11,21,111,121,100,100,5,pdf one",
                "W-002,web,1,12,22,112,122,100,100,5,web two",
                "P-002,pdf,1,13,23,113,123,100,100,5,pdf two",
            ]
        ),
        encoding="utf-8",
    )

    web, pdf = MODULE._load_entries_from_metadata_csv(csv_path, web_count=2, pdf_count=2)

    assert len(web) == 2
    assert len(pdf) == 2
    assert web[0].id == "W-001"
    assert web[0].rect == [10, 20, 110, 120]
    assert pdf[1].id == "P-002"
    assert pdf[1].rect == [13, 23, 113, 123]


def test_run_benchmark_synthetic_smoke():
    result = MODULE.run_benchmark(
        web_count=20,
        pdf_count=20,
        repeats=2,
        first_slo_sec=2.0,
        rerun_slo_sec=0.5,
        dataset=MODULE.DATASET_SYNTHETIC,
    )

    assert result["config"]["dataset"] == MODULE.DATASET_SYNTHETIC
    assert result["config"]["web_count"] == 20
    assert result["config"]["pdf_count"] == 20
    assert len(result["samples"]) == 2
    assert result["first_run"]["avg"] >= 0.0
    assert result["rerun"]["avg"] >= 0.0
