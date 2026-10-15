## Affective Reconsolidation and Plasticity Engine (ARPE): A Neurocognitive Model of Emotion-Driven Memory Updating and Structural Plasticity

- **Author:** Jason Brisart
- **Affiliation:** Brisart Research Archive
- **Contact:** [jason@brisartresearcharchive.com](mailto:jason@brisartresearcharchive.com)
- **ORCID / Website:** [Brisart Research Archive](http://www.brisartresearcharchive.com/)
- **Version:** Core Edition v1.0
- **Date:** October 2026

---

### Abstract

The Affective Reconsolidation and Plasticity Engine (ARPE) is a conceptual framework for modeling durable psychological change as a threshold-governed structural update loop.

ARPE distinguishes activation from durable update. A memory, belief, intention, learned association, self-model, or narrative structure may become active without being rewritten. The framework proposes that update eligibility depends on the joint presence of affective charge and resonance error, while successful loop closure depends on the integration of new input and the recovery of coherence.

The framework is summarized by two relations:

$$
G(t)=\mathbf{1}\!\left[A(t)E(t)\geq\theta_R\right]
$$

$$
S(t+1)=
\begin{cases}
S(t), & G(t)=0,\\
\Phi\!\left(S(t),I(t),A(t),E(t),C(t)\right), & G(t)=1.
\end{cases}
$$

Here, $G(t)$ is the loop-opening gate. The function $\Phi$ represents the full update process after threshold crossing. It does not guarantee improvement, successful integration, or durable change.

ARPE is presented as a structured proposal for future operationalization, simulation, and empirical testing. It is not a completed biological theory, diagnostic instrument, clinical protocol, or validated treatment model.

---

## 1.0 Introduction

ARPE addresses the difference between activating a cognitive-emotional structure and durably updating it.

A person may recall a memory, revisit a belief, experience strong emotion, encounter contradiction, or understand a new interpretation without carrying a changed structure into later contexts. ARPE proposes that durable update requires a completed sequence in which:

1. a stabilized structure becomes active;
2. affective charge and resonance error jointly meet an update-eligibility threshold;
3. the structure becomes temporarily labile or revisable;
4. new input is integrated during that interval;
5. coherence is recovered; and
6. the resulting structure is carried into a later cycle.

The framework is implementation-neutral. It does not require one measurement technology, one biological mechanism, one clinical procedure, or one domain of application.

---

## 2.0 Core Mechanism

| Symbol | Definition |
|---|---|
| $S(t)$ | The cognitive-emotional structure active at time $t$. |
| $I(t)$ | Incoming information or experience relevant to the active structure. |
| $A(t)$ | Affective charge or emotional salience associated with the active state. |
| $E(t)$ | Resonance error: mismatch between the active structure's expectations and the incoming input. |
| $C(t)$ | Coherence: the system's capacity to recover organized stability after destabilization. |
| $\theta_R$ | The proposed threshold for loop opening or update eligibility. |
| $G(t)$ | A binary loop-opening indicator determined by the threshold rule. |
| $\Phi$ | The as-yet-unspecified process governing integration, weighting, coherence recovery, and closure. |
| $S(t+1)$ | The structure carried forward after the cycle. It may be updated, partially updated, defensively preserved, unstable, or effectively unchanged. |

The variables require domain-specific operational definitions before empirical use. Their inclusion does not imply that they are already measurable on a universal scale.

---

### 2.1 Threshold-Governed Loop Opening

The loop-opening gate is:

$$
G(t)=\mathbf{1}\!\left[A(t)E(t)\geq\theta_R\right]
$$

where $\mathbf{1}[\cdot]$ equals $1$ when the condition is met and $0$ otherwise.

The proposed interpretation is:

- High affect with little meaningful mismatch may produce activation without update eligibility.
- High mismatch with little affective significance may be noticed without becoming structurally consequential.
- Jointly sufficient affective charge and resonance error may place the active structure in an update-eligible condition.

The product $A(t)E(t)$ is a proposed interaction term, not an empirically established biological law. It assumes that $A(t)$ and $E(t)$ are represented on compatible, nonnegative scales. That assumption must be defined and tested in any implementation.

Threshold crossing opens the possibility of update. It does not guarantee successful integration, coherence recovery, or durable change.

---

### 2.2 Structural Update Relation

The core structural relation is:

$$
S(t+1)=
\begin{cases}
S(t), & G(t)=0,\\
\Phi\!\left(S(t),I(t),A(t),E(t),C(t)\right), & G(t)=1.
\end{cases}
$$

When $G(t)=0$, the model represents the structure as returning substantially unchanged for purposes of the framework. This does not exclude temporary activation, emotion, insight, rehearsal, or short-lived state change.

When $G(t)=1$, the update function $\Phi$ becomes active. Its output depends on whether input becomes bound to the active structure, internal weighting changes, coherence is recovered, and the resulting organization persists.

The prime notation from earlier ARPE drafts is therefore not required. The carried-forward structure is written simply as $S(t+1)$, with outcome type specified separately.

---

## 3.0 Internal Processing Dynamics

ARPE organizes the proposed update loop into seven phases:

1. **Activation**  
   The target structure $S(t)$ becomes available through recall, attention, contextual cueing, bodily state, action, or re-entry into a relevant situation.

2. **Threshold evaluation**  
   The interaction of $A(t)$ and $E(t)$ is evaluated against $\theta_R$.

3. **Labile opening**  
   If the threshold condition is met, the active structure becomes eligible for revision.

4. **Input tagging**  
   Relevant input $I(t)$ becomes associated with the active structure during the proposed update interval.

5. **Structural reweighting**  
   The relative influence of old and new elements may change.

6. **Coherence recovery**  
   The system attempts to regain organized stability without rejecting, fragmenting, or failing to integrate the new input.

7. **Restabilization and later re-entry**  
   The resulting structure is carried forward and evaluated during later activation.

These phases are functional distinctions within the framework. They are not presented as a demonstrated sequence of discrete biological events.

---

### 3.1 Outcome Classes

ARPE distinguishes several outcomes:

| Outcome | Description |
|---|---|
| **Non-opening activation** | The structure activates, but the threshold condition is not met. |
| **Temporary destabilization** | The threshold opens, but new input does not become durably integrated. |
| **Defensive preservation** | The system returns to an organization that substantially preserves the previous structure. |
| **Instability** | The structure destabilizes without recovering sufficient coherence. |
| **Partial update** | Some new input is incorporated, but the prior organization remains substantially influential. |
| **Durable update** | A changed structure persists and alters later activation or behavior. |
| **Effective non-update** | The carried-forward structure is functionally indistinguishable from the prior structure under the selected assessment. |

These classes require operational criteria. They must not be assigned solely because a participant reports insight, emotional intensity, or immediate subjective change.

---

### 3.2 Core Claims

ARPE proposes the following claims:

1. Activation is not equivalent to durable structural update.
2. Affective charge alone is not sufficient for reliable update.
3. Resonance error alone is not sufficient for reliable update.
4. Joint affective charge and resonance error determine update eligibility through a proposed threshold interaction.
5. Threshold crossing permits update but does not guarantee it.
6. Relevant input must be integrated while the structure is update-eligible.
7. Coherence recovery is necessary for organized restabilization in the model.
8. Immediate emotion, insight, or novelty does not establish durable change.
9. Durable update requires evidence that the changed structure persists during later re-entry.
10. The resulting structure is not assumed to be healthier, more accurate, or more adaptive.

---

## 4.0 Applications and Predictions

ARPE generates predictions that can be evaluated after its variables are operationalized:

1. Reactivation alone should produce less durable structural change than a completed update condition.
2. Affect without meaningful mismatch should produce activation or arousal more reliably than durable target-structure revision.
3. Mismatch without sufficient affective significance should be less likely to produce durable target-structure revision.
4. Affect-plus-mismatch conditions meeting the proposed threshold should show greater update eligibility than affect-only or mismatch-only conditions.
5. Threshold crossing without successful integration or coherence recovery should produce weaker, unstable, or defensive outcomes rather than reliable durable update.
6. Evidence of durable update should appear during delayed re-entry into the target structure, not solely during the original session.

These are proposed predictions. The framework does not yet specify universally valid measures, effect sizes, timing windows, or parameter values.

---

### 4.1 Candidate Application Domains

ARPE may be evaluated in domains where a target structure can be identified before activation and reassessed after restabilization, including:

- autobiographical memory;
- fear learning and expectancy violation;
- belief revision;
- intention formation;
- self-model and narrative revision;
- skill correction;
- adaptive learning under salient feedback; and
- research on therapeutic change.

Use in a candidate domain does not establish clinical efficacy or biological validity. Each domain requires its own operational definitions, controls, safety considerations, and validation methods.

---

### 4.2 Falsifiability and Evaluation

Evidence challenging ARPE would include reproducible findings such as:

- durable target-structure update occurring independently of the proposed threshold variables under conditions where those variables are validly measured;
- affect-plus-mismatch conditions failing to predict update eligibility better than activation-only, affect-only, or mismatch-only conditions;
- coherence recovery showing no relationship to organized restabilization after threshold crossing;
- delayed re-entry failing to distinguish durable update from temporary state change; or
- the full-loop condition failing to outperform simpler explanations such as rehearsal, exposure, ordinary learning, compliance, mood change, or social reinforcement.

A null result cannot be interpreted until the variables, time windows, target structure, comparison conditions, and outcome criteria have been specified in advance.

---

## 5.0 Limitations and Future Development

ARPE is a conceptual and methodological framework. It is not:

- a completed biological account of reconsolidation;
- proof that affect and mismatch combine multiplicatively in the nervous system;
- a validated clinical protocol;
- a diagnostic system;
- an individual treatment recommendation;
- an executable implementation; or
- evidence that every durable psychological change follows this loop.

Major unresolved requirements include:

- operational definitions for $A(t)$, $E(t)$, $C(t)$, and $S(t)$;
- validated measurement scales;
- threshold estimation;
- definition of the update interval;
- separation of durable structural change from temporary state effects;
- delayed outcome verification;
- domain and population boundary conditions;
- comparison against simpler models; and
- preregistered criteria for classifying outcomes.

---

## 6.0 Final Synthesis

ARPE proposes that durable psychological change can be studied as a threshold-governed structural update loop.

The loop-opening condition is:

$$
G(t)=\mathbf{1}\!\left[A(t)E(t)\geq\theta_R\right]
$$

The structural transition is:

$$
S(t+1)=
\begin{cases}
S(t), & G(t)=0,\\
\Phi\!\left(S(t),I(t),A(t),E(t),C(t)\right), & G(t)=1.
\end{cases}
$$

The framework's central distinction is between activation and durable update. Threshold crossing creates update eligibility; input integration and coherence recovery determine the proposed path toward restabilization; delayed re-entry is required to evaluate whether change endured.
