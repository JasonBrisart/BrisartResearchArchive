# Band D — Day 1: The Declared Variable Set

**Duration:** 50 min

---

## Objective

Students understand variable closure — that the system is fully defined by its declared set, with no additional latent processes assumed.

---

## 1. Hook — Add a Variable (8 min)

**Say:**
> "Here's the system: `Input(t)`, `Minfo(t)`, `Sim(t)`, `E(t)`, `F(t)`. Propose a sixth variable that would make it better."

Students propose: attention, motivation, confidence, fatigue.

Write them all on the board.

**Say:**
> "Every one of these is plausible. The framework declines all of them. Today: why that's a design decision, not an oversight."

---

## 2. Name — Closure (14 min)

Write the constraint:

```
VARIABLE CLOSURE

All valid inferences are restricted to:
  Input(t), Minfo(t), Sim(t), E(t), F(t)

No additional constructs, latent processes,
or external variables are assumed or inferred
beyond this set.
```

**Say:**
> "This is a commitment, and it costs something. The model gives up explanatory reach to gain testability."

**Explain the trade:**
> "If I can add a variable whenever the model fails, the model can never fail. Closure is what makes the framework falsifiable."

Return to the student proposals.

**Ask for each:**
> "Where would attention have to live? Can it be expressed through the existing five?"

Some can be partially absorbed — attention affecting what gets sampled as `Input(t)`. Some cannot. Both answers are instructive.

---

## 3. Work — The Absorption Exercise (18 min)

Students take four proposed variables and attempt to express each through the declared set.

```
Proposed variable: ______________________

Can it be expressed through the five?   Yes / No / Partly

If yes, how: ___________________________

If no, what would adding it cost the model?
_______________________________________
```

The final line is the analytical work. Expected answers: reduced falsifiability, unbounded fitting, loss of adjudication.

---

## 4. Compare — The Cost Argument (8 min)

Collect the strongest "what would it cost" answers.

**Say:**
> "A framework that explains any result explains nothing. Closure is what lets someone else prove this wrong."

---

## 5. Carry (2 min)

**Say:**
> "Tomorrow: the relation that combines three of those five. Note which one is missing from it."

---

## Instructor Notes

- Students frequently propose "attention." It is the best case for discussion because it is partially absorbable.
- Do not present closure as arbitrary strictness. Frame it as the price of testability.
