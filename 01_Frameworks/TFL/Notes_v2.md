# Temporal Feedback Loop (TFL) Notes

This section defines clarifications and boundary conditions for interpreting the Temporal Feedback Loop (TFL) framework. It specifies how the model should be applied, what it does and does not describe, and how it interfaces with broader theoretical systems.

## Scope of the Framework

TFL specifies the temporal and recursive structure of cognitive processing as a closed-loop interaction over:

- `Input(t)`.
- `Minfo(t)`.
- `E(t)`.
- `Sim(t)`.
- `F(t)`.

It formalizes how these variables interact across discrete temporal windows. However, it does not independently define full network-level dynamics beyond its minimal circuit-level grounding in hippocampal-prefrontal interaction.

## Implementation-Ready but Non-Prescriptive

Although the Institutional Edition includes a runnable baseline model with default parameters and update rules, TFL remains a structural template rather than a fixed implementation.

Valid implementations require laboratory-specific adaptation, including:

- Retrieval functions.
- Feature mappings.
- Parameter calibration.

The framework defines system structure and constraints but does not prescribe a canonical implementation.

## Affective Parameter Limits

`E(t)` is defined as a scalar parameter representing affective intensity. It captures the minimal affective structure required for simulation persistence and cross-cycle reentry.

It does not:

- Encode full emotional phenomenology.
- Represent multidimensional affective states.

Its role is strictly functional: to determine whether simulation content persists across temporal windows.

## Belief as Structural Prior

Beliefs are defined as affectively stabilized structural priors that bias:

- Memory retrieval (`Minfo(t)`).
- Simulation generation (`Sim(t)`).
- Interpretation of incoming input.

This definition is operational rather than philosophical and does not commit the framework to any specific account of selfhood, identity, or ontology.

## Temporal Window Approximation

The canonical processing interval of approximately 100 to 300 ms reflects empirically observed ranges associated with perceptual updating and hippocampal-prefrontal interaction.

This interval should be treated as:

- An approximate operating range.
- Not a fixed parameter.

## Integration with Other Frameworks

TFL is designed to function as a substrate within a broader framework stack.

It can be embedded within:

- Identity-related systems.
- Social simulation models.
- Predictive processing architectures.
- Temporospatial and integration frameworks.

TFL specifies local recursive dynamics, while higher-level frameworks define large-scale structure, coordination, and system-level behavior.

## Model Boundaries

TFL does not independently account for:

- Large-scale network transitions, such as DMN-CEN switching.
- Sleep or altered-state dynamics.
- Multi-agent or collective cognition.
- Full emotional or experiential richness.

These domains require additional frameworks or extensions beyond the TFL loop.

## Interpretive Guidance

TFL should be interpreted as a structural model of recursive, affectively modulated simulation.

It specifies:

- How internal representations are generated.
- How they persist or decay.
- How they update in response to incoming input.

It does not:

- Prescribe behavioral interventions.
- Define therapeutic methods.
- Provide applied clinical protocols.

Its role is mechanistic and explanatory.
