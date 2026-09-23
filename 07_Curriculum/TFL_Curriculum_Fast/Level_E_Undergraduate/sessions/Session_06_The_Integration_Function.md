# Level E — Session 6: The Integration Function

**Duration:** 75 min

## Objective

Students read, decode, and reason with the integration relation, including conditional determinism.

---

## 1. Frame — What's Missing (8 min)

Point at the board.

    F(t) = w1·Input(t) + w2·Minfo(t) + w3·Sim(t)

**Ask:** Five declared variables. How many appear here?

Three inputs plus `F(t)` as output. `E(t)` is absent.

**Say:**
> "Session 7 is that absence. Today, everything except it."

---

## 2. Build — Reading the Relation (25 min)

Decode term by term.

| Term | Meaning |
|---|---|
| `F(t)` | The integrated state at this window |
| `w1` | Weight on sensory input |
| `w2` | Weight on retrieved memory |
| `w3` | Weight on predictive simulation |

Read it aloud as a sentence. Require students to do the same.

**Conditional determinism:**

    Given fixed Input(t), Minfo(t), Sim(t), and fixed
    parameter values, the resulting F(t) is uniquely determined.

**Say:**
> "Same inputs, same weights, same output. Variability across implementations comes from parameterization, measurement, or input conditions — not from randomness in the architecture. That's a commitment, and it's checkable."

**Parameters are not quantities people possess:**

> "The weights are model parameters requiring empirical estimation. Nobody has a `w2` in their head. A weight you cannot connect to data is decoration."

---

## 3. Contest — Is Linear Weighting Defensible? (20 min)

Assigned positions:

- **Student A:** Linear additive combination is a simplification that almost certainly misdescribes the process; interactions between memory and simulation are expected.
- **Student B:** Linearity is the correct starting point — it is the simplest form that produces distinct predictions, and complexity should be added only when data demand it.

**Say:**
> "A is likely right about the world. B is right about method. The framework's position is B, and the honest description is that linearity is a first approximation the framework has committed to in exchange for estimability."

**Then:** "What observation would force the framework to abandon linearity?" Collect. This previews Session 13.

---

## 4. Apply — Weight Cases (17 min)

| Case | w1 | w2 | w3 | Dominant | Expected system behavior |
|---|---|---|---|---|---|
| A | 0.7 | 0.2 | 0.1 | | |
| B | 0.2 | 0.6 | 0.2 | | |
| C | 0.1 | 0.2 | 0.7 | | |
| D | 0.33 | 0.33 | 0.33 | | |

Then:
1. In which case does behavior most closely track incoming evidence?
2. In which case would two people receiving identical input diverge most?

**Critical framing, stated aloud:**
> "These describe system behavior. They do not describe people, personality types, or conditions. A high-`w3` description is not a diagnosis and not a character sketch."

---

## 5. Propagate (5 min)

**Say:**
> "Next session is the pivot of this course. The missing variable, and why its absence is the most falsifiable claim in the framework."

---

## Instructor Notes

- Students from quantitative backgrounds will want to fit the equation to data. Redirect: estimation requires measured variables, which is Level F.
- The "not a description of a person" framing must be said explicitly every time weight cases appear. Without it, Case C reliably becomes an amateur diagnosis by the end of the hour.
