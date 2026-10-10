# Hello World Buyer

Hollerau needs an autonomous procurement agent that can defend price increases, renew contracts,
source new parts and improve quality. It must research the company data, exchange e-mails with
supplier bots, and accept one binding term sheet or walk away.

For the operating decisions supported by our practice runs, use the [negotiation strategy](strategy.md).
The [historical evaluation report](evaluation.md) preserves earlier results and failures; the
[active strategy validation](hidden-case-validation.md) records the latest hosted rehearsal.

## Why the problem is harder than haggling

The objective is the case's total cost over its fixed demand and horizon. A €41.60 quote for
12 months can cost more than €43.20 for 24 months because the uncovered second year must be
purchased at the fallback price. Payment, freight, lead times, quality, tooling and index clauses
also change the result. Strategic categories add a penalty for pushing the supplier below a
sustainable margin. Breaking one must-have gives a score of zero.

The supplier's documents matter: omitted fields close on its standard terms. Negotiation also
depends on people and circumstances. A supplier with a cash shortage may value early payment;
another may need a longer commitment or approval from its owner. Valid evidence must be relevant,
accurate, and cited by ID. Each supplier thread has a 60-second reply clock.

## Implementation

1. **Prepare shared research.** `Research` reads the package's CSV tables and canonical facts,
   including the Sunday release. Supplier dossiers include notes, letters, contracts, news,
   should-cost estimates, scorecards, forecasts and previous negotiations. The factory loads
   data and documents before opening any session; agents assemble case dossiers from memory.
2. **Compute evidence.** Market changes use two observations from the same series,
   3–12 months apart, with a recent endpoint; the strongest recent decline is quoted with its
   explicit start and end dates, rather than described as an annual trend. Relevant series come from the part's
   records. Quality and delivery use the latest scorecard; should-cost and growing demand can
   supply additional arguments. E-mails quote figures from code alongside their source IDs.
   Contract notice discrepancies provide another grounded argument. Transcripts track previously
   cited evidence, including after a restart, and citations are reserved before parallel requests
   complete. A cheaper current competing offer is used only if it meets the case's must-haves.
3. **Search commercial packages.** The planner evaluates the published cost function and each
   must-have over allowed term options, including the supplier's standard values. It searches
   exactly up to 4,096 combinations and uses a beam of 64 partial candidates for larger menus.
   It proposes the best computed package, an earlier-payment/price trade when feasible, and an
   alternative such as symmetric indexation or lower complaint chargebacks. Quality cases also
   offer the least demanding permitted defect guarantee with minimal chargebacks, so the supplier
   can price a simpler route to compliance. Equal-cost choices
   favour more delivery time, longer commitments and less demanding quality guarantees within
   the must-haves. This avoids asking suppliers for extra effort with no modelled buyer benefit.
   Alternatives now share the primary bid's full-cost budget: financing, quality liability,
   index risk and any estimated relationship penalty are paid for through the price. A delivery
   alternative also tests extra permitted production time, discounting enough to cover its
   lateness cost. This can uncover cheaper deals that a fixed-price term search misses.
   The buyer promotes the supplier's compliant combination to the first slot, repairs an
   infeasible quoted term to the nearest permitted compliant value, and carries concessions
   forward by total cost when package order changes. RFQs prioritize verified cheaper rival
   evidence and anchor opening bids to compliant market cost. At the final stage, the buyer
   protects the cheapest ready quote while allowing a bounded challenge to another bidder.
   Concessions respond to resistance and preserve previous price moves. Price anchors remain
   heuristics; the search does not know the supplier's hidden floor.
4. **Choose a negotiation tactic.** `buyer` uses category and supplier-context rules.
   `buyer-llm` gives the model the dossier, recent messages, attachments, fixed and negotiable
   fields, must-haves, and the actual proposed packages. It selects evidence and writes a short
   response to the supplier's objections. Code rejects narrative containing digits, source IDs,
   URLs, common sensitive disclosures, or certain promises to change fixed terms. The model
   cannot set binding terms or accept a deal. This prose filter is a practical constraint, not
   a semantic proof of every sentence; rejected prose uses a supplier-aware template instead.
   The model's explanation remains private.
