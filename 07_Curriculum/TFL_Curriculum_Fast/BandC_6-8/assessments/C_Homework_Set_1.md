# Band C — Homework Set 1

**Assign after:** Day 2 · **Due:** Day 4 · **Points:** 15

---

## Part 1 — Variable Mapping (6 points)

Label all five components for two real moments.

**Moment 1:** _______________________________

```
Input(t):  _______________________________
Minfo(t):  _______________________________
Sim(t):    _______________________________
E(t):      high / medium / low
F(t):      _______________________________
```

**Moment 2:** _______________________________

```
Input(t):  _______________________________
Minfo(t):  _______________________________
Sim(t):    _______________________________
E(t):      high / medium / low
F(t):      _______________________________
```

**Requirement:** Each `Sim(t)` must be specific enough that someone could check whether it happened.

---

## Part 2 — Window Math (5 points)

The temporal window is roughly 100-300 ms. Use 200 ms as your estimate.

| Event | Duration | Estimated windows |
|---|---|---|
| A sneeze | 1 second | |
| Crossing a room | 8 seconds | |
| A 3-minute song | 180 seconds | |
| Your lunch period | | |

Then answer:

> A thought lasts about 5 seconds. Someone says "so the temporal window is 5 seconds." What's wrong with that?

```
_________________________________________________

_________________________________________________
```

---

## Part 3 — The Constraint (4 points)

In your own words, explain what `E(t)` does and what it does **not** do.

```
E(t) does: ______________________________________

E(t) does NOT: __________________________________
```

---

## Scoring

| Part | Points | Criteria |
|---|---|---|
| 1 | 6 | Both moments complete; `Sim(t)` specific and checkable |
| 2 | 5 | Four estimates reasonable; explains update rate ≠ content duration |
| 3 | 4 | States persistence gating; states it does not build the prediction or judge accuracy |
