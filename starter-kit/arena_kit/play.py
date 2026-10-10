"""Play cases with an agent against the arena over HTTP - the hosted arena (practice, sandbox,
final) or `arena-sim`, the local contract simulator. Both speak the same API.

An agent is any object with `decide(case, threads) -> {"supplier_id": ..., "message": {...}}`:
  threads: {supplier_id: [message, ...]} - every e-mail so far, both directions, in order;
           supplier attachments carry their text under "text" (see `docs.read_document`).
  message: subject, body, up to 3 term sheets, refs - or an "action" that closes the case:
           {"type": "accept", "term_sheet_id": ...} or {"type": "walk_away"}.
"""

import functools
import logging
import re
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

import httpx

from .client import ArenaError
from .cost import must_haves_ok, total_cost
from .docs import read_document, standard_terms

log = logging.getLogger("arena")

ENDED = {"walked_away", "no_bid"}
# A message later than this after the supplier's last one counts as a timeout.
MOVE_LIMIT_S = 60
# In the Live Final, close this long before the wave's cap - or the slowest round of the case so far
# (your decision plus a supplier reply of up to about a minute) plus a margin, if that is longer.
CLOSE_BEFORE_CAP_S, ROUND_MARGIN_S = 90, 15
RUNNING = re.compile(r"one session per case in the final: (\S+)")
# Practice: the case list shows every practice case file; only those marked hosted can be played
# (a session on another is a 403). Without the marker every listed case counts as hosted.
HOSTED_FIELD = "hosted"


class RemoteTable:
    """The arena over HTTP: the practice arena, the final, or a hosted sandbox."""

    def __init__(self, client, case=None):
        self.client, self.session_id, self.case, self.done = client, None, case, None

    def open(self, case_id):
        try:
            r = self.client.open_session(case_id)
        except ArenaError as e:
            running = RUNNING.search(str(e.detail)) if e.status == 409 else None
            if not (running and self.case):
                raise
            return self.resume(running.group(1))
        self.session_id = r["session_id"]
        log.info("session %s", self.session_id)
        return r["case"], r["threads"]

    def resume(self, session_id):
        """Pick up a final session this team already started (e.g. after a crash): every thread
        so far, from the arena."""
        self.session_id = session_id
        log.info("resuming session %s", session_id)
        state = self.client.session(session_id)
        if state["status"] == "ended":
            self.done = self.result()
        threads = {}
        for supplier in state["threads"]:
            thread = self.client.thread(session_id, supplier)
            events = list(thread["messages"])
            # Timeout replies are stored separately by the arena. Historical message IDs
            # are no longer standing offers; never resume by accepting one of them.
            current = next((q for q in reversed(thread.get("timeouts", []))
                            if q.get("offer_id") == thread.get("offer_id")), None)
            if current:
                events.append({"from": "arena", "status": "walked_away" if thread.get("closed") else thread["status"],
                               "body": "Current offer after timeout.", "attachments": [],
                               "term_sheets": [] if thread.get("closed") else [
                                   {"term_sheet_id": thread["offer_id"], "terms": current["terms"]}]})
            threads[supplier] = events
        return self.case, threads

    def send(self, supplier_id, message):
        return self.client.send_message(self.session_id, supplier_id, message)

    def close(self, supplier_id, message):
        reply = self.client.send_message(self.session_id, supplier_id, message)
        return reply.get("result", reply)  # the supplier's last e-mail carries the result

    def attachment(self, attachment_id):
        return self.client.attachment(self.session_id, attachment_id)

    def missed(self, supplier_id, error):
        """After a 409: the result if the case has ended (e.g. at a wave's cap), else what the
        thread now says (a timeout answer, or the reason it ended)."""
        state = self.client.session(self.session_id)
        if state.get("status") == "ended":
            return {"result": state.get("result") or {"deal": False, "end_reason": state.get("end_reason")}}
        t = self.client.thread(self.session_id, supplier_id)
        last = (t.get("timeouts") or [{}])[-1]
        sheet = [{"term_sheet_id": t["offer_id"], "terms": last.get("terms", {})}]
        return {
            "from": "arena",
            "status": "walked_away" if t["closed"] else t["status"],
            "term_sheets": [] if t["closed"] else sheet,
            "body": f"({error.detail})",
            "missing_fields": last.get("missing_fields", []),
            "attachments": [],
        }

    def result(self):
        state = self.client.session(self.session_id)
        return state.get("result") or {"deal": False, "end_reason": state.get("end_reason"), **state}


