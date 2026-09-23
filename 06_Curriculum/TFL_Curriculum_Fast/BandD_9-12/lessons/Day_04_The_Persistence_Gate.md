# Band D — Day 4: The Persistence Gate

**Duration:** 50 min

---

## Objective

Students explain why affective intensity is structurally separated from integration.

---

## 1. Quiz 1 (10 min)

---

## 2. Hook — Resolve the Day 2 Question (5 min)

**Say:**
> "Two days ago you noticed `E(t)` is missing from the integration function. Here's where it lives instead."

Write:

```
Sim(t+1) = Sim(t),  if  E(t) > θ_persistence
```

---

## 3. Name — Exclusive Gating (14 min)

Write the constraint as explicitly as possible:

```
E(t) functions EXCLUSIVELY as a persistence gate.

It does NOT:
  - contribute to integration weighting
  - participate in simulation construction
  - indicate accuracy
```

**Say:**
> "Most intuitive models of emotion say the opposite — that strong feeling colors everything. This framework makes a narrower claim, and the narrowness is what makes it testable."

**Draw the separation:**

```
INTEGRATION          PERSISTENCE
Input(t) ─┐
Minfo(t) ─┼→ F(t)    E(t) > θ → Sim carries forward
Sim(t)  ──┘          E(t) ≤ θ → decay / replace / suppress
          ↑
      no E(t) here
```

**Also write the bounded property:**

```
E(t) is bounded within a finite range.
It cannot produce unbounded escalation.
```

---

## 4. Work — The Structural Argument (16 min)

Students write a formal argument.

**Prompt:**

> A researcher proposes modifying TFL so that `E(t)` also scales `w3`, on the grounds that strong feelings make predictions dominate perception.
>
> Write a response addressing: (a) what this changes structurally, (b) what it costs in testability, (c) what evidence would be required to justify it.

This is a genuine architectural argument, not a comprehension check.

---

## 5. Compare — The Cost (5 min)

Collect responses on (b).

Strong answers note: the modification would let the model absorb results that currently contradict it, which weakens falsifiability.

---

## Homework

Assign **Homework Set 2**.
