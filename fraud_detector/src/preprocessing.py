import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def load_train_data():
    logger.info('Loading training data...')

    # Import Train dataset
    train = pd.read_csv('./train_data/train.csv')
    logger.info('Raw train data imported. Shape: %s', train.shape)

    # Add some features
    train = add_features(train)
    logger.info('Train data processed. Shape: %s', train.shape)

    return train


def add_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Создаёт собственные признаки: циклическое время, лог-сумму и географию."""
    result = frame.copy()
    timestamp = pd.to_datetime(result.pop("transaction_time"), errors="coerce")
    # Базовые календарные/географические признаки оставлены для совместимости
    # со стартовой моделью из образа; ниже добавляются новые признаки проекта.
    result["year"] = timestamp.dt.year
    result["month"] = timestamp.dt.month
    result["day"] = timestamp.dt.day
    result["hour"] = timestamp.dt.hour
    result["minute"] = timestamp.dt.minute
    result["weekend"] = (timestamp.dt.dayofweek >= 5).fillna(False).astype(int)
    lat1, lon1, lat2, lon2 = map(
        np.radians,
        [result["lat"], result["lon"], result["merchant_lat"], result["merchant_lon"]],
    )
    dlat, dlon = lat2 - lat1, lon2 - lon1
    haversine_a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    haversine_a = np.clip(haversine_a, 0, 1)
    result["haversine"] = 6371 * 2 * np.arctan2(np.sqrt(haversine_a), np.sqrt(1 - haversine_a))
    result["txn_hour_sin"] = np.sin(timestamp.dt.hour * 2 * np.pi / 24)
    result["txn_hour_cos"] = np.cos(timestamp.dt.hour * 2 * np.pi / 24)
    result["txn_weekday"] = timestamp.dt.dayofweek.fillna(-1).astype(int).astype(str)
    result["txn_is_weekend"] = (timestamp.dt.dayofweek >= 5).fillna(False).astype(int)
    result["amount_log1p"] = np.log1p(
        pd.to_numeric(result["amount"], errors="coerce").clip(lower=0).fillna(0)
    )
    result["customer_merchant_lat_delta"] = result["lat"] - result["merchant_lat"]
    result["customer_merchant_lon_delta"] = result["lon"] - result["merchant_lon"]
    # Идентифицирующие/свободнотекстовые поля не используем как модельные признаки.
    result = result.drop(columns=["name_1", "name_2", "street"], errors="ignore")
    return result


def run_preproc(input_df: pd.DataFrame, training: bool = False) -> pd.DataFrame:
    """Преобразует транзакции. Метка target разрешена только при подготовке обучения."""
    output = add_features(input_df)
    if not training:
        output = output.drop(columns=["target"], errors="ignore")
    logger.info("Feature engineering complete. Shape: %s", output.shape)
    return output