def latest(events):
    """The supplier's latest message in a thread."""
    return next(m for m in reversed(events) if m.get("from") != "buyer")


def standing(events):
    """(term_sheet_id, terms) of the supplier's standing term sheet, or (None, {})."""
    sheets = latest(events).get("term_sheets") or []
    return (sheets[0]["term_sheet_id"], sheets[0]["terms"]) if sheets else (None, {})


def live_threads(threads):
    """Suppliers whose thread has not ended."""
    return [sid for sid, ev in threads.items() if latest(ev).get("status") not in ENDED]


def moves_left(case, events):
    """Messages you may still send in this thread (the round limit counts each of them)."""
    return case.get("round_limit", 10) - sum(m.get("from") == "buyer" for m in events)


def fetch_documents(table, message):
    """Download every attachment of a supplier message and add its text."""
    def read_attachment(att):
        if att.get("attachment_id") and "text" not in att:
            try:
                att["text"] = read_document(att["name"], table.attachment(att["attachment_id"]))
            except (ArenaError, httpx.TransportError) as exc:
                # An unavailable auxiliary file must not discard an already received
                # supplier offer. Missing standards still cannot establish must-haves.
                status = getattr(exc, "status", None)
                if isinstance(exc, ArenaError) and status not in {404, 408, 410, 429} and status < 500:
                    raise
                att["read_error"] = {"type": type(exc).__name__, "http_status": status}
                log.warning("attachment unavailable: %s status=%s", type(exc).__name__, status)
    attachments = message.get("attachments") or []
    if len(attachments) > 1:
        with ThreadPoolExecutor(max_workers=min(4, len(attachments))) as pool:
            list(pool.map(read_attachment, attachments))
    else:
        for att in attachments:
            read_attachment(att)
    return message


def expired_offer(error):
    return error.status == 422 and "not a standing offer" in str(error.detail)


def closing_move(case, threads):
    """Accept the cheapest standing term sheet that keeps the must-haves and beats the alternative
    (C with each supplier's standard terms), else walk away - what to do when time runs out."""
    alt = case["buyer"].get("alternative") or {}
    c_alt = total_cost(case, alt["terms"]) if alt.get("terms", {}).get("unit_price") else float("inf")
    best = None
    for sid in live_threads(threads):
        sheet_id, terms = standing(threads[sid])
        std = standard_terms(threads[sid])
        if sheet_id and must_haves_ok(case, terms, std) and (c := total_cost(case, terms, std)) < c_alt:
            best = min(best or (c, sid, sheet_id), (c, sid, sheet_id))
    if best is None:
        return {"supplier_id": live_threads(threads)[0], "message": {"action": {"type": "walk_away"}}}
    return {"supplier_id": best[1], "message": {"action": {"type": "accept", "term_sheet_id": best[2]}}}


