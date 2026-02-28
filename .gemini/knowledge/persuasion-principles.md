# Persuasion Principles for Skill Design

**Load this when:** creating or refining workflow skills, designing rules, or debugging why a model ignores instructions.

## Why This Matters

Research (Meincke et al., 2025, N=28,000 AI conversations): Persuasion techniques more than doubled LLM compliance rates (33% → 72%).

LLMs are "parahuman" — trained on human text containing these patterns. Authority language precedes compliance in training data.

## The Three Most Effective Principles

### 1. Authority

Imperative language: "YOU MUST", "Never", "No exceptions."
Eliminates decision fatigue and rationalization.

```markdown
✅ Write code before test? Delete it. Start over. No exceptions.
❌ Consider writing tests first when feasible.
```

### 2. Commitment

Require announcements and explicit choices. Track with checklists.

```markdown
✅ When you find a skill, you MUST announce: "I'm using [Skill Name]"
❌ Consider letting your partner know which skill you're using.
```

### 3. Scarcity (Urgency)

Time-bound requirements prevent "I'll do it later."

```markdown
✅ After completing a task, IMMEDIATELY request code review before proceeding.
❌ You can review code when convenient.
```

## Principle Combinations by Skill Type

| Skill Type           | Use                                   | Avoid               |
| -------------------- | ------------------------------------- | ------------------- |
| Discipline-enforcing | Authority + Commitment + Social Proof | Liking, Reciprocity |
| Guidance/technique   | Moderate Authority + Unity            | Heavy authority     |
| Collaborative        | Unity + Commitment                    | Authority, Liking   |
| Reference docs       | Clarity only                          | All persuasion      |

## Why Bright-Line Rules Work

- "YOU MUST" removes decision fatigue
- Absolute language eliminates "is this an exception?" questions
- "When X, do Y" (implementation intentions) creates automatic behavior
- Explicit anti-rationalization counters specific loopholes

## Quick Design Checklist

1. What type of skill is this? (Discipline vs. guidance vs. reference)
2. What behavior am I trying to change?
3. Which principle(s) apply? (Usually authority + commitment for discipline)
4. Am I combining too many? (Don't use all seven)
5. Is this ethical? (Serves user's genuine interests?)
