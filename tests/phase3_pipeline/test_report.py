import pandas as pd

from conftest import SALES_COLS, W3, WEATHER_COLS
from demandfcst import storage
from demandfcst.pipeline import process, report

SHEETS = {"Summary", "Checks", "Sanity", "Deliveries", "Corrections", "Weekly volumes", "Unit tests"}


def test_report_has_every_sheet_and_passes_on_clean_data(small_raw, tmp_path):
    process.run(small_raw.raw, small_raw.processed, small_raw.start)
    path, status = report.make_report(small_raw.raw, small_raw.processed, storage.join(tmp_path, "reports"))
    assert path.endswith("data_quality_2025-01-12.xlsx")
    sheets = pd.read_excel(path, sheet_name=None)
    assert set(sheets) == SHEETS
    assert (sheets["Checks"]["level"] == "pass").all()
    assert status == "PASS"


def test_report_fails_when_processing_missed_the_latest_delivery(small_raw, tmp_path):
    process.run(small_raw.raw, small_raw.processed, small_raw.start)
    small_raw.put(small_raw.raw, "sellin_daily", W3, [("2025-01-14", "SP", "001", 2.0)], SALES_COLS)
    small_raw.put(small_raw.raw, "weather_weekly", W3,
                  [("SP", "2025-01-13", 30, 20, 25, 1.0), ("RJ", "2025-01-13", 30, 20, 25, 1.0)], WEATHER_COLS)
    _, status = report.make_report(small_raw.raw, small_raw.processed, storage.join(tmp_path, "reports"))
    assert status == "FAIL"                                     # new valid delivery, but not processed yet


def test_unit_test_results_are_read_from_junit_xml(tmp_path):
    xml = tmp_path / "pytest.xml"
    xml.write_text('<?xml version="1.0" encoding="utf-8"?><testsuites>'
                   '<testsuite name="pytest" tests="2" failures="1" errors="0" skipped="0" '
                   'timestamp="2026-10-26T08:00:00"><testcase classname="tests.a" name="test_ok"/>'
                   '<testcase classname="tests.a" name="test_bad"><failure message="x"/></testcase>'
                   '</testsuite></testsuites>', encoding="utf-8")
    summary, cases = report.unit_tests(str(xml))
    assert summary["tests"] == 2 and summary["failures"] == 1
    assert list(cases["outcome"]) == ["passed", "failure"]
