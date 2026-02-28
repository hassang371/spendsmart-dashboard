# Project Development Patterns

## Task-Model Fit

Match task complexity to the right approach:

| Task Type       | Approach                        | Context Needs    |
| --------------- | ------------------------------- | ---------------- |
| Simple query    | Single turn                     | Minimal          |
| Multi-step task | Agent with tools                | Moderate         |
| Complex project | Multi-agent with planning       | High (partition) |
| Long-running    | Agent with memory + compression | Managed          |

## Idempotent Pipelines

Design agent pipelines that can be safely re-run:

- Same input → same output (deterministic where possible)
- Checkpoints for long-running tasks
- Graceful resumption after failures
- No side effects from partial execution

## Structured Output

Use structured formats for agent communication:

- JSON for data exchange between agents
- Markdown for human-readable reports
- Explicit schemas for tool inputs/outputs
- Validation at boundaries

## Development Workflow

1. **Start small** — single agent, simple tools
2. **Measure** — token usage, quality, latency
3. **Optimize** — compression, caching, partitioning
4. **Scale** — multi-agent only when single-agent limits reached
5. **Evaluate** — probe-based testing, continuous monitoring

## Error Handling

- Retry with backoff for transient errors
- Circuit breakers for repeated failures
- Fallback strategies (simpler approach when complex fails)
- Log everything for debugging (but compress old logs)

## Anti-Patterns

- Building multi-agent before proving single-agent works
- Ignoring token economics
- No evaluation framework
- Premature optimization
- Assuming larger context = better results
