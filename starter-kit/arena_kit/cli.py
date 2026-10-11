"""`arena` command line: register, list cases, play one case or a whole set, show the board,
run the MCP server."""

import argparse
import functools
import io
import json
import logging
import os
import statistics
import zipfile
from pathlib import Path

from .client import ArenaClient, ArenaError
from .play import RemoteTable, hosted, play, play_all, play_waves


def load_env(path=".env"):
    """Read KEY=VALUE lines from .env into the environment (real env vars win)."""
    p = Path(path)
    if p.is_file():
        for line in p.read_text().splitlines():
            key, sep, value = line.partition("=")
            value = value.strip().strip("\"'")
            if sep and value and not key.strip().startswith("#"):
                os.environ.setdefault(key.strip(), value)


def agent_factory(name, data):
    from .agents import BuyerAgent, LLMAgent, NaiveAgent, llm_from_env

    if name == "naive":
        return NaiveAgent
    if name in {"buyer", "buyer-llm"} and not data:
        bundled = Path(__file__).resolve().parents[2] / "data"
        data = bundled if (bundled / "facts.json").is_file() else None
    package = None
    if data:
        from .data import DataPackage

        package = DataPackage(data)
        package.lookup("")  # build the ID index once, before agents share it
    if name in {"buyer", "buyer-llm"}:
        from .research import Research

        research = Research(package)
        complete = llm_from_env(timeout=12.0, max_tokens=600, reasoning_effort="low") if name == "buyer-llm" else None
        return lambda: BuyerAgent(research, complete)
    complete = llm_from_env()
    return lambda: LLMAgent(complete, package)


def summary(result):
    keep = ("deal", "supplier_id", "terms", "c_open", "c_deal", "c_best", "score")
    return {k: result.get(k) for k in keep if k in result}


def require_model_completion():
    """Check connectivity before play or run opens an arena session."""
    from .agents import llm_from_env

    model = os.environ.get("LLM_MODEL", "<unset>")
    try:
        reply = llm_from_env(timeout=15.0, max_tokens=256)(
            "Reply with exactly READY.", "Model connectivity check."
        )
        if not isinstance(reply, str) or reply.strip() != "READY":
            raise ValueError("unexpected model response")
    except Exception as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        detail = f"HTTP {status}" if status else type(exc).__name__
        raise SystemExit(f"Model preflight failed for {model}: {detail}; no arena session opened") from None
    print(f"Model preflight passed: {model}")