5. **Keep the negotiation moving.** Independent RFQ requests run concurrently, with one request
   in flight per supplier. The coordinator owns the transcripts and decisions. Final offers
   are never countered. Once every bidder has been contacted, a final offer or agreement
   triggers comparison after outstanding replies arrive. A viable final offer normally gets a
   30-second age guard. The guard extends to 45 seconds when a pending bidder has a compliant
   standing quote at least 1% cheaper on full estimated cost; this leaves time to settle the
   ready offer. Near a wave cap, the agent can accept a valid ready offer without waiting for
   an outstanding supplier request.
   Attachments download concurrently. An expired-offer response refreshes the standing terms
   and reruns the acceptance checks; the same rejected offer is never retried indefinitely.
   The model has a ten-second decision
   budget and a bounded shared worker pool; invalid, failed or slow calls use the computed
   strategy. Each case retains at most one outstanding model call.
6. **Close deliberately.** Every standing sheet is evaluated, including multiple packages in
   one supplier reply. The agent accepts the cheapest feasible sheet that beats or matches the
   alternative; otherwise it walks away. The same guard runs when the final wave deadline
   forces closure. The original runner retains its wave polling, session recovery, request
   pacing and idempotent retries.

For strategic categories, a supplier-specific should-cost row provides an estimate for the
relationship term. It is used only when the part and price unit match. The trace records its
source and uncertainty. This is an estimate of supplier economics, not privileged knowledge;
when no matching estimate exists the relationship term remains unpriced, as in the kit.

## Run it

From the repository root:

```bash
cd starter-kit
uv sync --extra sim
uv run arena benchmark --data ../data --out /tmp/arena-benchmark.json
```

The benchmark needs no API credentials, network, LLM or background server. It uses the actual
simulator's message validation, quote PDFs, cost-breakdown attachments and settlement code.
Its JSON report includes terms, costs, scores and decision explanations.

For hosted play, configure `starter-kit/.env` or environment variables. Real environment
variables take precedence; `.env` is already ignored by git.

| Variable | Use |
|---|---|
| `ARENA_URL` | Hosted arena URL, or the local simulator's address |
| `ARENA_API_KEY` | Your team key; required for hosted play |
| `ARENA_DATA` | Data directory; use `../data` from `starter-kit`, or pass `--data` |
| `ARENA_RELEASE` | Optional explicit Sunday release directory |
| `LLM_PROVIDER` | `anthropic` or `openai` for the existing compatible-endpoint adapter |
| `LLM_MODEL` | Model name from your provider; required for `buyer-llm` |
| `ANTHROPIC_API_KEY` | Required for the Anthropic adapter |
| `LLM_BASE_URL` | Optional URL for a compatible model endpoint |
| `LLM_API_KEY` | Key for that compatible endpoint |
| `LLM_EFFORT` | Optional effort setting supported by your Anthropic model |
| `LLM_REASONING_EFFORT` | Optional OpenAI-compatible reasoning effort override; `buyer-llm` defaults to `low` |

`buyer` makes no model calls. `buyer-llm` requires a configured provider; missing provider
configuration fails at startup, before a session is opened. Runtime model failures fall back
automatically. For Anthropic, install `uv sync --extra sim --extra anthropic` first.
Practice `buyer-llm` play/run checks a real model reply before opening sessions.
`evaluate --agent buyer-llm --require-model` also checks a tactical response and records
successful calls and fallbacks per case.

```bash
uv run arena play case:P01 --agent buyer --data ../data -v
uv run arena play case:P01 --agent buyer-llm --data ../data -v
uv run arena run --set practice --agent buyer-llm --data ../data --parallel 8 -v
```

For a repeatable experiment with a saved report and replay links:

```bash
uv run arena evaluate --agent buyer-llm --require-model --data ../data --parallel 5 \
  --out /tmp/arena-evaluation.json
# Or spend only one session per selected case:
uv run arena evaluate --cases case:P05 case:P10 case:P11 --agent buyer-llm \
  --data ../data --out /tmp/arena-targeted.json
```

