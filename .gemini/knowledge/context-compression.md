# Context Compression Strategies

## Core Concept

Optimize for **tokens-per-task** (total tokens to complete a task), not tokens-per-request. Aggressive compression that loses critical details causes expensive re-fetching.

## Three Approaches

| Method             | Ratio | Quality | Best For                              |
| ------------------ | ----- | ------- | ------------------------------------- |
| Anchored Iterative | 98.6% | 3.70/5  | Long sessions, file tracking          |
| Regenerative       | 98.7% | 3.44/5  | Clear phase boundaries                |
| Opaque             | 99.3% | 3.35/5  | Maximum token savings, short sessions |

**Anchored Iterative** (recommended): Maintain structured summaries with explicit sections. On compression, summarize only new content and merge with existing summary. Structure forces preservation.

## Structured Summary Template

```markdown
## Session Intent

[What the user is trying to accomplish]

## Files Modified

- file.ts: What changed

## Decisions Made

- Decision and rationale

## Current State

- Test status, blockers

## Next Steps

1. Immediate next action
```

## Compression Triggers

| Trigger         | When                        |
| --------------- | --------------------------- |
| Fixed threshold | 70-80% context utilization  |
| Task boundary   | At logical task completions |
| Sliding window  | Keep last N turns + summary |

## Artifact Trail Problem

File tracking is the weakest dimension across ALL compression methods (2.2-2.5/5). Consider maintaining a separate file index for coding tasks.

## Key Insight

0.7% more tokens retained by structured summarization buys 0.35 quality points. For any task where re-fetching costs matter, structured approaches win.
