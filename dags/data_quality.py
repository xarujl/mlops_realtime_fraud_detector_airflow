"""DAG периодической проверки размеченной витрины и публикации HTML-отчёта."""

from datetime import datetime, timedelta

from airflow.decorators import dag, task

from pipeline.data_quality import check_dataset_quality, publish_quality_report


@dag(
    dag_id="data_quality",
    description="Проверяет labeled_transactions и публикует HTML-отчёт",
    schedule="*/5 * * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    dagrun_timeout=timedelta(minutes=10),
    default_args={"retries": 1, "retry_delay": timedelta(seconds=30)},
    tags=["mlops", "data-quality"],
)
def data_quality():
    """Связывает SQL-проверки данных и создание HTML-отчёта."""
    result = task(check_dataset_quality, task_id="check_dataset_quality")()
    task(publish_quality_report, task_id="publish_html_report")(result)


data_quality()
