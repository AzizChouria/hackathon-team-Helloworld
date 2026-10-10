# Hello World Buyer

Hollerau needs an autonomous procurement agent that can defend price increases, renew contracts,
source new parts and improve quality. It must research the company data, exchange e-mails with
supplier bots, and accept one binding term sheet or walk away.

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
2. **Compute evidence.** Market changes use two observations from the same series, at most
   12 months apart, with a recent endpoint. Relevant cost-driver series come from the part's
   records. Quality and delivery use the latest scorecard; should-cost and growing demand can
   supply additional arguments. E-mails quote figures from code alongside their source IDs.
   Transcripts track previously cited evidence, including after a restart. Current competing
   offers can be cited separately to each bidder.
3. **Search commercial packages.** The planner evaluates the published cost function and each
   must-have over allowed term options, including the supplier's standard values. It searches
   exactly up to 4,096 combinations and uses a beam of 64 partial candidates for larger menus.
   It proposes the best computed package, an earlier-payment/price trade when feasible, and a
   longer commitment when that produces a distinct package. Price anchors and incremental
   concessions are heuristics; the search does not know the supplier's hidden floor.
4. **Choose a negotiation tactic.** `buyer` uses category and supplier-context rules.
   `buyer-llm` gives the model the dossier, recent supplier messages and attachment text. The
   model chooses a tactic and up to two computed arguments. Code writes the e-mail from those
   selections. Model-generated text cannot inject a price, an unverified claim, a private budget
   or an accept action. The model's reason is retained privately for explanation.
5. **Keep the negotiation moving.** Independent RFQ requests run concurrently, with one request
   in flight per supplier. The coordinator owns the transcripts and decisions. Final offers
   are never countered. Once every bidder has been contacted, a final offer or agreement
   triggers comparison after outstanding replies arrive. The model has an eight-second decision
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

`buyer` makes no model calls. `buyer-llm` requires a configured provider; missing provider
configuration fails at startup, before a session is opened. Runtime model failures fall back
automatically. For Anthropic, install `uv sync --extra sim --extra anthropic` first.

```bash
uv run arena play case:P01 --agent buyer --data ../data -v
uv run arena play case:P01 --agent buyer-llm --data ../data -v
uv run arena run --set practice --agent buyer-llm --data ../data --parallel 8 -v
```

For the final, refresh the data before starting the runner:

```bash
uv run arena data --out ../data
uv run arena run --set final --agent buyer-llm --data ../data --parallel 10 -v
```

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
failures and injection attempts, restart-safe evidence usage, deadline closure, concurrent RFQs,
and full negotiations through both the in-process and HTTP simulators.

| Simulator case | Baseline cost (€) | Buyer cost (€) | Baseline score | Buyer score |
|---|---:|---:|---:|---:|
| S01 | 112,451.50 | 107,488.38 | 0.521 | 0.888 |
| S02 | 614,057.20 | 586,072.63 | 0.513 | 0.886 |
| S03 | 3,864,138.60 | 3,688,263.16 | 0.678 | 0.927 |

These results validate the interface and basic strategy against a scripted opponent. A separate
hosted P01 run of `buyer-llm` closed a deal at **0.755** (unit price €137.20), versus an earlier
**0.585** before correcting the offer progression and evidence selection. All its cited claims
were verified, and the configured model returned successfully without fallback. The last small
concession adjustment, made after that hosted run, has local test coverage only. A single hosted
case does not predict final competition scores. The agent does not infer exact hidden supplier
preferences, its beam search can miss the global optimum, and estimated supplier margins can
differ from the arena's
private costs. The fixed tactic vocabulary makes outgoing claims auditable but limits how
flexibly the model can phrase and adapt arguments.

For submission, use this repository, the short approach description above, and
[the pitch deck](pitch.md). Record the commit that you actually run using `git rev-parse HEAD`
after committing your final changes. Uploading to ehl.gg and starting the hosted final are
separate operational steps.
