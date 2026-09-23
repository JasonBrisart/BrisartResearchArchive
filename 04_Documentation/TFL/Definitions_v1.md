# Temporal Feedback Loop (TFL)

## Definitions (v1 Draft)

### 1. `Input(t)`

**Definition:**

External or environmental sensory information available at time `t`.

**Notes:**

- Represents current perceptual input.
- Does not include internally generated content.
- Serves as one of the primary drivers of state updates.

### 2. `Minfo(t)`

**Definition:**

Memory-derived information retrieved or activated at time `t`.

**Notes:**

- Not stored memory itself, but the subset actively brought into the current cycle.
- Selection is not random and is influenced by current context and internal state.
- May include recombined or reconstructed elements.

### 3. `E(t)`

**Definition:**

Affective state at time `t`, representing internal weighting or intensity.

**Notes:**

- Modulates persistence, salience, and selection.
- Does not represent emotion as content, but as influence on system dynamics.
- Higher values correlate with increased persistence and reactivation likelihood.

### 4. `Sim(t)`

**Definition:**

Internally generated simulation or interpretive output at time `t`.

**Notes:**

- Combines `Input(t)`, `Minfo(t)`, and `E(t)`.
- Represents the system's constructed interpretation of the current state.
- May include predictions, expectations, or inferred meanings.

### 5. `F(t)`

**Definition:**

Forward-propagated state carried into the next iteration.

**Notes:**

- Represents what persists after a cycle.
- Enables continuity and recurrence across time.
- Drives reentry and delayed reactivation phenomena.

### 6. Loop Iteration

**Definition:**

A single processing cycle in which current input and internal states are integrated to produce an updated simulation and forward state.

**Notes:**

- The system operates as repeated iterations rather than a continuous stream.
- Each moment of experience corresponds to the output of a loop iteration.

### 7. Persistence

**Definition:**

The continued presence or reactivation of a simulation across multiple iterations.

**Notes:**

- Influenced by `E(t)` and prior `F(t)`.
- Does not require continuous activation and may reappear after delay.

### 8. Reentry

**Definition:**

The recurrence of a previously active simulation at a later iteration.

**Notes:**

- Triggered by overlap between current state and stored forward state.
- Not random and dependent on internal structure and weighting.

### 9. Contradiction

**Definition:**

Mismatch between `Input(t)` and `Sim(t)` content.

**Notes:**

- Does not necessarily eliminate a simulation.
- May result in modification, weakening, or delayed update rather than immediate removal.

### 10. Multi-Simulation State

**Definition:**

Condition in which multiple competing simulations exist within or across iterations.

**Notes:**

- Simulations may coexist or alternate in dominance.
- The system does not enforce a single stable interpretation at all times.

### 11. Integration

**Definition:**

Process by which `Input(t)`, `Minfo(t)`, and `E(t)` are combined to produce `Sim(t)`.

**Notes:**

- Occurs within each iteration.
- Mechanism not fully specified at v1.
