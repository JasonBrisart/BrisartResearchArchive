# Temporal Feedback Loop (TFL) Definitions

This section defines the core variables, terms, and structural components of the Temporal Feedback Loop (TFL). All definitions are restricted to the minimal variable set required for valid implementation and do not introduce additional latent processes.

## Core Variables

### `Input(t)`

Sensory evidence available within the current temporal window. This includes exteroceptive, interoceptive, and proprioceptive signals that provide external and internal constraint on system state.

### `Minfo(t)`

Retrieved memory content active within the current window. This includes contextually relevant episodic fragments, associative traces, or prior-linked representations that constrain interpretation and prediction.

### `Sim(t)`

Predictive simulation representing an anticipated or inferred outcome. Simulation content must be identifiable and corresponds to a specific hypothesis about a near-future or counterfactual state generated from `Input(t)`, `Minfo(t)`, and prior system state.

### `E(t)`

Affective intensity at time `t`. `E(t)` functions exclusively as a persistence parameter that determines whether `Sim(t)` is carried forward into subsequent temporal windows. It does not contribute to integration weighting or simulation construction.

### `F(t)`

Integrated internal state representing the system's current momentary state ("felt present"). `F(t)` is the result of integrating `Input(t)`, `Minfo(t)`, and `Sim(t)`, and is propagated forward as a prior into the next cycle.

## Additional Structural Term

### `Belief(t)`

An affectively stabilized structural prior that constrains retrieval (`Minfo(t)`) and simulation generation (`Sim(t)`) under conditions of ambiguity. `Belief(t)` does not function as a dynamic core signal within each timestep but defines a constraint on system behavior across cycles.

## Core Functions

### Integration Function

```text
F(t) = w1 · Input(t) + w2 · Minfo(t) + w3 · Sim(t)
```

The integration function combines sensory input, retrieved memory, and simulation content into the current internal state `F(t)`. Affective intensity is not part of this function.

### Persistence Condition

```text
Sim(t+1) = Sim(t), if E(t) > θ_persistence
```

Simulation persistence across temporal windows depends strictly on affective intensity exceeding a defined threshold. Simulations below this threshold are not guaranteed to persist and may decay or be replaced.

## Temporal Structure

### Temporal Window

A discrete processing interval of approximately 100 to 300 milliseconds within which all variables are evaluated and updated. Each window constitutes a complete execution cycle of the TFL system.

## Operational Components

### Encoding

Sampling of sensory input and activation of relevant internal content within the current temporal window.

### Integration

Combination of `Input(t)`, `Minfo(t)`, and `Sim(t)` into the unified internal state `F(t)`. Integration is deterministic given inputs and parameter values.

### Simulation Generation

Construction of `Sim(t)` as a predictive hypothesis constrained by current input, retrieved memory, prior state, and belief structure.

### Propagation

Carry-forward of `F(t)` and any persistent `Sim(t)` into the subsequent temporal window.

### Update / Resolution

Modification or termination of `Sim(t)` based on:

- Confirmation or contradiction from `Input(t)`
- Decay of affective intensity `E(t)`
- Replacement by alternative simulations

## State Dynamics Terms

### Simulation Persistence

The continued presence of a simulation across temporal windows, determined solely by `E(t)` relative to the persistence threshold.

### Recurrence

The reappearance of previously identified simulation content across temporal windows, measurable as a function of persistence and reentry conditions.

### Contradiction

Mismatch between `Sim(t)` and `Input(t)` that produces measurable update effects, including revision or suppression.

### Resolution

Termination or transformation of a simulation resulting from contradiction, confirmation, or affective decay.

## Definition Constraints

- All valid definitions are restricted to `Input(t)`, `Minfo(t)`, `Sim(t)`, `E(t)`, and `F(t)`.
- No additional latent variables or processes are implied.
- Affective intensity is defined solely in terms of persistence, not general modulation.
- All defined terms must be operationalizable and measurable in valid implementations.