def main(argv=None):
    load_env()
    ap = argparse.ArgumentParser(prog="arena")
    ap.add_argument("-v", "--verbose", action="store_true")
    verbose = argparse.ArgumentParser(add_help=False)  # -v also after the command
    verbose.add_argument("-v", "--verbose", action="store_true", default=argparse.SUPPRESS)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser = functools.partial(sub.add_parser, parents=[verbose])
    r = sub.add_parser(
        "register", help="arena-sim only: get a simulator key (the arena's key comes from the organisers)"
    )
    r.add_argument("team_name")
    r.add_argument("event_code")
    data = {"default": os.environ.get("ARENA_DATA"), "help": "data package folder"}
    sets = {"default": "practice", "help": "practice, final or sandbox"}
    c = sub.add_parser("cases", help="list the cases you can play")
    c.add_argument("--set", **sets)
    p = sub.add_parser("play", help="play one case")
    p.add_argument("case_id")
    p.add_argument("--agent", default="buyer", choices=["naive", "llm", "buyer", "buyer-llm"])
    p.add_argument("--data", **data)
    p.add_argument("--require-model", action="store_true", help="verify the model before opening a session")
    a = sub.add_parser("run", help="play every case of a set in parallel")
    a.add_argument("--set", **sets)
    a.add_argument("--agent", default="buyer", choices=["naive", "llm", "buyer", "buyer-llm"])
    a.add_argument("--data", **data)
    a.add_argument("--require-model", action="store_true", help="verify the model before opening sessions")
    a.add_argument("--parallel", type=int, default=8, help="cases at once (at most 10)")
    a.add_argument("--waves", type=int, default=5, help="final: stop after this many waves have closed (rehearsal: 2)")
    d = sub.add_parser("data", help="download and unpack the data (package, Sunday release once public)")
    d.add_argument("--out", default="data", help="folder to unpack into")
    sub.add_parser("me", help="your team: practice quota used and left, best score per case")
    b = sub.add_parser("board", help="show the leaderboard")
    b.add_argument("--set", **sets)
    m = sub.add_parser("mcp", help="run the read-only MCP server over the data (stdio)")
    m.add_argument("--data", **data)
    bench = sub.add_parser("benchmark", help="compare buyer and naive locally, with no keys or network")
    bench.add_argument("--data", **data)
    bench.add_argument("--out", help="optional JSON report including decision explanations")
    experiment = sub.add_parser("evaluate", help="run a bounded hosted practice experiment and save results")
    experiment.add_argument("--cases", nargs="+", help="explicit case IDs; default: all hosted practice cases")
    experiment.add_argument("--agent", choices=["buyer", "buyer-llm", "naive", "llm"], default="buyer-llm")
    experiment.add_argument("--data", **data)
    experiment.add_argument("--require-model", action="store_true", help="require a valid tactical model preflight")
    experiment.add_argument("--parallel", type=int, choices=range(1, 11), default=5)
    experiment.add_argument("--seconds", type=int, default=390)
    experiment.add_argument("--out", required=True, help="JSON report; updated as each case completes")
    args = ap.parse_args(argv)
    if args.cmd in {"play", "run", "evaluate"} and args.require_model and args.agent != "buyer-llm":
        ap.error("--require-model is supported for --agent buyer-llm")
    hosted_practice = (
        (args.cmd == "play" and args.case_id.startswith("case:P"))
        or (args.cmd == "run" and args.set == "practice")
    )
    if args.cmd in {"play", "run"} and args.agent == "buyer-llm" and (
        args.require_model or hosted_practice
    ):
        require_model_completion()
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.cmd == "mcp":
        from .mcp_server import main as serve

        return serve(args.data)
    if args.cmd == "benchmark":
        from .benchmark import benchmark

        report = benchmark(agent_factory("buyer", args.data)().research)
        for run in report["runs"]:
            result = run["result"]
            print(
                f"{run['case_id']}  {run['agent']:5}  score={result['score']:.3f}  "
                f"C={result['c_deal']}  rounds={run['rounds']}"
            )
        print(report["limitation"])
        if args.out:
            Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"report: {args.out}")
        return
    client = ArenaClient()
    if args.cmd == "evaluate":
        from .evaluation import evaluate

        report = evaluate(
            client,
            agent_factory(args.agent, args.data),
            args.cases,
            args.parallel,
            args.seconds,
            args.out,
            agent_name=args.agent,
        )
        print(f"mean score: {report['mean_score']:.3f}; report: {args.out}")
        return
    if args.cmd == "register":
        out = client.register(args.team_name, args.event_code)
        print(json.dumps(out, indent=2))
        print("\nA simulator key: put it into .env as ARENA_API_KEY=... while you point ARENA_URL at arena-sim.")
    elif args.cmd == "cases":
        cases = client.cases(args.set)
        playable = {c["case_id"] for c in hosted(cases)}
        for case in cases:
            mark = "" if case["case_id"] in playable else "  (not hosted: data only)"
            print(case["case_id"], case.get("type", ""), case.get("title", "") + mark, sep="  ")
    elif args.cmd == "me":
        try:
            print(json.dumps(client.me(), indent=2))
        except ArenaError as e:
            print(f"no team view on this arena ({e})" if e.status == 404 else e)
    elif args.cmd == "board":
        print(json.dumps(client.leaderboard(args.set), indent=2))
    elif args.cmd == "data":
        for name, info in client.downloads().items():
            if info.get("url"):
                zipfile.ZipFile(io.BytesIO(client.download(name))).extractall(args.out)
                print(f"{name}: {Path(args.out) / name}")
            else:
                print(f"{name}: public from {info.get('at')}")
    elif args.cmd == "play":
        table = RemoteTable(client)
        agent = agent_factory(args.agent, args.data)()
        try:
            result = play(table, args.case_id, agent)
        except ArenaError as e:  # e.g. not hosted, the quota, a paused key: the arena says why
            raise SystemExit(str(e)) from None
        print(json.dumps(summary(result), indent=2))
        if args.agent == "buyer-llm":
            print(f"model calls: {agent.model_successes} succeeded, {agent.model_fallbacks} fell back")
        replay = client.session(table.session_id).get("replay_url")
        if replay:  # the supplier's reasons, move by move: read it, improve, play again
            print(f"replay: {os.environ['ARENA_URL'].rstrip('/')}{replay}")
    elif args.set == "final":  # waits for each wave and plays its cases within the cap
        out = play_waves(client, agent_factory(args.agent, args.data), args.waves, min(args.parallel, 10))
    else:
        ids = [case["case_id"] for case in hosted(client.cases(args.set))]
        out = play_all(
            lambda: RemoteTable(client),
            ids,
            agent_factory(args.agent, args.data),
            min(args.parallel, 10),
        )
    if args.cmd == "run":
        for case_id, result in out.items():
            print(case_id, result if isinstance(result, Exception) else summary(result))
        scores = {c: r.get("score") for c, r in out.items() if isinstance(r, dict)}
        if args.set == "final" and scores:  # points so far: each wave 0-100, their sum, as the board counts
            waves = {}
            for case in client.cases("final"):  # your own case list: which wave each case was in
                waves.setdefault(case["wave"], []).append(scores.get(case["case_id"]) or 0)
            points = {n: round(100 * statistics.mean(v), 1) for n, v in sorted(waves.items())}
            print(f"waves: {points}  points so far: {round(sum(points.values()), 1)} (the board is the record)")
        elif scores and all(v is not None for v in scores.values()):
            print(f"mean score: {100 * statistics.mean(scores.values()):.1f}")
    if args.cmd in ("play", "run") and client.practice_remaining is not None:
        print(f"practice sessions left today: {client.practice_remaining}")


if __name__ == "__main__":
    main()
