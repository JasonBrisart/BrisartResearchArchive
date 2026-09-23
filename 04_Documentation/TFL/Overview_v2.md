# Temporal Feedback Loop (TFL) Overview

Temporal Feedback Loop (TFL) defines cognition as a recursive integration system in which sensory input, memory retrieval, and predictive simulation are combined within discrete temporal windows of approximately 100 to 300 ms, with affective intensity governing the persistence of simulated content across time.

At each timestep, the system integrates current sensory input, retrieved memory, and an internally generated predictive simulation into a unified internal state. This state is then carried forward as a prior, allowing cognition to operate as a closed-loop process that recursively updates across successive temporal windows.

**The system is fully defined by the specified variables and does not introduce additional latent stages beyond `Input(t)`, `Minfo(t)`, `Sim(t)`, `E(t)`, and `F(t)`.**

```text
encode → retrieve → simulate → integrate → propagate → update → reloop
```

**System type:** Affect-modulated recursive simulation-integration system with persistence-gated updating.

Cognitive continuity corresponds to the persistence and resolution of content-identifiable simulations within this recursive loop structure.

## Core Variables

- **`Input(t)`:** Real-time sensory input providing external constraint.
- **`Minfo(t)`:** Retrieved memory content providing contextual structure.
- **`Sim(t)`:** Predictive simulation representing anticipated or inferred outcomes.
- **`E(t)`:** Affective intensity modulating persistence of simulations across windows.
- **`F(t)`:** Integrated internal state, or "felt present," carried forward as a prior.

### Additional Structural Term

- **`Belief(t)`:** Affectively stabilized structural prior that constrains memory retrieval and simulation generation under conditions of ambiguity.

## Core Integration and Persistence Structure

```text
F(t) = w1 · Input(t) + w2 · Minfo(t) + w3 · Sim(t)
```

Where `w1`, `w2`, and `w3` represent integration weights.

```text
Sim(t+1) = Sim(t), if E(t) > θ_persistence
```

Where `θ_persistence` is the affective threshold required for persistence across windows.

**Affective intensity does not contribute to integration weights and functions exclusively as a persistence gate.**

In the absence of sufficient affective intensity, simulations decay, are replaced, or are suppressed.

## Operational Loop

Each temporal cycle proceeds as follows:

1. Encode current sensory input.
2. Retrieve context-relevant memory content `Minfo(t)`.
3. Generate predictive simulation `Sim(t)`.
4. Register affective intensity `E(t)`.
5. Integrate signals into unified state `F(t)`.
6. Propagate state forward as a prior.
7. Update or suppress simulation based on feedback and persistence conditions.
8. Repeat across subsequent windows.

## Loop Phases

- **Encoding:** Sensory input and internal signals are sampled within a defined temporal window.
- **Integration:** `Input(t)`, `Minfo(t)`, and `Sim(t)` are combined into a unified internal state.
- **Simulation:** Forward predictions are generated based on current state and retrieved priors.
- **Propagation:** Simulations persist across windows if affective intensity exceeds the persistence threshold.
- **Update / Resolution:** Simulations are modified or terminated through environmental confirmation or contradiction, behavioral enactment, affective decay, or cognitive reinterpretation.

## System Dynamics

System behavior is defined in terms of measurable changes across time in:

- Simulation recurrence probability.
- Affective intensity `E(t)`.
- Contradiction between predicted and observed outcomes.

These variables determine whether system behavior reflects:

- Rapid resolution with low persistence.
- Sustained recurrence with high persistence.
- Escalation under unresolved contradiction.

## Core Principle

TFL treats cognition as a recursive, affect-modulated simulation system in which cognitive continuity arises from the persistence of simulations across temporal windows, gated by affective intensity and updated through feedback.

System behavior depends on:

- Affective persistence, defined as `E(t)` relative to `θ_persistence`.
- Simulation recurrence and decay.
- Belief-constrained retrieval, expressed as `Belief(t) → Minfo(t)`.
- Feedback-driven updating through confirmation versus contradiction.

## Behavioral and Cognitive Outcomes

Variation in these parameters produces:

- **Stable cognition:** Low persistence and rapid resolution.
- **Persistent thought patterns:** High affective intensity and repeated simulation recurrence.
- **Bias-amplified perception:** Sustained simulations shaping interpretation under ambiguity.

## Scientific Constraint

The framework requires empirical adjudication against alternative explanations, including:

- Uncertainty-only models.
- Arousal-only models.
- Habit-based models.

All variables require explicit operationalization and must be measurable through prespecified observables to constitute a valid implementation of the framework.

TFL is supported only if persistence, recurrence, bias, and update effects cannot be fully explained by these alternatives.

## Final Interpretation

TFL formalizes cognition as a closed-loop system in which internally generated simulations are continuously integrated with sensory input and memory, persist conditionally based on affective intensity, and are updated through interaction with feedback.

The defining feature of the system is not the presence of prediction, memory, or affect individually, but the recursive persistence of content-identifiable simulations across temporally structured integration windows.