def play(table, case_id, agent, deadline=None):
    """Play one case to its end. `deadline` (time.time(), or a function returning it): a Live Final
    wave's cap - shortly before it, `closing_move` closes the case so it does not end without a deal."""
    if hasattr(agent, "prepare") and getattr(table, "case", None):
        agent.prepare(table.case)
    case, threads = table.open(case_id)
    if getattr(table, "done", None):  # resumed a case that had already ended
        return table.done
    received = time.monotonic()
    for events in threads.values():
        latest(events).setdefault("_received_at", received)
    if hasattr(agent, "decide_ready"):
        return play_threads(table, case, threads, agent, deadline)
    for events in threads.values():
        for m in events:
            fetch_documents(table, m)
    if hasattr(agent, "response_guard_s"):
        return _play_coordinated(table, case, threads, agent, deadline)
    slowest = 0.0  # the longest round so far: decision + the supplier's reply
    while live_threads(threads):
        t0 = time.monotonic()
        cap = deadline() if callable(deadline) else deadline
        if cap and time.time() > cap - max(CLOSE_BEFORE_CAP_S, slowest + ROUND_MARGIN_S):
            log.info("%s: the wave's cap is near - closing", case_id)
            decision = getattr(agent, "closing_move", closing_move)(case, threads)
        else:
            if hasattr(agent, "decide_many"):
                decisions = agent.decide_many(case, threads)
                if len(decisions) > 1 and not any(d["message"].get("action") for d in decisions):
                    # All RFQ threads receive a move together. No serial supplier-reply waits.
                    def send_one(d):
                        supplier, message = d["supplier_id"], d["message"]
                        try:
                            reply = table.send(supplier, message)
                        except ArenaError as exc:
                            if exc.status != 409:
                                raise
                            reply = table.missed(supplier, exc)
                        return supplier, message, fetch_documents(table, reply)

                    with ThreadPoolExecutor(max_workers=len(decisions)) as pool:
                        replies = list(pool.map(send_one, decisions))
                    for supplier, message, reply in replies:
                        if "result" in reply:
                            return reply["result"]
                        threads[supplier] += [{**message, "from": "buyer"}, reply]
                    slowest = max(slowest, time.monotonic() - t0)
                    continue
                decision = decisions[0]
            else:
                decision = agent.decide(case, threads)
        if (took := time.monotonic() - t0) > MOVE_LIMIT_S * 0.75:
            log.warning("decision took %.1fs - the limit is %ss per message", took, MOVE_LIMIT_S)
        sid, msg = decision["supplier_id"], decision["message"]
        try:
            if msg.get("action"):
                log.info("%s %s", sid, msg["action"])
                return table.close(sid, msg)
            reply = table.send(sid, msg)
        except ArenaError as e:
            if e.status != 409:
                raise
            log.info("%s: %s", sid, e.detail)
            reply = table.missed(sid, e)  # e.g. late, or the thread or the case has ended
            if msg.get("action") and "result" not in reply:  # the case goes on: decide again
                threads[sid].append(fetch_documents(table, reply))
                continue
        if "result" in reply:  # the reply ended the case, e.g. the last supplier walked away
            return reply["result"]
        threads[sid] += [{**msg, "from": "buyer"}, fetch_documents(table, reply)]
        slowest = max(slowest, time.monotonic() - t0)
        log.info("%s %s %s", sid, reply.get("status"), standing(threads[sid])[1])
    return table.result()



def _play_coordinated(table, case, threads, agent, deadline):
    """Drain RFQ replies without a batch barrier; never act on an in-flight offer.

    Wait for other quotes only while ready threads have enough time. At the response
    guard, close using available quotes without another model call. One POST per supplier
    can be in flight; ambiguous transport failures propagate rather than being retried.
    """
    pool = ThreadPoolExecutor(max_workers=max(1, len(threads)))
    pending = {}
    slowest = 0.0

    def send(sid, message):
        try:
            reply = table.send(sid, message)
        except ArenaError as exc:
            if exc.status != 409:
                raise
            reply = table.missed(sid, exc)
        reply["_received_at"] = time.monotonic()
        return fetch_documents(table, reply)

    try:
        while True:
            for future in [f for f in pending if f.done()]:
                sid, started = pending.pop(future)
                reply = future.result()
                if "result" in reply:
                    return reply["result"]
                threads[sid].append(reply)
                slowest = max(slowest, time.monotonic() - started)
            busy = {sid for sid, _ in pending.values()}
            ready = {s: threads[s] for s in live_threads(threads) if s not in busy}
            if not ready and not pending:
                return table.result()
            now = time.monotonic()
            cap = deadline() if callable(deadline) else deadline
            near_cap = cap and time.time() > cap - max(CLOSE_BEFORE_CAP_S, slowest + ROUND_MARGIN_S)
            oldest = min((latest(ev).get("_received_at", now) for ev in ready.values()), default=now)
            remaining = agent.response_guard_s - (now - oldest)
            if pending and (not ready or remaining > 0 and not near_cap):
                wait(pending, timeout=max(0.001, min(1.0, remaining)), return_when=FIRST_COMPLETED)
                continue
            if near_cap:
                decisions = [agent.closing_move(case, ready)]
            else:
                decisions = agent.decide_many(case, ready, allow_model=not pending)
            for decision in decisions:
                sid, msg = decision["supplier_id"], decision["message"]
                if sid not in ready:
                    raise ValueError("Agent selected a supplier with no available reply")
                if msg.get("action"):
                    try:
                        result = table.close(sid, msg)
                    except ArenaError as exc:
                        if exc.status != 409:
                            raise
                        reply = table.missed(sid, exc)
                        if "result" in reply:
                            return reply["result"]
                        reply["_received_at"] = time.monotonic()
                        threads[sid].append(fetch_documents(table, reply))
                        break
                    return result
                threads[sid].append({**msg, "from": "buyer"})
                pending[pool.submit(send, sid, msg)] = sid, time.monotonic()
    finally:
        # An already sent request cannot be recalled. Let it finish without issuing another POST.
        pool.shutdown(wait=False, cancel_futures=True)


