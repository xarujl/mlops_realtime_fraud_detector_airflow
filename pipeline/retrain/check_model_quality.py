"""Сравнение кандидата с текущей production-моделью перед публикацией."""

import json
import logging

from airflow.exceptions import AirflowSkipException

from pipeline.settings import MODELS_DIR

logger = logging.getLogger(__name__)


def check_model_quality(train_info: dict) -> dict:
    """Проверяет метрики кандидата; при ухудшении блокирует production-публикацию.

    ROC-AUC — главная метрика и не должна быть ниже baseline; F1 допускает
    колебание до 0.01. Если baseline отсутствует (первый прогон), кандидат
    допускается. При отказе указатель месяца и current dataset не меняются.
    """
    latest_file = MODELS_DIR / "latest.txt"
    if not latest_file.exists():
        logger.info("Production baseline отсутствует, первый кандидат допускается.")
        return train_info

    current_version = latest_file.read_text(encoding="utf-8").strip()
    baseline_path = MODELS_DIR / f"my_catboost_{current_version}.metrics.json"
    if not baseline_path.exists():
        logger.info("Нет метрик baseline %s; кандидат допускается.", current_version)
        return train_info

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    candidate_auc = train_info["roc_auc"]
    baseline_auc = baseline.get("roc_auc")
    candidate_f1 = train_info["f1"]
    baseline_f1 = baseline.get("f1")
    if candidate_auc is None or baseline_auc is None:
        raise AirflowSkipException("Сравнение невозможно: ROC-AUC отсутствует у кандидата или baseline.")

    auc_ok = candidate_auc >= baseline_auc
    f1_ok = baseline_f1 is None or candidate_f1 >= baseline_f1 - 0.01
    if not (auc_ok and f1_ok):
        raise AirflowSkipException(
            "Кандидат не прошёл quality gate: "
            f"ROC-AUC {candidate_auc:.4f} vs {baseline_auc:.4f}, "
            f"F1 {candidate_f1:.4f} vs {baseline_f1:.4f}; "
            "production-модель и указатель месяца оставлены без изменений."
        )

    logger.info("Кандидат прошёл quality gate относительно %s.", current_version)
    return train_info
