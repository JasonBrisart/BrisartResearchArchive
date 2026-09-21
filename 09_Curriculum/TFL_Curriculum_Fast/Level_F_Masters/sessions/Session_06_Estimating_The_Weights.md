# Level F — Session 6: Estimating the Weights

**Duration:** 100 min

## Objective

Students determine what estimating `w1`-`w3` would require and decide honestly whether their design can do it.

---

## 1. Frame — Parameters Are Not Decoration (12 min)

Point at the integration relation.

**Say:**
> "Three weights. The framework requires that control parameters be linked to observable quantities in valid implementations. So: what would it take to estimate these, and can you?"

---

## 2. Build — Estimation Requirements (30 min)

To estimate the weights you need, at minimum:

    - Input(t), Minfo(t), and Sim(t) each measured on a
      common or convertible scale
    - F(t) measured independently of its three inputs
    - Variation across observations sufficient to identify
      three coefficients
    - Inputs that are not collinear with one another

**Say:**
> "The fourth is where this usually dies. Memory and simulation are correlated by construction in most tasks — the prediction comes from the memory. Collinear predictors make the individual weights unidentifiable even with good measurement."

**The independent `F(t)` problem:**

> "If you measure the integrated state by asking what someone expected, you have measured `Sim(t)` again. `F(t)` needs an instrument that is not one of its own components."

**The honest position, and it is acceptable:**

> "Most course designs cannot estimate the weights. That is not a failure. Declare them as unestimated in your design and test claims that do not depend on their values. The gating claim, contradiction effects, and persistence dynamics are all testable without knowing `w1`."

---

## 3. Contest — Is an Unestimable Model Meaningful? (25 min)

- **Student A:** A model with three free parameters nobody has estimated is not a model, it is a schema. Its predictions are whatever the parameters need to be.
- **Student B:** Conditional determinism is the answer. Fixed inputs plus fixed parameters yield a unique `F(t)`. The claim is structural, and structural claims are testable without point estimates.

**Say:**
> "A's challenge is serious and the framework's answer is B, but B only works if the structural claims are genuinely independent of the parameter values. Check that. Which of the framework's claims survive if `w1`, `w2`, and `w3` are unknown?"

Most do. The persistence gate in particular is untouched. That is worth discovering rather than being told.

---

## 4. Apply — Estimation Feasibility Statement (28 min)

    Can this design estimate w1, w2, w3?     Yes / No / Partially
    If no, why:
    Which claims does my design test that do not depend on the weights:
    Which claims am I therefore excluded from testing:

---

## 5. Propagate (5 min)

**Say:**
> "You now know what you can and can't measure. Next: designing so that the result means something — adjudication."

---

## Assessment

Administer the **Operationalization Examination** after this session.

## Instructor Notes

- Engineering and CS students will propose simulating the equations. Redirect firmly: a simulation demonstrates the model's behavior, it does not test whether the model describes people.
- The discovery that the gating claim survives parameter ignorance is the session's best moment. Do not give it away early.
