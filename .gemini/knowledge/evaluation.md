# Evaluation Frameworks

## Core Concept

Traditional metrics (ROUGE, BLEU) fail to capture functional quality. Use probe-based evaluation that directly tests whether the system can use preserved information.

## Probe-Based Evaluation

| Probe Type   | Tests             | Example                       |
| ------------ | ----------------- | ----------------------------- |
| Recall       | Factual retention | "What was the error message?" |
| Artifact     | File tracking     | "Which files were modified?"  |
| Continuation | Task planning     | "What should we do next?"     |
| Decision     | Reasoning chain   | "Why did we choose Redis?"    |

If the system answers correctly, information was preserved. If it guesses or hallucinates, compression/context management failed.

## Six Quality Dimensions

1. **Accuracy** — Technical details correct (file paths, function names, error codes)
2. **Context Awareness** — Reflects current conversation state
3. **Artifact Trail** — Knows which files were read/modified
4. **Completeness** — Addresses all parts of the question
5. **Continuity** — Can work continue without re-fetching
6. **Instruction Following** — Respects stated constraints

## LLM-as-Judge

Use a separate LLM to evaluate outputs against rubrics. Mitigate bias:

- Randomize option order (position bias)
- Use specific rubrics, not general "rate quality"
- Multiple judges for important evaluations
- Pairwise comparison for relative quality

## When to Evaluate

- After implementing compression strategies
- When changing context management approaches
- Periodically during production operation
- Before and after optimization changes
