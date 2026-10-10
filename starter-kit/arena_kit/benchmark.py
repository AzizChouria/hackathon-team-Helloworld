"""A reproducible, network-free comparison against the supplied contract simulator."""

import copy
import threading
import time

from .agents import BuyerAgent, NaiveAgent
from .play import play
from .sim import Sim, load_cases


class LocalTable:
    """Use exactly the simulator's messages, validation and documents without binding a port."""

    def __init__(self, case, facts=None):
        self.sim = Sim({case["case_id"]: case}, facts=facts, no_clock=True)
        self.session_id = None
        self.lock = threading.Lock()

    def open(self, case_id):
        response = copy.deepcopy(self.sim.open("local-benchmark", case_id))
        self.session_id = response["session_id"]
        return response["case"], response["threads"]

    def send(self, sid, message):
        with self.lock:
            return copy.deepcopy(self.sim.message("local-benchmark", self.session_id, sid, message))

    def close(self, sid, message):
        return self.send(sid, message)["result"]

    def attachment(self, ref):
        with self.lock:
            return self.sim.attachment("local-benchmark", self.session_id, ref)[0]

    def result(self):
        return self.sim.sessions[self.session_id]["result"]


def benchmark(research):
    records = []
    for case in load_cases().values():
        for name, agent in (("naive", NaiveAgent()), ("buyer", BuyerAgent(research))):
            table = LocalTable(case, research.facts)
            start = time.monotonic()
            result = play(table, case["case_id"], agent)
            state = table.sim.sessions[table.session_id]
            records.append(
                {
                    "case_id": case["case_id"],
                    "agent": name,
                    "seconds": round(time.monotonic() - start, 3),
                    "rounds": sum(t["round"] for t in state["threads"].values()),
                    "result": result,
                    "decisions": getattr(agent, "trace", []),
                }
            )
    return {
        "environment": "Local scripted contract simulator; no hosted supplier or LLM calls.",
        "limitation": "Simulator scores validate mechanics, not performance against the hosted suppliers.",
        "runs": records,
    }
