# Temporal Feedback Loop (TFL) Guarantees

The Temporal Feedback Loop establishes non-negotiable architectural guarantees that define system behavior across temporal cycles. These guarantees apply only under the assumptions and constraints specified in the TFL framework and are restricted to the declared variable set.

## 1. State Continuity Constraint

The system guarantees continuity of internal state across cycles through recursive propagation of:

- The integrated state `F(t)`.
- Any simulation `Sim(t)` that satisfies persistence conditions.

State continuity is selective rather than exhaustive. Only simulations that meet persistence criteria are carried forward. Non-persistent simulations are replaced or decay without contributing to subsequent state formation.

## 2. Threshold-Gated Simulation Persistence

Simulation persistence is governed strictly by affective intensity relative to a persistence threshold:

```text
Sim(t+1) = Sim(t), if E(t) > θ_persistence
```

Only simulations exceeding the persistence threshold are carried forward into subsequent cycles. Simulations below this threshold are not guaranteed to reappear and may decay or be replaced.

Affective intensity functions exclusively as a persistence gate and does not contribute to integration weighting.

## 3. Conditional Determinism of Integration

Given fixed inputs, the integration function is conditionally deterministic:

```text
F(t) = w1 · Input(t) + w2 · Minfo(t) + w3 · Sim(t)
```

For a given set of `Input(t)`, `Minfo(t)`, `Sim(t)`, and fixed parameter values, the resulting `F(t)` is uniquely determined. Variability across implementations arises from differences in parameterization, measurement, or input conditions rather than inherent stochasticity in the architectural definition.

## 4. Temporal Window Constraint

All loop operations are constrained to discrete temporal windows within an empirically bounded range of approximately 100 to 300 ms. Each window defines a complete update cycle in which:

- All core variables are evaluated.
- Integration occurs once.
- The resulting state is propagated forward.

All cross-window effects occur through explicit propagation of `F(t)` and persistent `Sim(t)`. No integration occurs outside the defined discrete update cycle.

## 5. Convergence Under Defined Conditions

The system guarantees resolution of simulations under the following conditions:

- Sufficient congruence between `Sim(t)` and `Input(t)`.
- Contradiction-driven updating or suppression.
- Decay of affective intensity below the persistence threshold.

Convergence is not globally guaranteed. It occurs only when these conditions are satisfied.

## 6. Bounded Affective Persistence

Affective intensity is bounded within a finite range and functions solely to regulate simulation persistence across cycles.

Under valid implementations:

- `E(t)` cannot produce unbounded escalation.
- Persistence effects are limited by threshold and decay parameters.

This ensures controlled, finite persistence dynamics.

## 7. Standardized Variable Interface

All valid implementations of TFL expose:

- `Input(t)`.
- `Minfo(t)`.
- `E(t)`, the affective persistence constraint.
- `Sim(t)`.
- `F(t)`.

These variables define the complete system interface. No additional variables are required or assumed for valid operation of the framework.

## 8. Measurable State Evolution

System dynamics are guaranteed to be observable through measurable changes in:

- Simulation recurrence across cycles.
- Affective intensity relative to persistence thresholds.
- Alignment or contradiction between prediction and input.

These observables define all valid behavioral outputs of the system.

## 9. Adjudication Compatibility

A valid TFL implementation guarantees compatibility with model comparison against:

- Uncertainty-only explanations.
- Arousal-only explanations.
- Habit-based explanations.

System behavior must be expressible in a form that permits adjudication against these alternative accounts.
