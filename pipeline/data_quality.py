"""SQL-проверки качества размеченной витрины и HTML-отчёт."""

import html
import logging
from datetime import datetime, timezone
from pathlib import Path

from pipeline.db import get_conn

logger = logging.getLogger(__name__)

REPORT_DIR = Path("/opt/airflow/reports")


def check_dataset_quality() -> dict:
    """Выполняет агрегатные DQ-проверки над labeled_transactions.

    Читает только агрегаты, поэтому отчёт не выгружает весь датасет в память.
    Возвращает сериализуемые результаты правил для следующей задачи DAG.
    """
    checks_sql = {
        "Есть данные": "SELECT count(*) FROM labeled_transactions",
        "Время заполнено": "SELECT count(*) FROM labeled_transactions WHERE transaction_time IS NULL",
        "Метка заполнена": "SELECT count(*) FROM labeled_transactions WHERE target IS NULL",
        "Метка бинарная (0/1)": "SELECT count(*) FROM labeled_transactions WHERE target NOT IN (0, 1)",
        "Сумма заполнена и неотрицательна": "SELECT count(*) FROM labeled_transactions WHERE amount IS NULL OR amount < 0",
        "Координаты клиента в диапазоне": "SELECT count(*) FROM labeled_transactions WHERE lat IS NULL OR lon IS NULL OR lat NOT BETWEEN -90 AND 90 OR lon NOT BETWEEN -180 AND 180",
        "Координаты продавца в диапазоне": "SELECT count(*) FROM labeled_transactions WHERE merchant_lat IS NULL OR merchant_lon IS NULL OR merchant_lat NOT BETWEEN -90 AND 90 OR merchant_lon NOT BETWEEN -180 AND 180",
        "Категория заполнена": "SELECT count(*) FROM labeled_transactions WHERE cat_id IS NULL OR btrim(cat_id) = ''",
    }
    conn = get_conn()
    try:
        results = []
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM labeled_transactions")
            row_count = int(cur.fetchone()[0])
            for name, query in checks_sql.items():
                cur.execute(query)
                value = int(cur.fetchone()[0])
                passed = row_count > 0 if name == "Есть данные" else value == 0
                results.append({"name": name, "value": value, "passed": passed})
    finally:
        conn.close()
    return {"checked_at": datetime.now(timezone.utc).isoformat(), "row_count": row_count, "checks": results}


def publish_quality_report(result: dict) -> str:
    """Сохраняет HTML-отчёт рядом с каталогом моделей, с уникальным именем."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    rows = "\n".join(
        "<tr><td>{}</td><td>{}</td><td class='{}'>{}</td></tr>".format(
            html.escape(check["name"]),
            check["value"],
            "ok" if check["passed"] else "fail",
            "PASS" if check["passed"] else "FAIL",
        )
        for check in result["checks"]
    )
    status = "PASS" if all(check["passed"] for check in result["checks"]) else "FAIL"
    report_path = REPORT_DIR / f"data_quality_{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.html"
    report_path.write_text(
        "<!doctype html><html lang='ru'><meta charset='utf-8'><title>Data Quality</title>"
        "<style>body{font:16px sans-serif;margin:2rem}table{border-collapse:collapse}"
        "td,th{border:1px solid #aaa;padding:.6rem}.ok{color:green}.fail{color:red}</style>"
        f"<h1>Data Quality: {status}</h1><p>Строк в витрине: {result['row_count']}</p>"
        f"<p>Проверено: {html.escape(result['checked_at'])}</p>"
        f"<table><tr><th>Правило</th><th>Нарушений / строк</th><th>Результат</th></tr>{rows}</table></html>",
        encoding="utf-8",
    )
    logger.info("HTML DQ report saved to %s", report_path)
    return str(report_path)
