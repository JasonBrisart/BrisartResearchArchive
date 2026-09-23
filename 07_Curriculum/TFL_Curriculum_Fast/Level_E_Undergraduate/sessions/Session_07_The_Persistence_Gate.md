# Level E — Session 7: The Persistence Gate

**Duration:** 75 min

## Objective

Students explain why affective intensity is structurally separated from integration, and evaluate that separation as a claim.

**This is the pivot session of Level E.**

---

## 1. Frame — Resolving the Absence (8 min)

**Say:**
> "Two sessions ago you noticed `E(t)` is missing from the integration function. Here is where it lives instead."

Write:

    Sim(t+1) = Sim(t),  if  E(t) > θ_persistence

Decode symbol by symbol, aloud, slowly. Require a student to read it back as a sentence.

---

## 2. Build — Exclusive Gating (25 min)

Write the constraint as strongly as the framework states it:

    E(t) functions EXCLUSIVELY as a persistence gate.

    It does NOT:
      - contribute to integration weighting
      - participate in simulation construction
      - indicate accuracy

Draw the separation:

    INTEGRATION                PERSISTENCE

    Input(t) ─┐
    Minfo(t) ─┼→ F(t)          E(t) >  θ → Sim carries forward
    Sim(t)  ──┘                E(t) ≤  θ → decay / replace / suppress
              ↑
         no E(t) here

Below threshold, three outcomes:

    - simulations decay
    - alternative simulations are generated
    - prior simulations are suppressed

**Bounded property:**

    E(t) is bounded within a finite range.
    It cannot produce unbounded escalation.

**Say:**
> "Most intuitive accounts of emotion say the opposite — that strong feeling colors everything. This framework makes a deliberately narrower claim. The narrowness is what makes it testable, and it is also the framework's most exposed position."

**Threshold direction — address the standard reversal:**

    θ_persistence ↑ → higher bar → fewer clear it → LESS persistence
    θ_persistence ↓ → lower bar  → more clear it  → MORE persistence

---

## 3. Contest — The Gate Is Wrong (22 min)

The most important Contest phase in Level E. Assign in advance.

- **Student A:** Affective intensity demonstrably shapes perception and interpretation, not merely retention. The exclusive-gating claim is empirically implausible.
- **Student B:** The framework's narrowness is the point. A model where affect touches everything absorbs any result.

After both, pose the deciding question to the room:

> "What observation would settle this? Be specific."

Target answer, which students usually reach with prompting:

> Integration weights shift systematically with measured `E(t)`, with inputs held constant.

**Say:**
> "That's a real falsification condition for a specific claim. Write it down — it appears on your final."

---

## 4. Apply — The Structural Argument (15 min)

Written, individual, 150-250 words:

> A researcher proposes modifying TFL so that `E(t)` also scales `w3`, on the grounds that strong feelings make predictions dominate perception.
>
> Address: (a) what changes structurally, (b) what it costs in testability, (c) what evidence would justify it.

Strong answers on (b) note that the modification lets the framework absorb results that currently contradict it.

---

## 5. Propagate (5 min)

**Say:**
> "Next session you test the gate against your own logged data. Bring the log."

---

## Assessment

Administer **Problem Set 2** and the **Midterm Examination** after this session.

## Instructor Notes

- Do not cut this session. If the term compresses, cut Session 10.
- The contest here should end unresolved. A student who leaves certain in either direction has been over-steered.
