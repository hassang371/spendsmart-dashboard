# Context Fundamentals

## Core Concept

Context is the complete state available to a language model at inference time: system instructions, tool definitions, retrieved documents, message history, and tool outputs. Context engineering is curating the smallest high-signal token set that achieves desired outcomes.

## Context Components

| Component        | Position | Persistence  | Budget Impact                                      |
| ---------------- | -------- | ------------ | -------------------------------------------------- |
| System prompts   | Front    | Session-long | Low (loaded once)                                  |
| Tool definitions | Front    | Session-long | Low-medium                                         |
| Retrieved docs   | Middle   | On-demand    | Variable                                           |
| Message history  | Growing  | Accumulates  | High (dominates long sessions)                     |
| Tool outputs     | Inline   | Per-call     | Very high (83.9% of total in typical trajectories) |

## Attention Budget

The attention mechanism creates n² relationships between n tokens. As context grows, the model's ability to capture relationships gets stretched thin. This creates a finite "attention budget" that depletes with context length.

## Progressive Disclosure

Load information only as needed. At startup, load only skill names/descriptions. Full content loads only when activated. This keeps agents fast while giving access to more context on demand.

## Key Principles

1. **Informativity over exhaustiveness** — include what matters, exclude what doesn't
2. **Position matters** — beginning and end get more attention than middle
3. **Quality over quantity** — 50 focused tokens > 500 unfocused tokens
4. **File system as context** — store externally, load on demand
5. **Context is iterative** — curate each time you pass tokens to the model
