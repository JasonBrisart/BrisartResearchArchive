# Temporal Feedback Loop (TFL) Architecture

TFL operates over discrete temporal windows of approximately 100 to 300 milliseconds and is defined by five core variables integrated by a looped architecture.

TFL operates over discrete temporal windows and is defined by five core variables: `Input(t)`, `Minfo(t)`, `E(t)`, `Sim(t)`, and `F(t)`.

## Core Variables

- **`Input(t)`**: Real-time sensory information available at time `t`.
- **`Minfo(t)`**: Contextually relevant memory traces retrieved via hippocampal reactivation at time `t`.
- **`E(t)`**: Affective-autonomic state at time `t`, including valence and intensity, functioning as a gain parameter.
- **`Sim(t)`**: Predictive simulation constructed from `Input(t)`, `Minfo(t)`, and `E(t)`, representing anticipated or desired future states.
- **`F(t)`**: Integrated internal representation of the present moment, experienced as the "felt now."

## Loop Sequence

The loop architecture follows a structured sequence within each window:

1. Acquisition of `Input(t)`.
2. Memory retrieval to form `Minfo(t)`.
3. Affective evaluation to update `E(t)`.
4. Simulation construction to generate `Sim(t)`.
5. Integration to compute `F(t)`.
6. Carry-forward, where `F(t)` and `Sim(t)` become priors for the next cycle.

This architecture is recursive: the output of one cycle becomes part of the input state for subsequent cycles, allowing simulations and beliefs to persist, evolve, or resolve over time.
