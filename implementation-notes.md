# Implementation notes

## Deviations

- 2026-11-25, #38 [10]: the plan assumed `kit doctor` exiting 0 with a red review line was a hole to close. It is the documented contract: the exit code covers rungs 0 to `--rung`, `--rung 3` already exits 1 on a red review, CI runs `--rung 2`, and `test_next_never_says_climb_a_gated_rung` pins exit 0 there. Changing it would turn CI red on `main` with no commit. Left the exit code alone and wrote the contract into the module docstring and `docs/ladder.md`.
