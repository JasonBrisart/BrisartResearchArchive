# Band D — Homework Set 3

**Assign after:** Day 6 · **Due:** Day 8 · **Points:** 20

---

## Part 1 — Five-Cycle Trace (10 points)

Trace a real situation across five windows.

**Situation:** _______________________________

For each cycle:

```
CYCLE n
  Carried in (F(t-1)):         ________________
  Carried in (persistent Sim): ________________
  Input(t):                    ________________
  Minfo(t):                    ________________
  Sim(t):                      ________________
  E(t):                        high / low
  Above θ_persistence?         Y / N
  F(t):                        ________________
```

**Requirement:** Cycles 2-5 must each show inherited content. A cycle originating content from nowhere violates the architecture.

---

## Part 2 — Guarantee Mapping (6 points)

For three guarantees, state the observable consequence and the violating observation.

```
GUARANTEE 1: _______________________________
Observed if it holds: ______________________
Violated if we observed: ___________________

GUARANTEE 2: _______________________________
Observed if it holds: ______________________
Violated if we observed: ___________________

GUARANTEE 3: _______________________________
Observed if it holds: ______________________
Violated if we observed: ___________________
```

---

## Part 3 — The Convergence Limit (4 points)

The framework does **not** guarantee global convergence.

**(a)** Name the three conditions under which resolution does occur.

```
1. _______________________
2. _______________________
3. _______________________
```

**(b)** Why is declining to guarantee universal resolution a strength rather than a weakness?

```
_________________________________________________
```

---

## Scoring

| Part | Pts | Criteria |
|---|---|---|
| 1 | 10 | Five cycles; inheritance explicit in 2-5; persistence answers consistent with stated `E(t)` |
| 2 | 6 | Three guarantees; each violation names an observation |
| 3 | 4 | Congruence, contradiction-driven update, affective decay; (b) cites falsifiability |
