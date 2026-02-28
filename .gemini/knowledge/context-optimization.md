# Context Optimization Techniques

## Core Concept

Extend effective context capacity through strategic compression, masking, caching, and partitioning. Quality matters more than quantity.

## Four Optimization Strategies

### 1. Compaction

Summarize context near limits, reinitialize with summary. Priority:

- Tool outputs → summarize (highest impact)
- Old turns → compress early conversation
- Retrieved docs → summarize if recent versions exist
- System prompt → NEVER compress

### 2. Observation Masking

Tool outputs = 80%+ of token usage. Replace verbose outputs with compact references once their purpose is served.

- **Never mask:** Current task observations, most recent turn, active reasoning
- **Always mask:** Repeated outputs, boilerplate, already-summarized content

### 3. KV-Cache Optimization

Place stable elements first (system prompt, tool definitions), then reusable elements, then unique content. Avoid dynamic content like timestamps in shared prefixes.

### 4. Context Partitioning

Split work across sub-agents with isolated contexts. Most aggressive but often most effective. Each sub-agent operates in clean context focused on its subtask.

## When to Optimize

| Signal                    | Strategy                      |
| ------------------------- | ----------------------------- |
| Tool outputs dominate     | Observation masking           |
| Retrieved docs dominate   | Summarization or partitioning |
| Message history dominates | Compaction with summarization |
| Multiple components       | Combine strategies            |

## Performance Targets

- Compaction: 50-70% token reduction, <5% quality loss
- Masking: 60-80% reduction in masked observations
- Cache: 70%+ hit rate for stable workloads
