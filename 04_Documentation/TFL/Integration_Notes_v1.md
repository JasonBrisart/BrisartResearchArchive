# Temporal Feedback Loop (TFL) Integration Notes

## 1. TFL Role and Scope

**Role:** TFL is the system's **short-timescale predictive simulation engine**. Each cycle, approximately 100 to 300 ms, it synthesizes a predictive simulation by recombining:

- Current sensory evidence.
- Contextually relevant retrieved memory content.
- Affective modulation `A(t)`.

This simulation becomes the **integrated conscious state** for that moment and is carried forward as the next prior.

**Scope limits:**

- TFL does not attribute agency, volition, or selfhood to internal processes.
- Simulations are computational hypotheses, not ontological claims.
- Guarantees apply only to the five declared variables (PFT, SST, IRE, TCRF, VRIF).
- TFL does not infer unmodeled constructs.

## 2. TFL ↔ PFT: Perceptual Framing

**Mechanism:**

- **PFT → TFL:** PFT provides the active interpretive frame. This frame acts as a retrieval query, selecting memory traces relevant to the current scene.
- **TFL → PFT:** TFL recombines retrieved traces with sensory evidence to synthesize a predictive simulation. This simulation biases PFT's frame completion and disambiguation.

**Integration boundary:**

- Stabilized frames act as priors that constrain TFL's output space.
- If TFL's affective gain `A(t)` dominates the evidence channel, perception collapses into overfitted priors, including maladaptive persistence and belief rigidity.

## 3. TFL ↔ SST: Identity Synchronization

**Mechanism:**

- **SST → TFL:** SST computes affective prediction errors `ϵ`, updates identity representations, sets identity-relevance weights on the trace pool, and can modulate `A(t)`.
- **TFL → SST:** TFL provides emotionally modulated predictive scenarios that SST evaluates against expected social feedback.

**Integration boundary:** Avoid symmetric overcoupling. If SST's identity weighting and TFL's simulation persistence mutually amplify, the system enters rigid, self-confirming identity loops.

## 4. TFL ↔ IRE: Volitional Arbitration

**Mechanism:**

- **TFL → IRE:** TFL supplies reward expectancy and affective charge for intention evaluation.
- **IRE → TFL:** Once IRE resolves an intention, the outcome is encoded as a new trace, expanding TFL's future retrieval pool.

**Integration boundary:** TFL performs no decision-making. It provides the predictive context IRE requires to evaluate competing intention vectors.

## 5. TFL ↔ TCRF: Temporal Coherence

**Mechanism:**

- **TCRF → TFL:** TCRF enforces temporal coherence by calibrating phase, frequency, and amplitude signatures to minimize resonance mismatch with TFL's simulation.
- **TFL → TCRF:** TFL's processing windows must align with TCRF's temporal kernels.

**Integration boundary:** A structural mismatch between TFL's simulation and incoming sensory evidence produces a resonance error `Re`. `Re` forces TFL to revise or suppress the simulation to maintain continuity.

## 6. TFL ↔ VRIF: Resonance-Based Integration

**Mechanism:**

- **VRIF → TFL:** VRIF provides a continuous Integration Strength (`IS`) that determines how strongly TFL's simulation binds into unified awareness.
- **TFL → VRIF:** The affective intensity and coherence of TFL's simulation modulate system-wide resonance.

**Integration boundary:** Low `IS` weakens binding, producing fragmentation or intrusive phenomena. High-arousal simulations that fail to resolve can destabilize cross-stream coupling.

## 7. TFL → RIET: Emergent Apparitional Phenomena

**Mechanism:** RIET, specifically RIETM, is an emergent operational state of the TFL/PFT loop under extreme conditions:

- High sensory uncertainty.
- Salient spatial cues.
- Elevated affective intensity.

Under these conditions, TFL's recombined simulation can dominate awareness. Source-monitoring bias under ambiguity leads to phenomenological misattribution, producing site-anchored echoes known as Ghost Perception Events (GPEs).

**Integration boundary:** RIET is not a peer module. It is a boundary-condition expression of the predictive loop.

## 8. System-Level Directional Roles

- **PFT:** Defines the interpretive frame.
- **TFL:** Synthesizes predictive simulations from sensory and memory data.
- **SST:** Stabilizes the identity experiencing the frame.
- **IRE:** Arbitrates competing intentions.
- **TCRF:** Maintains temporal coherence.
- **VRIF:** Scales resonance binding across streams.

## Operational Appendix: Control Variables

- **`A(t)`:** Affective gain scalar controlling TFL sampling rate and persistence. Range: 0 to 1.
- **`ϵ`:** Affective prediction error computed by SST to update identity weights.
- **`Re`:** Resonance error signal computed as normalized phase/frequency mismatch between TFL simulation and sensory input.
- **`IS`:** Integration Strength, a continuous scalar determining the degree of phenomenological binding. Low `IS` produces fragmentation; high `IS` produces unified awareness.
- **`DecisionProximity`:** Scalar that increases as IRE approaches a resolution threshold, increasing TFL sampling density and counterfactual richness.
- **Processing Window:** Canonical TFL cycle of 100 to 300 ms, aligned to TCRF temporal kernels.
