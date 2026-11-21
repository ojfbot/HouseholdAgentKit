# Review request: find the checks that would pass when they shouldn't

You are an independent reviewer. A different model wrote everything you are about to read, and your job is to distrust it. You are not asked to improve the code or the plan.

## What this is

A small public repo, `ojfbot/HouseholdAgentKit`, holds code that four separate AI sessions wrote without running each other's work. It is being integrated in ten steps ("rungs"), from "the repo is coherent" to "the demo bundle runs offline on the laptop that goes on stage on Dec 2". Each rung is gated by checks that print green or red. A command, `kit doctor`, runs them.

The owner's rule: **the plan must not depend on the checks being right.** A bad check should cost hours, not a week. So every check must have been shown red on a deliberately broken setup and green on a working one, and one adversarial review of the checks happens before anyone climbs past rung 2. This is that review.

## What to read (in this order)

1. `docs/ladder.md`: the rungs, each check, and the breaks each check was proven against.
2. `kit/src/kit_cli/doctor.py`: the checks and their proofs (about 640 lines).
3. `tests/doctor/test_doctor_checks.py` and `.github/workflows/ci.yml`.
4. `docs/integration-risk-register.md`: what the audit found, including five checks that already passed when they should not have (R-04 to R-08).

## The two questions

**1. Which checks would pass when they shouldn't?** For each check, try to describe a broken setup that it would still call green. Things worth trying:

- The break that was planted is the easy one. What is the realistic break next to it? Example: `ports_agree` reads defaults with three regular expressions. What happens if a default moves to a config file, or a fourth service appears?
- Does a check test the thing, or a description of the thing? Example: `runners_hosted` reads `runs-on` labels. Can a workflow still reach a private machine with a hosted label (a reusable workflow, a container, a step that opens a connection)?
- Does a proof's "working setup" resemble a real one? Several proofs run on a partial copy of the repo in a temp folder.
- Does green on GitHub's Linux runner get read as green for a Mac? Which rung-2 checks could be green in CI and wrong on macOS?
- `hello_world_smoke` runs a reference stand-in agent. What would it take for it to stay green while the real agent is broken or absent?
- Does any check depend on today's date, the network, the order of a dictionary, or an environment variable such as `UV_FROZEN`?
- Can a check be made green by editing the file it reads (the port registry, the checksum file, the risk register's review section) instead of fixing the problem? Which of those edits would a hurried agent make?

**2. Which seams have no check?** A seam is any place where one piece meets another piece, a machine, or a date. Look for ones the ladder never tests. Starting points:

- Two packages that agree only by convention (the label vocabulary on numbers, money as integer cents or floats, the two synthetic taco worlds in R-12).
- Contracts that are "loose" or unacknowledged while code is built on them.
- Things that change on a calendar date (R-02).
- The step from fixtures to live services in the demo console.
- Rungs 3 to 10: their checks are only planned. For each planned check and planned break in `docs/ladder.md`, say whether the break is the right one and what second break you would demand.
- Anything between "CI is green" and "it works on stage with phones on a hotspot".

## What to send back

A list, most serious first. For each item:

- **Check or seam** (name it as the docs do).
- **The broken setup that stays green**, concretely enough that someone could build it in ten minutes.
- **Why it matters for Dec 2** in one sentence.
- **The smallest fix**: a second planted break, a tighter condition, or a new check.
- **Confidence**: did you run it, read it, or infer it?

Then one closing line for each of these: the check you trust least, the seam you would test first, and anything in the risk register you think is wrong.

Do not soften findings, and do not pad the list. If a check is sound, say so in one line and move on. If you could not open or run something, say which thing.

## How the result is used

The findings and the fixes go into `docs/integration-risk-register.md` under "Independent review". `kit doctor` reads that section, and rung 3 does not start until it says `Status: recorded`.
