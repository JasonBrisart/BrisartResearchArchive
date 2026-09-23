# Temporal Feedback Loop (TFL) Reference Implementation

This pseudocode represents the structural logic of a single TFL cycle. It preserves architectural relationships between variables without specifying implementation procedures, parameter identification methods, or measurement pipelines.

```text
# Core state at time t:
# Input(t): sensory evidence
# Minfo(t): retrieved memory content
# E(t): observed affective intensity (persistence parameter)
# Sim(t): predictive simulation
# F(t): integrated current state

# Parameters (structural only; must be identified from observables
# in valid implementations):
# w_in, w_mem, w_sim
# persistence_threshold

function TFL_STEP(state, Input_t, params):
    # 1. Memory retrieval (structure only)
    Minfo_t = RETRIEVE_MEMORY(Input_t, state.memory_bank)

    # 2. Affective intensity (observation-defined)
    # No procedural update specified
    E_t = OBSERVED_AFFECT(state.E, Input_t)

    # 3. Simulation generation (no weighting or affect contribution)
    Sim_t = GENERATE_SIMULATION(
        Input_t = Input_t,
        Minfo_t = Minfo_t,
        Sim_prev = state.Sim
    )

    # 4. Integration (STRICT: no affect involvement)
    F_t = INTEGRATE_STATE(
        Input_t = Input_t,
        Minfo_t = Minfo_t,
        Sim_t = Sim_t,
        w_in = params.w_in,
        w_mem = params.w_mem,
        w_sim = params.w_sim
    )

    # 5. Persistence condition (affect-only effect)
    persists = (E_t > params.persistence_threshold)

    # 6. Optional diagnostic (non-essential to core system)
    congruence = SIMILARITY(Sim_t, Input_t)

    # 7. State update (recursive propagation)
    state.E = E_t
    state.Sim = Sim_t if persists else ZERO_VECTOR(dim(Sim_t))
    state.F = F_t

    return state
```
