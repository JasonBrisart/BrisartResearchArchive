# TFL — Internal Development

This directory contains the structured empirical refinement work that came *after* the raw pre-development notes and *before* formal integration into the released Temporal Feedback Loop (TFL) framework. Where the pre-development notes were informal observation, this stage treats those observations as testable claims: logging anomalies, running test ideas, tracking decisions, and identifying candidate variables and model extensions.

This is internal working material, not a specification of the released framework. Values, parameters, and mechanisms discussed here may be provisional, later revised, rejected, or superseded by the formal TFL release.

## What's in here

| File | Content |
|---|---|
| `observations.md` | Empirical-style observations derived from the raw notes — persistence thresholds, contradiction asymmetry, cue-overlap gating, memory retrieval bias, and other candidate effects framed in more formal (E(t), Sim(t), Minfo(t), Input(t)) terms. |
| `anomalies.md` | Cases where the emerging model's predictions don't hold — persistence without expected affective intensity, contradiction without suppression, reentry without cue overlap, and similar mismatches. |
| `decisions.md` | Working conclusions drawn from the observations/anomalies, each flagged with what still needs formal integration into the model (e.g. persistence as threshold rather than linear, asymmetric confirmation/contradiction updating). |
| `decision_triggers.md` | The criteria used to decide whether an observation gets promoted to a framework element, rejected, or flagged for further testing. |
| `experiment_log.md` | A running log of specific tests run against candidate mechanisms (persistence threshold, contradiction strength, cue-overlap reentry) and their outcomes/status. |
| `test_ideas.md` | Proposed experiments to isolate and validate individual mechanisms — e.g. varying contradiction strength to find a revision/suppression bifurcation point, or decoupling behavioral bias from self-report. |
| `mapping.md` | A short table tracing specific observations through to their test and resulting framework impact (observation → test → result → framework impact). |
| `variable_candidates.md` | Candidate parameters and state variables proposed for the model (persistence_threshold, cue_overlap, persistence_inertia, simulation_competition, contradiction_gain, belief_weight, ambiguity_weight, latent_simulation_state). |
| `extensions.md` | Proposed structural extensions to the model based on the above — explicit thresholds, belief as a weighting function, multi-simulation competition dynamics, asymmetric update rules, and related additions. |
| `failure_modes.md` | Conditions under which the system/model breaks down or becomes untestable (e.g. simulation content can't be uniquely identified, baseline models explain the effect equally well). |
| `open_questions.md` | Unresolved questions driving further work — whether persistence is truly threshold-based, what determines revision vs. suppression, whether resolution is discrete or continuous, and others. |
| `random_notes.md` | Unstructured working notes and gut impressions made alongside the more formal artifacts above. |

## What this is not

- This is **not** the formal TFL specification or its released documentation.
- Parameters and mechanisms named here (e.g. `persistence_threshold`, `belief_weight`) are candidates under evaluation, not confirmed or final components of TFL.
- This is **not** curriculum or onboarding material for labs.

For the released TFL framework, see the formal documentation elsewhere in the Brisart Research Archive.
