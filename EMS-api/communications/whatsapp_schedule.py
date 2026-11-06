"""
Space WhatsApp sends so a bulk publish does not hit pair-rate limit 131056.

Meta's pair limit is 1 message per recipient per 6 seconds. A class
publish enqueues one task per parent in a single request. Those tasks
share one lane: each send is scheduled ``WHATSAPP_PAIR_INTERVAL_SECONDS``
after the previous one (default 6). The same number is also kept 6
seconds apart if a parent is queued twice (two children, or a retry
that was enqueued again).

The Celery countdown is the throttle. The worker does not sleep, and
the request that queued the logs does not wait. Redis keeps the lane
across workers. If Redis is down, an in-process lane is used so one
process still spaces its own burst.
"""

import logging
import threading
import time

from django.conf import settings

logger = logging.getLogger(__name__)

# Keep leftover lane keys from living forever after a burst.
_KEY_TTL_SECONDS = 24 * 60 * 60
_GLOBAL_KEY = 'ems:whatsapp:pair:global'

_LUA_RESERVE = """
local phone_key = KEYS[1]
local global_key = KEYS[2]
local now = tonumber(ARGV[1])
local interval = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])
local phone_next = tonumber(redis.call('GET', phone_key) or '0')
local global_next = tonumber(redis.call('GET', global_key) or '0')
local slot = now
if phone_next > slot then slot = phone_next end
if global_next > slot then slot = global_next end
local nxt = slot + interval
redis.call('SET', phone_key, tostring(nxt), 'EX', ttl)
redis.call('SET', global_key, tostring(nxt), 'EX', ttl)
return tostring(slot - now)
"""

_schedule = None
_redis_warned = False


def pair_interval_seconds():
    raw = getattr(settings, 'WHATSAPP_PAIR_INTERVAL_SECONDS', 6)
    try:
        interval = float(raw)
    except (TypeError, ValueError):
        return 6.0
    if interval < 0:
        return 0.0
    return interval


class MemorySchedule:
    """Single-process lane. Tests use this so Redis state cannot leak in."""

    def __init__(self):
        self._phone_next = {}
        self._global_next = 0.0
        self._lock = threading.Lock()

    def reserve(self, phone, *, now=None, interval=None):
        if interval is None:
            interval = pair_interval_seconds()
        interval = float(interval)
        now = float(time.time() if now is None else now)
        if interval <= 0:
            return 0.0
        with self._lock:
            phone_next = float(self._phone_next.get(phone, 0.0))
            slot = max(now, phone_next, self._global_next)
            nxt = slot + interval
            self._phone_next[phone] = nxt
            self._global_next = nxt
            return max(0.0, slot - now)

    def clear(self):
        with self._lock:
            self._phone_next.clear()
            self._global_next = 0.0


class RedisSchedule:
    """Lane shared by every Celery worker. ``reserve`` matches MemorySchedule."""

    def __init__(self, client):
        self.client = client

    def reserve(self, phone, *, now=None, interval=None):
        if interval is None:
            interval = pair_interval_seconds()
        interval = float(interval)
        now = float(time.time() if now is None else now)
        if interval <= 0:
            return 0.0
        phone_key = 'ems:whatsapp:pair:' + str(phone).lstrip('+')
        raw = self.client.eval(
            _LUA_RESERVE,
            2,
            phone_key,
            _GLOBAL_KEY,
            str(now),
            str(interval),
            str(_KEY_TTL_SECONDS),
        )
        countdown = float(raw)
        if countdown < 0:
            return 0.0
        return countdown


def _redis_client():
    global _redis_warned
    url = getattr(settings, 'REDIS_URL', '') or ''
    if not url:
        return None
    try:
        import redis
        client = redis.Redis.from_url(
            url,
            socket_connect_timeout=0.2,
            socket_timeout=0.2,
        )
        client.ping()
    except Exception:
        if not _redis_warned:
            logger.warning(
                'WhatsApp pair scheduler could not reach Redis; '
                'spacing sends inside this process only.'
            )
            _redis_warned = True
        return None
    return client


def _build_schedule():
    client = _redis_client()
    if client is None:
        return MemorySchedule()
    return RedisSchedule(client)


def get_schedule():
    global _schedule
    if _schedule is None:
        _schedule = _build_schedule()
    return _schedule


def use_memory_schedule():
    """Force the in-process lane. Tests call this so Redis cannot leak slots."""
    global _schedule
    _schedule = MemorySchedule()
    return _schedule


def reserve_pair_countdown(phone):
    """
    Seconds until this number may be sent.

    Zero means the task can run immediately. A positive value is the
    Celery countdown for ``send_notification``.
    """
    if not phone:
        return 0.0
    interval = pair_interval_seconds()
    if interval <= 0:
        return 0.0
    countdown = float(get_schedule().reserve(phone, interval=interval))
    if countdown <= 0:
        return 0.0
    return countdown
