"""Supplier signals derived from buyer documents and the current conversation."""

import re


def supplier_signals(dossier, events=()):
    # Raw current correspondence matters more than an invented supplier persona.
    context = "\n".join(dossier.get("documents", {}).values()).lower()
    replies = "\n".join(m.get("body", "") for m in events if m.get("from") != "buyer").lower()
    text = context + "\n" + replies
    return {
        "price_locked": any(
            s in text
            for s in (
                "frozen all price",
                "freeze on price",
                "freeze on reductions",
                "no room on price",
                "unable to offer any further discounts",
            )
        ),
        "cash_sensitive": any(
            s in text
            for s in (
                "liquidity",
                "cash flow",
                "cash-flow",
                "bank is watching",
                "cash discount",
                "pay earlier",
                "pay our invoices within",
                "overdue invoices",
            )
        ),
        "spare_capacity": any(s in text for s in ("second shift has been on hold", "additional parts at short notice")),
        "capacity_tight": any(
            s in text
            for s in (
                "high capacity utilisation",
                "high capacity utilization",
                "order intake is very strong",
                "prioritise customers with firm",
                "binding 12-month commitment",
            )
        ),
        "approval_needed": any(s in text for s in ("pricing committee", "head office", "approval")),
        "hedged": "covered at fixed prices" in text or "hedged" in text,
        "relationship": any(s in text for s in ("expects partnership", "reference customer", "long-standing")),
        "resistant": any(
            s in replies
            for s in (
                "moved backwards",
                "no movement",
                "no genuine",
                "exact same figures",
                "unchanged proposal",
            )
        ),
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
