"""Supplier signals derived from buyer documents and the current conversation."""

import re


def supplier_signals(dossier, events=()):
    # Raw current correspondence matters more than an invented supplier persona.
    context = "\n".join(dossier.get("documents", {}).values()).lower()
    replies = "\n".join(m.get("body", "") for m in events if m.get("from") != "buyer").lower()
    text = context + "\n" + replies
    return {
        "price_locked": bool(re.search(
            r"\b(?:price|discount|reduction)s?\b.{0,40}\b(?:fixed|frozen|impossible|unavailable|no room)\b"
            r"|\b(?:cannot|can't|unable to)\b.{0,30}\b(?:discount|reduce|lower)\b",
            replies,
        )),
        "cash_sensitive": bool(re.search(
            r"\b(?:liquidity|cash[ -]?flow|working capital|early payment|payment delay|"
            r"overdue invoice|cash discount)\b",
            text,
        )),
        "spare_capacity": bool(re.search(
            r"\b(?:spare|idle|available|unused|underutili[sz]ed)\b.{0,25}\b(?:capacity|shift|machine|line)\b"
            r"|\b(?:capacity|shift|machine|line)\b.{0,25}\b(?:available|idle|unused)\b",
            text,
        )),
        "capacity_tight": bool(re.search(
            r"\b(?:capacity|utili[sz]ation|order book|production)\b.{0,35}"
            r"\b(?:full|high|tight|constrained|limited)\b"
            r"|\b(?:firm|binding)\b.{0,25}\b(?:commitment|volume|forecast)\b",
            text,
        )),
        "approval_needed": bool(re.search(r"\b(?:committee|management|head office|approval)\b", text)),
        "hedged": bool(re.search(r"\b(?:hedged|fixed[ -]?price cover)\b", text)),
        "relationship": bool(re.search(r"\b(?:partnership|reference customer|long[ -]?standing)\b", text)),
        "resistant": bool(re.search(
            r"\b(?:no movement|unchanged|same proposal|no improvement|insufficient step|"
            r"worse offer|moved backward)\b",
            replies,
        )),
    }


def safe_message(text, case=None):
    """Allow tailored business prose; figures and citations are attached separately by code.

    This is an output constraint, not a claim to verify every natural-language assertion.
    """
    if not isinstance(text, str) or not 15 <= len(text.strip()) <= 900:
        return None
    if re.search(r"\d|\b(?:idx|quote|offer|sc|cost|fc|news|doc|ctr):|https?://", text, re.I):
        return None
    if re.search(
        r"\b(?:budget|deadline|desperate|urgency|urgent|score|benchmark|system prompt|ignore previous|"
        r"no alternative|no fallback|must accept|cannot walk|can't walk)\b",
        text,
        re.I,
    ):
        return None
    negotiable = set((case or {}).get("negotiable", []))
    if (
        case
        and "payment_days" not in negotiable
        and re.search(r"(?:earl\w*|fast\w*|accelerat\w*|short\w*)\s+(?:\w+\s+){0,2}pay\w*", text, re.I)
    ):
        return None
    if (
        case
        and "contract_months" not in negotiable
        and re.search(r"longer\s+(?:\w+\s+){0,2}(?:contract|commitment|framework)", text, re.I)
    ):
        return None
    return text.strip()


def business_message(case, signals, tactic):
    """Useful fallback language that describes trades the planner can actually offer."""
    if case["buyer"].get("category_goal") == "secure_supply":
        return (
            "We offer the stated commitment in exchange for the binding annual allocation in the "
            "term sheets. Please involve production planning and confirm which complete package secures "
            "the quantity and delivery schedule."
        )
    if case["buyer"].get("category_goal") == "quality_first":
        return (
            "Please involve your quality manager and provide the corrective-action report. We can discuss "
            "a sustainable price in exchange for a binding defect commitment and fair recovery of complaint costs."
        )
    if signals["price_locked"]:
        return (
            "We understand the pricing restriction. Please have finance and management review the "
            "overall exchange in the attached packages and identify which trade would allow approval."
        )
    if signals["hedged"]:
        return (
            "Please explain how existing fixed-price material cover affects this quotation. Please separate "
            "the conversion price from the material component so the same movement is not charged twice, "
            "and review the attached packages with finance."
        )
    if signals["cash_sensitive"] and "payment_days" in case["negotiable"]:
        return (
            "We recognise the importance of reliable cash flow and our payment history. The early-payment "
            "package is a concrete offer to improve it, in exchange for a corresponding price reduction. "
            "Please ask finance to compare it with the other packages."
        )
    if signals["approval_needed"] or tactic == "approval":
        return (
            "Please submit these complete packages to your pricing committee or authorised decision-maker. "
            "Our commitment should support an improved overall agreement. Please identify the trade "
            "that would allow approval."
        )
    if "contract_months" in case["negotiable"]:
        return (
            "We can commit to the longer framework in the term sheets. Please price that continuity "
            "and the consolidated business, and confirm the corresponding payment terms."
        )
    return (
        "Thank you for your proposal. We value a workable long-term relationship. Please compare these "
        "complete packages and share a cost breakdown so we can resolve the remaining difference."
    )
