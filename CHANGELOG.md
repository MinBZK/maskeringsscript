# Changelog

Alle noemenswaardige wijzigingen aan dit project worden in dit bestand vastgelegd.

Het formaat is gebaseerd op [Keep a Changelog](https://keepachangelog.com/nl/1.1.0/)
en dit project volgt [Semantic Versioning](https://semver.org/lang/nl/).

De wijzigingen hieronder zijn de eerste "pre-publicatie hardening" van de
MaskeringSignalen-tool, t.o.v. de oorspronkelijke (interne) repo. Ze zijn in twee
golven doorgevoerd: **golf 1** op 2026-06-25 (BSN-lek, CLI-vlaggen, packaging,
repo-URL, hygiëne) en **consolidatie + scoring-guard** op 2026-06-26. De item-codes
(V01, V02, …) verwijzen naar de interne verbeteringen-prioriteitenmatrix.

## [1.1.1] — 2026-06-26

### Beveiliging / Privacy
- **BSN-recall-lek gedicht** (V01, 2026-06-25). Een 9-cijferig BSN dat de elfproef
  niet haalt (fout ingevoerd maar reëel) bleef ongemaskeerd. `_anonymize_bsn` werkt
  nu twee-pass met een nieuwe `_BSN_CONTEXT_RE`: een BSN-vormig getal direct na
  `bsn`/`burgerservicenummer` wordt altijd gemaskeerd (óók bij gefaalde elfproef),
  terwijl willekeurige 9-cijferreeksen buiten die context níet over-gemaskeerd
  worden. BSN-recall 0,67 → 1,00, residu-PII 0; precisie behouden.
  (`src/anonymizer/anonymizer.py`)

### Toegevoegd
- **`requires-python = ">=3.10"`** in `pyproject.toml` (V05, 2026-06-25). De code
  gebruikt 3.10+-syntax (`bool | None`); zonder deze ondergrens brak een install op
  oudere Python onverwacht.
- **Expliciete Python-versie-eis in de README** (2026-06-26): "Requires Python 3.10
  or higher" / "Vereist Python 3.10 of hoger" bij de installatie-instructies (EN + NL).
- **`.DS_Store` in `.gitignore`** (V21, 2026-06-25) — voorkomt dat macOS-metadata
  meegecommit wordt.

### Gewijzigd
- **CLI-vlaggen werken nu daadwerkelijk** (V02, 2026-06-25). `--blacklist-path` en
  `--whitelist-path` werden aan lokale variabelen toegekend i.p.v. de module-globals,
  en `--masked-text-column` werd genegeerd. `main()` zet nu `global LIST_PATH,
  WHITELIST_PATH` vóór constructie en bepaalt de uitvoerkolomnaam uit
  `args.masked_text_column`. Geen wijziging in maskeer-gedrag.
  (`src/anonymizer/anonymizer.py`)
- **README-installatie-URL ingevuld** (V06-deel, 2026-06-25). Beide voorkomens van
  de `[repo_url]`-placeholder vervangen door
  `https://github.com/MinBZK/maskeringsscript`. (`README.md`)
- **Default-lijsten als package-data meegebundeld** (V04, 2026-06-26). De default
  blacklist/whitelist stonden in repo-root `input_files/` met relatieve paden, en
  werden na `pip install` niet gevonden bij uitvoeren vanuit een andere map. Ze zijn
  verplaatst naar `src/anonymizer/input_files/`, opgenomen in
  `[tool.setuptools.package-data]`, en `LIST_PATH`/`WHITELIST_PATH` worden nu
  package-relatief opgelost via `importlib.resources`. Hierdoor werkt de tool
  out-of-the-box na installatie. Lijst-inhoud ongewijzigd (geen maskeer-impact).
  (`src/anonymizer/anonymizer.py`, `src/anonymizer/helpers/sample_testset/sample_testset.py`,
  `pyproject.toml`)

### Hersteld
- **Deling-door-nul in `scoring.py`** (V08, 2026-06-26). Bij nul maskeringen
  (`tp+fp == 0`) gaf `score()` stil `nan` (numpy 0/0) i.p.v. een gedefinieerde
  uitkomst. `precision`, `recall` en `f_beta` zijn nu voorzien van een
  noemer-guard die `0.0` teruggeeft (conventie sklearn `zero_division=0`), zodat de
  uitkomst altijd eindig is. (`src/anonymizer/helpers/scoring/scoring.py`)

### Verwijderd
- **`requirements.txt`** (V03, 2026-06-25). Het bestand was UTF-16/BOM met de
  volledige dev-omgeving, faalde op Linux/macOS bij `pip install -r` en vormde een
  tweede, divergerende dependency-bron. `pyproject.toml` is nu de enige bron van
  dependencies.

---

### Niet in deze golven (bewust open)
- V06-rest — LICENSE-bestand + Kyden-copyright (EUPL v1.2 NL staat al in de
  canonieke repo).
- V07 — herkomst `Sample_Rotterdam.xlsx` (synthetisch vs. echt niet vast te stellen).
- V11 — Credit_Card over-maskeert een 13–19-cijferig bestel-/barcodenummer
  (precisie; gedocumenteerde `xfail` in de regressie-harness).
- Ondertekeningsnaam (initiaal + achternaam) na afsluitgroet blijft ongemaskeerd
  (recall-gat; gedocumenteerde `xfail`).

> De wijzigingen zijn geverifieerd tegen de regressie-harness (staging, buiten deze
> repo): unit + B4-red→green-tests groen, regex-snapshot zonder onverklaarde delta,
> en de recall-gate zonder harde regressie (BSN 1,00 / residu-PII 0).
