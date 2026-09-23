# Temporal Feedback Loop (TFL) Architecture

TFL specifies a closed-loop cognitive architecture composed of a fixed set of interacting components operating over discrete temporal windows. The architecture defines how sensory evidence, retrieved memory, predictive simulation, and affective persistence constraints are organized into a recursive system that produces temporally continuous internal states.

The system is fully defined by five core components, `Input(t)`, `Minfo(t)`, `Sim(t)`, `E(t)`, and `F(t)`, together with a belief-based prior constraint. No additional latent stages or processes are assumed beyond this defined component set.

## 1. Core Architectural Components

The architecture consists of five functional components, each representing a distinct role in the system, together with a belief constraint.

### Input System: `Input(t)`

Provides real-time sensory evidence. Acts as the external constraint on system state, supplying stimulus-dependent information within each temporal window.

### Memory System: `Minfo(t)`

Supplies contextually relevant memory content retrieved at time `t`. This component constrains interpretation and prediction by reinstating prior information.

### Simulation Generator: `Sim(t)`

Constructs predictive simulations representing anticipated or inferred future states. Simulation content is generated from the interaction of current input, retrieved memory, and prior system state.

### Persistence Gate: `E(t)`

Represents affective intensity at time `t` and governs whether simulations persist across temporal windows. This component functions exclusively as a persistence constraint and does not contribute to integration.

### State Integrator: `F(t)`

Produces the unified internal state for the current window. This state corresponds to the system's momentary representation of the present and is propagated forward as a prior.

### Belief Constraint: `Belief(t)`

Acts as an affectively stabilized structural prior that biases memory retrieval and constrains simulation generation under ambiguity.

## 2. Information Flow Structure

The architecture is defined by a fixed pattern of signal flow between components:

```text
Input(t) ─┐
          ├──→ State Integrator → F(t) → prior → next cycle
Minfo(t) ─┤
          │
Sim(t) ───┘

F(t)      → influences → Sim(t+1)
E(t)      → gates      → Sim(t+1) persistence
Belief(t) → constrains → Minfo(t), Sim(t)
```

1. `Input(t)`, `Minfo(t)`, and `Sim(t)` converge at the integrator to produce `F(t)`.
2. `F(t)` is propagated forward and conditions subsequent simulation generation.
3. `E(t)` determines whether `Sim(t)` is retained or replaced in the next cycle.
4. `Belief(t)` constrains both memory retrieval and simulation selection.

This structure defines a closed-loop system in which internal states recursively influence future processing.

## 3. Temporal Execution Model

TFL operates over discrete temporal windows of approximately 100 to 300 milliseconds, each corresponding to a complete execution cycle.

Within each temporal window:

1. `Input(t)` is sampled from the environment.
2. `Minfo(t)` is retrieved based on current state and prior constraints.
3. `Sim(t)` is generated as a predictive hypothesis.
4. `E(t)` is registered as an affective intensity signal.
5. `F(t)` is computed as the integrated system state.

The output state `F(t)`, together with persistent simulations, is carried forward to the next window.

This defines a **synchronous, discrete-time recursive system** in which all components update once per cycle and the system evolves through iterative state propagation.

## 4. Integration and Persistence Mechanisms

The integrated state is computed as:

```text
F(t) = w1 · Input(t) + w2 · Minfo(t) + w3 · Sim(t)
```

Where:

- `w1`, `w2`, and `w3` are integration weights determining the relative contributions of input, memory, and simulation.

Simulation persistence is governed by:

```text
Sim(t+1) = Sim(t), if E(t) > θ_persistence
```

Where:

- `θ_persistence` defines the affective threshold required for simulation carry-over.

Affective intensity does not influence integration weights and functions exclusively as a persistence gate.

If `E(t)` does not exceed the threshold:

- Simulations decay.
- Alternative simulations are generated.
- Prior simulations are suppressed.

## 5. Control Parameters

System behavior is governed by a minimal parameter set:

1. **Integration weights (`w1`, `w2`, `w3`)**: Determine the influence of input, memory, and simulation.
2. **Persistence threshold (`θ_persistence`)**: Determines simulation carry-over.
3. **Belief weighting**: Constrains retrieval and simulation under ambiguity.
4. **Feedback-driven update conditions**: Determine modification versus suppression of active simulations.

These parameters define the controllable dimensions of the architecture and must be linked to observable quantities in valid implementations.

## 6. Recursive State Propagation

The defining property of the architecture is recursive propagation:

- `F(t)` becomes a prior influencing `Minfo(t+1)` and `Sim(t+1)`.
- Simulations that persist re-enter subsequent cycles.
- Feedback modifies future simulation generation.

This recursion produces:

- Temporal continuity.
- Persistence of internal content.
- Dynamic updating based on incoming information.

## 7. System Dynamics: State Evolution

System-level behavior emerges from measurable changes across cycles in:

- Simulation recurrence.
- Affective intensity.
- Alignment or contradiction between simulation and input.

These dynamics define system evolution as:

- **Rapid resolution**: Low persistence and high turnover.
- **Sustained recurrence**: Persistent simulation carry-over.
- **Escalation**: Repeated simulation under unresolved contradiction.

## 8. Architectural Constraints

The architecture is subject to the following constraints:

1. The system is fully defined by `Input(t)`, `Minfo(t)`, `Sim(t)`, `E(t)`, `F(t)`, and `Belief(t)`.
2. No additional latent processes or stages are assumed.
3. Affective intensity functions exclusively as a persistence parameter.
4. Component outputs must be operationalizable and measurable in valid implementations.

## 9. Functional Summary

The TFL architecture implements a recursive system in which:

- Sensory input, memory, and simulation are integrated within discrete cycles.
- Affect governs persistence across cycles.
- Belief constrains retrieval and prediction.
- Internal states propagate forward as priors.

The system is defined not by sequential processing alone, but by the structured interaction of components within a closed-loop architecture that produces persistent, evolving internal representations over time.
