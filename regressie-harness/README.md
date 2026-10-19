# Regression harness

This harness tests the source checkout in this repository. GitHub Actions
integration remains a separate step. All test data is synthetic. A green run means
that the selected checks pass. Eleven known failures remain documented in
[KNOWN_FAILURES.md](KNOWN_FAILURES.md). This does not guarantee that a text is
free of personal data.

## Language

Documentation, comments, docstrings, diagnostics and explanatory metadata use
English. Dutch inputs, expected outputs, translated masking labels and stable
case IDs are intentional test content. Preserve them when editing documentation.

## Three test levels

1. **Harness only:** `python -m pytest --unit-only`. Requires only
   `requirements-test.txt`; checks fragment detection, the gate and configuration.
2. **Full project regression without a model:** `python -m pytest --require-full-suite`. Exercises the
   project, all 952 regex snapshot texts and known failures. No model is loaded.
   Project imports still require runtime libraries, including GLiNER and Torch.
3. **Full model test:** `python -m pytest --run-integration tests/integration`.
   Requires a local model and a prepared Hugging Face cache. The full gold gate
   is strict, including names and addresses. Downloads are disabled.

Missing configuration, dependencies, gold data or a snapshot cause errors rather
than a successful all-skipped run.

## Install and run

Run the commands below from the harness directory. Alternatively,
`python -m pytest regressie-harness --require-full-suite` also works from the repository root.

Tested model reference: CPython 3.14.4 on Windows x64. A fresh installation on
Ubuntu 26.04.1 x86_64 with CPython 3.14.4 also passed the full model-free suite
and gold gate. Model execution on Linux has not been tested. Package pins are in
`requirements-runtime.lock`; Linux adds indirect dependencies, including CUDA
and Triton packages, whose versions are not pinned there. This is not yet a
complete cross-platform lock. Model files are separate from package installation.

For harness-only tests, use a fresh virtual environment:

```powershell
python -m pip install -r requirements-test.txt
python -m pytest --unit-only
```

For project tests, use a separate environment:

```powershell
python -m pip install -r requirements-runtime.lock
$env:ANONYMIZER_REPO = '<source repository checkout>'
python -m pytest --require-full-suite
python scorecard.py --gate baseline-v2.json
```

The same Python commands work in Bash. Create the environment on the target
machine; do not copy an existing virtual environment. Activate it on Linux with
`source <venv>/bin/activate`. Keep installation reports and test output outside
the checkout. For example, after activating a fresh environment:

```bash
python -m pip install --no-cache-dir -r requirements-runtime.lock
python -m pip check
python -m pytest --require-full-suite
python scorecard.py --gate baseline-v2.json
```

The checkout must contain `src/anonymizer/anonymizer.py`; the harness imports
that source directly. Once inside the source repository, the harness can discover
the enclosing repository automatically. An explicit `ANONYMIZER_REPO` takes
precedence. There is no fallback to a neighboring local checkout.
Both tests and scorecards reject already loaded project modules or package search
paths outside the selected checkout. Use a fresh process after such a failure;
the harness does not silently unload and replace cached modules.

For model tests:

```powershell
$env:GLINER_MODEL_PATH = '<local GLiNER model directory>'
$env:HF_HUB_CACHE = '<prepared Hugging Face hub cache>'
python -m pytest --run-integration tests/integration
```

The reference model is `gliner-multi-pii-domains-v1`, with the
`microsoft/mdeberta-v3-base` backbone. The model directory contains its weights,
GLiNER configuration and tokenizer files. The backbone configuration must be
available in the cache. Hashes are in `baseline-v2-provenance.json`.
Prepare these files separately according to the model documentation and license.
Model runs are forced offline and fail if required files are unavailable.
Results may vary across hardware and backends.

The PowerShell runner works from any working directory and propagates failures:

```powershell
.\run_tests.ps1 -UnitOnly
.\run_tests.ps1 -Repo '<checkout>'
.\run_tests.ps1 -Repo '<checkout>' -WithModel -Model '<model directory>' -HfCache '<hub cache>'
```

