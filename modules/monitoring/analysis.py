"""Content analysis over the long-term memory.

Pure logic: given freshly fetched channel metrics and the previous reports,
build a report (N, G, V_0, V_1, d_global, d_video, blow-ups) and append the new
per-video snapshots to the memory.

Definitions follow `BrainrotHustler.md` (section "Analyse"). Timestamps are Unix
seconds (`int`).
"""

from __future__ import annotations

import time

METRICS = ("views", "comments", "likes")

# TikTok field name -> our metric key
_FIELD = {"views": "view_count", "comments": "comment_count", "likes": "like_count"}


def _metric_of(video: dict) -> dict:
    """Pick the metrics we track out of a fetched TikTok video."""
    return {m: int(video.get(f, 0)) for m, f in _FIELD.items()}


def match_videos(mem, videos: list[dict], tol: int = 1800):
    """Map fetched TikTok videos onto memory video ids.

    Primary match: exact (non-empty) title. Fallback: nearest `upload_at` within
    `tol` seconds. Returns (matched {mem_id: metric}, unmatched_videos).
    """
    memory = mem.listVideos()
    by_title: dict[str, list[dict]] = {}
    for row in memory:
        if row["title"]:
            by_title.setdefault(row["title"], []).append(row)

    matched: dict[int, dict] = {}
    used: set[int] = set()
    rest: list[dict] = []
    for video in videos:
        title = video.get("title")
        cands = [r for r in by_title.get(title, []) if r["id"] not in used] if title else []
        if len(cands) == 1:
            matched[cands[0]["id"]] = _metric_of(video)
            used.add(cands[0]["id"])
        else:
            rest.append(video)

    open_mem = [r for r in memory if r["id"] not in used and r["upload_at"]]
    unmatched: list[dict] = []
    for video in rest:
        created = int(video.get("create_time") or 0)
        best, best_d = None, tol + 1
        for row in open_mem:
            if row["id"] in used:
                continue
            delta = abs(int(row["upload_at"]) - created)
            if delta <= tol and delta < best_d:
                best, best_d = row, delta
        if best is not None:
            matched[best["id"]] = _metric_of(video)
            used.add(best["id"])
        else:
            unmatched.append(video)
    return matched, unmatched


def build_report(mem, matched: dict, totals: dict, prev_reports=None, now=None,
                 blowup: bool = True) -> dict:
    """Build a report and append the V_0/V_1 snapshots to the memory.

    mem:          LongTermMemory
    matched:      {memory_video_id: {"views","comments","likes"}} fresh metrics
    totals:       G = channel totals {"views","comments","likes"} over all fetched
    prev_reports: previous report dicts, oldest first (uses the last two)
    """
    prev_reports = list(prev_reports or [])
    now = int(time.time()) if now is None else int(now)
    prev = prev_reports[-1] if prev_reports else None
    prev2 = prev_reports[-2] if len(prev_reports) >= 2 else None

    # V_0: videos uploaded in the current window; V_1: the window before it.
    z_start = int(prev["ts"]) if prev else 0
    v0 = [v["id"] for v in mem.videosUploadedSince(z_start)]
    prev_start = int(prev2["ts"]) if prev2 else 0
    v1 = [v["id"] for v in mem.videosUploadedSince(prev_start)
          if prev and int(v["upload_at"]) < int(prev["ts"])]

    G = {m: int(totals.get(m, 0)) for m in METRICS}

    d_global: dict = {}
    for m in METRICS:
        if prev and prev2:
            denom = int(prev["G"][m]) - int(prev2["G"][m])
            d_global[m] = (G[m] - int(prev["G"][m])) / denom if denom else None
        else:
            d_global[m] = None

    V0 = {i: matched[i] for i in v0 if i in matched}
    V1 = {i: matched[i] for i in v1 if i in matched}

    d_video: dict = {}
    for i in v1:
        if i not in matched:
            continue
        snapshot = mem.newestMetric(i)
        if not snapshot:
            continue
        d_video[i] = {m: ((matched[i][m] - int(snapshot[m])) / int(snapshot[m])
                          if int(snapshot[m]) else None) for m in METRICS}

    blowups: list = []
    if blowup:
        gains = []
        for i, current in matched.items():
            snapshot = mem.newestMetric(i)
            base = int(snapshot["views"]) if snapshot else 0
            gains.append((current["views"] - base, i))
        gains.sort(key=lambda t: t[0], reverse=True)
        top = {i for _, i in gains[: 2 * len(v0)]}
        blowups = sorted(top - set(v0) - set(v1))

    # Persist the fresh snapshots for V_0 and V_1 at the report time.
    for i in set(v0) | set(v1):
        if i in matched:
            mem.addMetric(i, matched[i]["views"], matched[i]["comments"],
                          matched[i]["likes"], ts=now)

    return {
        "ts": now,
        "window": {"from": z_start, "to": now},
        "N": len(v0),
        "G": G,
        "d_global": d_global,
        "V_0": V0,
        "V_1": V1,
        "d_video": d_video,
        "blowups": blowups,
    }


def run_analysis(mem, videos: list[dict], store=None, now=None, blowup: bool = True) -> dict:
    """Match -> build report -> persist. Returns {"report", "unmatched"}."""
    matched, unmatched = match_videos(mem, videos)
    totals = {m: sum(int(v.get(f, 0)) for v in videos) for m, f in _FIELD.items()}
    prev = store.recent(2) if store else []
    report = build_report(mem, matched, totals, prev, now=now, blowup=blowup)
    if store:
        store.append(report)
    return {"report": report, "unmatched": [v.get("id") for v in unmatched]}
