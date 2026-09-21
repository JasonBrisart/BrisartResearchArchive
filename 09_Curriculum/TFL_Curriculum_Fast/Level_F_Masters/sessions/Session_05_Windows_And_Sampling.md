# Level F — Session 5: Windows and Sampling

**Duration:** 100 min

## Objective

Students select and defend a unit of observation appropriate to their design.

---

## 1. Frame — You Will Not Observe a 200 ms Window (12 min)

**Say:**
> "The framework specifies windows of 100-300 ms. Almost none of you can observe at that resolution. What follows from that?"

Let the room sit with it.

**Say:**
> "Two honest options. Either your design observes aggregate behavior across many windows and says so, or it uses instrumentation fast enough to approach the window scale. What you may not do is observe at one-minute resolution and describe your findings in window language."

---

## 2. Build — Matching Claim to Resolution (30 min)

    CLAIM SCALE vs OBSERVATION SCALE

    Claim about a single window
      → requires window-scale instrumentation
      → most course designs cannot support this

    Claim about propagation across many windows
      → supportable at coarser resolution
      → must be stated as aggregate, not per-window

    Claim about persistence over minutes or hours
      → supportable by sampling
      → must define the gap it can detect

**Say:**
> "Write which row your design occupies at the top of your protocol. Reviewers will check whether your conclusions stay in that row, and most drift upward."

Then the underspecification point, carried from Level E:

> "The interval is a parameter requiring empirical determination, not a derived constant. Your design may treat it as a free parameter and say so. That is more defensible than asserting a number the framework has not justified."

---

## 3. Contest — Does Aggregation Destroy the Claim? (25 min)

- **Student A:** A framework about 200 ms windows tested at one-minute resolution is not being tested. The aggregate claim is a different claim.
- **Student B:** Propagation claims are inherently multi-window. Testing them at aggregate resolution is appropriate, and the per-window mechanism is not the only testable content.

**Say:**
> "Both are right about different claims, which is why you must declare which one you are testing. A design that blurs them is untestable in the specific way that matters: no result can embarrass it."

---

## 4. Apply — Resolution Declaration (28 min)

Students add to their protocol:

    CLAIM SCALE:            single window / multi-window propagation / extended persistence
    OBSERVATION RESOLUTION:
    JUSTIFICATION:
    WHAT THIS DESIGN CANNOT SEE:
    CONCLUSIONS I AM THEREFORE NOT ENTITLED TO DRAW:

The last line is the graded item and the hardest to write honestly.

---

## 5. Propagate (5 min)

**Say:**
> "Next: the weights. Parameters you will almost certainly not be able to estimate, and what to do about that."

---

## Assessment

Administer **Problem Set 2**.
