# Micro-Lesson C3: Threshold Walk

**Duration:** 7 minutes
**Band:** C (6-8)
**Materials:** Board

---

## Purpose

Make the persistence condition readable symbol by symbol.

## Script

Write:

```
Sim(t+1) = Sim(t),  if  E(t) > θ_persistence
```

**Say:**
> "Nobody translates the whole thing at once. One symbol at a time."

Walk it:

| Symbol | Say aloud |
|---|---|
| `Sim(t+1)` | "The simulation in the next window" |
| `=` | "is the same as" |
| `Sim(t)` | "the simulation now" |
| `if` | "but only when" |
| `E(t)` | "the intensity right now" |
| `>` | "is greater than" |
| `θ_persistence` | "the persistence threshold" |

**Full read:**
> "The next window keeps this simulation only if the intensity clears the threshold."

## The Check Question

> "Why doesn't `E(t)` show up in the integration function?"

Answer: because affective intensity functions exclusively as a persistence gate and does not contribute to integration.

Students who can answer this understand the model's most distinctive constraint.

## Use

Any time before Band D. Also effective as exam review.