Use `-Python` to select an interpreter. Only `-WithModel` enables the model;
a model environment variable alone does not enable it. The runner first runs
the ordinary suite and then the gold gate, adding `--full --strict-ner` when
`-WithModel` is selected.

The runner always adds `--require-full-suite` for project regression. This checks
that the snapshot, all documented desired-behavior cases and their inventory
checks are collected and executed with the expected outcomes. Ignoring,
deselecting or skipping required checks fails the full run. Intentional subsets
remain available with plain pytest and a test path or `-k`; they are not a full
regression check. `--unit-only` is also a deliberately separate level.

## Interpretation and limits

`source-coverage-v2` counts a gold span as fully masked only when none of its
letters or digits can remain visible. Partially visible account numbers are
residuals. Spaces and punctuation are not identifying characters for this metric.
Uncertain alignment is `indeterminate` and never receives full credit. See
[EVALUATION.md](EVALUATION.md) for details.

The sixteen gold texts contain seventeen annotated entities, including four NER
spans. This is a small synthetic control set, not an independently annotated,
representative gold set. The legacy JSON field `recall` denotes the fraction of
fully masked gold spans, not general recall or precision. Four PII-free negative
texts provide only an overmasking warning signal. The snapshot preserves behavior
and may contain existing mistakes.

`scorecard.py --full` includes the model. With direct `--gate` use, NER reductions
are advisory by default; add `--strict-ner` for a hard gate. The model-enabled
runner and integration test use that strict setting. Without `--full`, the four
NER spans are excluded from the score.

## Baselines and deliberate updates

`baseline-v2.json` is the separate reference for the new metric. The frozen regex
snapshot and gold texts are unchanged. The original v1 baseline, provenance,
environment lock, reports and backups are archived outside this directory and
excluded from publication. The old GitLab snippet, which automatically updated
baselines, is also archived.

A normal run never writes a baseline. The v2 gate rejects a v1 baseline or a
changed gold set. It also rejects missing, non-finite or inconsistent measurements
in either scorecard; an invalid baseline cannot silently disable the comparison.
Measure into a separate candidate file first:

```powershell
python scorecard.py --full --strict-ner --gate baseline-v2.json --save candidate.json
```

Review output differences, residuals, model changes and source changes before
replacing the reference. `--gate` and `--save` must not use the same path.
Every scorecard run records input hashes before and after evaluation and refuses
to save a measured result if they change. Its unsigned receipt binds the result
and timestamps to source, gold, evaluation code, Python/platform, installed
package versions and, for full runs, model/tokenizer/backbone files. Model lookup
uses the actual offline cache; no manually supplied config substitutes for it.

`repin.py` validates the card and receipt and requires the current inputs to match
the recorded hashes. It uses recorded hashes rather than attributing current
files to an old result. A clean Git source checkout is required. It does not
change a baseline:

```powershell
python repin.py --card candidate.json --output candidate-provenance.json --note '<reason and maintainer assessment>'
```

`--backbone-config` is an optional additional hash check, not an input override.
Legacy cards without a receipt remain usable as gate references, but cannot be
repinned as newly measured; run a fresh measurement instead. Edited results,
changed timestamps, or source/model/environment drift invalidate the receipt.

The receipt is an auditable consistency record, not a signature or independent
proof that execution or human review occurred. It does not attest pytest coverage,
binary-equivalent environments or general model quality. A maintainer's note is
an assertion by that maintainer, not something the tool verifies. There is no
arbitrary age cutoff for otherwise consistent historical measurements.

Replacing existing provenance also requires `--replace`. After reviewing a
candidate, explicitly promote it and its provenance together. Use `SNAPSHOT_UPDATE=1`
only for an intentional, separately reviewed snapshot update. The runner rejects
this variable during regression checks. See [BASELINE_REPORT.md](BASELINE_REPORT.md)
for the current reference and recorded validation.

## Publication contents

Publish the code, tests, synthetic fixtures, active snapshot, approved v2 baseline
and provenance, pinned dependencies, configuration and these four Markdown
documents. Exclude backups, caches, virtual environments, local review reports,
candidate measurements and model weights. The main repository README links to
this harness; no GitHub Actions workflow is included here.
