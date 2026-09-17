# Temporal Feedback Loop (TFL) Definitions

This section defines the core terms, variables, and structural components used throughout the Temporal Feedback Loop framework.

## Core Variables

### `Input(t)`

Present-moment sensory input at time `t`, including exteroceptive, interoceptive, and proprioceptive channels.

### `Minfo(t)`

Memory content retrieved via hippocampal activation at time `t`. Includes episodic fragments, associative traces, and contextually relevant priors.

### `E(t)`

Affective-autonomic state at time `t`, including valence and intensity, functioning as a gain-control parameter that modulates encoding, persistence, and reactivation.

### `Sim(t)`

Predictive simulation derived from `Input(t)`, `Minfo(t)`, and `E(t)`, representing anticipated or desired future states that may persist across cycles.

### `F(t)`

Fully integrated internal representation of the present loop cycle. The "felt now" produced by the integration function.

## Structural Processes

### Integration Function

Prefrontal synthesis of `Input(t)`, `Minfo(t)`, `E(t)`, and `Sim(t)` that yields `F(t)` and feeds its output into subsequent cycles.

```text
F(t) = Integration(Input(t), Minfo(t), E(t), Sim(t))
```

### Encoding Phase

A stimulus, thought, or belief enters awareness. If accompanied by elevated `E(t)`, it is preferentially encoded into the loop and becomes a candidate for simulation.

### Integration Phase

`Input(t)`, `Minfo(t)`, and `E(t)` are combined to construct `Sim(t)` and update `F(t)`, shaping current experience through prior memory and affective weighting.

### Propagation Phase

Unresolved simulations with `E(t)` above persistence thresholds re-enter subsequent cycles, potentially intensifying or transforming as new input arrives.

### Resolution Phase

The loop terminates for a given simulation when behavior, observation, affective decay, or reinterpretation discharges the simulation from active dynamics.
