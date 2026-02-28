# Multi-Agent Architecture Patterns

## Core Concept

Sub-agents exist primarily to **isolate context**, not to anthropomorphize roles. Each agent operates in a clean context focused on its subtask.

## Three Patterns

### 1. Supervisor/Orchestrator

Central agent delegates to specialists, synthesizes results.

- **Use when:** Clear task decomposition, human oversight needed
- **Watch for:** Supervisor bottleneck, "telephone game" (supervisor paraphrases incorrectly)
- **Fix telephone game:** Allow sub-agents to pass responses directly to user

### 2. Peer-to-Peer / Swarm

Agents communicate directly via handoff mechanisms. No central control.

- **Use when:** Flexible exploration, emergent requirements
- **Watch for:** Divergence without central state keeper

### 3. Hierarchical

Layers: Strategy → Planning → Execution. Each layer has different context structure.

- **Use when:** Large-scale projects with clear hierarchy

## Token Economics

| Architecture         | Token Multiplier |
| -------------------- | ---------------- |
| Single agent chat    | 1×               |
| Single agent + tools | ~4×              |
| Multi-agent system   | ~15×             |

**Key insight:** Upgrading to better models often provides larger gains than doubling token budgets.

## Context Isolation Mechanisms

| Mechanism               | Trade-off                                          |
| ----------------------- | -------------------------------------------------- |
| Full context delegation | Maximum capability, defeats isolation purpose      |
| Instruction passing     | Maintains isolation, limits flexibility            |
| File system memory      | Shared state without context passing, adds latency |

## Failure Modes

- **Supervisor bottleneck** → Output schema constraints, checkpointing
- **Coordination overhead** → Minimize communication, batch results
- **Divergence** → Clear objective boundaries, convergence checks
- **Error propagation** → Validate outputs, retry with circuit breakers
