"""Commercial commitments and objections derived only from the buyer's live case."""

import os
import re

from .cost import closing_terms


def objections(events):
    """Use the latest reply, not an old objection that the supplier already resolved."""
    reply = next((m.get("body", "") for m in reversed(events) if m.get("from") != "buyer"), "")
    return {
        "volume": bool(re.search(
            r"(?:which|what|binding|commit\w*|higher).{0,35}volume|volume.{0,35}commit", reply, re.I,
        )),
        "breakdown_refused": bool(re.search(
            r"(?:do not|don't|not).{0,25}share.{0,30}(?:breakdown|detail|calculation)"
            r"|\b(?:do not|don't|cannot|can't|will not|won't)\b.{0,30}"
            r"\b(?:provide|give|send|do)\b.{0,25}\b(?:cost\s+)?(?:breakdowns?|calculations?)\b"
            r"|(?:breakdown|calculation|cost detail).{0,30}(?:confidential|proprietary|internal)",
            reply, re.I,
        )),
        "stalled": bool(re.search(
            r"\b(?:unchanged|no movement|insufficient improvement|same proposal|token concession|"
            r"marginal reduction)\b", reply, re.I,
        )),
    }


def commercial_brief(case, packages, dossier, events, standard=None):
    """Make the permitted commitment explicit; do not imply extra unpriced business.

    The model may explain the exchange but code owns the numeric terms, including
    fixed volume/duration omitted from the negotiable term sheets.
    """
    if not packages:
        return ""
    terms = [closing_terms(case, p, standard) for p in packages]
    first = terms[0]
    parts = dossier.get("tables", {}).get("parts", [])
    unit = parts[0].get("uom", "units") if len(parts) == 1 else "units"
    unit = unit if unit in {"pc", "kg", "t", "m", "units", "set"} else "units"
    quantity = first["volume_per_year"]
    duration = first["contract_months"]
    commitment = f"Our lead package commits {quantity:g} {unit} per year"
    commitment += f" for {duration:g} months" if duration else " as the stated order"
    commitment += "; the alternatives are separate complete offers, not cumulative commitments."
    if objections(events)["volume"] and "volume_per_year" not in case["negotiable"]:
        commitment += " This is the firm quantity available; please price it without assuming additional volume."
    details = (
        f"For that commitment we offer EUR {first['unit_price']:.2f} per price unit, "
        f"payment in {first['payment_days']:g} days and delivery in {first['lead_time_days']:g} days."
    )
    if clause := first.get("index_clause"):
        details += (
            f" The proposed {clause['series']} clause covers {clause['material_share'] * 100:g}% "
            f"with a {clause['deadband_pct']:g}% deadband."
        )
    return commitment + " " + details


def relevant_evidence(evidence, case, events, dossier, fact):
    """Do not argue against ourselves or repeat an explicitly inapplicable hedge claim."""
    messages = [m for m in events if m.get("from") != "buyer"]
    reply = messages[-1].get("body", "") if messages else ""
    source_text = "\n".join(dossier.get("documents", {}).values()) + "\n" + reply
    # Restrict a hedge exclusion to its named series, so unrelated conversion/energy
    # evidence remains available. A generic hedge statement cannot identify a series.
    sentences = re.split(r"[.!?\n]", source_text)
    offers = messages[-1].get("term_sheets", []) if messages else []
    prices = [s['terms']['unit_price'] for s in offers if s.get('terms', {}).get('unit_price')]
    asking = min(prices, default=float('inf'))
    out = []
    for e in evidence:
        if e.kind == 'cost' and any(float(fact(ref).get('unit_cost') or 0) >= asking for ref in e.refs):
            continue
        if e.kind == 'history':
            paid = [float(fact(ref).get('unit_price') or 0) for ref in e.refs]
            if not paid or sum(paid) / len(paid) >= asking:
                continue  # history that is not cheaper than today's ask argues against us
        if e.kind == 'index':
            series = {fact(ref).get('series') for ref in e.refs} - {None}
            if any(
                name.lower() in sentence.lower()
                and re.search(r'hedg|covered at fixed|fixed.price.{0,20}cover|secured at fixed', sentence, re.I)
                for name in series for sentence in sentences
            ):
                continue
        out.append(e)
    # Volume makes a useful opening exchange; delivery evidence alone does not
    # rebut a material-price increase. Model selection may still choose other facts.
    priority = {'notice': 0, 'rival': 1, 'quality': 2, 'index': 3, 'volume': 4, 'cost': 5, 'delivery': 6,
                'history': 7, 'news': 8}
    return adaptive_order(sorted(out, key=lambda e: priority.get(e.kind, 9)), events)


_KINDS = (  # first match wins; words the supplier uses for what it checked
    ('index', r'index|indices|series'), ('delivery', r'deliver|on-time|punctual'),
    ('volume', r'forecast|demand|volume'), ('cost', r'should-?cost|cost estimate|estimate'),
    ('notice', r'notice|contract'), ('quality', r'quality|ppm|defect|complaint'),
    ('rival', r'quote|offer|rival|alternative'), ('history', r'order history|orders|purchase'),
    ('news', r'press|news|report'),
)


def claim_reactions(events):
    """How this supplier treated each kind of claim we cited: +1 'took it into account', -1 'does not change
    our calculation'. Read from its own sentences, so it adapts to any supplier without a hard-coded persona."""
    score = {}
    for m in events:
        if m.get('from') == 'buyer':
            continue
        for sentence in re.split(r'(?<=[.!?])\s+|\n', m.get('body', '') or ''):
            low = sentence.lower()
            if 'holds' not in low and 'checked' not in low:
                continue
            kind = next((k for k, pat in _KINDS if re.search(pat, low)), None)
            if kind is None:
                continue
            if re.search(r'does not change|doesn.t change|not change our', low):
                score[kind] = score.get(kind, 0) - 1
            elif re.search(r'took it into account|taken into account|fair point', low):
                score[kind] = score.get(kind, 0) + 1
    return score


def adaptive_order(evidence, events):
    """Keep notice/rival first (hard facts); then claim kinds this supplier accepted before kinds it ignored."""
    if os.environ.get('LAB_ADAPTIVE') == '0':
        return evidence
    w = claim_reactions(events)
    return sorted(evidence, key=lambda e: (0 if e.kind in ('notice', 'rival') else 1, -w.get(e.kind, 0)))
