# Band D — Day 2: The Integration Function

**Duration:** 50 min

---

## Objective

Students read, decode, and apply the integration relation.

---

## 1. Hook — What's Missing? (6 min)

Write:

```
F(t) = w1·Input(t) + w2·Minfo(t) + w3·Sim(t)
```

**Say:**
> "Five declared variables. Count how many appear here."

Three, plus `F(t)` as output. Four total.

**Ask:**
> "Which one is absent?"

`E(t)`.

**Say:**
> "That absence is the most distinctive structural claim in the framework. Hold that question until Day 4."

---

## 2. Name — Reading the Relation (14 min)

Decode it term by term.

| Term | Meaning |
|---|---|
| `F(t)` | The integrated state at this window |
| `w1` | Weight on sensory input |
| `w2` | Weight on retrieved memory |
| `w3` | Weight on predictive simulation |
| `+` | Contributions combine |

**Say:**
> "Read aloud: the integrated state is the weighted combination of input, memory, and simulation."

**Key property — conditional determinism:**

```
Given fixed Input(t), Minfo(t), Sim(t), and fixed
parameter values, the resulting F(t) is uniquely
determined.
```

**Say:**
> "Same inputs, same weights, same output. Variability across implementations comes from parameterization, measurement, or input conditions — not from randomness built into the architecture."

---

## 3. Work — Structural Computation (20 min)

Students compute relative contributions with assigned weights.

**Example given:**
```
w1 = 0.6, w2 = 0.3, w3 = 0.1
```

**Ask:** Which component dominates `F(t)`? What kind of behavior would that produce?

Students then work four cases:

| Case | w1 | w2 | w3 | Dominant | Expected behavior |
|---|---|---|---|---|---|
| A | 0.7 | 0.2 | 0.1 | | |
| B | 0.2 | 0.6 | 0.2 | | |
| C | 0.1 | 0.2 | 0.7 | | |
| D | 0.33 | 0.33 | 0.33 | | |

**Important framing:** these are model parameters, not measured quantities students possess. State this explicitly.

---

## 4. Compare — Case C (8 min)

Focus on the simulation-dominant case.

**Ask:**
> "What does behavior look like when `w3` dominates?"

Steer toward: prediction-driven interpretation, input mattering less, expectation shaping what gets experienced.

**Say:**
> "That's a structural description. It is not a description of any person or condition."

---

## 5. Carry (2 min)

**Say:**
> "Tomorrow: what happens to system behavior when these weights shift."

---

## Homework

Assign **Homework Set 1**.
