# Level E — Session 4: The Temporal Window

**Duration:** 75 min

## Objective

Students distinguish update rate from content duration and evaluate the window specification critically.

---

## 1. Frame — A Number Worth Questioning (8 min)

Write: `TEMPORAL WINDOW ≈ 100-300 ms`

**Say:**
> "Roughly three to ten updates per second. Before we use this, I want you to notice it's a parameter, not a derivation. Nothing in the framework proves it. Hold that."

---

## 2. Build — What Happens Inside a Window (22 min)

Write the execution order:

    WITHIN EACH WINDOW:
      Input(t) is sampled
      Minfo(t) is retrieved
      Sim(t) is generated
      E(t) is registered
      F(t) is computed
        → F(t) and surviving simulations propagate forward

**Say:**
> "All components update once per cycle. All cross-window effects occur through explicit propagation. Nothing integrates outside the cycle. That's a real constraint — it forbids hidden channels between moments."

**Address the standard error directly:**

> "This is not how long a thought lasts. It's how often the system updates. A film updates many times per second; a scene lasts minutes."

Write: `update rate ≠ content duration`

---

## 3. Contest — Defend the Interval (22 min)

Assigned in advance. Two students argue:

- **Student A:** The interval is empirically motivated by known perceptual integration timescales and is a reasonable first approximation.
- **Student B:** The interval is unmotivated within the framework, is doing no work that a wider or narrower one wouldn't, and its specificity creates false precision.

**Say after both:**
> "B is on strong ground and the framework should concede it. An underdetermined parameter is genuine underspecification. The correct response is to flag it as an open question requiring empirical determination, not to defend it."

**Then the harder question:**

> "Does the framework survive if the number is wrong? Which claims depend on the specific interval, and which only require that *some* discrete window exists?"

Most claims require only discreteness. That is worth discovering.

---

## 4. Apply — Window Estimation and Its Limits (18 min)

Students estimate window counts at 200 ms for four events of their choosing, then answer:

1. Across those windows, did your prediction stay constant or change partway?
2. How many windows would you estimate the change took?
3. What would you need to measure to answer (2) rather than estimate it?

Question 3 is the point. There is no answer available from the armchair, which previews Level F.

---

## 5. Propagate (5 min)

**Say:**
> "Next: the rule that decides whether the framework applies to your example at all. Some of what you wrote in Session 3 will not survive it."

---

## Assessment

Administer **Problem Set 1** at the end of this session.

## Instructor Notes

- Students who arrive from Band D will have been taught the interval as settled. Correcting that here is important and they generally receive it well.
- Do not over-defend the number. The framework is better served by conceding underspecification than by manufacturing justification.
