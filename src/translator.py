import aiohttp
import os
import requests
import time
import asyncio
import threading
from collections import OrderedDict
from src.logger import logger

DEEPL_ENDPOINT = "https://api-free.deepl.com/v2/translate"

# キャッシュ設定
CACHE_MAX_ENTRIES = 500
CACHE_TTL_SECONDS = 600  # 10分

# レート制限設定（簡易的にリクエスト間隔と同時実行数を制御）
MIN_REQUEST_INTERVAL = 0.4  # 約2.5req/sec
MAX_CONCURRENT_REQUESTS = 2
RETRY_BACKOFF = [0.5, 1.0, 2.0]  # 429等のときの再試行待機


class _TranslationCache:
    """単純なLRUキャッシュ（TTL付き）"""

    def __init__(self, max_entries=CACHE_MAX_ENTRIES, ttl=CACHE_TTL_SECONDS):
        self.max_entries = max_entries
        self.ttl = ttl
        self._store = OrderedDict()
        self._lock = threading.Lock()

    def _cleanup(self):
        now = time.time()
        keys_to_remove = []
        for k, (ts, _) in list(self._store.items()):
            if now - ts > self.ttl:
                keys_to_remove.append(k)
        for k in keys_to_remove:
            self._store.pop(k, None)

        # サイズ超過分を削除
        while len(self._store) > self.max_entries:
            self._store.popitem(last=False)

    def get(self, key):
        with self._lock:
            self._cleanup()
            if key not in self._store:
                return None
            ts, value = self._store.pop(key)
            # 再挿入で新しい順に
            self._store[key] = (ts, value)
            return value

    def set(self, key, value):
        with self._lock:
            self._cleanup()
            self._store[key] = (time.time(), value)
            # 最新を末尾に
            self._store.move_to_end(key)
            self._cleanup()


class _RateLimiter:
    """簡易レートリミッター（最小間隔 & 同時実行数）"""

    def __init__(self, min_interval=MIN_REQUEST_INTERVAL, max_concurrent=MAX_CONCURRENT_REQUESTS):
        self.min_interval = min_interval
        self._last_time = 0.0
        self._lock = threading.Lock()
        self._sem_async = asyncio.Semaphore(max_concurrent)

    def wait_sync(self):
        with self._lock:
            now = time.monotonic()
            wait = self.min_interval - (now - self._last_time)
            if wait > 0:
                time.sleep(wait)
            self._last_time = time.monotonic()

    async def wait_async(self):
        async with self._sem_async:
            wait = 0.0
            # 同じロックを利用してインターバルを共有
            with self._lock:
                now = time.monotonic()
                wait = self.min_interval - (now - self._last_time)
                self._last_time = time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)


_cache = _TranslationCache()
_rate_limiter = _RateLimiter()
_translation_filters = []
_translation_dictionary = []
_stats = {
    "requests": 0,
    "cache_hits": 0,
    "filtered": 0,
    "errors": 0,
}


def _normalize_text(text):
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    return text


def _make_cache_key(text, mode, api_key):
    safe_key = api_key or ""
    return (text, mode, safe_key)


def set_translation_filters(filters):
    """翻訳フィルタの設定（部分一致で判定、lower比較）"""
    global _translation_filters
    _translation_filters = [f.strip().lower() for f in filters or [] if f]
    logger.info(f"Translation filters updated: {len(_translation_filters)} entries")


def set_translation_dictionary(entries):
    """翻訳前置換の辞書を設定"""
    global _translation_dictionary
    normalized = []
    for e in entries or []:
        if isinstance(e, dict):
            src = str(e.get("source", ""))
            tgt = str(e.get("target", ""))
            if src:
                normalized.append({"source": src, "target": tgt})
    _translation_dictionary = normalized
    logger.info(f"Translation dictionary updated: {len(_translation_dictionary)} entries")


def should_filter(text: str) -> bool:
    """フィルタに合致する場合 True"""
    if not text:
        return False
    lowered = text.lower()
    return any(f in lowered for f in _translation_filters)


