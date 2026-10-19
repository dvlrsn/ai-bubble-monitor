"""Point-in-time view of the archive: every lookup only sees data up to `asof`.

This is what lets the same indicator code score today and any past day.
Lookups index into the full series instead of copying it, so replaying
decades of history stays fast.
"""

from bisect import bisect_right
from datetime import date, timedelta


def _d(s):
    return date.fromisoformat(s[:10])


class Ctx:
    def __init__(self, series, manual, asof):
        self.series = series        # {id: [(date, value), ...]} sorted
        self.manual = manual        # parsed manual.json
        self.asof = asof            # 'YYYY-MM-DD'
        self._dates = {k: [d for d, _ in v] for k, v in series.items()}

    def at(self, asof):
        c = Ctx.__new__(Ctx)
        c.series, c.manual, c.asof, c._dates = self.series, self.manual, asof, self._dates
        return c

    # --- automated series -------------------------------------------------
    def _end(self, sid):
        """Number of observations on or before asof."""
        if sid not in self.series:
            return 0
        return bisect_right(self._dates[sid], self.asof)

    def s(self, sid):
        return self.series[sid][:self._end(sid)] if sid in self.series else []

    def last(self, sid):
        i = self._end(sid)
        return self.series[sid][i - 1] if i else None

    def tail(self, sid, n):
        i = self._end(sid)
        return self.series[sid][i - n:i] if i >= n else None

    def drawdown(self, sid, n=252):
        """% below the n-session high (positive number)."""
        t = self.tail(sid, n)
        if not t:
            return None
        hi = max(v for _, v in t)
        return 100 * (1 - t[-1][1] / hi), t[-1][0]

    def vs_sma(self, sid, n=200, lag=0):
        end = self._end(sid) - lag
        if end < n:
            return None
        s = self.series[sid]
        sma = sum(v for _, v in s[end - n:end]) / n
        return 100 * (s[end - 1][1] / sma - 1), sma, s[end - 1][0]

    def sma(self, sid, n, lag=0):
        r = self.vs_sma(sid, n, lag)
        return r[1] if r else None

    def value_ago(self, sid, days):
        """Latest value on or before (last date - days)."""
        last = self.last(sid)
        if not last:
            return None
        target = (_d(last[0]) - timedelta(days=days)).isoformat()
        i = bisect_right(self._dates[sid], target)
        return self.series[sid][i - 1] if i else None

    def min_since(self, sid, days):
        end = self._end(sid)
        if not end:
            return None
        start = (_d(self.series[sid][end - 1][0]) - timedelta(days=days)).isoformat()
        i = bisect_right(self._dates[sid], start)
        return min(v for _, v in self.series[sid][i:end])

    def ratio_series(self, a, b, n=None):
        ta = self.tail(a, n) if n else self.s(a)
        sb = dict(self.tail(b, n + 10) if n else self.s(b)) if (n is None or self._end(b) >= n + 10) else dict(self.s(b))
        if not ta:
            return []
        return [(d, v / sb[d]) for d, v in ta if sb.get(d)]

    # --- manual readings --------------------------------------------------
    def readings(self, mid):
        rs = self.manual.get("readings", {}).get(mid, [])
        return sorted((r for r in rs if r["date"] <= self.asof), key=lambda r: r["date"])

    def reading(self, mid):
        rs = self.readings(mid)
        return rs[-1] if rs else None

    def age_days(self, d):
        return (_d(self.asof) - _d(d)).days
