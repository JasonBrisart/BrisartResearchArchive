## Temporal Feedback Loop (TFL) — Baseline Reference Implementation

This package provides a **runnable behavioral baseline implementation** of the Temporal Feedback Loop (TFL) framework.

It is designed as an **editable reference implementation** that enables laboratories to execute a complete session, generate structured output data, and adapt the system to local task materials, equipment, and analysis pipelines.

This is not a full laboratory stack. It is a **controlled baseline** that preserves the core structural commitments required to test TFL.


---

## 1. Scope of this implementation

This baseline implements the minimal structure required for a valid TFL assay:

- Fixed temporal trial structure (120 trials, 3 blocks)
- Two-alternative ambiguity paradigm (Interpretation A / B)
- Content-identifiable prediction capture (Sim(t))
- Affect-intensity measurement (0–100 scale) (E(t))
- Behavioral choice and reaction-time logging
- Graded feedback (confirmatory / contradictory)
- Probe trials for content identification
- Delayed reentry trials (structured recurrence)
- Structured CSV output for downstream analysis

This implementation is sufficient to generate data for:

- simulation persistence
- ambiguity-driven behavioral bias
- contradiction-driven updating
- perturbation-sensitive changes in simulation stability and interpretation persistence


---

## 2. Explicit limitations

This package does **not** include:

- physiological acquisition (e.g., skin conductance, EEG)
- stimulus validation pipelines
- participant/session management
- blind coding infrastructure
- model comparison (e.g., cross-validation, likelihood-based evaluation)
- compliance / IRB infrastructure

Laboratories must implement these components independently.

All extensions must preserve the core structural commitments defined below.


---

## 2.1 Perturbation Adaptation (Design Consideration)

Repeated exposure to fixed perturbation structures (e.g., identical instructions or fixed timing intervals) may lead to participant adaptation, where perturbations become predictable and are incorporated into ongoing cognitive processing rather than functioning as external disruptions.
As a result:

perturbation effectiveness may decrease over time
simulation stability measures may be inflated under repeated exposure
participants may begin to execute perturbations as procedural routines

To mitigate this, laboratories may consider:

introducing variability in perturbation timing (e.g., non-fixed intervals)
applying minimal variation to perturbation instructions (e.g., directional or duration changes)
limiting repeated exposure to identical perturbation sequences across sessions

The current baseline implementation (v2.5) prioritizes controlled, reproducible structure and does not include these extensions by default.


---

## 3. Directory structure

TFL_Baseline/
├── experiment/
│   ├── run_tfl.py          # experiment execution engine
│   └── config.json         # experimental parameters
├── stimuli/
│   └── tfl_stimuli.csv     # editable ambiguity stimuli
├── analysis/
│   └── analyze_tfl.py      # baseline analysis script
└── data/
    └── tfl_output.csv      # generated output


---

## 4. Requirements

- Python 3.8 or higher  
- `pandas` (required to run analyze_tfl.py)


---

## 5. Running the experiment

1. Open a terminal  
2. Navigate to:


cd TFL_Baseline/experiment/

3. Run:


python run_tfl.py

4. Complete all trials (default: 120 trials)  

5. Output will be written to:


/data/tfl_output.csv


---

## 6. Running analysis

1. Navigate to:


cd ../analysis/

2. Run:


python analyze_tfl.py

The analysis script provides:

- trial and block counts  
- prediction and behavioral distributions  
- affect summary  
- reaction time summary  
- prior-consistency metrics  
- contradiction breakdown  
- probe-based recurrence estimate  
- delayed reentry summary  
- basic completion/quality check  
- perturbation-level switch metrics
- interpretation stability following perturbation


---

## 7. Experimental structure (baseline)

- Total trials: 120  
- Blocks:
  - Affect (amplification under fixed uncertainty)
  - Belief (prior manipulation)
  - Contradiction (graded feedback)

Each trial consists of:

- cue / context  
- ambiguous stimulus (A/B interpretations)  
- prediction (simulation selection)  
- affect-intensity rating (0–100)  
- optional perturbation step (selected trials)  
- immediate post-perturbation content probe (selected trials)  
- behavioral choice (A/B)  
- reaction time (prediction + behavioral)  
- feedback (confirmatory or contradictory)  
- probe (intermittent)  
- delayed reentry (recurrence condition)


---

## 8. Editing the implementation

### 8.1 Task content

Edit:


/stimuli/tfl_stimuli.csv

Each stimulus must define:

- ambiguous input  
- Interpretation A  
- Interpretation B  

Interpretations must be:

- mutually exclusive  
- exhaustively codable  


---

### 8.2 Experimental structure

Edit:


/experiment/config.json

Adjust:

- trial count  
- block structure  
- probe interval  
- delayed reentry interval  
- feedback schedule  
- perturbation_interval
- perturbation_types

---

## 9. Structural requirements (non-negotiable)

Any valid adaptation must retain:

- Two-alternative, content-identifiable simulations (A/B)  
- Per-trial affect-intensity measurement  
- Ambiguity-based input structure  
- Feedback-based updating (including contradiction)  
- Probe-based content identification  
- Recurrence-capable trial structure (including delayed reentry)  

If these conditions are not preserved, the implementation no longer tests TFL.


---

## 10. Intended use

This implementation is intended for:

- internal validation of TFL dynamics  
- laboratory prototyping  
- paradigm development  
- integration with physiological and advanced modeling systems  

It provides a **runnable baseline**, not a complete experimental system.


---

## 11. Version History

### v1.0 — Initial Conceptual Prototype
- Early experimental script structure
- Manual trial definition
- Basic prediction and affect capture
- No standardized task format or ambiguity structure
- No formal analysis pipeline

---

### v2.0 — Structured Execution Framework
- Introduced fixed trial structure (120 trials, 3 blocks)
- Established A/B ambiguity paradigm
- Added prediction, affect, and reaction-time logging
- Implemented CSV-based data output
- Introduced initial analysis script

---

### v2.1 — TFL Structural Alignment
- Aligned trial structure with TFL core variables (Sim(t), E(t))
- Added block differentiation (affect, belief, contradiction)
- Introduced basic feedback logic
- Improved data consistency and formatting

---

### v2.2 — Advanced Trial Mechanics
- Added probe trial logic for content identification
- Implemented delayed reentry trials
- Expanded output fields for recurrence and tracking
- Improved experimental coherence across blocks

---

### v2.3 — Baseline Stabilization
- Completed runnable end-to-end experiment system
- Standardized directory structure (experiment, stimuli, analysis, data)
- Refined ambiguity stimulus format (CSV-based)
- Improved analysis outputs (recurrence, contradiction breakdown, completion gate)
- Established institutional-grade README and documentation

---

### v2.4 — Baseline Completion (Reference Implementation)
- Fixed stimulus system (clean schema, no parsing errors)
- Fully synchronized experiment, config, stimuli, and analysis layers
- Verified complete execution pipeline (run → data → analysis)
- Improved documentation formatting and usability
- Achieved stable, reproducible baseline reference implementation

---

#### v2.5 — Embedded Perturbation Integration (Current)
- Integrated controlled sensory/body perturbation trials into baseline execution
- Added immediate post-perturbation content probe
- Added perturbation-specific output fields for stability testing
- Expanded analysis layer to compute perturbation-specific switch metrics
- Preserved all prior TFL baseline structural commitments while extending the baseline to test sensitivity to sensory/context variation in simulation stability

---

**Current Version:** Baseline Reference Implementation v2.5  
Future versions will expand parameter estimation, model evaluation, and integration with physiological data streams.

---

## Author

Jason Brisart  
Brisart Research Archive
