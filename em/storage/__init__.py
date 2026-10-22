"""storage 域入口：暴露 SQLite 存储。"""
from em.storage.sqlite_store import (
    connect,
    upsert_mail,
    store_classification,
    query_date_range,
    latest_unclassified,
    migrate_json_if_needed,
    DB_PATH,
)

__all__ = [
    "connect", "upsert_mail", "store_classification", "query_date_range",
    "latest_unclassified", "migrate_json_if_needed", "DB_PATH",
]
