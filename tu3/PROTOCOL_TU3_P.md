# PROTOCOL TU3-P — modulul P: parser multi-joc (6/49, 5/40, Joker)

Sesiunea 2026-10-26 (start ~16:12Z), continuare din checkpoint-ul 20261026T160731Z, la cererea utilizatorului.
Scris și sigilat ÎNAINTE de orice cod al modulului (`tu3/parser_multi.py` și testele lui nu există la sigilare).
Subordonat `PROTOCOL_TU3_P1.md` (§0 abateri, §1 ordinea modulelor); nu modifică nimic din modulul J.

## 0. Încadrare onestă

- Modulul P este INGESTIE/INVENTAR: citire, verificarea integrității, validare cu motive explicite, deduplicare,
  ordonare, grupare pe zile, tensori. Nu este experiment de selecție, nu calculează operatori, nu produce variante,
  scoruri sau prognoze. Calcul clasic (PyTorch, CUDA pe RTX 5060 Laptop; fallback CPU jurnalizat).
  `positive_claims_allowed=false`.
- `engine.py` (sha `1da9be4e…`) și `parser.py` (sha `219e5d20…`) rămân NEMODIFICATE; P nu apelează `parser.main`
  (care ar rescrie `rezultate/parser_manifest.json`), ci numai `parser.build_dataset` / `parser.resolve_device`.
- P nu atinge: baza/snapshot-urile colectorului, protocolul prospectiv înghețat și gardul lui (decizia utilizatorului),
  OGLINDA (nu citește prognoza, nu compară nicio extragere cu vreo prognoză, nu face settle), DL, modelele închise.
  Arhiva este deja explorată; nu există set „nevăzut”.

## 1. Surse

- **Produs = arhiva LIVE.** Lanț de integritate, citit O SINGURĂ DATĂ per apel (pointerul se mută atomic, versiunile
  sunt imutabile): `tu3/date/live/CURRENT_LIVE.json` → `version_dir` (trebuie să fie strict sub `tu3/date/live/versiuni/`)
  → `MANIFEST_LIVE.json` cu sha256 = `manifest_sha256` din pointer → fișierul `extrageri_<joc>.jsonl` cu sha256 egal
  ATÂT cu manifestul, CÂT și cu pointerul; numărul de rânduri JSON citite = `records` din manifest; `draw_size` din
  manifest = regula jocului. Orice abatere ⇒ `IntegrityError` (refuz, niciun dataset parțial).
- **Referință pentru protocoalele sigilate = exporturile înghețate.** 5/40 și Joker: `tu3/date/extrageri_540.jsonl`
  (`e1591b87…`), `tu3/date/extrageri_joker.jsonl` (`45713aa2…`), verificate față de `tu3/date/MANIFEST_DATE.json`.
  6/49: fișierul de cercetare sigilat `predictie_numere/probe_date/extrageri_649.jsonl` (`193eaf7a…707c`, sursa
  implicită `parser.DEFAULT_SOURCE`), citit numai prin `parser.build_dataset`; hash diferit ⇒ `IntegrityError`.
- Se poate da și o cale explicită (teste, fixturi); atunci nu există lanț de manifest, hash-ul se raportează.

## 2. Jocuri (fixate)

| cod | nume | n (urna) | r (numere/extragere) | bilet | Joker m |
|---|---|---|---|---|---|
| `649` | Loto 6/49 | 49 | 6 | 6 | — |
| `540` | Loto 5/40 | 40 | 6 | 5 | — |
| `joker` | Joker | 45 | 5 | 5 + 1 | 20 |

5/40: extragerea are 6 numere (TU3-P1 §0), biletul/varianta 5; P validează extragerea, nu biletul.

## 3. Validare 5/40 și Joker (schema LIVE = schema exporturilor înghețate)

Câmpuri: `draw_key`, `draw_date`, `game`, `numbers`, `numbers_order_as_stored`, `joker`, `draw_kind`,
`has_source_disagreement`, `verification`, `source_count`, `provenance`. Primul motiv care se aplică, în ordinea:
`draw_key_missing`, `game_mismatch`, `draw_date_missing`, `draw_date_invalid`, `numbers_count_invalid` (≠ r),
`numbers_not_int` (bool nu e int), `numbers_out_of_range` (în afara 1..n), `numbers_duplicate_in_row`, apoi pentru
Joker `joker_missing`, `joker_not_int`, `joker_out_of_range` (în afara 1..20), iar pentru jocurile fără Joker
`joker_unexpected` (joker ≠ null). Deduplicare după validare, în ordinea fișierului: `duplicate_draw_key`, apoi
`duplicate_date_set` (aceeași dată + aceleași numere sortate + același Joker). Semnalări (rândul se păstrează):
`stored_vs_sorted_mismatch` (ordinea afișată sortată ≠ numerele), `source_disagreement_kept`,
`key_prefix_mismatch` (prefixul cheii ≠ `<joc>:`). Ordonare stabilă după `(draw_date, draw_key)`; ordinea din aceeași
zi NU se folosește; o zi calendaristică = un pas (CSR `step_offsets`, exact ca `parser.py`).

