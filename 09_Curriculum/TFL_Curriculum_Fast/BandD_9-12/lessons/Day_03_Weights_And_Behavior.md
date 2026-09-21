# Band D — Day 3: Weights and Behavior

**Duration:** 50 min

---

## Objective

Students predict system behavior from parameter changes.

---

## 1. Hook — Predict Before Computing (6 min)

**Say:**
> "`w2` doubles. Everything else holds. What changes?"

Take predictions before any analysis.

**Say:**
> "Today you build the reasoning that makes that answerable without guessing."

---

## 2. Name — The Control Parameters (12 min)

Write the full parameter set:

```
CONTROL PARAMETERS

Integration weights (w1, w2, w3)
  → relative influence of input, memory, simulation

Persistence threshold (θ_persistence)
  → determines simulation carry-over

Belief weighting
  → constrains retrieval and simulation under ambiguity

Feedback-driven update conditions
  → modification versus suppression of active simulations
```

**Say:**
> "These are the controllable dimensions. And there's a requirement attached: they must be linked to observable quantities in valid implementations."

Underline that. It becomes Day 7.

---

## 3. Work — The Parameter Table (20 min)

Students complete a full prediction table.

| Change | Effect on `F(t)` | Effect on behavior |
|---|---|---|
| `w1` increases | | |
| `w2` increases | | |
| `w3` increases | | |
| `θ_persistence` raised | | |
| `θ_persistence` lowered | | |
| `E(t)` drops below threshold | | |

Then two integrative questions:

**1.** Which change would produce behavior most tightly tracking the environment?

**2.** Which combination would produce the longest-lasting simulations?

---

## 4. Compare — The Threshold Direction Error (10 min)

Poll: raising `θ_persistence` — more persistence or less?

**Less.** A higher bar means fewer simulations clear it.

This is the most common Band D reversal error. Address it directly:

```
θ_persistence ↑  →  harder to persist  →  fewer carry-overs
θ_persistence ↓  →  easier to persist  →  more carry-overs
```

---

## 5. Carry (2 min)

**Say:**
> "Tomorrow: the question from Day 2. Why `E(t)` isn't in the integration function."

---

## Assessment

Administer **Quiz 1** at the start of Day 4.
