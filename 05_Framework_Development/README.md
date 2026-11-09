# Framework Development

This directory owns the standards and infrastructure used by the Brisart Research Archive to classify, select, construct, document, verify, complete, map, and integrate research frameworks.

The files form one development system. They do not replace the individual framework specifications and do not by themselves establish empirical validity.

## Responsibilities

1. **Classification:** Is the candidate a research framework, development standard, implementation module, protocol, dataset, or governance document?
2. **Selection:** Does a proposed mechanism justify development as a distinct framework?
3. **Construction:** How must an accepted mechanism be decomposed, bounded, and formalized?
4. **Documentation:** How must the public framework specification be organized?
5. **Verification:** Does the framework remain structurally, dynamically, empirically, and systemically coherent?
6. **Completion:** Does the public specification contain everything required for release?
7. **Integration:** Where does the framework belong, how does it relate to other frameworks, and can it be mapped into an execution structure without changing its mechanism?

## Development Lifecycle

```text
Candidate material
    |
    v
Classification
    |
    +--> Development infrastructure / protocol / dataset / governance
    |
    v
Framework selection
    |
    v
Framework construction
    |
    v
Brisart Format authoring
    |
    v
Verification
    |
    v
Completion review
    |
    v
Public framework specification
    |
    v
Conceptual integration and optional implementation mapping
```

Failure at any framework stage returns the work to revision. A document is not promoted merely because it is polished, lengthy, reusable, computational, or conceptually interesting.

## Directory Contents

### [The Brisart Format](The%20Brisart%20Format.md)

Owns the public manuscript structure for archive frameworks. It governs presentation and required coverage, not empirical validity or framework admission.

### [Framework Selection Criteria](Framework%20Selection%20Criteria.md)

Determines whether a candidate explanatory mechanism deserves development as a distinct framework.

### [Framework Construction Method](Framework%20Construction%20Method.md)

Defines how an accepted mechanism is isolated, decomposed, formalized, bounded, connected to observable behavior, and translated into an abstract implementation structure.

### [Framework Verification Protocol](Framework%20Verification%20Protocol.md)

Tests structural traceability, dynamic consistency, parameter mapping, constraint integrity, cross-framework compatibility, behavioral coherence, empirical alignment, document conformity, and implementation-mapping consistency.

### [Framework Completion Criteria](Framework%20Completion%20Criteria.md)

Defines the minimum public specification required for release.

### [Cascade Module](Cascade%20Module.md)

Provides an optional adapter-based execution pattern for frameworks with activation, expansion, filtering, scoring, refinement, and commitment stages. Cascade is infrastructure, not a cognitive framework.

### [Architecture](ARCHITECTURE.md)

Defines organizational placement and separates cognitive framework layers from development infrastructure.

### [Interactions](INTERACTIONS.md)

Defines the current high-level conceptual interaction map among published cognitive frameworks.

## Development Standard

1. Classify the material.
2. Establish that the mechanism is necessary, distinct, bounded, and testable.
3. Define components, inputs, outputs, dynamics, assumptions, exclusions, and failure conditions.
4. Map every symbol, threshold, state, and transformation to a declared element or observable.
5. Author the public specification using the Brisart Format.
6. Map implementation abstractly. Use Cascade only where it naturally preserves the mechanism.
7. Apply the complete verification protocol.
8. Apply every completion criterion.
9. Integrate the completed framework without erasing its independent definition.

## Review Checklist

### Classification

- [ ] The item is correctly classified as framework, infrastructure, module, protocol, dataset, or governance.
- [ ] Supporting infrastructure is not presented as an empirically validated framework.

### Framework quality

- [ ] The mechanism is distinct, necessary, bounded, and testable.
- [ ] Components, inputs, outputs, dynamics, assumptions, and failure conditions are explicit.
- [ ] Formal notation maps directly to declared elements.
- [ ] Predictions include supporting and falsifying conditions.
- [ ] The manuscript conforms to the Brisart Format.
- [ ] Every claimed behavior traces to a defined component or interaction.
- [ ] No required component or relationship remains implicit.

### Optional Cascade mapping

- [ ] Cascade is used only when the mechanism naturally fits its execution pattern.
- [ ] Every adapter maps to a defined framework element.
- [ ] No hidden mechanism or unsupported parameter was introduced.
- [ ] Software executability is not treated as empirical validation.

## Reading Order

### First-time readers

1. `README.md`
2. `The Brisart Format.md`
3. `ARCHITECTURE.md`
4. `INTERACTIONS.md`
5. `Framework Selection Criteria.md`
6. `Framework Construction Method.md`
7. `Framework Verification Protocol.md`
8. `Framework Completion Criteria.md`
9. `Cascade Module.md`, when implementation mapping is relevant

### Framework authors and reviewers

1. `Framework Selection Criteria.md`
2. `Framework Construction Method.md`
3. `The Brisart Format.md`
4. `Framework Verification Protocol.md`
5. `Framework Completion Criteria.md`
6. `Cascade Module.md`, when applicable
7. `ARCHITECTURE.md`
8. `INTERACTIONS.md`

## File Authority

- `README.md` owns directory purpose, lifecycle, navigation, and the combined development standard.
- `The Brisart Format.md` owns public framework manuscript structure.
- `Framework Selection Criteria.md` owns admission into framework development.
- `Framework Construction Method.md` owns mechanism construction and abstract implementation mapping.
- `Framework Verification Protocol.md` owns validation and coherence checks.
- `Framework Completion Criteria.md` owns public release readiness.
- `Cascade Module.md` owns the optional adapter-based execution contract.
- `ARCHITECTURE.md` owns organizational placement.
- `INTERACTIONS.md` owns the current conceptual interaction map.

No supporting document may silently redefine a framework's core mechanism.

## Scope and Limitations

This directory does not itself validate an individual framework, replace a full specification, prove reduction between frameworks, convert conceptual relationships into implemented dependencies, require every framework to use Cascade, or disclose restricted institutional configuration.

## Summary

Framework development follows a controlled sequence: **classify the material, select a necessary mechanism, construct and formalize it, document it through the Brisart Format, verify its coherence, confirm completion, and integrate it without weakening its independent definition.**
