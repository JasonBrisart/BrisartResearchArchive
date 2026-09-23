# BrisartOS Dependency Policy

BrisartOS is intended to remain dependency-free.

The project should be understandable, portable, inspectable, and usable in offline or air-gapped research environments.

---

## Policy

BrisartOS should not require third-party Python packages or external build frameworks.

The preferred implementation model is:

```text
Python standard library only
```

---

## Not Allowed By Default

The project should not depend on:

- `pip` packages
- External Python libraries
- C extensions
- Compilers for normal project use
- Assemblers for normal project use
- Linkers for normal project use
- GRUB as a required project foundation
- Linux distribution build systems
- Embedded Linux frameworks
- Cloud services
- Online package retrieval

---

## Allowed

The following are acceptable by default:

- Python standard library modules
- Plain text documentation
- Generated binary files created by repository Python scripts
- Deterministic local build scripts written in Python
- Local inspection and validation scripts written in Python

---

## Rationale

Dependency-free development supports:

- Offline operation
- Air-gapped research environments
- Long-term preservation
- Source inspection
- Reproducibility
- Reduced supply-chain exposure
- Maintainability
- Educational clarity

---

## Design Rule

If a feature requires a dependency, the first design question should be:

> Can BrisartOS implement the required behavior directly using Python standard library code or generated binary structures?

If the answer is yes, BrisartOS should prefer the internal implementation.
