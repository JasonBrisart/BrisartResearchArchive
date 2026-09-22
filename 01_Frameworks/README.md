# 01_Frameworks

## Purpose

This folder is the home of the core theoretical framework documents for the Brisart Research Archive. Each subfolder corresponds to a single framework, identified by its acronym, and contains the versioned drafts that define that framework's architecture, terminology, guarantees, and boundaries.

This is where a framework's *theory* lives — its formal structure, variables, and claims — independent of curriculum materials, public release packaging, licensing, or execution/software tooling, which are maintained elsewhere in the archive.

---

## Document Types

Each framework subfolder uses a consistent set of document types, versioned independently as the framework matures:

| Document | Role |
|---|---|
| **Overview** | High-level summary of the framework's core claim, variables, and operational loop. |
| **Architecture** | Formal structural definition of components, layers, and information flow. |
| **Boundaries** | Explicit scope limits — what the framework does *not* claim or model. |
| **Guarantees** | Non-negotiable architectural properties the framework enforces across implementations. |
| **Definitions** | Precise definitions of every core variable and structural term. |
| **Reference_Implementation** | Pseudocode representation of a single processing cycle, structural only. |
| **Integration_Notes** | How the framework interfaces with other frameworks in the archive (directional relationships and constraints). |
| **Notes** | Clarifications, interpretive guidance, and implementation caveats. |
| **Release_Notes** | Version history and development timeline for the framework. |

---

## Versioning Convention

Files are suffixed `_v1`, `_v2`, etc., reflecting successive drafts of the same document type as a framework's theory is refined. Higher version numbers represent more recent, more structurally constrained iterations (e.g., TFL's `Guarantees_v4` tightens affective-intensity semantics relative to `_v1`–`_v3`). Earlier versions are retained rather than overwritten, preserving the reasoning trail behind each revision.

## Notes

- Documents in this folder are theory-only: variable definitions, architecture, and scope. Licensing terms, public release packaging, curriculum, and execution/software code are maintained in their respective archive folders, not here.
