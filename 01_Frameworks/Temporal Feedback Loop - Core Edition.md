## The Temporal Feedback Loop: A Recursive Model of Emotionally Modulated Simulation

- **Author:** Jason Brisart
- **Affiliation:** Brisart Research Archive
- **Contact:** [jason@brisartresearcharchive.com](mailto:jason@brisartresearcharchive.com)
- **ORCID / Website:** [Brisart Research Archive](http://www.brisartresearcharchive.com/)
- **Version:** Core Edition v1
- **Date:** September 2026

### Abstract

The Temporal Feedback Loop (TFL) defines cognition as a recursive integration system in which sensory input, retrieved memory, and predictive simulation are combined within discrete temporal windows, while affective intensity governs the persistence of simulated content across time. At each cycle, current input, retrieved memory, and internally generated simulation are integrated into a unified internal state that is carried forward as a prior, allowing cognition to proceed as a closed-loop process of recursive updating. The model is fully defined by the declared variable set and does not introduce additional latent stages beyond sensory input, memory retrieval, predictive simulation, affective persistence, and integrated state formation.

TFL treats cognition as an affect-modulated recursive simulation–integration system with persistence-gated updating. Cognitive continuity corresponds to the persistence, recurrence, and resolution of content-identifiable simulations within this closed-loop structure. The model therefore specifies a fixed recursive organization in which integrated states propagate forward, constrain subsequent simulation, and remain open to revision through contradiction and affective decay. Public materials may demonstrate one way of rendering this logic, but the present manuscript is concerned only with the framework itself rather than any canonical procedure.

### 1.0 Introduction

TFL addresses a specific structural problem: how content-identifiable predictive simulations are generated, maintained, recur, bias interpretation under ambiguity, and resolve when contradicted. Existing accounts illuminate parts of this problem, but they do not specify a minimal recursive system that makes explicit how sensory evidence, memory retrieval, affective persistence, and predictive simulation are organized within the same temporally structured process.

Within each temporal cycle, TFL integrates current sensory evidence, retrieved memory content, and predictive simulation into a unified internal state that is then carried forward as a prior. Its central commitments are fourfold: affective intensity governs whether simulations persist across windows, belief-conditioned retrieval constrains simulation content under ambiguity, contradiction redirects the loop through revision or suppression, and these dynamics arise from the structured interaction of the declared variables rather than from unspecified latent stages.

### 2.0 Core Mechanism

#### 2.1 Core Variables

TFL operates across discrete temporal windows that may be understood as bounded cycles of updating. Within each cycle, five kinds of information remain conceptually distinct: sensory input, retrieved memory content, predictive simulation, affective intensity, and the integrated current state. The model is fully defined by this declared variable set together with a belief-based prior constraint, and it does not require additional latent stages beyond these components.

- **Sensory evidence** (`Input(t)`): the information available from the environment during the current cycle. In functional terms, this is what the system is currently taking in.
- **Retrieved memory content** (`Minfo(t)`): previously stored context that becomes relevant again in the present cycle. Functionally, this is the background information the system brings forward to help interpret what is happening now.
- **Affective state** (`E(t)`): the felt intensity attached to the current cycle. Functionally, this is the signal that marks whether a simulation is likely to persist or fade.
- **Predictive simulation** (`Sim(t)`): the internally generated expectation of what may happen next. Functionally, this is the working anticipation the system produces from current input, memory, and prior state.
- **Integrated current state** (`F(t)`): the unified outcome of the current cycle. Functionally, this is the system's current best state, carried forward to influence what happens next.
- **Belief prior:** a stabilized, affectively reinforced constraint on retrieval and simulation under ambiguity, operating across cycles rather than within any single one.

The table below restates each element's operational definition and functional role for reference:

| Term | Symbol | Operational definition | Role |
|---|---|---|---|
| Sensory evidence | `Input(t)` | Current sensory information available within a temporal cycle, including whatever environmental features constrain the system's present state. | Integration input |
| Retrieved memory content | `Minfo(t)` | Contextually relevant memory content brought forward within the present cycle and contributing background structure to interpretation and prediction. | Integration input |
| Predictive simulation | `Sim(t)` | An internally generated anticipation of a near-future or counterfactual state arising from current input, retrieved memory, and the system's prior condition. | Integration input |
| Affective state | `E(t)` | The affective intensity associated with the present cycle, functioning as the condition under which a simulation is maintained, weakened, or released. | Persistence control only — not an integration input |
| Integrated current state | `F(t)` | The unified state of the present cycle, corresponding to the system's momentary current condition and serving as the prior for what follows. | Output of integration |
| Belief prior | — | A stabilized, affectively reinforced constraint on retrieval and simulation under ambiguity, operating across cycles rather than within any single one. | Cross-cycle constraint, not a momentary variable |

| **Model element** | **Conceptual role** | **Illustrative description** |
|----|----|----|
| Predictive simulation | Carries forward an anticipated interpretation or outcome. | When prior state and incoming information align, the expectation is maintained; when they diverge, revision becomes more likely. |
| Affective state | Supports persistence or release of active content. | When intensity remains elevated, a simulation is more likely to continue; when it weakens, the simulation is more likely to fade. |
| Belief prior | Biases retrieval and interpretation under ambiguity. | When input remains unclear, interpretation tends to follow the more strongly stabilized prior. |
| Integrated current state | Represents the unified outcome of the cycle. | The current state reflects the best available integration of input, memory, simulation, and affect. |

#### 2.2 Loop Structure

The loop may be summarized as follows: encode, retrieve, simulate, integrate, propagate, update, and reloop. At each cycle, sensory evidence is sampled, relevant memory is brought forward, affective intensity is registered, a predictive simulation is formed, and these elements are integrated into the current state. The resulting state is then propagated forward as a prior that conditions subsequent simulation and updating.

#### 2.3 Affective Salience as Gain Control

Affective intensity functions exclusively as a persistence condition. It does not contribute representational content to the integrated state and does not alter integration weighting. Its role is restricted to determining whether simulated content remains active across temporal windows or is released, replaced, or allowed to decay.

#### 2.4 Belief as Structural Prior

Belief is treated as an affectively stabilized structural prior that constrains memory retrieval and simulation generation under ambiguity. It does not function as an independent stage within each cycle, but as a directional constraint on what retrieved content is reinstated and which simulations are preferentially sustained when input remains underdetermined.

#### 2.5 Core Integration and Persistence Structure

TFL is governed by a minimal parameter structure. Relative integration weights determine how strongly sensory evidence, retrieved memory content, and predictive simulation contribute to the current state within each window. A persistence threshold determines whether a simulation remains active into the next cycle. Conditions of fading govern how quickly affective support and simulation strength diminish when the loop is not reinforced, while conditions of revision determine how strongly contradiction redirects the active simulation. Together, these define the controllable dimensions of the model without introducing new components.

Taken together, these dimensions include relative influence in integration, a persistence boundary for simulation carry-over, conditions of fading, conditions of revision, and a belief-based constraint on retrieval and simulation under ambiguity. They do not introduce additional elements into the model; rather, they specify the conditions under which the same loop yields stronger continuity, faster decay, or more rapid redirection.

The relationship between the integrated current state and its constituent elements can be stated compactly as:

```text
F(t) = Integration[Input(t), Minfo(t), Sim(t)]
```

Affective state is deliberately absent from this relation. It is not an argument of integration; instead, it governs a separate condition:

```text
Persistence of Sim(t) into the next cycle depends on E(t)
```

This compact form is offered only as a notational summary of what the preceding subsections already state in full. It commits the framework to nothing beyond what has already been described: affective state remains outside the integration that produces the current state, and its role remains confined to whether an already-formed simulation is carried forward.

### 3.0 Internal Processing Dynamics

#### 3.1 Stability, Recurrence, and Escalation

System behavior may take the form of rapid resolution, sustained recurrence, or escalation under unresolved contradiction. These regimes are defined by changes across windows in simulation recurrence, affective intensity, and the degree of alignment or mismatch between simulation and incoming input.

#### 3.2 Time-Displaced Reentry

Delayed reentry refers to the reappearance of a previously identified simulation after an interval in which it was not active. Within TFL, reentry is expected to depend on the affective intensity attached to the earlier simulation together with the degree of cue overlap at reactivation.

#### 3.3 Conditions of Discernibility

Three interpretive dimensions are especially important for understanding how the loop unfolds: the point at which affective support is sufficient to carry a simulation forward, the pace at which unsupported continuity diminishes across windows, and the degree to which contradiction redirects the loop toward revision or release. These dimensions clarify the model's internal organization rather than adding new stages to it.

For the loop to remain meaningfully interpretable, some way of tracing active simulation, ambiguity-sensitive response, and affective intensity must remain available in principle. Together, these mark the minimum conditions under which persistence, bias, and revision can be discussed coherently within the model.

#### 3.4 Variable Closure and Boundary Conditions

TFL applies only where predictive content remains distinguishable, affective intensity can plausibly govern persistence, and contradiction can meaningfully alter the course of the loop. It does not extend beyond the declared variables of sensory input, retrieved memory content, predictive simulation, affective intensity, integrated current state, and belief-based prior constraint. Where these conditions fall away, including under chaotic input, absent simulation content, or extreme physiological disruption, the framework's explanatory reach becomes limited.

These boundary conditions rest on four structural requirements, restated here for direct reference:

| **Element** | **Conceptual requirement** | **Interpretive description** |
|----|----|----|
| Temporal cycle | Processing unfolds in repeatable bounded cycles. | Each cycle moves through intake, interpretation, simulation, and updating. |
| Simulation coding | Active content must remain distinguishable at the conceptual level. | The active simulation must remain identifiable so later cycles can be compared against it. |
| Affective persistence | Intensity influences whether a simulation continues. | Strong affective support tends to keep a simulation active across cycles. |
| Contradiction handling | Mismatch can trigger revision or release of the active simulation. | As contradiction intensifies, the active simulation becomes more likely to be revised or let go. |

The framework remains coherent only if its defining conditions are preserved: bounded cycles, distinguishable simulation content, affective persistence, belief-constrained interpretation under ambiguity, and the possibility of contradiction-driven revision or release. If these conditions are removed, the resulting account no longer preserves TFL as described here.

### 4.0 Applications and Predictions

#### 4.1 Affective Salience and Persistent Thought

Persistent thought emerges when affective support stabilizes a simulation strongly enough for it to continue shaping interpretation across multiple windows. In this view, stronger affective support produces greater continuity of active content and stronger bias under ambiguity.

- **Persistence**. When affective support attached to an active simulation increases while ambiguity is held constant, the model is expected to maintain that simulation across more successive windows and for longer durations.
- **Bias under ambiguity**. As simulation persistence increases, interpretation and behavioral selection are expected to drift more strongly toward outcomes that remain congruent with the active simulation.
- **Resolution through contradiction**. When contradiction intensifies, the model is expected to reduce the continuity of the active simulation unless belief and affective support maintain reinterpretation, in which case the loop shifts toward simulation revision rather than simple disappearance.

The model is intended to be read in a way that keeps content-specific recurrence distinct from generic autonomic activation. Its interpretive value therefore depends on whether recurrence and bias remain tied to the simulation itself rather than collapsing into a purely physiological account.

#### 4.2 Belief-Congruent Perception

Belief-congruent perception emerges when stabilized priors channel retrieval and simulation generation in a direction that remains compatible with ambiguous input

- **Retrieval bias**. Stronger priors are expected to channel retrieval toward memory content that remains consistent with the established belief structure.
- **Simulation constraint**. Under the same ambiguous input, active simulations are expected to shift toward outcomes that preserve belief-consistent continuity.
- **Belief-consistent interpretation**. Stronger priors are expected to preserve interpretation against mild contradiction, while stronger contradiction redirects the loop toward revision or suppression depending on the remaining affective support behind the active simulation.

#### 4.3 Delayed Reentry

A useful way of thinking about delayed reentry is to ask whether a previously identified simulation continues to shape later choice or action after some interval. The model distinguishes itself most clearly when earlier content remains traceable in later behavior rather than disappearing without remainder.

#### 4.4 Minimal Empirical Outline

Any later empirical translation of TFL would need some way of making visible three broad functional tendencies: the strengthening of affective support, the biasing force of prior interpretation, and the role of contradiction in redirecting an active simulation. By the same token, any observational rendering would need some way of keeping recurrence of content, ambiguity-sensitive response, and shifts in affective intensity conceptually in view. These are described here as interpretive contours rather than as a fixed observational scheme.

#### 4.5 Distinguishing Criteria

TFL is intended to remain distinguishable from uncertainty-only, arousal-only, and habit-based accounts. Its explanatory value depends on whether persistence, recurrence, ambiguity-driven bias, and contradiction-driven updating remain attributable to the interaction of simulation continuity, affective persistence, and belief-constrained retrieval rather than to these simpler alternatives.

#### 4.6 Scope of Empirical Specification

The present account does not fix a single observational scheme, exclusion logic, or comparison procedure. Its purpose is to define the framework's internal structure and conditions of interpretation, while leaving specific empirical renderings open.

Any public rendering of the loop should therefore be read only as one illustrative expression of the framework rather than as the framework itself. The present manuscript remains confined to the structural logic of TFL.

Adaptations are permitted at the level of task materials, feature mappings, retrieval functions, parameter values, coding labels, equivalent measurement channels, and signal-processing settings. Adaptations are not permitted if they eliminate fixed temporal windows, content-identifiable simulation, affective persistence, belief-constrained retrieval, contradiction-driven updating or suppression, or meaningful comparison against uncertainty-only, arousal-only, and habit-based alternatives.

### 5.0 Limitations and Future Work

#### 5.1 Quantifying Simulation Strength

Simulation strength is described only through the persistence of identifiable content across windows and its influence on ambiguity-sensitive behavior. Where neither of these remains visible, the notion loses its interpretive footing within the present account.

#### 5.2 Limits of Introspective Report

Introspective report may help clarify active content, but it cannot bear the full interpretive weight of the model on its own. The framework becomes easier to read when subjective report, ambiguity-sensitive behavior, and some correlate of affective intensity can be considered together, even though no single observational arrangement is fixed here.

#### 5.3 Generalizability and Individual Differences

Between-person variation may be understood as differences in how readily simulations persist, how quickly they fade, and how strongly contradiction redirects them. Such differences remain meaningful only if the same underlying content and affective tendencies can still be followed with reasonable consistency.

#### 5.4 Scope and Interpretive Limits

TFL is a local mechanistic framework describing short-timescale recursive integration across sensory input, retrieved memory content, predictive simulation, affective persistence, and the integrated current state. By itself, it does not specify exact neural circuits, anatomical substrates, neurotransmitter systems, laminar pathways, or oscillatory signatures, nor does it on its own explain large-scale network transitions, long-term memory consolidation, identity formation, narrative construction, developmental trajectories, collective cognition, or the full richness of emotional experience. Affective intensity is modeled here only in the minimal form required for persistence and reentry, not as a full theory of emotion or phenomenology.

TFL should be read as a structural account of recursive, affect-modulated simulation. It does not explain what consciousness is, why awareness exists, or how subjectivity arises, and it does not attribute agency, volition, goals, or selfhood to internal processes. Nor does it prescribe therapeutic methods, behavioral interventions, or clinical protocols. Its role is mechanistic and explanatory, and it may be situated within broader predictive, global workspace, temporospatial, identity-related, or social-simulation accounts.

### 6.0 Final Synthesis

#### 6.1 Closing Statement

TFL formalizes cognition as a closed-loop system in which internally generated simulations are continuously integrated with sensory input and memory, persist conditionally on affective intensity, and are revised through interaction with contradiction and feedback. Its defining feature is not the presence of prediction, memory, or affect individually, but the recursive persistence of content-identifiable simulations across temporally structured integration windows. TFL is therefore best understood as a constrained, falsifiable component within a broader cognitive framework.
