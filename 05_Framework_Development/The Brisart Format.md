# The Brisart Format

## Purpose

The Brisart Format is the archive-wide authoring standard for public research-framework specifications maintained by the Brisart Research Archive. It defines the minimum document structure used to present a framework clearly, consistently, and in a form that can be reviewed, compared, revised, and preserved over time.

The format governs presentation and required coverage. It does not determine whether a candidate mechanism deserves framework status, establish empirical validity, or replace the separate selection, construction, verification, and completion standards maintained in this directory.

## Applicability

Use the Brisart Format for theoretical, conceptual, methodological, computational, and interdisciplinary research frameworks released through the archive.

A document conforms to the format only when each required section contains framework-specific material. Headings alone, generic placeholder language, or duplicated prose do not establish conformity.

Supporting documents, implementation modules, protocols, datasets, changelogs, and archive-governance files may use structures appropriate to their own responsibilities and are not required to imitate the framework manuscript format.

## Required Record Information

Each framework manuscript must identify:

- **Framework title**
- **Author**
- **Affiliation**
- **Contact**
- **ORCID or website**, where applicable
- **Version or edition**
- **Publication or revision date**

## Standardized Core Structure

_The Brisart Format v4.1_

### Abstract

Provide a concise overview of the framework's purpose, scope, central mechanism, principal contribution, and current evidential status.

The abstract must distinguish a proposal, validated result, exploratory extension, and implementation claim. A reader should be able to identify what the framework explains and what it does not establish without reading the full manuscript.

### 1.0 Introduction

Define the problem, phenomenon, or explanatory gap that motivated the framework.

Identify the framework's intended domain, relevant prior approaches, and the precise contribution being proposed. Introduce important scope limits early enough to prevent the title or opening claims from implying broader support than the manuscript provides.

### 2.0 Core Mechanism

Define the framework's components, variables, states, relationships, inputs, outputs, and governing constraints.

Every named mechanism must have a distinct functional role. Formal notation must map directly to defined elements and must not introduce unexplained variables, hidden stages, or unsupported implementation assumptions.

### 3.0 Internal Processing Dynamics

Explain how the mechanism behaves over time or across processing cycles.

Describe information flow, state transitions, feedback, recursion, thresholds, persistence, failure, recovery, and termination where applicable. Stable, transitional, and degraded behavior should be distinguishable from one another.

### 4.0 Applications and Predictions

State the framework's practical, theoretical, analytical, or interdisciplinary applications and derive testable predictions from the mechanism.

Predictions must identify observable outcomes, supporting conditions, comparison conditions, and findings that would weaken or falsify the proposed account. Applications must remain within the declared scope of the framework.

### 5.0 Limitations and Future Development

Identify assumptions, exclusions, unresolved variables, measurement limits, competing explanations, implementation gaps, and conditions under which the framework fails or becomes uninterpretable.

Future work should follow from specific unresolved requirements rather than serve as an unrestricted expansion of the framework's scope.

### 6.0 Final Synthesis

Integrate the framework's central mechanism, contribution, predictions, and limitations without introducing new claims.

The conclusion should state what the framework currently provides, the level of evidence supporting it, and the next work required for stronger interpretation, implementation, or validation.

## Optional Supporting Material

Appendices may be used for symbol definitions, protocol detail, worked examples, measurement mappings, data dictionaries, audit requirements, or implementation notes when those materials would interrupt the main argument.

Appendices must remain subordinate to the manuscript's declared mechanism and may not silently expand its scope or evidential ceiling.

## Relationship to Framework Development

The Brisart Format is applied after a candidate has entered formal development and continues to govern the public specification through revision and completion review.

- **Framework Selection Criteria** determines whether a candidate deserves development as a distinct framework.
- **Framework Construction Method** defines how the mechanism is decomposed and formalized.
- **Framework Verification Protocol** tests structural, dynamic, empirical, and cross-framework coherence.
- **Framework Completion Criteria** determines whether the public specification is complete.
- **Cascade Module** may support abstract implementation mapping when its adapter-based execution model fits the framework, but Cascade conformance is not required for every framework.

## Conformity Rule

A framework conforms to the Brisart Format when all required sections are present, each section performs its assigned responsibility, terminology and formal notation remain consistent across the manuscript, claims remain bounded by the stated evidence, and the document satisfies the applicable construction, verification, and completion requirements.
