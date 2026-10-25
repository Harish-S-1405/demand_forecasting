"""Weekly data quality report (Excel) for the latest delivery, for the manager.

Run after ingest and process. For the unit-test line, run pytest with --junitxml first:
    python -m pytest -q --junitxml=outputs/reports/pytest.xml
    python scripts/phase3_pipeline/report.py
Writes outputs/reports/data_quality_<ingest_date>.xlsx, and uploads it to
s3://<bucket>/reports/ when storage = "s3".
"""

import logging

from demandfcst import config, storage
from demandfcst.pipeline import report

log = logging.getLogger("report")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    paths = config.pipeline_paths()
    local_dir = config.locations(storage="local")["reports"]
    remote_dir = config.locations()["reports"]

    path, status = report.make_report(paths["raw"], paths["processed"], local_dir,
                                      tests_xml=storage.join(local_dir, "pytest.xml"),
                                      project_root=config.PROJECT_ROOT)
    log.info("report: %s -> status %s", path, status)
    if remote_dir != local_dir:
        remote = storage.join(remote_dir, path.rsplit("/", 1)[-1])
        storage.copy_file(path, remote)
        log.info("uploaded: %s", remote)


if __name__ == "__main__":
    main()
