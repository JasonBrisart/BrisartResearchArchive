# Temporal Feedback Loop (TFL) Reference Implementation

This section provides a pseudocode representation of a single TFL cycle, abstracted from the Institutional reference implementation.

The manuscript includes a complete, runnable baseline model with default parameters and clearly specified inputs and outputs. It can be executed as-is and adapted to laboratory-specific data streams by updating weights, thresholds, and feature mappings. The pseudocode below preserves the structure without exposing full source code.

```text
# Core state at time t:
#   Input(t): sensory/task feature vector
#   Minfo(t): retrieved memory vector
#   E(t): scalar affective gain
#   Sim(t): predictive simulation vector
#   F(t): integrated present-state vector

# Parameters (examples):
#   dt_ms                    # temporal window size, e.g., 200 ms
#   w_in, w_mem, w_sim       # weights on input, memory, prior simulation
#   e_decay                  # affective decay rate per step
#   e_input_gain             # gain from salient input to E(t)
#   persistence_threshold
#   resolution_congruence

function TFL_STEP(state, Input_t, input_salience, params):
    # 1. Memory retrieval
    Minfo_t = RETRIEVE_MEMORY(Input_t, state.memory_bank, k = params.k)

    # 2. Affective update
    E_t = UPDATE_AFFECT(
        E_prev = state.E,
        input_salience = input_salience,
        e_decay = params.e_decay,
        e_input_gain = params.e_input_gain
    )

    # 3. Simulation construction
    Sim_t = BUILD_SIMULATION(
        Input_t = Input_t,
        Minfo_t = Minfo_t,
        Sim_prev = state.Sim,
        w_in = params.w_in,
        w_mem = params.w_mem,
        w_sim = params.w_sim
    )

    # 4. Integration
    F_t = INTEGRATE_STATE(
        Input_t = Input_t,
        Minfo_t = Minfo_t,
        E_t = E_t,
        Sim_t = Sim_t,
        w_in = params.w_in,
        w_mem = params.w_mem
    )

    # 5. Diagnostics
    congruence = SIMILARITY(Sim_t, Input_t)  # e.g., cosine similarity
    persists = (E_t >= params.persistence_threshold)
    resolved = (congruence >= params.resolution_congruence) OR (NOT persists)

    # 6. Optional memory update
    if params.store_memory:
        APPEND(state.memory_bank, F_t)

    # 7. State update for next cycle
    state.E = E_t
    state.Sim = Sim_t if persists else ZERO_VECTOR(dim(Sim_t))
    state.F = F_t

    return state, {
        "E": E_t,
        "congruence": congruence,
        "persists": persists,
        "resolved": resolved
    }
```

This pseudocode mirrors the Institutional reference implementation while remaining descriptive rather than executable.
