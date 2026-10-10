# Full hosted practice run — 10 October 2026

All **10 hosted practice cases** ran once. The mean score was **0.627333**, counting
errors as zero, with **10/10 valid deals** and **0 execution errors**.
The 0.8 mean target was **not met**; 3/10 individual cases reached 0.8.

**Model configuration problem:** `.env` selected `gpt-6.1-astra`, but completion requests
returned HTTP 404. A read-only query to the configured endpoint's model list did not contain
that model; it did contain the previously used `gpt-6.1-sol`. The buyer continued through its
built-in deterministic fallback, with **43 model fallback warnings**.
These results therefore evaluate that fallback policy, **not Astra's negotiation performance**.
The running batch was allowed to finish, and no replacement batch was opened.

## Results

| Case | Score | Outcome | Seconds | Rule fallback decisions | Replay |
|---|---:|---|---:|---:|---|
| P01 | 0.870550 | Valid deal | 67.52 | 2 | [View](https://arena.tacto.ai/replay/262b6a13dcc539ab) |
| P02 | 0.318973 | Valid deal | 105.62 | 4 | [View](https://arena.tacto.ai/replay/ae18dbaca97f9ece) |
| P03 | 0.922833 | Valid deal | 104.89 | 4 | [View](https://arena.tacto.ai/replay/e65bfa2be85647ab) |
| P04 | 0.860445 | Valid deal | 59.73 | 3 | [View](https://arena.tacto.ai/replay/ba06983a16001d2a) |
| P05 | 0.458784 | Valid deal | 220.72 | 10 | [View](https://arena.tacto.ai/replay/ea1e9d22e814df64) |
| P07 | 0.662570 | Valid deal | 84.54 | 4 | [View](https://arena.tacto.ai/replay/e4db01a1ace1e249) |
| P08 | 0.416011 | Valid deal | 97.42 | 4 | [View](https://arena.tacto.ai/replay/c4898639507710d8) |
| P10 | 0.670711 | Valid deal | 43.68 | 2 | [View](https://arena.tacto.ai/replay/6114477156c6fdbe) |
| P11 | 0.619591 | Valid deal | 173.11 | 7 | [View](https://arena.tacto.ai/replay/59846cb26f207f6f) |
| P18 | 0.472865 | Valid deal | 81.83 | 3 | [View](https://arena.tacto.ai/replay/2c1baf84b3c385a8) |

Claim checks reported by the host: 3 duplicate, 38 verified.
The slowest case took **220.72 seconds**.

## Configuration and quota

- Agent: `buyer-llm`; configured provider: `openai`; requested reasoning effort: `low`.
- Runtime source SHA-256: `cf0c3cf3ecff2ca6c76096fb8cb48686cc2fc9fd88e3416919ba453c1eeb09d0`. Source stayed unchanged during the batch.
- Ten parallel workers; 480 seconds per case, including the existing 90-second closing reserve.
- Hosted sessions opened: **10**. Quota: **493 → 483** remaining.
- Raw decision traces remain in the local temporary report; the repository record excludes them and credentials.

The earlier full hosted rehearsal averaged **0.621** with older code and a functioning
`gpt-6.1-sol` configuration. This single run cannot isolate a code or model effect, and local
synthetic scores are not comparable hosted measurements. Hidden cases remain untested.

## Reproduction

From `starter-kit`, the command used was:

```sh
.venv/bin/arena evaluate --agent buyer-llm --data ../data --parallel 10 --seconds 480 \
  --out /tmp/all-hosted-current-evaluation.json -v
```

Before another hosted batch, select a model available at the configured endpoint and confirm
one completion succeeds. That check does not require opening an Arena practice session.

[Machine-readable results](all-hosted-current-evaluation.json) · [Validation history](hidden-case-validation.md)
