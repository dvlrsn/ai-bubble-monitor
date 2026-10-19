"""Fetch every automated source and archive it. Failures are logged, never fatal."""

import json
from concurrent.futures import ThreadPoolExecutor

from . import OUT_DIR, store
from .sources import breadth, edgar, finra, fred, news, yahoo


def _try(name, fn, log):
    try:
        fn()
        return True
    except Exception as e:  # one broken source must not stop the run
        store.log_failure(name, f"error: {e}"[:300])
        log(f"  ! {name}: {e}")
        return False


def collect(log=print, with_breadth=True, with_news=True):
    ok = fail = 0

    log("FRED…")
    for sid in fred.SERIES:
        if _try(f"fred:{sid}", lambda sid=sid: store.save_series(f"fred:{sid}", fred.fetch(sid)), log):
            ok += 1
        else:
            fail += 1

    log("Prices…")

    def price(t):
        rng = "max" if t in yahoo.LONG_HISTORY else "5y"
        return t, _try(f"px:{t}", lambda: store.save_series(f"px:{t}", yahoo.fetch(t, rng)), log)

    with ThreadPoolExecutor(max_workers=6) as ex:
        for _, good in ex.map(price, yahoo.TICKERS):
            ok, fail = (ok + 1, fail) if good else (ok, fail + 1)

    log("SEC filings…")
    for t in edgar.COMPANIES:
        def one(t=t):
            for concept, pts in edgar.fetch(t).items():
                store.save_series(f"edgar:{t}:{concept}", pts)
        if _try(f"edgar:{t}", one, log):
            ok += 1
        else:
            fail += 1

    log("FINRA margin debt…")
    if _try("finra:margin_debt", lambda: store.save_series("finra:margin_debt", finra.fetch()), log):
        ok += 1
    else:
        fail += 1

    if with_breadth:
        log("S&P 500 breadth (about 500 price histories, takes a minute)…")

        def b():
            p50, p200, n = breadth.fetch(progress=log)
            store.save_series("breadth:pct50", p50, status=f"ok ({n} members)")
            store.save_series("breadth:pct200", p200, status=f"ok ({n} members)")
        if _try("breadth", b, log):
            ok += 1
        else:
            fail += 1

    if with_news:
        log("Headline scan for tripwires…")

        def n():
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            hits = news.scan()
            (OUT_DIR / "news_candidates.json").write_text(json.dumps(hits, indent=1), encoding="utf-8")
        if _try("news", n, log):
            ok += 1
        else:
            fail += 1

    log(f"Done: {ok} sources ok, {fail} failed.")
    return ok, fail
