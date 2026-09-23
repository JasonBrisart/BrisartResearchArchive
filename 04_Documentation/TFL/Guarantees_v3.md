# Temporal Feedback Loop (TFL) Guarantees

The Temporal Feedback Loop provides non-negotiable architectural guarantees that govern its behavior across cycles and implementations.

TFL enforces the following properties:

- **Continuity of Internal State:** Each cycle preserves the relevant components of the prior state, including `F(t)`, `Sim(t)`, and `E(t)`, required for convergence. No essential information is discarded between iterations.
- **Threshold-Bound Persistence:** Simulation persistence is governed by affective thresholds on `E(t)`. Only simulations above a defined persistence threshold re-enter subsequent cycles.
- **Deterministic Integration:** Given the same `Input(t)`, `Minfo(t)`, `E(t)`, and prior `Sim(t)`, the integration function produces the same `F(t)` and `Sim(t)` trajectory. No stochastic elements are required at the loop level.
- **Temporal Window Constraint:** Loop operation is constrained to an approximate 100 to 300 ms temporal window, consistent with perceptual updating and hippocampal-prefrontal interaction.
- **Convergence Under Defined Conditions:** The loop is guaranteed to resolve when congruence between `Sim(t)` and `Input(t)` exceeds a resolution threshold or when `E(t)` decays below persistence thresholds.
- **Bounded Affective Influence:** `E(t)` functions as a gain parameter but is bounded between defined minima and maxima, preventing unbounded escalation in well-specified implementations.
- **Standardized Input/Output Structure:** All implementations expose `Input(t)`, `Minfo(t)`, `E(t)`, `Sim(t)`, and `F(t)` in a consistent format, enabling integration with other frameworks and experimental pipelines.
