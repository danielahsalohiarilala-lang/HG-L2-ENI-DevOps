"""Limitation des tentatives de connexion (fenêtre glissante, en mémoire).

Limite : l'état est local à un processus. Avec plusieurs instances de l'API, il faudra le déplacer dans Redis.
"""
import time
from collections import defaultdict, deque

from app.core.config import get_settings


class FailureLimiter:
    def __init__(self, max_failures: int, window_seconds: int, clock=time.monotonic):
        self.max, self.window, self.clock = max_failures, window_seconds, clock
        self._fails: dict[str, deque] = defaultdict(deque)

    def _prune(self, key: str) -> deque:
        q, now = self._fails[key], self.clock()
        while q and now - q[0] > self.window:
            q.popleft()
        return q

    def retry_after(self, key: str) -> int:
        """0 si l'accès est autorisé, sinon nombre de secondes à attendre."""
        q = self._prune(key)
        if len(q) < self.max:
            return 0
        return max(1, int(self.window - (self.clock() - q[0])) + 1)

    def record_failure(self, key: str) -> None:
        self._prune(key).append(self.clock())

    def reset(self, key: str) -> None:
        self._fails.pop(key, None)

    def clear(self) -> None:
        self._fails.clear()


_s = get_settings()
login_limiter = FailureLimiter(_s.login_max_attempts, _s.login_window_seconds)