def apply_translation_dictionary(text: str) -> str:
    """翻訳前に辞書置換を適用"""
    if not text:
        return text
    result = text
    for entry in _translation_dictionary:
        src = entry.get("source", "")
        tgt = entry.get("target", "")
        if src:
            result = result.replace(src, tgt)
    return result


def get_stats():
    return _stats.copy()


def _build_payload(text, mode, api_key):
    if mode == '英→日':
        source_lang = 'EN'
        target_lang = 'JA'
    elif mode == '日→英':
        source_lang = 'JA'
        target_lang = 'EN'
    else:
        source_lang = None
        target_lang = 'JA'

    data = {
        "auth_key": api_key,
        "text": text,
        "target_lang": target_lang,
        "tag_handling": "xml",
        "ignore_tags": "k",
    }
    if source_lang:
        data["source_lang"] = source_lang
    return data


async def _translate_http_async(payload):
    async with aiohttp.ClientSession() as session:
        async with session.post(DEEPL_ENDPOINT, data=payload) as resp:
            body = await resp.text()
            return resp.status, body, await resp.json() if resp.status == 200 else None


def _translate_http_sync(payload):
    resp = requests.post(DEEPL_ENDPOINT, data=payload)
    return resp.status_code, resp.text, resp.json() if resp.status_code == 200 else None


async def translate_text(text, mode, api_key):
    if not api_key:
        logger.error("DeepL API Key is missing.")
        return _normalize_text(text)

    text = _normalize_text(text)
    if not text.strip():
        return text

    # フィルタチェック
    if should_filter(text):
        _stats["filtered"] += 1
        logger.info("Translation skipped by filter")
        return ""

    # 辞書置換
    text = apply_translation_dictionary(text)

    cache_key = _make_cache_key(text, mode, api_key)
    cached = _cache.get(cache_key)
    if cached is not None:
        _stats["cache_hits"] += 1
        logger.debug("translate_text cache hit")
        return cached

    payload = _build_payload(text, mode, api_key)
    await _rate_limiter.wait_async()
    _stats["requests"] += 1

    for backoff in [0] + RETRY_BACKOFF:
        if backoff:
            await asyncio.sleep(backoff)
        try:
            status, body, result = await _translate_http_async(payload)
            if status == 200:
                translated = result["translations"][0]["text"]
                _cache.set(cache_key, translated)
                return translated
            elif status in (429, 503):
                logger.warning(f"DeepL rate limited ({status}). Retrying after {backoff}s...")
                continue
            else:
                logger.error(f"DeepL API Error: {status} {body}")
                break
        except Exception as e:
            logger.error(f"Exception during DeepL request: {e}", exc_info=True)
            _stats["errors"] += 1
            break

    return text


def translate_text_sync(text, mode, api_key):
    if not api_key:
        logger.error("DeepL API Key is missing.")
        return _normalize_text(text)

    text = _normalize_text(text)
    if not text.strip():
        return text

    if should_filter(text):
        _stats["filtered"] += 1
        logger.info("Translation skipped by filter")
        return ""

    text = apply_translation_dictionary(text)

    cache_key = _make_cache_key(text, mode, api_key)
    cached = _cache.get(cache_key)
    if cached is not None:
        _stats["cache_hits"] += 1
        logger.debug("translate_text_sync cache hit")
        return cached

    payload = _build_payload(text, mode, api_key)
    _rate_limiter.wait_sync()
    _stats["requests"] += 1

    for backoff in [0] + RETRY_BACKOFF:
        if backoff:
            time.sleep(backoff)
        try:
            status, body, result = _translate_http_sync(payload)
            if status == 200:
                translated = result["translations"][0]["text"]
                _cache.set(cache_key, translated)
                return translated
            elif status in (429, 503):
                logger.warning(f"DeepL rate limited ({status}). Retrying after {backoff}s...")
                continue
            else:
                logger.error(f"DeepL API Error: {status} {body}")
                break
        except Exception as e:
            logger.error(f"Exception during DeepL request: {e}", exc_info=True)
            _stats["errors"] += 1
            break

    return text
