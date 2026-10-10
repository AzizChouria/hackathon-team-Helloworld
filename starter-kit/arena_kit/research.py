"""Buyer-side research and reproducible claims; no access to supplier internals or live feeds."""

import csv
from collections import defaultdict
from dataclasses import dataclass


def month_number(month):
    year, month = map(int, month[:7].split("-"))
    return year * 12 + month


@dataclass(frozen=True)
class Evidence:
    text: str
    refs: tuple[str, ...]
    kind: str


class Research:
    """Load once before opening sessions, then share immutable data among case agents.

    CSV rows retain metadata that facts.json intentionally omits (supplier, price unit,
    document paths). Canonical claim values always come from facts.json when available.
    """

    TABLES = (
        "parts",
        "suppliers",
        "supplier_intel",
        "documents",
        "news",
        "contracts",
        "contract_clauses",
        "should_cost",
        "cost_drivers",
        "scorecards",
        "quotes",
        "negotiation_history",
        "price_conditions",
        "sourcing",
        "forecasts",
    )

    def __init__(self, package=None):
        self.package = package
        self.rows = defaultdict(list)
        self.documents = {}
        self.facts = dict(package.facts) if package else {}
        if not package:
            return
        roots = [package.root] + ([package.release] if package.release else [])
        for root in roots:
            for name in self.TABLES:
                path = root / "data" / f"{name}.csv"
                if path.is_file():
                    with path.open(encoding="utf-8", newline="") as stream:
                        self.rows[name].extend(dict(row) for row in csv.DictReader(stream))
        refs = {row["id"] for row in self.rows["documents"] + self.rows["contracts"]}
        refs.update(ref for ref in self.facts if ref.startswith(("doc:", "ctr:")))
        for ref in sorted(refs):
            try:
                self.documents[ref] = package.document(ref)
            except (FileNotFoundError, ValueError):
                pass

    def fact(self, case, ref):
        return case.get("facts", {}).get(ref) or self.facts.get(ref) or {}

    def related(self, table, case, sid):
        parts = set(case.get("parts", []))
        rows = []
        for row in self.rows[table]:
            supplier, part = row.get("supplier_id"), row.get("part_id")
            if supplier and supplier != sid:
                continue
            if part and part not in parts:
                continue
            if table == "suppliers" and row.get("id") != sid:
                continue
            if table == "parts" and row.get("id") not in parts:
                continue
            if not supplier and not part and table not in ("suppliers", "parts"):
                continue
            rows.append(row)
        return sorted(rows, key=lambda r: r.get("date") or r.get("quarter") or r.get("valid_from") or "", reverse=True)

    def dossier(self, case, sid):
        tables = {name: self.related(name, case, sid)[:10] for name in self.TABLES}
        refs = [r["id"] for r in tables["documents"] + tables["contracts"]]
        if trigger := case.get("trigger_doc"):
            refs.insert(0, trigger)
        docs = {ref: self.documents[ref][:5000] for ref in dict.fromkeys(refs) if ref in self.documents}
        # Facts-only Sunday releases still contribute supplier news and letters.
        release_facts = {
            ref: fact
            for ref, fact in self.facts.items()
            if ref.startswith(("news:", "doc:")) and fact.get("supplier") == sid
        }
        for ref in release_facts:
            if ref in self.documents:
                docs.setdefault(ref, self.documents[ref][:5000])
        return {"tables": {k: v for k, v in tables.items() if v}, "documents": docs, "news_and_letters": release_facts}

    def estimate(self, case, sid, standard):
        """A labelled estimate, never a claim to know the supplier's hidden cost floor."""
        rows = self.related("should_cost", case, sid)
        # A multi-part case has no unambiguous single unit cost.
        if len(case.get("parts", [])) != 1 or not rows:
            return None
        row = max(rows, key=lambda r: r.get("estimate_date", ""))
        part = next((r for r in self.rows["parts"] if r["id"] == row["part_id"]), {})
        if part and float(row["price_unit"]) != float(part["price_unit"]):
            return None
        return {
            "full_cost": float(row["unit_cost"]),
            "interest_rate": case["buyer"]["interest_rate"],
            "standard": standard,
            "source": row["id"],
            "uncertainty_pct": float(row.get("confidence_pct") or 15),
        }

    def evidence(self, case, sid):
        facts = {**self.facts, **case.get("facts", {})}
        out = []
        drivers = self.related("cost_drivers", case, sid)
        series = {row["series_id"] for row in drivers}
        # Inline case references work even when no package was provided.
        series.update(self.fact(case, ref).get("series") for ref in case.get("refs", []) if ref.startswith("idx:"))
        indices = [(ref, f) for ref, f in facts.items() if ref.startswith("idx:") and f.get("month")]
        newest = max((month_number(f["month"]) for _, f in indices), default=0)
        changes = []
        for name in sorted(s for s in series if s):
            rows = sorted(((ref, f) for ref, f in indices if f.get("series") == name), key=lambda r: r[1]["month"])
            if len(rows) < 2:
                continue
            end_id, end = rows[-1]
            end_month = month_number(end["month"])
            if newest - end_month > 12:
                continue
            windows = [
                (ref, f) for ref, f in rows if 3 <= end_month - month_number(f["month"]) <= 12 and float(f["value"]) > 0
            ]
            # Cite the actual, explicit window. Recent declines can coexist with an annual rise.
            start = max(windows, key=lambda pair: float(pair[1]["value"]), default=None)
            if not start or float(start[1]["value"]) <= 0:
                continue
            start_id, start = start
            change = (float(end["value"]) / float(start["value"]) - 1) * 100
            claim = Evidence(
                f"The {name} index changed {change:+.1f}% from {start['month']} to {end['month']} "
                f"({start_id}, {end_id}).",
                (start_id, end_id),
                "index",
            )
            changes.append((change, claim))
        out.extend(claim for _, claim in sorted(changes, key=lambda pair: pair[0]))
        cards = [(ref, f) for ref, f in facts.items() if ref.startswith("sc:") and f.get("supplier") == sid]
        if cards:
            ref, card = max(cards, key=lambda pair: pair[1].get("quarter", ""))
            if case["buyer"].get("category_goal") == "quality_first" and card.get("ppm") is not None:
                out.insert(0, Evidence(f"Recorded quality was {float(card['ppm']):g} ppm ({ref}).", (ref,), "quality"))
            elif card.get("otd_pct") is not None:
                out.append(Evidence(f"On-time delivery was {float(card['otd_pct']):g}% ({ref}).", (ref,), "delivery"))
        for row in self.related("should_cost", case, sid):
            ref = row["id"]
            fact = self.fact(case, ref)
            if fact.get("unit_cost") is not None:
                out.append(
                    Evidence(
                        f"Our should-cost estimate is EUR {float(fact['unit_cost']):.2f} per price unit "
                        f"({ref}); please help us reconcile this estimate with your cost breakdown.",
                        (ref,),
                        "cost",
                    )
                )
        for part in case.get("parts", []):
            forecasts = [(r, f) for r, f in facts.items() if r.startswith("fc:") and f.get("part") == part]
            if forecasts:
                ref, fact = max(forecasts, key=lambda pair: pair[0].rsplit("@", 1)[-1])
                if fact.get("change_pct") is not None and float(fact["change_pct"]) > 0:
                    out.append(
                        Evidence(
                            f"The demand forecast changed {float(fact['change_pct']):+.1f}% ({ref}).",
                            (ref,),
                            "volume",
                        )
                    )
        # Only the case's available alternative/quotes are commercial leverage; old RFQs
        # in the ERP are not represented as still available.
        alternative = case.get("buyer", {}).get("alternative") or {}
        refs = list(case.get("refs", [])) + [alternative.get("ref")]
        for ref in dict.fromkeys(refs):
            fact = self.fact(case, ref) if ref else {}
            if (
                ref
                and ref.startswith("quote:")
                and fact.get("part") in case.get("parts", [])
                and fact.get("supplier") != sid
                and fact.get("unit_price")
            ):
                out.insert(
                    0,
                    Evidence(
                        f"The alternative quote is EUR {float(fact['unit_price']):.2f} per price unit ({ref}).",
                        (ref,),
                        "rival",
                    ),
                )
        notice = self.fact(case, case.get("trigger_doc"))
        if notice.get("days") is not None and notice.get("supplier") == sid:
            for row in self.related("contracts", case, sid):
                contract = self.fact(case, row["id"])
                if contract.get("days") and float(notice["days"]) < float(contract["days"]):
                    out.insert(
                        0,
                        Evidence(
                            f"The letter gives {float(notice['days']):g} days of notice against the agreed "
                            f"{float(contract['days']):g} days ({case['trigger_doc']}, {row['id']}).",
                            (case["trigger_doc"], row["id"]),
                            "notice",
                        ),
                    )
                    break
        return out
