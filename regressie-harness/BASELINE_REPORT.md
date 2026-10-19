# Harness preparation report — 19 October 2026

Source: `main @ 7ab801e7d9ad4540b3fc71c5f4aef46ec8bd6259`, version 1.1.13.
The reference was prepared in staging against this source revision. Adding the
harness to the repository does not change masking code, fixtures or the reference.

## Metric and reference

The previous presence-only check could incorrectly approve partial masking.
`source-coverage-v2` evaluates whether letters or digits from each gold span can
remain visible. The old and new metrics cannot be gated against each other.
A separate `baseline-v2.json` records the new reference, with portable provenance.
No reduced score was accepted as a new norm to conceal a fault.

The gold set, corpus and regex snapshot remain byte-for-byte unchanged. The v1
baseline, provenance and historical reports were preserved outside the active
harness directory, with a full backup taken before editing. The `.gitattributes`
preserves the original bytes of frozen fixtures.

## Validation during functional preparation

| Check | Result |
| --- | --- |
| Harness in a clean environment with test dependencies only | 29 passed; no project or model libraries installed |
| Ordinary suite through the PowerShell runner | 525 passed, 11 strict expected failures |
| Exact regex snapshot | All 952 texts match the existing reference |
| Model-free gold gate | 13/13 evaluated spans fully masked; four NER spans excluded |
| Separate offline integration test | Passed; full gate including NER enforced |
| Full gold gate through the runner | 17/17 spans fully masked; all ten categories at 1.00; no residuals or overmasking warnings on this set |
| Existing runtime dependencies | `pip check`: no conflicts |
| Missing repository, runtime dependencies or model configuration | Failure status rather than an all-skipped green run |
| Runner from another working directory, with local configuration variables removed | Harness-only tests pass; runtime failure is propagated |

The 525 passing tests comprise 29 harness tests, eleven inventory checks and the
485 existing regression tests. Inventory checks characterize current faults;
they do not approve them. The eleven desired-behavior tests remain separately
marked `xfail(strict=True)`.

## Demonstrating fragment detection

The historical PR #16 prototype was rerun with regex and list passes on the gold
set. S05 and S15 retained `NL12 RABO` and `NL12 INGB`, respectively, while their
digits were replaced by `<Telefoon>`. This was a fresh regex/list measurement of
that variant, not a fresh full-model measurement of it.

| Scorer | IBANs counted as fully masked | Gate |
| --- | --- | --- |
| Previous presence-only check | 2/2 | Fragments were not detected |
| V2 coverage check | 0/2 | Regression, exit 1 |

Eight of eighteen letters/digits remained visible per account. Additional tests
cover a single surviving character, partial names, repeated values, ambiguous
alignment, invalid gold, existing tags and unsupported rewrites. A small exhaustive
check compares alignment with independently enumerated possible positions. The
gate also rejects legacy references, missing categories, changed support and
overwriting its own comparison baseline.

## English documentation and cleanup

The publication set uses English documentation, comments, docstrings, diagnostics
and explanatory metadata. Dutch test inputs, expected output, masking labels and
stable case IDs are preserved. The method and baseline reports were renamed to
`EVALUATION.md` and `BASELINE_REPORT.md`, with references updated. Remaining
snapshot backups and the redundant directory placeholder were archived outside
the active harness directory.

This language round does not change masking or evaluation logic. Original
measurement timestamps and numerical baseline results are preserved. Provenance
records the editorial update separately. Language validation uses the model-free
suite, harness-only environment, fixture hashes and a source-structure comparison;
the model results above remain the functional-preparation measurements.

## Pre-publication corrections

Two additional review findings were corrected in staging:

- The subprocess import test now uses the harness directory explicitly, so it
  also works when pytest is started from the enclosing repository root.
- The gate validates both scorecards before comparison. Missing, null,
  non-finite, out-of-range and inconsistent measurements fail rather than being
  skipped. Non-standard JSON numbers and invalid tolerances are also rejected.

Verification after these corrections:

| Check | Result |
| --- | --- |
| Harness-only suite in the clean test environment | 80 passed, including from the repository root |
| Ordinary suite in an isolated source export, from the harness directory | 576 passed, 11 strict expected failures |
| Same suite from the enclosing repository root | 576 passed, 11 strict expected failures |
| Model-free gold gate with automatic repository discovery | Passed; 13/13 spans fully masked |
| Offline full-model integration test from the repository root | Passed with the strict gate; 17/17 spans fully masked |
| CLI with null or NaN baseline scores | Nonzero exit status; no green gate result |

The 51 additional harness cases test invalid measurements and tolerances plus a
valid partial reference. This does not change the coverage metric, masking
behavior, fixture bytes, numerical baseline values or original measurement
timestamps. Provenance records the gate correction and updated scorer hash
separately; the approved baseline has not been replaced.

