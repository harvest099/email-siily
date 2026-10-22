"""storage 域入口：暴露 SQLite 存储 (按账号分库)。"""
from em.storage.sqlite_store import (
    connect,
    upsert_mail,
    store_classification,
    query_date_range,
    latest_unclassified,
    migrate_json_if_needed,
    db_path_for,
    DEFAULT_DB,
    DATA_DIR,
)

__all__ = [
    "connect", "upsert_mail", "store_classification", "query_date_range",
    "latest_unclassified", "migrate_json_if_needed", "db_path_for",
    "DEFAULT_DB", "DATA_DIR",
]
