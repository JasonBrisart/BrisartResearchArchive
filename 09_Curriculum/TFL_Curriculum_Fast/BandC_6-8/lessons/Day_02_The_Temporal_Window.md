# Band C — Day 2: The Temporal Window

**Duration:** 45 min
**Materials:** Timer with second hand

---

## Objective

Students understand the update interval and distinguish it from the duration of content.

---

## 1. Hook — How Fast? (6 min)

**Say:**
> "How many times per second do you think your experience updates?"

Collect guesses. Most say once, or a few.

**Say:**
> "Roughly every 100 to 300 milliseconds. So somewhere between three and ten times per second."

Demonstrate: tap the desk about five times per second.

**Say:**
> "Something like that fast."

---

## 2. Name — The Window (12 min)

Write:

```
TEMPORAL WINDOW ≈ 100-300 ms

Within each window:
  1. Input(t) is sampled
  2. Minfo(t) is retrieved
  3. Sim(t) is generated
  4. E(t) is registered
  5. F(t) is computed
  → then propagated forward
```

**Say:**
> "Every one of those happens, in order, in about a quarter of a second. Then it hands off and starts again."

**Address the misconception directly:**

> "This is *not* how long a thought lasts. It's how often the system updates. A movie updates 24 times a second but a scene lasts three minutes. Same idea."

Write it:

```
update rate  ≠  content duration
```

---

## 3. Work — Counting Windows (15 min)

Students estimate window counts for real events.

| Event | Duration | Approximate windows (at ~200 ms) |
|---|---|---|
| A door opening | 1 second | 5 |
| Walking to the next room | 10 seconds | 50 |
| This class period | 45 min | ~13,500 |
| Hearing your name called | 0.5 seconds | ~2-3 |

Students fill in four more events of their own, computing estimates.

**Then the real question:**

> "Pick one event. Did your prediction stay the same across all those windows, or did it change partway?"

Students write a short answer.

---

## 4. Compare — Where It Changed (8 min)

Collect examples where a prediction changed mid-event.

**Ask:**
> "How many windows do you think it took to change?"

There is no exact answer. The point is recognizing that change happens **across** windows, not instantly within one.

**Say:**
> "Updating takes cycles. Nothing switches in a single window."

---

## 5. Carry (4 min)

**Say:**
> "Tomorrow: a rule about what counts as a real simulation. Some of what you wrote yesterday won't qualify."

---

## Homework

Assign **Homework Set 1**.