def play_threads(table, case, threads, agent, deadline=None):
    """Keep RFQ requests in flight independently, so one slow bidder cannot starve the others.

    Only this coordinator mutates transcripts or calls the agent. Worker threads perform
    transport and attachment reads; at most one request per supplier is outstanding.
    """
    pending, docs_pending, slowest, rejected = {}, {}, 0.0, set()
    closing_checked = None

    def send(sid, message):
        try:
            reply = table.send(sid, message)
        except ArenaError as exc:
            if exc.status != 409:
                raise
            reply = table.missed(sid, exc)
        reply["_received_at"] = time.monotonic()
        return reply

    pool = ThreadPoolExecutor(max_workers=max(1, len(threads)))
    docs_pool = ThreadPoolExecutor(max_workers=max(1, len(threads)))
    for sid, events in threads.items():
        for index, original in enumerate(events):
            if original.get("attachments"):
                copy = {**original, "attachments": [a.copy() for a in original["attachments"]]}
                future = docs_pool.submit(fetch_documents, table, copy)
                docs_pending[future] = (sid, index, original)
    try:
        while live_threads(threads):
            for future, (sid, index, original) in list(docs_pending.items()):
                if future.done():
                    del docs_pending[future]
                    try:
                        hydrated = future.result()
                    except Exception as exc:
                        log.warning("%s attachment read failed (%s)", sid, type(exc).__name__)
                        continue
                    if threads[sid][index] is original:
                        threads[sid][index] = hydrated
            for sid, (future, message, started) in list(pending.items()):
                if not future.done():
                    continue
                reply = future.result()
                del pending[sid]
                closing_checked = None
                if "result" in reply:
                    return reply["result"]
                threads[sid] += [{**message, "from": "buyer"}, reply]
                if reply.get("attachments"):
                    copy = {**reply, "attachments": [a.copy() for a in reply["attachments"]]}
                    future = docs_pool.submit(fetch_documents, table, copy)
                    docs_pending[future] = (sid, len(threads[sid]) - 1, reply)
                slowest = max(slowest, time.monotonic() - started)
            if not live_threads(threads):
                break
            cap = deadline() if callable(deadline) else deadline
            closing = cap and time.time() > cap - max(CLOSE_BEFORE_CAP_S, slowest + ROUND_MARGIN_S)
            ready = [sid for sid in live_threads(threads) if sid not in pending]
            started = time.monotonic()
            if closing and pending:
                # Pending replies may outlast the wave. Settle a valid ready offer
                # now; otherwise give the pending bidders time until the final
                # 30 seconds, while keeping a chance to walk away cleanly.
                if not ready:
                    wait([item[0] for item in pending.values()], timeout=0.25, return_when=FIRST_COMPLETED)
                    continue
                if closing_checked is None or closing_checked[0] != tuple(ready):
                    closing_checked = (tuple(ready), agent.close(case, {s: threads[s] for s in ready}))
                decision = closing_checked[1]
                if decision["message"].get("action", {}).get("type") != "accept" and time.time() < cap - 30:
                    wait([item[0] for item in pending.values()], timeout=0.25, return_when=FIRST_COMPLETED)
                    continue
            else:
                decision = agent.close(case, threads) if closing else agent.decide_ready(case, threads, ready)
            if decision is None:
                if not pending:
                    decision = agent.close(case, threads)
                else:
                    wait([item[0] for item in pending.values()], timeout=0.25, return_when=FIRST_COMPLETED)
                    continue
            sid, message = decision["supplier_id"], decision["message"]
            if message.get("action"):
                try:
                    return table.close(sid, message)
                except ArenaError as exc:
                    if expired_offer(exc):
                        ref = (sid, (message.get("action") or {}).get("term_sheet_id"))
                        if ref in rejected:
                            raise
                        rejected.add(ref)
                    elif exc.status != 409:
                        raise
                    reply = table.missed(sid, exc)
                    if "result" in reply:
                        return reply["result"]
                    if expired_offer(exc):
                        reply["term_sheets"] = [
                            s for s in reply.get("term_sheets", []) if (sid, s["term_sheet_id"]) not in rejected
                        ]
                    threads[sid].append(fetch_documents(table, reply))
                    continue
            if sid not in ready:
                raise ValueError("agent selected a supplier with a request already in flight")
            pending[sid] = (pool.submit(send, sid, message), message, started)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
        docs_pool.shutdown(wait=False, cancel_futures=True)
    return table.result()


