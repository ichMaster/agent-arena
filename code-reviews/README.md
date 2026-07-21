# code-reviews/ — full per-branch review documents

The detailed, unabridged code reviews behind [`../branch-comparison-report.md`](../branch-comparison-report.md).
Each was produced by an independent read-only review pass (via `git show` against the branch tip —
no checkouts) covering: inventory, architecture adherence, correctness, typing, testing,
security/robustness, spec quality, speed, post-generation bugs, and 4-criteria scores.

| File | Branch | Spec → Code | Mode |
|---|---|---|---|
| [Anthropic-Opus4.8-Opus4.8-dev.md](Anthropic-Opus4.8-Opus4.8-dev.md) | `Anthropic-Opus4.8-Opus4.8-dev` | Opus 4.8 → Opus 4.8 | pipeline |
| [Anthropic-Opus4.8-Sonet5-dev.md](Anthropic-Opus4.8-Sonet5-dev.md) | `Anthropic-Opus4.8-Sonet5-dev` | Opus 4.8 → Sonnet 5 | pipeline |
| [Anthropic-Gemini3.1Pro-Sonet5-dev.md](Anthropic-Gemini3.1Pro-Sonet5-dev.md) | `Anthropic-Gemini3.1Pro-Sonet5-dev` | Gemini 3.1 Pro → Sonnet 5 | pipeline |
| [Gemini-3.1Pro-3.5Flash-dev.md](Gemini-3.1Pro-3.5Flash-dev.md) | `Gemini-3.1Pro-3.5Flash-dev` | Gemini 3.1 Pro → Gemini 3.5 Flash | pipeline |
| [Gemini-3.1Pro-3.1Pro-dev.md](Gemini-3.1Pro-3.1Pro-dev.md) | `Gemini-3.1Pro-3.1Pro-dev` | Gemini 3.1 Pro → Gemini 3.1 Pro | pipeline |
| [Anthropic-Opus4.8-dev.md](Anthropic-Opus4.8-dev.md) | `Anthropic-Opus4.8-dev` | Opus 4.8 (interactive) | interactive |
| [Gemini-3.1Pro-dev.md](Gemini-3.1Pro-dev.md) | `Gemini-3.1Pro-dev` | Gemini 3.1 Pro (interactive) | interactive |

Note: on each branch there are also the *in-pipeline* review artifacts written during its own build
(`spec/implementation/*-code-review.md` on the Anthropic-pipeline branches,
`spec/implementation/code-review-report.md` on `Anthropic-Gemini3.1Pro-Sonet5-dev`) — those are the
builds' self-reviews; the files here are the independent cross-branch comparison reviews.
