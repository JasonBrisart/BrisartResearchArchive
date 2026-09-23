# Temporal Feedback Loop (TFL) Integration Notes

This section defines the role of the Temporal Feedback Loop (TFL) within a multi-framework system architecture. It specifies directional relationships between TFL and adjacent frameworks while preserving TFL as a constrained, locally defined component.

All interactions described here are external to TFL's internal structure and do not modify its core variables, guarantees, or operational constraints.

## 1. TFL Role and Scope

### Role

TFL operates as a short-timescale predictive simulation module. Within each temporal window of approximately 100 to 300 ms, it constructs predictive simulations from the interaction of:

- Sensory evidence (`Input(t)`).
- Retrieved memory content (`Minfo(t)`).
- Prior system state.

Simulation persistence across temporal windows is governed by affective intensity (`E(t)`), which determines whether simulations are carried forward into subsequent cycles.

These simulations contribute to the integrated internal state `F(t)`, which is propagated forward as a prior across cycles.

### Scope Constraints

- TFL does not attribute agency, volition, goals, or selfhood to internal processes.
- Simulations are treated as computational hypotheses, not ontological claims.
- TFL guarantees apply strictly to `Input(t)`, `Minfo(t)`, `E(t)`, `Sim(t)`, and `F(t)`.
- TFL does not infer or depend on constructs outside this variable set.

## 2. TFL ↔ PFT: Perceptual Framing

### Mechanism

- **PFT → TFL:** PFT defines the active interpretive frame, biasing the selection of `Minfo(t)` under current sensory conditions.
- **TFL → PFT:** TFL generates predictive simulations that may influence perceptual interpretation by biasing frame completion under ambiguity.

### Integration Constraint

Stabilized perceptual frames constrain the space of admissible simulations. TFL outputs remain bounded by available sensory evidence and retrieved memory content.

## 3. TFL ↔ SST: Identity Synchronization

### Mechanism

- **SST → TFL:** SST defines identity-relevant constraints that may bias interpretation of simulated content under ambiguity.
- **TFL → SST:** TFL produces predictive simulations that SST may evaluate relative to identity-consistent or socially expected outcomes.

### Integration Constraint

TFL does not encode or represent identity states. Identity-related structure operates externally by influencing interpretation and evaluation, not by modifying TFL's internal variables.

## 4. TFL ↔ IRE: Volitional Arbitration

### Mechanism

- **TFL → IRE:** TFL provides predictive simulations that may serve as input to intention evaluation processes.
- **IRE → TFL:** Outcomes of resolved decisions may be encoded into memory, influencing future retrieval (`Minfo(t)`).

### Integration Constraint

TFL performs no decision-making or action selection. It supplies predictive context only. All arbitration processes are external to the TFL loop.

## 5. TFL ↔ TCRF: Temporal Coherence

### Mechanism

- **TCRF → TFL:** TCRF operates at the level of temporal coherence, within which TFL processing must remain consistent with the temporal structure of incoming sensory input.
- **TFL → TCRF:** TFL produces temporally structured outputs that remain compatible with ongoing sensory input.

### Integration Constraint

Mismatch between predictive simulation and sensory input results in contradiction conditions that drive revision or suppression of `Sim(t)` within TFL. Temporal coherence is not computed by TFL and is enforced externally.

## 6. TFL ↔ VRIF: Resonance-Based Integration

### Mechanism

- **VRIF → TFL:** VRIF defines the degree to which TFL-generated content contributes to broader system-level integration.
- **TFL → VRIF:** TFL provides predictive simulation content that may be incorporated into system-wide processing.

### Integration Constraint

TFL does not control system-level integration strength. It produces predictive simulation content only. Cross-stream integration is governed externally.

## 7. TFL → RIET: Boundary-Condition Phenomena

### Mechanism

Under specific conditions:

- High sensory uncertainty.
- Identifiable but ambiguous input.
- Elevated affective intensity.

TFL-PFT interaction may produce dominant simulations that strongly bias the internal state.

### Integration Constraint

RIET is not a peer system component. It is a boundary-condition expression of TFL dynamics under conditions of ambiguity and persistence. It does not modify TFL structure, variables, or guarantees.

## 8. System-Level Directional Roles

Within the broader architecture:

- **PFT:** Defines interpretive framing constraints.
- **TFL:** Generates predictive simulations from sensory and memory input.
- **SST:** Stabilizes identity-relevant structure.
- **IRE:** Performs decision and action selection.
- **TCRF:** Operates at the level of temporal coherence.
- **VRIF:** Governs cross-stream integration and binding.

Each system operates as a distinct module. TFL remains a local integration mechanism within this larger system.

## 9. Cross-Framework Constraint Rule

All interactions listed above:

- Do not introduce new variables into TFL.
- Do not modify TFL's internal integration or persistence functions.
- Do not extend TFL guarantees beyond its defined variable set.

TFL remains fully defined and valid independently of any higher-level framework.
