# Context Degradation Patterns

## Core Concept

Context degradation is predictable and follows distinct patterns as context grows. Understanding these patterns prevents performance failures.

## Five Degradation Patterns

### 1. Lost-in-Middle

U-shaped attention curve: beginning and end get reliable attention, middle suffers 10-40% lower recall.

- **Fix:** Place critical info at beginning or end. Use section headers to aid navigation.

### 2. Context Poisoning

Errors/hallucinations enter context and compound through repeated reference, creating feedback loops.

- **Symptoms:** Degraded output quality, tool misalignment, persistent hallucinations
- **Fix:** Truncate to before poisoning point, restart with clean context, or explicitly note the error

### 3. Context Distraction

Irrelevant information competes with relevant information for attention. Even ONE irrelevant document reduces performance.

- **Fix:** Filter aggressively before loading. Use tool calls instead of preloading.

### 4. Context Confusion

Model can't determine which context applies to current situation. Mixes requirements from multiple sources.

- **Fix:** Explicit task segmentation, clear transitions, isolate contexts for different objectives.

### 5. Context Clash

Accumulated information directly conflicts, creating contradictory guidance.

- **Fix:** Priority rules, version filtering, explicit conflict marking.

## The Four-Bucket Mitigation

| Strategy     | What It Does                                         |
| ------------ | ---------------------------------------------------- |
| **Write**    | Save context outside the window (scratchpads, files) |
| **Select**   | Pull only relevant context via retrieval/filtering   |
| **Compress** | Reduce tokens while preserving information           |
| **Isolate**  | Split context across sub-agents or sessions          |

## Key Insight

Larger context windows don't solve degradation. Performance remains stable up to a threshold, then degrades rapidly, regardless of window size.
