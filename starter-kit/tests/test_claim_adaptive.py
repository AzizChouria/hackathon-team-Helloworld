from arena_kit.commercial import adaptive_order, claim_reactions
from arena_kit.research import Evidence


def supplier(body):
    return {"from": "sales@x", "body": body}


def test_reactions_read_the_suppliers_own_sentences():
    events = [supplier(
        "We checked the delivery record you cited; it holds, but it does not change our calculation.\n"
        "We checked the index change data you cited; it holds and we took it into account.\n"
        "We did not know that - a fair point.")]
    assert claim_reactions(events) == {"delivery": -1, "index": 1}


def test_ordering_prefers_accepted_kinds_and_keeps_hard_facts_first():
    ev = [Evidence("d", ("sc:1",), "delivery"), Evidence("r", ("quote:1",), "rival"),
          Evidence("i", ("idx:1",), "index"), Evidence("v", ("fc:1",), "volume")]
    events = [supplier("We checked the delivery record; it holds, but it does not change our calculation. "
                       "We checked the forecast; it holds and we took it into account.")]
    assert [e.kind for e in adaptive_order(ev, events)] == ["rival", "volume", "index", "delivery"]


def test_no_reaction_keeps_the_order():
    ev = [Evidence("a", ("x",), "index"), Evidence("b", ("y",), "cost")]
    assert adaptive_order(ev, [supplier("Thank you.")]) == ev