`evaluate` opens one session per selected hosted practice case and checks the remaining quota
first. It saves each result as it finishes, including errors, replay links, rounds,
model-call counts, claim-check counts, private decisions, and a source-code fingerprint.
Failed runs count as zero in the mean.
The default budget is 390 seconds per case, including a 90-second closing reserve; use
`--seconds 480` to match the final wave duration. Reports contain private reasoning, so the
checked-in evaluation summary includes only metrics and replay links.

For the final, refresh the data before starting the runner:

```bash
uv run arena data --out ../data
uv run arena run --set final --agent buyer --data ../data --parallel 10 -v
```

The [hosted comparison](codex-hosted-comparison-20261010.md) measured 0.654 mean for
`buyer` and 0.617 for `buyer-llm` across one ten-case batch each, with zero model
fallbacks. That evidence currently favors `buyer` for the final launch; hidden cases
and Sunday data can change the choice. To use the model, replace `buyer` with
`buyer-llm` in the command.

The data command creates `../data/package` and `../data/release-sunday`. The committed base data
is already in `../data`; `DataPackage` merges the release there. Alternatively, use
`--data ../data/package` to use the newly downloaded base package. Data is loaded at startup.
The final agent never reads the leaderboard, results, screen or event feed.

Verbose logs include private research and decision reasoning, so use the negotiation replay,
rather than raw private logs, when sharing e-mails with suppliers.

## Validation and practical limits

```bash
uv run pytest
uv run ruff check .
```

Tests cover research and Sunday data, arithmetic and citation windows, total-cost search,
must-haves, supplier standard terms, multiple standing offers, relationship estimates, model
failures and injection attempts, fixed-term constraints, supplier-friendly choices at equal cost,
concurrent citation reservation, restart-safe evidence usage, deadline closure, concurrent RFQs,
expiring offers, acceptance recovery and concurrent attachment downloads,
evaluation failures and quota checks, and negotiations through both local simulators.

| Simulator case | Baseline cost (€) | Buyer cost (€) | Baseline score | Buyer score |
|---|---:|---:|---:|---:|
| S01 | 112,451.50 | 107,488.38 | 0.521 | 0.888 |
| S02 | 614,057.20 | 586,072.63 | 0.513 | 0.886 |
| S03 | 3,864,138.60 | 3,688,263.16 | 0.678 | 0.927 |

These results validate mechanics against a scripted opponent. The latest local suite passed
**124 tests, with 1 optional test skipped**, and lint passed. The historical hosted evaluation record covers
34 sessions across several revisions: five matched cases averaged **0.583 initially and 0.620
in the later full-practice batch**. The complete ten-case batch averaged **0.559**, including
one acceptance error. Targeted follow-ups then tested quality packages and settlement handling.
See [the historical record](evaluation.md) and [current validation](hidden-case-validation.md),
including the RFQ score regression after conservative closure.

The earlier RFQ timing, opening and concession changes had local validation and one hosted P05
follow-up scoring 0.452; they have not had another complete hosted rehearsal. The
[local score report](local-score-optimization.md) records a separate 48-case holdout mean of
0.816–0.821 and its limitations. The subsequent
[equal-value package change](package-exchange-validation.md) reached **0.834394** on the same
48-case parameter holdout, compared with **0.815851** for the immediately preceding buyer.
That exchange revision had local validation, including a separate delivery mechanism test.
The subsequent [supplier-preference and competition policy](competitive-strategy-validation.md)
reached a local holdout mean of **0.842956**. Its first hosted P05 test regressed to 0.350283;
after a timing correction the second scored **0.458784**, a small gain over 0.451910, still
below 0.8. Both runs and individual local regressions are recorded in that report.
These observations do not predict final competition scores. The agent does not know exact hidden
supplier preferences, its beam search can miss the global optimum, and estimated supplier margins
can differ from private costs. Natural-language filtering is not a complete defence against
misleading prose. Supplier replies vary, so the next comparison should repeat the same cases
under consistent conditions.

For submission, use this repository, the short approach description above, and
[the pitch deck](pitch.md). Record the commit that you actually run using `git rev-parse HEAD`
after committing your final changes. Uploading to ehl.gg and starting the hosted final are
separate operational steps.