def hosted(cases):
    """The cases you can play: those marked hosted, or all of them if the list has no marker."""
    if any(HOSTED_FIELD in c for c in cases):
        return [c for c in cases if c.get(HOSTED_FIELD)]
    return cases


def quota_used_up(error):
    """The practice quota's 429 ("practice limit: …"): retrying does not help before it resets."""
    return isinstance(error, ArenaError) and error.status == 429 and str(error.detail).startswith("practice limit")


def play_all(new_table, case_ids, new_agent, parallel=8):
    """Play many cases at once (e.g. every practice case). `new_table()` and `new_agent()` give
    each case its own table and agent. Once the practice quota is used up, no further case starts.
    Returns {case_id: result or the exception that stopped it}."""
    used_up = threading.Event()

    def one(case_id):
        if used_up.is_set():
            return case_id, ArenaError(429, "not started: the practice quota is used up")
        try:
            return case_id, play(new_table(), case_id, new_agent())
        except ArenaError as e:
            if quota_used_up(e):
                used_up.set()
                log.warning("practice quota used up: %s", e.detail)
            elif e.status == 403:
                log.warning("%s: %s", case_id, e.detail)  # e.g. not hosted for practice
            else:
                log.exception("%s failed", case_id)
            return case_id, e
        except Exception as e:  # one broken case must not stop the others
            log.exception("%s failed", case_id)
            return case_id, e

    with ThreadPoolExecutor(max_workers=parallel) as pool:
        return dict(pool.map(one, case_ids))


def play_waves(client, new_agent, waves=5, parallel=10, poll=5.0):
    """The Live Final: wait for each wave, play its cases in parallel within the wave's cap, wait
    for the next. Keep it running from before the first wave until the last has closed; it returns
    after `waves` waves have closed and every case has finished: {case_id: result or exception}."""
    started, closed, caps = {}, set(), {}  # caps: wave -> its cap as time.time()

    def one(case, deadline):
        try:
            return play(RemoteTable(client, case), case["case_id"], new_agent(), deadline)
        except Exception as e:  # one broken case must not stop the others
            log.exception("%s failed", case["case_id"])
            return e

    with ThreadPoolExecutor(max_workers=parallel) as pool:
        while len(closed) < waves or not all(f.done() for f in started.values()):
            try:
                cases = client.cases("final")
            except ArenaError as e:
                if e.status != 403:  # 403: no wave has started yet
                    raise
                cases = []
            for case in cases:
                if not case.get("open"):
                    closed.add(case["wave"])
                    continue
                if case.get("seconds_left") is not None:  # each wave has its own cap; follow an extension
                    caps[case["wave"]] = time.time() + case["seconds_left"]
                if case["case_id"] not in started and case.get("seconds_left"):
                    if case["wave"] not in {c["wave"] for c in cases if c["case_id"] in started}:
                        log.warning("wave %s started: %s", case["wave"], case.get("theme"))
                    started[case["case_id"]] = pool.submit(one, case, functools.partial(caps.get, case["wave"]))
            time.sleep(poll)
    return {case_id: f.result() for case_id, f in started.items()}