## 4. 6/49 — delegare la `parser.build_dataset` (nemodificat)

Schema LIVE diferă de schema `parser.py`. Adaptor pur, fără filtrare: `numbers_sorted ← numbers`,
`numbers_as_stored ← numbers_order_as_stored`, `draw_kind_as_stored ← draw_kind`,
`has_source_disagreement_as_stored ← has_source_disagreement`, plus `draw_key`, `draw_date`, `game`, `provenance`;
rândurile JSON invalide se copiază ca atare (parserul le raportează). Fișierul adaptat se scrie adresat prin conținut,
`tu3/date/derivat/649_<sha12 sursă>.jsonl` (0444; dacă există, se verifică byte-identic, altfel refuz), apoi
`parser.build_dataset(cale)`. Validarea, motivele, deduplicarea, gruparea și tensorii 6/49 sunt deci EXACT cei din
`parser.py`.

## 5. Ieșire: `GameDataset`

`game` (specificația §2), `draws` [T, r] int64 sortate, `onehot` [T, n] float32, `joker` [T] int64 (1..20) sau
None, `joker_onehot` [T, 20] float32 sau None, `step_index`, `step_offsets`, `pair_counts` = onehotᵀ·onehot [n, n]
float32, `cross_counts` = onehotᵀ·joker_onehot [45, 20] float32 (numai Joker), `dates`, `keys`, `kinds`,
`step_dates`, `device`, `source`, `source_sha256`, `source_kind` (`live`/`frozen`/`path`), `provenance` (pointer +
manifest), `n_raw`, `anomalies`, `json_errors`; la 6/49 și `base` (obiectul `parser.Dataset`, aceiași tensori).
`summary()` (descriptiv, ca la `parser.py`) și `to(device)`.

## 6. Martori (teste; trebuie să treacă exact)

- **P1** validare sintetică: câte un rând pentru fiecare motiv din §3 ⇒ `removed_by_reason` exact (5/40 și Joker).
- **P2** deduplicare/ordonare/grupare pe intrare amestecată cu zile duble ⇒ chei, `step_dates`, `step_offsets` exacte.
- **P3** tensori: sumele pe rând ale `onehot` = r, ale `joker_onehot` = 1; diag(`pair_counts`) = frecvențe;
  Σ`cross_counts` = 5T și `cross_counts` = `joker_entanglement.joint_counts` (egal exact); GPU = CPU bit cu bit.
- **P4** 6/49: pe o fixtură sintetică în schema LIVE (inclusiv rânduri invalide/duplicate), tensorii, cheile, pașii și
  motivele = `parser.build_dataset` pe echivalentul în schema `parser.py`; adaptorul este idempotent (aceeași cale,
  același hash); conținut diferit la aceeași cale ⇒ refuz.
- **P5** integritate pe o copie temporară a structurii LIVE: octet modificat în JSONL, manifest modificat, pointer cu
  hash greșit, număr de rânduri diferit, `version_dir` în afara `versiuni/` ⇒ `IntegrityError` fiecare; copia
  nealterată se încarcă.
- **P6** LIVE real: pentru toate 3 jocurile, `n_draws` = `records` din pointer, 0 excluderi, 0 erori JSON,
  `last_date` = pointerul; 5/40 are r = 6 și bilet 5; Joker trece `joker_entanglement.validate_draws`.
- **P7** înghețat real: 5/40 și Joker = `MANIFEST_DATE` (număr, hash, 0 excluderi); orice cheie înghețată există în
  LIVE cu aceeași dată/numere/Joker (LIVE ⊇ înghețat). 6/49: fișierul de cercetare are hash-ul `193eaf7a…707c`;
  diferențele de chei/numere față de LIVE se RAPORTEAZĂ în manifest, fără aserțiune de egalitate și fără reparare
  (diferențele externe moștenite rămân explicite; nu se legitimează, nu se rescorează nimic).
- **P8** `engine.py` și `parser.py` au hash-urile de mai sus; `rezultate/parser_manifest.json` neatins de teste.
- Suita existentă `tu3/tests` (15) trebuie să treacă în continuare.

## 7. Artefacte

`tu3/parser_multi.py` (CLI `--stare` și `--manifest`), `tu3/tests/test_parser_multi.py`,
`tu3/rezultate/P/MANIFEST_P_<UTC>.json` (rezumatul LIVE + înghețat pe joc, raportul 6/49 de la P7, dispozitiv;
fișier nou la fiecare rulare, refuză suprascrierea), `tu3/date/derivat/` (fișiere adaptate, adresate prin conținut).
Orice corecție după sigilare = amendament nou sigilat; acest fișier nu se rescrie.
