# Context Management Rules

These rules are loaded at startup. Apply them continuously throughout every session.

## Attention Budget

Your context window is finite. Every token competes for attention (n² scaling). Load only what's needed for the current decision.

- System prompts + tool definitions = low cost (loaded once)
- Tool outputs = highest cost (83.9% of total in typical sessions)
- Message history = accumulates and dominates long sessions

## Compression Triggers

| Signal                     | Action                                            |
| -------------------------- | ------------------------------------------------- |
| 70-80% context utilization | Checkpoint to `.gemini/current_state.md`          |
| Task boundary completion   | Summarize completed work, discard exploration     |
| Tool output processed      | Mask verbose outputs once their purpose is served |
| Context feels crowded or progress unclear | Read and follow `context-checkpoint.md` workflow  |

### Compression Technique (Anchored Iterative)

Maintain structured summaries in `current_state.md`:

- Session Intent → Files Modified → Decisions Made → Current Status → Next Steps
- On compression: summarize only new content, merge with existing summary
- NEVER compress system prompts or active task context

## Degradation Patterns — Recognize and Fix

| Pattern                 | Symptom                                      | Fix                                                 |
| ----------------------- | -------------------------------------------- | --------------------------------------------------- |
| **Lost-in-Middle**      | Missing info from middle of context          | Place critical info at beginning/end                |
| **Context Poisoning**   | Errors compound through repeated reference   | Truncate to before poisoning, restart clean         |
| **Context Distraction** | Irrelevant info degrades output quality      | Filter aggressively, use tool calls over preloading |
| **Context Confusion**   | Mixing requirements from multiple sources    | Explicit task segmentation, clear transitions       |
| **Context Clash**       | Contradictory guidance from accumulated info | Priority rules, version filtering                   |

## Optimization Strategies

1. **Mask tool outputs** — Replace verbose outputs with compact summaries once processed
2. **Stable content first** — System prompt → tool definitions → reusable elements → unique content
3. **Partition when needed** — Split independent work across sub-agents with isolated contexts
4. **File system as context** — Store intermediate results in scratch files, load on demand

## Self-Assessment

Ask yourself at task boundaries and whenever output quality feels off:

1. Is my context growing faster than my progress? → Compress
2. Am I re-reading the same files? → Summarize and cache in scratch file
3. Is output quality declining? → Check for degradation patterns above
4. Am I loading information I won't use? → Stop preloading, use just-in-time retrieval
