"""Case-scoped evidence; facts and hypotheses are kept separate."""
import hashlib
import json

from ..cost import closing_terms
from ..data import DataPackage


class Intelligence:
    def __init__(self, package=None):
        self.package = package
        self.signature = self.fingerprint()
        self.cache = {}

    def fingerprint(self):
        if not self.package:
            return ""
        roots = {self.package.root, self.package.root.parent / "release-sunday"}
        if self.package.release:
            roots.add(self.package.release)
        entries = []
        for root in roots:
            if root.exists():
                for p in root.rglob("*"):
                    if p.is_file() and p.suffix in {".json", ".sqlite", ".db", ".csv", ".md", ".txt", ".pdf", ".xlsx"}:
                        s = p.stat()
                        entries.append((str(p), s.st_mtime_ns, s.st_size))
        return hashlib.sha256(repr(sorted(entries)).encode()).hexdigest()

    def refresh(self):
        signature = self.fingerprint()
        if signature != self.signature and self.package:
            old = self.package
            self.package = DataPackage(old.root, old.release)
            if old.db:
                old.db.close()
            self.signature, self.cache = signature, {}

    def prepare(self, case, sid):
        key = (sid, self.signature, json.dumps(case, sort_keys=True, default=str))
        if key in self.cache:
            return self.cache[key]
        p = self.package
        facts = {**(p.facts if p else {}), **case.get("facts", {})}
        parts = set(case["parts"])
        related = {k: v for k, v in facts.items()
                   if v.get("supplier") == sid and (not v.get("part") or v.get("part") in parts)
                   or v.get("part") in parts and not v.get("supplier")}
        evidence, notes, hypotheses = [], [], []
        # Only precomputed sentences can become supplier claims; model chooses their indices.
        cards = [(k, v) for k, v in related.items() if k.startswith("sc:")]
        if cards:
            k, v = max(cards)
            if case.get("type") == "quality":
                evidence.append({"refs": [k], "text": f"Your rolling scorecard reports {v['ppm']} ppm ({k})."})
            elif case.get("type") == "capacity":
                evidence.append({"refs": [k], "text": f"Recorded on-time delivery is {v['otd_pct']}% ({k})."})
        estimate = None
        if p:
            # Public tables supply richer context than the small claim-checking facts.
            rows = (p.query("SELECT * FROM documents WHERE supplier_id = ? ORDER BY date DESC",
                            (sid,), 12) if p.db else [])
            rows.sort(key=lambda r: (r["id"] != case.get("trigger_doc"),
                                    not any(part in str(r.get("part_ids")) for part in parts)))
            if p.db:
                for table in ("supplier_intel", "contracts", "sourcing", "quotes", "invoices"):
                    extra = p.query(f"SELECT * FROM {table} WHERE supplier_id = ?", (sid,), 3)
                    notes.extend(json.dumps(row, default=str)[:700] for row in extra)

            # Trigger documents may exist only in the Sunday release, outside SQLite.
            trigger = case.get("trigger_doc")
            trigger_row = p.lookup(trigger) if trigger else None
            triggers = [trigger] if trigger and (
                len(case["suppliers"]) == 1 or trigger_row and trigger_row.get("supplier_id") == sid
            ) else []
            document_notes = []
            for ref in dict.fromkeys(triggers + [row["id"] for row in rows[:5]]):
                try:
                    document_notes.append(p.document(ref)[:1200])
                except (FileNotFoundError, ValueError, UnicodeError):
                    pass
            notes = document_notes + notes
            for _ref, row in sorted(p._ids.items(), reverse=True):
                if row.get("supplier_id") == sid and row.get("table") in {"news", "supplier_intel"}:
                    notes.append(json.dumps(row, default=str)[:900])
            for part in parts:
                master = p.lookup(part) or {}
                unit = master.get("price_unit", 1)
                hypotheses.append(f"{part}: ERP price_unit={unit}; preserve case monetary convention.")
                if p.db:
                    rows = p.query("SELECT * FROM should_cost WHERE part_id = ?", (part,))
                    for row in rows:
                        if row.get("supplier_id") == sid and row.get("price_unit", 1) == unit:
                            estimate = {"full_cost": row["unit_cost"], "interest_rate": 0.12}
                            hypotheses.append("Relationship estimate: supplier-specific should-cost, "
                                              "uncertain by at least 5%; financing assumption 12%, not verified.")
                    history = p.query("SELECT * FROM negotiation_history WHERE supplier_id = ? AND part_id = ? "
                                      "ORDER BY date DESC", (sid, part), 2)
                    notes.extend(json.dumps(x) for x in history)
                    # Do not turn historic or stale prices into fictitious current competing quotes.
                    orders = p.query("SELECT id, price, price_unit, price_note FROM po_lines "
                                     "WHERE supplier_id = ? AND part_id = ? ORDER BY order_date DESC",
                                     (sid, part), 8)
                    clean = [r for r in orders if r["price_note"] != "stale_condition"][:2]
                    if len(clean) == 2 and all(r["id"] in facts for r in clean):
                        ids = [r["id"] for r in clean]
                        evidence.append({"refs": ids, "text": "Please review our recorded order price history "
                                         f"for this part ({', '.join(ids)})."})
                    drivers = p.query("SELECT series_id FROM cost_drivers WHERE part_id = ?", (part,))
                    for driver in drivers:
                        series = driver["series_id"]
                        values = sorted((k, v) for k, v in facts.items()
                                        if k.startswith("idx:") and v.get("series") == series)
                        if len(values) < 2:
                            continue
                        end_id, end = values[-1]
                        year, month = map(int, end["month"].split("-"))
                        start_month = f"{year - 1:04}-{month:02}"
                        starts = [(k, v) for k, v in values if v["month"] >= start_month and k != end_id]
                        if not starts:
                            continue
                        start_id, start = starts[0]
                        change = (end["value"] / start["value"] - 1) * 100
                        if change < 0:
                            evidence.insert(0, {"refs": [start_id, end_id],
                                "text": f"{series} changed {change:+.2f}% between {start['month']} "
                                        f"and {end['month']} ({start_id}, {end_id})."})
        # Case-specific Sunday facts supplement package evidence; never cite unknown IDs.
        for ref in case.get("refs", []):
            if ref in facts and ref.startswith("news:") and facts[ref].get("supplier") == sid:
                evidence.append({"refs": [ref], "text": f"Could we discuss the implications of this news ({ref})?"})
        result = {"evidence": evidence[:8], "notes": notes[:8], "hypotheses": hypotheses,
                  "estimate": estimate, "fingerprint": self.signature}
        self.cache[key] = result
        return result

    def estimate(self, case, sid, std):
        raw = self.prepare(case, sid)["estimate"]
        if not raw:
            return None
        return {**raw, "standard": closing_terms(case, std)}
