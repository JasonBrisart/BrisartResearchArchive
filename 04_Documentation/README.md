# 05_Documentation

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

---

## Versioning Convention

Files are suffixed `_v1`, `_v2`, etc., reflecting successive drafts of the same document type as a framework's theory is refined. Higher version numbers represent more recent, more structurally constrained iterations (e.g., TFL's `Guarantees_v4` tightens affective-intensity semantics relative to `_v1`–`_v3`). Earlier versions are retained rather than overwritten, preserving the reasoning trail behind each revision.
