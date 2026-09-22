# Cascade Module

## Plug-and-Play Specification

---

## Adapter Contract

| # | Adapter | Signature |
|---|---|---|
| 1 | SeedAdapter | `SeedAdapter(seed_input, host_context) -> SeedRegion` |
| 2 | ConstraintAdapter | `ConstraintAdapter(host_context) -> Constraints` |
| 3 | ScoreAdapter | `ScoreAdapter(host_context) -> Score(x) in [0,1]` |
| 4 | ParamsAdapter | `ParamsAdapter(host_context) -> {theta_activate, theta_expand, theta_continue, theta_bind, Rmax, ...}` |
| 5 | DistanceMetric | `DistanceMetric(host_context, SeedRegion) -> Dist` |
| 6 | Activate | `Activate(signal, theta_activate) -> {0,1}` |
| 7 | Expand | `Expand(signal, SeedRegion, Dist, theta_expand, Params) -> Candidates` |
| 8 | Filter | `Filter(Candidates, Constraints, Params) -> Viable` |
| 9 | SelectBest | `SelectBest(Viable, Score) -> x` |
| 10 | Refine | `Refine(Viable, r, signal, Constraints, Params) -> Viable` |
| 11 | CommitAdapter | `CommitAdapter(x_star, host_context) -> {commit_kind, commit_payload}` |

---

## Reference Pseudocode

```text
function Cascade_Run(signal, seed_input, host_context):
    SeedRegion  = SeedAdapter(seed_input, host_context)
    Constraints = ConstraintAdapter(host_context)
    Score       = ScoreAdapter(host_context)
    Params      = ParamsAdapter(host_context)
    Dist        = DistanceMetric(host_context, SeedRegion)

    active = Activate(signal, Params.theta_activate)
    if active == 0:
        return {status: "inactive", x_star: null, commit_kind: null, commit_payload: null}

    Candidates = Expand(signal, SeedRegion, Dist, Params.theta_expand, Params)
    Viable     = Filter(Candidates, Constraints, Params)

    for r in 1..Params.Rmax:
        x_r = SelectBest(Viable, Score)
        if Score(x_r) >= Params.theta_continue:
            break
        Viable = Refine(Viable, r, signal, Constraints, Params)

    x_star = SelectBest(Viable, Score)
    if Score(x_star) >= Params.theta_bind:
        {kind, payload} = CommitAdapter(x_star, host_context)
        return {status: "commit", x_star: x_star, commit_kind: kind, commit_payload: payload}
    else:
        return {status: "no_commit", x_star: null, commit_kind: null, commit_payload: null}
```

---

## Return Values

| `status` | `x_star` | `commit_kind` | `commit_payload` | Condition |
|---|---|---|---|---|
| `inactive` | `null` | `null` | `null` | `Activate` returns 0 |
| `commit` | selected `x_star` | from `CommitAdapter` | from `CommitAdapter` | `Score(x_star) >= theta_bind` |
| `no_commit` | `null` | `null` | `null` | `Score(x_star) < theta_bind` |

---

## Parameters

| Parameter | Used by | Role |
|---|---|---|
| `theta_activate` | `Activate` | gates entry; below it the module returns `inactive` |
| `theta_expand` | `Expand` | bounds candidate generation from the seed region |
| `theta_continue` | refinement loop | early-exit score; breaks the loop when met |
| `theta_bind` | commit check | minimum score for `CommitAdapter` to be invoked |
| `Rmax` | refinement loop | maximum refinement rounds |
