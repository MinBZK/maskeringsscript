# Evaluation method

## Detecting visible fragments

The previous scorer checked only whether the complete gold value still occurred
literally in the output. It counted `NL12 RABO <Telefoon>` as successful masking
of `NL12 RABO 0123456789`. V2 reports `partially_masked` and excludes it from
`masked`. Even a single surviving letter or digit prevents full credit.

The scorer has no access to the masker's detection spans. It determines which
source characters could remain visible by aligning output literals and
placeholders with the source. Literal chunks must match exactly; a placeholder
may replace a source span. Forward and backward reachability identify all valid
alignments. A character is considered possibly visible if it survives in any
valid alignment. Repeated values cannot be assigned to the most favorable
occurrence to make the result appear safer.

A gold value without offsets must occur exactly once in the source. Otherwise,
explicit `start` and `end` offsets are required. The source slice must equal
`value`. Missing, empty or inconsistent spans cause an error.

| Status | Meaning | Counts as fully masked |
| --- | --- | --- |
| `fully_masked` | No source letter or digit can remain visible | Yes |
| `partially_masked` | Some source letters or digits can remain visible | No |
| `unmasked` | All source letters and digits can remain visible | No |
| `indeterminate` | No supported alignment, or computation limit exceeded | No |

The alignment supports the current angle-bracket forms `<Tag>`, `<(Tag)>` and
`<[Tag, C0.95]>`, using the label grammar in `coverage_eval.TAG_RE`. This is an
evaluation contract for the current output, not a general HTML parser. Tags
already present in the source are also evaluated as potentially literal text.

Other mask formats, rewritten text, changed whitespace or an alignment exceeding
two million DP cells may yield `indeterminate`. This can underestimate masking;
such cases never receive full-masking credit. Spaces and punctuation within gold
spans are not counted as identifying characters.

The analysis covers only annotated spans and their letters and digits. It does
not prove removal of unannotated personal data or measure precision. An
independently annotated span-gold set is still needed.

## Gate and snapshot

Source imports are checked against the selected checkout before and after import,
including cached project submodules and package search paths. A cached foreign
installation is an error, even when its output would match the reference.

The gate compares the same metric version and gold hash. Missing categories,
changed support and incompatible baselines are errors. Both scorecards must have
finite scores in [0, 1], positive integer support, valid masked counts and matching
residual counts. Scores must agree with masked/support. Missing measurements,
non-standard JSON numbers such as NaN, and invalid tolerances are rejected.
A model-free run compares
only deterministic categories; a full run requires a full baseline. Reduced
complete-masking coverage fails for regex/list categories. NER reductions fail
with `--strict-ner`; otherwise they are advisory warnings.

The exact regex snapshot contains 952 synthetic texts. Differences require
investigation. An unchanged snapshot does not establish correctness: it may
preserve existing mistakes. The model test is separate from this snapshot.

## Known failures

The eleven desired-behavior tests in `test_pr15_postcode_context.py` remain
strict `xfail`. An unexpected improvement produces `XPASS(strict)` and fails
the run until the expectation and documentation have been reviewed. Stable IDs
K01–K11 refer to [KNOWN_FAILURES.md](KNOWN_FAILURES.md) and `known_failures.json`.

Separate inventory tests verify that the documented current output is accurate.
A passing characterization test does not approve that behavior. Collection
rejects undocumented, duplicate or non-strict xfails. When fixing a case, update
its desired-behavior test, inventory and documentation together. Do not add an
xfail merely to make a new regression appear green.

## Full-run coverage

`--require-full-suite` requires the snapshot and the desired/inventory test IDs
listed in `known_failures.json`. Missing or deselected tests fail collection.
At session end, the snapshot and inventory checks must have passed and the known
desired-behavior cases must have produced their strict expected failures. A
skipped or otherwise unexecuted required check cannot give a green full run.
The PowerShell project runner enables this policy. Plain pytest supports
intentional subsets and does not claim full-run coverage.

## Measurement provenance

`measurement.py` hashes the source and evaluation inputs before and after a
scorecard run. It records the actual environment and offline model files and
rejects changes during evaluation. A canonical result hash binds the scorecard
contents, including its UTC generation time. Receipt start/end times must enclose
that generation time. `repin.py` first applies the gate's card validation, then
checks the receipt against current inputs and a clean Git source checkout.
New hashes are never substituted for hashes from the measured run.

This is unsigned, inspectable consistency evidence. It is not independent proof
of execution, protection against deliberately forged receipts, proof of human
assessment or an attestation of the pytest suite. Historical references without
receipts are retained for comparison; creating measured provenance requires a
new run. Source/model changes require remeasurement rather than a timestamp edit.
