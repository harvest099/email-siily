"""fetch 域入口：暴露 IMAP 抓取。"""
from em.fetch.imap_fetch import fetch_recent, get_text, decode_mime_words

__all__ = ["fetch_recent", "get_text", "decode_mime_words"]
