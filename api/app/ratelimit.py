"""Process-local rate limiting.

Counters live in memory, never in the database. Rejected or hostile traffic therefore costs no database round
trip: on 20 Oct 2026 a 300-request parallel flood made the API write a budget row to the remote database for
every request, the single remote writer jammed, and the whole site returned 503 for about eight minutes.

Trade-off: counters reset when the process restarts and are not shared between instances. The production
topology is a single Render instance, so this is the right granularity; a multi-instance deployment would need
a shared in-memory store such as Redis instead.
"""
import threading
import time

FAILURE_WINDOW_MINUTES = 15
MAX_KEYS = 200_000


class RateLimiter:
    def __init__(self, clock=time.time):
        self._clock = clock
        self._lock = threading.Lock()
        self._counts = {}
        self._failures = {}
        self._pruned_at = None

    def reset(self):
        with self._lock:
            self._counts.clear()
            self._failures.clear()
            self._pruned_at = None

    def _minute(self):
        return int(self._clock() // 60)

    def _prune(self, minute):
        if minute != self._pruned_at or len(self._counts) > MAX_KEYS:
            self._counts = {key: value for key, value in self._counts.items() if key[1] >= minute}
            cutoff = minute - FAILURE_WINDOW_MINUTES
            for scope in list(self._failures):
                kept = {m: c for m, c in self._failures[scope].items() if m > cutoff}
                if kept:self._failures[scope] = kept
                else:del self._failures[scope]
            if len(self._counts) > MAX_KEYS:self._counts.clear()
            self._pruned_at = minute

    def hit(self, items):
        """Increment every (scope, limit) counter for this minute; True if any exceeded its limit."""
        minute = self._minute()
        over = False
        with self._lock:
            self._prune(minute)
            for scope, limit in items:
                key = (scope, minute)
                count = self._counts.get(key, 0) + 1
                self._counts[key] = count
                over = over or count > limit
        return over

    def failure_total(self, scope, minutes=FAILURE_WINDOW_MINUTES):
        minute = self._minute()
        with self._lock:
            return sum(c for m, c in self._failures.get(scope, {}).items() if m > minute - minutes)

    def add_failure(self, scopes):
        minute = self._minute()
        with self._lock:
            self._prune(minute)
            for scope in scopes:
                bucket = self._failures.setdefault(scope, {})
                bucket[minute] = bucket.get(minute, 0) + 1


limiter = RateLimiter()
