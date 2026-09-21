# Band D — Day 6: Guarantees

**Duration:** 50 min

---

## Objective

Students state what the architecture commits to and where those commitments stop.

---

## 1. Hook — Guarantee or Not? (6 min)

Read four claims. Students vote.

```
1. "The loop always resolves eventually."
2. "Same inputs and parameters give the same F(t)."
3. "E(t) can escalate without limit."
4. "Every implementation exposes the same five variables."
```

Answers: 1 no, 2 yes, 3 no, 4 yes.

---

## 2. Name — The Guarantee Set (16 min)

Write the core commitments:

```
STATE CONTINUITY
  Selective, not exhaustive. Only simulations meeting
  persistence criteria carry forward.

THRESHOLD-GATED PERSISTENCE
  Only simulations above θ_persistence are carried.

CONDITIONAL DETERMINISM
  Fixed inputs + fixed parameters → unique F(t).

TEMPORAL WINDOW CONSTRAINT
  One integration per discrete cycle. No integration
  outside the cycle.

BOUNDED AFFECTIVE PERSISTENCE
  E(t) is bounded; no unbounded escalation.

STANDARDIZED VARIABLE INTERFACE
  All valid implementations expose the five variables.

MEASURABLE STATE EVOLUTION
  Recurrence, intensity, and alignment are observable.
```

**Then the limit:**

```
CONVERGENCE IS NOT GLOBALLY GUARANTEED.

Resolution occurs only under:
  - sufficient congruence between Sim(t) and Input(t)
  - contradiction-driven updating or suppression
  - decay of E(t) below threshold
```

**Say:**
> "Note what's missing. The framework does not promise that every simulation resolves. A model that guaranteed universal resolution would be making a much stronger and much less defensible claim."

---

## 3. Work — Guarantee Mapping (18 min)

Students map each guarantee to a testable consequence.

```
Guarantee: _______________________________

What would we observe if it holds?
_______________________________

What observation would violate it?
_______________________________
```

Complete four.

The violation column is the valuable one — it converts guarantees into falsifiable claims.

---

## 4. Compare — The Strongest Violation (8 min)

Collect the clearest violation conditions.

**Say:**
> "You've just written the beginnings of falsification tests. That's Day 10."

---

## 5. Carry (2 min)

**Say:**
> "Tomorrow: the requirement that makes all of this real. Every parameter has to connect to something you can actually measure."

---

## Homework

Assign **Homework Set 3**.
