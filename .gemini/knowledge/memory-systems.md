# Memory System Design

## Core Concept

Memory provides persistence across sessions. Key insight: **tool complexity matters less than reliable retrieval** — filesystem agents outperformed specialized memory tools in benchmarks.

## Memory Layers

| Layer       | Persistence             | Implementation                | When                         |
| ----------- | ----------------------- | ----------------------------- | ---------------------------- |
| Working     | Context window          | Scratchpad in prompt          | Always                       |
| Short-term  | Session                 | Files, in-memory cache        | Intermediate results         |
| Long-term   | Cross-session           | Key-value → graph DB          | User prefs, domain knowledge |
| Entity      | Cross-session           | Entity registry               | Identity consistency         |
| Temporal KG | Cross-session + history | Graph with validity intervals | Facts that change over time  |

## Choosing Architecture

**Start simple, add complexity only when retrieval fails:**

1. **Prototype:** File-system memory (JSON with timestamps)
2. **Scale:** Vector store with metadata (Mem0)
3. **Complex reasoning:** Temporal knowledge graph (Zep/Graphiti)
4. **Full control:** Agent self-management (Letta)

## Retrieval Strategies

| Strategy                   | Best For                     |
| -------------------------- | ---------------------------- |
| Semantic (embedding)       | Direct factual queries       |
| Entity-based (graph)       | "Tell me everything about X" |
| Temporal (validity filter) | Facts that change over time  |
| Hybrid (all combined)      | Best overall accuracy        |

## Anti-Patterns

- Stuffing everything into context (use just-in-time retrieval)
- Ignoring temporal validity (facts go stale)
- Over-engineering early (filesystem first)
- No consolidation strategy (memory grows unbounded)

## Error Recovery

- Empty retrieval → broaden search, ask user
- Stale results → check timestamps, trigger consolidation
- Conflicting facts → prefer most recent, surface conflict
- Storage failure → queue writes, never block agent response