## Independent-audit follow-up

The independent audit identified three further safeguards, now implemented:

- Both pytest and the scorecard check the actual loaded project namespace,
  including cached submodules and package search paths, against the selected
  source checkout. A preloaded foreign installation is rejected before measurement.
- Official project runs require the snapshot and every documented desired and
  inventory test. Omission or deselection fails collection; a skipped required
  check fails the run. Intentional partial pytest runs remain supported.
- Scorecards record input hashes before and after evaluation, actual environment
  metadata and a result fingerprint. Repinning requires a valid card, a matching
  receipt and unchanged current inputs from a clean Git checkout. It cannot
  attribute today's hashes to an unrecorded old measurement.

Verification of the follow-up:

| Check | Result |
| --- | --- |
| Clean harness-only environment, including repository-root invocation | 104 passed |
| Full project suite from the harness directory and enclosing repository root | 600 passed, 11 strict expected failures at each location |
| PowerShell project runner with automatic source discovery in an isolated export | Passed, with full-suite policy and model-free gold gate |
| Preloaded foreign modules in scorecard and pytest | Rejected, exit 1 and 4 respectively |
| Required tests ignored in full mode | Rejected before execution, exit 4 |
| Snapshot deliberately skipped in full mode | Rejected at session end, exit 1 |
| Deliberate targeted suite without full mode | Passed |
| Empty, unrecorded historical or edited scorecard passed to repin | Rejected without writing provenance, exit 2 |
| Simulated mismatch in recorded source or model hashes | Rejected without writing provenance, exit 2 |
| Fresh full offline measurement and strict gate | 17/17 spans fully masked; all category results exactly equal to the previous approved reference |

The reference was reissued from that fresh full run with UTC timestamps and its
run receipt. Numerical category results, support, residuals, metric, gold data,
corpus and snapshot were not changed. The prior reference and provenance remain
preserved outside the publication set. This is an explicit new measurement,
not a retrospective claim that an old scorecard was measured against new hashes.

The receipt is unsigned consistency evidence, not independent proof of execution,
human review, full pytest coverage or binary-identical environments. The tool
records the assessment note only as text. These limits are intentional
and are documented in the README and evaluation method.

## Limits of a green run

The sixteen synthetic gold texts are not an independently annotated,
representative sample. Complete masking on this set establishes neither general
recall/precision nor absence of personal data. The eleven known faults are
documented in [KNOWN_FAILURES.md](KNOWN_FAILURES.md). Model results may vary
across backends.

Package pins and model/tokenizer hashes are recorded. The harness-only
environment was installed fresh and tested. The Windows model reference used an
existing runtime environment. The separate Linux installation check below
recreated the runtime from the lock file. GitHub Actions remains a separate step.

## Clean Linux runtime installation

On 19 October 2026, a fresh virtual environment on Ubuntu 26.04.1 LTS x86_64
with CPython 3.14.4 installed all 53 pinned packages without version changes.
The source checkout was clean at `7ab801e`. Installation logs, pip's JSON
installation report, the installed-package list, JUnit results and the measured
scorecard were retained outside the publication set.

| Check | Result |
| --- | --- |
| Source builds for editdistpy and flashtext | Succeeded |
| Dependency consistency | `pip check`: no broken requirements |
| Full model-free suite with `--require-full-suite` | 600 passed, 11 strict expected failures |
| Model-free gold gate | 13/13 evaluated spans fully masked; no residuals |
| Recorded fixture, snapshot, lock and evaluation-code hashes | Match the publication set |

Linux also installed 19 indirect packages, mainly CUDA/NVIDIA libraries and
Triton. Their versions are retained in the installation report but are not
explicitly pinned in the current lock file. The check establishes successful
installation and model-free regression for this environment, not a fully locked
cross-platform environment or Linux model execution. No baseline was replaced.

## Repository integration check

The 41-file publication set was copied into `regressie-harness/`. Only this
report and the harness README were updated for integration and the Linux
installation findings; all executable files, tests, fixtures, snapshot, baseline
and provenance remain byte-identical to the audited set. The main README now
links to the harness in English and Dutch, and the changelog records its addition.

Checks after copying, with automatic discovery of the enclosing source checkout:

| Check | Result |
| --- | --- |
| Harness-only tests from the repository root in the clean test environment | 104 passed |
| Full suite from the repository root with `--require-full-suite` | 600 passed, 11 strict expected failures |
| PowerShell runner invoked from outside the repository, with the local Windows model | 600 passed, 11 strict expected failures; strict full gold gate passed, 17/17 spans fully masked |
| Comparison with the audited publication set | Exactly 41 files; only the two harness Markdown documents differ |

The source version remains 1.1.13. No reference was regenerated or repinned for
this integration, and no source-code or model change is included.
