# Temporal Feedback Loop (TFL) Architecture

## Architectural Requirements

1. Variables interact in a loop.
2. Define the order lightly.
3. Define iteration.
4. Define carry-forward.

## Iteration Sequence

At each iteration `t`:

1. `Input(t)` is received.
2. `Minfo(t)` is retrieved based on current state.
3. `E(t)` modulates weighting and persistence.
4. `Sim(t)` is generated from `Input(t)`, `Minfo(t)`, and `E(t)`.
5. `F(t)` is produced and carried forward to `t+1`.

This process repeats continuously.
