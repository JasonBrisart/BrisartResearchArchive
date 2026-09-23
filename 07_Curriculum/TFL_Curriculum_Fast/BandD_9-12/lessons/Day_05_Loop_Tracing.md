# Band D — Day 5: Loop Tracing

**Duration:** 50 min

---

## Objective

Students hand-trace the system across multiple cycles with correct propagation.

---

## 1. Hook — The Trace Standard (5 min)

**Say:**
> "A trace is correct when cycle 3 could not have been written without cycle 2. If your cycles are independent, you've written a list."

---

## 2. Name — The Cycle Sequence (10 min)

Write the execution order:

```
WITHIN EACH WINDOW:
  1. Input(t) is sampled
  2. Minfo(t) is retrieved
  3. Sim(t) is generated
  4. E(t) is registered
  5. F(t) is computed
  → F(t) and persistent Sim carried forward
```

**Say:**
> "All components update once per cycle. All cross-window effects happen through explicit propagation of `F(t)` and surviving simulations. Nothing integrates outside the cycle."

---

## 3. Work — The Five-Cycle Trace (25 min)

Students trace a defined scenario across five windows.

**Scenario provided:** A student is waiting for an announcement that has been delayed twice already.

**Per cycle:**

```
CYCLE n
  Carried in (F(t-1)):        ______________
  Carried in (persistent Sim): ______________
  Input(t):                   ______________
  Minfo(t):                   ______________
  Sim(t):                     ______________
  E(t):                       high / low
  Above θ_persistence?        Y / N
  F(t):                       ______________
  Propagated forward:         ______________
```

**Requirement:** every cycle after the first must show what it inherited.

**Circulate checking one thing only:** the "carried in" lines.

---

## 4. Compare — Break the Trace (8 min)

Put a trace on the board with cycle 4 inheriting nothing.

**Ask:**
> "Where does this violate the architecture?"

Students should cite: cross-window effects occur only through explicit propagation, so a cycle cannot originate content from nowhere.

---

## 5. Carry (2 min)

**Say:**
> "Tomorrow: what the architecture guarantees — and what it explicitly refuses to guarantee."
