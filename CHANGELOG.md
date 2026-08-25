# Changelog

Alle noemenswaardige wijzigingen aan dit project worden in dit bestand vastgelegd.

Het formaat is gebaseerd op [Keep a Changelog](https://keepachangelog.com/nl/1.1.0/)
en dit project volgt [Semantic Versioning](https://semver.org/lang/nl/).

De wijzigingen hieronder zijn de eerste "pre-publicatie hardening" van de
MaskeringSignalen-tool, t.o.v. de oorspronkelijke (interne) repo. Ze zijn in twee
golven doorgevoerd: **golf 1** op 2026-06-25 (BSN-lek, CLI-vlaggen, packaging,
repo-URL, hygiëne) en **consolidatie + scoring-guard** op 2026-06-26. De item-codes
(V01, V02, …) verwijzen naar de interne verbeteringen-prioriteitenmatrix.

## [1.1.8] — 2026-08-25

Golf 4, fase 2 (derde item, V32). Output-rakend (precisie); corpus-neutraal. Geverifieerd via de
regressie-harness tegen `main @ 983f32b` (suite groen, snapshot 0 delta, recall-gate OK, alle
categorieën 1,00, residu-PII 0), het volledige corpus (952 teksten) door regex + lijst + NER
(byte-identiek) en 18 gerichte zinnen per pass.

### Gewijzigd
- **Initialen-ná-naam-regel slokte hoofdletterafkortingen op** (V32, over-maskering). De
  initialen-postprocessing in `ListAnonymizer` en `NERAnonymizer` maskeerde na een naam-tag elke
  reeks van twee of meer hoofdletters mee, waardoor een afkorting direct naast een naam verdween:
  `Jansen (WW)` → `<Naam>)`, `Bakker UWV-consulent` → `<Naam>-consulent`, `Visser BV` → `<Naam>`.
  Het ná-de-naam-alternatief eist nu echte initialen — minimaal twee letters, alle behalve de
  laatste met punt — zodat `A.B.`, `K.L.` en `A.B` nog steeds worden mee gemaskeerd, maar `WW`,
  `UWV`, `AOW`, `BV` en `WMO` blijven staan. Beide passes tegelijk aangepast (consistentie); het
  vóór-de-naam-alternatief is ongewijzigd. Bekend: hoofdletters zonder punt na een naam (`Bakker
  AB`) laat de lijst-pass nu staan; in de volledige pijplijn vangt NER die alsnog.
  (`src/anonymizer/anonymizer.py`)

## [1.1.7] — 2026-08-25

Golf 4, fase 2 (tweede item, V28). Output-rakend in theorie; in de praktijk corpus-neutraal.
Geverifieerd via de regressie-harness tegen `main @ 5d1faa5` (suite groen, snapshot 0 delta,
recall-gate OK, alle categorieën 1,00, residu-PII 0) en aanvullend met het volledige corpus
(952 teksten) door regex + lijst + NER: byte-identiek.

### Opgelost
- **NER-initialenregel matchte nooit op echte tags** (V28). De initialen-postprocessing in
  `NERAnonymizer.anonymize` bouwde haar patroon op de vertaalde labelnaam (`"Naam"`) in plaats
  van op het tagformaat (`"<Naam>"`). Daardoor bleven initialen naast een door NER gedetecteerde
  naam staan (`Zwartendijk (K.L.)` → `<Naam> (K.L.)`), en kon formuliertekst als `Naam J.K. …`
  stil initialen verliezen zonder tag. `ListAnonymizer` deed dezelfde regel al goed. De regel
  gebruikt nu `name_tag_pattern` (het echte tagformaat, inclusief het optionele
  confidence-achtervoegsel in distinct-tags-modus) en vervangt door `_get_tag_format("Name")`.
  Bekend en bewust geaccepteerd: een hoofdletterafkorting direct naast een naam (`UWV`, `WMO`)
  wordt nu ook bij NER-namen als initialen mee gemaskeerd — hetzelfde gedrag dat de lijst-pass
  al had; aanscherpen in beide passes is een apart item (V32). (`src/anonymizer/anonymizer.py`)

## [1.1.6] — 2026-08-25

Externe bijdrage (PR #7, snamrick). Output-rakend; geverifieerd via de regressie-harness
tegen `main @ b1571e1` (snapshot 0 delta — het synthetische corpus bevat geen buitenlandse
nummers; recall-gate OK, alle categorieën 1,00, residu-PII 0) en aanvullend in de volledige
pijplijn op acht buitenlandse nummers.

### Opgelost
- **Buitenlandse telefoonnummers werden half gemaskeerd onder een verkeerde tag** (recall-lek).
  Het `Phone`-patroon eiste `+31` of een leidende `0`. Een nummer met een andere landcode werd
  daardoor niet als telefoonnummer herkend; een breder patroon verderop in de volgorde
  (`ID_Number`, `KVK`) maskeerde alleen de losse cijferreeks en liet landcode plus netnummer
  staan (`+49 30 12345678` → `+49 30 <KVK>`), of het nummer bleef volledig staan
  (`+55 11 912345678`). Het patroon accepteert nu een generieke landcode van 1 tot en met 3
  cijfers conform E.164; de cijferstructuur na de landcode en de insertievolgorde van
  `TAGGED_PATTERNS` zijn ongewijzigd. Bewust geaccepteerd precisie-randje: een `+`-getal direct
  gevolgd door 7–12 losse cijfers wordt nu als telefoonnummer gemaskeerd (was al deels
  gemaskeerd als `ID_Number`). Bekend en buiten deze uitgave: de `(0)`- en `00`-notaties
  (`+44 (0)20 …`, `0044 …`). (`src/anonymizer/anonymizer.py`)

### Documentatie
- README (EN + NL): buitenlands telefoonnummer toegevoegd aan de `Phone`-voorbeelden.

## [1.1.5] — 2026-07-21

Golf 4, fase 2 (eerste item): sluit een recall-lek in de ondertekening van brieven.
Output-rakend; geverifieerd via de regressie-harness (geen harde recall-daling per
categorie, residu-PII 0; de regex-snapshot beweegt alleen op ondertekening-records).

### Opgelost
- **Ondertekeningsnaam na afsluitgroet werd niet gemaskeerd** (recall-lek). Een
  afzendernaam (initiaal(en) + achternaam) op een eigen regel direct na een afsluitgroet
  ("Met vriendelijke groet", "Hoogachtend", "Groet", "Met dank", …) ontsnapte aan de hele
  pijplijn (regex + lijst + NER), omdat NER de naam in signatuur-positie mist.
  `RegexAnonymizer` kreeg hiervoor een deterministische sign-off-regel (`_SIGN_OFF_RE` /
  `_mask_signature_names`): de groet wordt hoofdletter-ongevoelig herkend, de naam wordt
  geankerd op echte initialen ("X.") en tot het regeleinde gemaskeerd, zodat meerdelige
  achternamen ("el Amrani", "de Vries") geen restant achterlaten.
  (`src/anonymizer/anonymizer.py`)

## [1.1.4] — 2026-07-20

Gemengde uitgave: de vierde golf fase 1 (code) en de uniformering van de documentatie. Geen van
beide wijzigt het gedrag van het script.

Vierde golf, fase 1: structurele opschoning zonder gedragswijziging op het standaardpad
(`CombinedAnonymizer`, taal `nl`, default mask). Byte-identiek geverifieerd via de
regressie-harness (regex-snapshot 0 delta; volledige recall-gate OK, alle categorieën 1,00,
residu-PII 0). (`src/anonymizer/anonymizer.py`)

### Gewijzigd
- **NER-whitelist als instance-state i.p.v. module-globaal** (V13). De muteerbare module-globale
  `WEAK_NER_WHITELIST` is verwijderd. `RegexAnonymizer`/`ListAnonymizer` exposen hun output-tags
  nu als instance-state (`weak_ner_tags`); `NERAnonymizer` accepteert ze expliciet via de nieuwe
  parameter `extra_weak_whitelist`, en `CombinedAnonymizer` bedraadt regex+lijst → NER. Dit
  voorkomt state-bleed tussen instanties (en onbegrensde groei van de lijst) in langlopende
  processen. **Gedragswijziging voor direct API-gebruik:** een standalone `NERAnonymizer()` die
  niet via `CombinedAnonymizer` loopt, erft niet langer impliciet de tags van eerder
  geconstrueerde Regex/List-anonymizers; geef die desgewenst expliciet mee via
  `extra_weak_whitelist`. Het `CombinedAnonymizer`-pad is output-equivalent (0 snapshot-delta).
- **Postcode-postprocessing robuuster** (V15). De hardcoded `'<Postcode>'`-tag in de
  regex-postprocessing wordt nu via `TRANSLATIONS`/`mask` opgebouwd, net als de overige tags.
  No-op voor `nl` en `en` (beide vertalen `Postcode → "Postcode"`) en voor de default mask; tevens
  een latente fix voor afwijkende mask-/taalconfiguraties, waar de oude hardcoded tag niet op de
  werkelijk geproduceerde tag matchte.
- **Order-contract `TAGGED_PATTERNS` vastgelegd** (V18). De betekenisvolle insertievolgorde
  (specifiek → breed) is expliciet gedocumenteerd in de `TAGGED_PATTERNS`-header en de
  `_build_patterns`-docstring; de characterization-snapshot in de regressie-harness blijft de
  wachter. Geen codewijziging.
- **Whitelist-lus: context-slice uit de per-item-lus gehesen** (V19, deel). De
  context-slice + lowercasing wordt nu één keer per woordpositie berekend i.p.v. per
  whitelist-item (constante-factor-winst, output-equivalent). De Aho-Corasick-herschrijving is
  bewust uitgesteld (output-equivalentierisico).

### Documentatie

Los van de vierde golf: uniformering van de documentatie, in afstemming met BZK. Vastgelegde
besluiten: de README blijft tweetalig in één bestand en wordt gelijkgetrokken (NL naar het
detailniveau van EN), de CHANGELOG blijft volledig Nederlands, en de licentie blijft gesplitst
in `LICENSE.md` (EN, canoniek) en `LICENSE_NL.md`. Deze stap maakt eerst de Engelse helft
feitelijk kloppend; het gelijktrekken van de Nederlandse helft volgt. Raakt geen code.

- **Onbewezen vergelijkende claims verwijderd** (V24, deel). Twee passages stelden dat het script
  beter presteert dan "the former script" respectievelijk "the previously used commercial
  solution". Die vergelijkingen zijn niet reproduceerbaar onderbouwd en zijn vervangen door een
  verwijzing naar de beschreven evaluatieprocedure. De prestatiecijfers zelf (recall 93%,
  precisie 92%, F3 93%) blijven staan: die zijn expliciet toegeschreven aan de meting bij
  Gemeente Rotterdam en dragen al een voorbehoud over generaliseerbaarheid.
- **Verouderde whitelist-instructie gecorrigeerd.** De NER-configuratiesectie verwees naar het
  bewerken van `WEAK_NER_WHITELIST` en `STRONG_NER_WHITELIST`. Sinds V13 zijn dat instance-
  attributen die bij constructie uit Excel worden opgebouwd; de instructie verwijst nu naar
  `Whitelist Basic.xlsx` en de Whitelists-sectie.
- **NER-Organization gedocumenteerd.** De detectie van organisatienamen was wel geïmplementeerd
  (label-mapping, drempel 0,84) maar ontbrak in de opsomming van entiteitstypen en in de
  label-naar-tag-mapping. Beide zijn aangevuld.

- **Nederlandse helft van de README gelijkgetrokken.** De Nederlandse helft was in de praktijk een
  beknopte samenvatting van de Engelse: 309 tegen 546 regels (57%). De sectiestructuur was al 1:1,
  maar hele instructieblokken ontbraken — onder meer het bewerken van de whitelist-sheets, de
  regexvoorbeelden, de hoofdlettergevoeligheid bij lijsten, de NER-drempels en labels, de zes
  generaliseerstappen, en de formules en confusion-matrixtermen bij de evaluatie. Alle secties
  staan nu op hetzelfde detailniveau (560 tegen 569 regels, 98%). Doorgevoerd in vier delen langs
  sectiegrenzen.

### Toegevoegd

- **Licentiesectie in de README** (beide helften, met ToC-vermelding). De README verwees nergens
  naar de licentie. De sectie benoemt EUPL-1.2 en verwijst naar beide taalversies; de
  bestandsopzet blijft ongewijzigd.
- **Codecommentaar consistent Engelstalig** (`anonymizer.py`, `scoring.py`). Het oorspronkelijke
  script is volledig Engelstalig becommentarieerd; het Nederlandstalige commentaar dat in latere
  wijzigingsrondes is toegevoegd, is teruggebracht naar het Engels. Het betreft dertien blokken en
  één docstring. Geverifieerd dat uitsluitend commentaar- en docstringregels zijn gewijzigd en
  geen enkele coderegel. Bijvangst: hiermee verdwijnen de laatste niet-ASCII-tekens uit de
  broncommentaren.

---

## [1.1.3] — 2026-06-29

Derde golf: precisie van de Credit_Card-detectie verhoogd. Raakt de maskeer-output, dus
geverifieerd via de regressie-harness (snapshot vóór/ná + recall-gate; geen regressie).

### Gewijzigd
- **Credit_Card met Luhn-validatie** (C1, V11). De Credit_Card-regex maskeerde elke reeks van
  13–19 cijfers, waardoor bestel-/barcodenummers werden over-gemaskeerd. Een nieuwe
  `is_valid_luhn`-guard maskeert nu alleen reeksen die de Luhn-checksum halen (zoals de
  BSN-elfproef-guard); echte kaartnummers blijven gemaskeerd, willekeurige nummers niet meer.
  Nieuwe parameter `validate_credit_card=True` op `RegexAnonymizer`. Recall onveranderd
  (geen Credit_Card-recall-target geraakt); de snapshot-delta betreft uitsluitend de twee
  bedoelde over-maskeringsgevallen. (`src/anonymizer/anonymizer.py`)

### Verwijderd
- **Verdwaald leeg bestand `77`** uit de repo-root (per ongeluk meegekomen in 1.1.2; repo-hygiëne).

---

## [1.1.2] — 2026-06-29

Tweede golf "legal/docs hardening": juridische en documentaire correcties zonder impact op
de maskeer-output (geen regressie-meting nodig; bestaande baselines blijven geldig).

### Gewijzigd
- **Auteursrecht/herkomst rechtgezet** (A1). De gemeente Rotterdam is als enige rechthebbende
  vermeld in de herkomst- en copyrightteksten. (`README.md`,
  `src/anonymizer/anonymizer.py`, `src/anonymizer/helpers/sample_testset/sample_testset.py`)
- **Licentie conform gemaakt** (A3, V06-rest). De Engelse canonieke EUPL-1.2-tekst is
  toegevoegd als `LICENSE.md` (zodat de licentie automatisch herkend wordt); de Nederlandse
  vertaling is hernoemd van `LICENCE_EUPL_1_2_NL.md` naar `LICENSE_NL.md`. `pyproject.toml`
  gebruikt nu de SPDX-expressie `license = "EUPL-1.2"` met `license-files`, en vereist
  `setuptools>=77` (PEP 639).
- **Versie gelijkgetrokken** (A4, V22). `__version__` (`anonymizer.py`), `pyproject.toml` en
  deze CHANGELOG noemen nu alle drie `1.1.2` (voorheen liep `__version__` op 1.1.0 achter).
- **Robuustere modellading** (B1, V12). De bare `except:` bij het lokaal laden van het
  GLiNER-model is vervangen door `except Exception as e:` met een duidelijker melding;
  systeemsignalen (zoals onderbrekingen) worden niet langer stil opgeslokt. Geen
  gedragswijziging in de fallback. (`src/anonymizer/anonymizer.py`)

### Toegevoegd
- **Privacy/AVG-disclaimer** in de README (EN + NL) (A2): het resultaat van de anonimisatie is
  niet gegarandeerd volledig en hangt mede af van de aangeboden informatie; of aanvullende
  controle nodig is hangt af van de eisen die de toepassing stelt, en die afweging ligt bij de
  gebruikende organisatie.

### Verwijderd
- **Stale doctest** onderaan `anonymizer.py` (A5, V20) die verwees naar niet-bestaande tags
  (`<CLAIM_ID>`, `<Time>`, …) — verwijderd om verwarring te voorkomen.

---

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
- V06-rest — LICENSE-bestand (inmiddels toegevoegd in 1.1.2; EUPL v1.2 NL staat al in de
  canonieke repo).
- V07 — herkomst `Sample_Rotterdam.xlsx` (synthetisch vs. echt niet vast te stellen).
- V11 — Credit_Card over-maskeert een 13–19-cijferig bestel-/barcodenummer
  (precisie; gedocumenteerde `xfail` in de regressie-harness).
- Ondertekeningsnaam (initiaal + achternaam) na afsluitgroet blijft ongemaskeerd
  (recall-gat; gedocumenteerde `xfail`).

> De wijzigingen zijn geverifieerd tegen de regressie-harness (staging, buiten deze
> repo): unit + B4-red→green-tests groen, regex-snapshot zonder onverklaarde delta,
> en de recall-gate zonder harde regressie (BSN 1,00 / residu-PII 0).
