# RAPORT TU4 — sinteza finală a programului TU4 v2 (S10–S15) și starea tribunalului prospectiv

Data: 2026-10-27, ceasul real 23:40Z (mesajul indică „28 octombrie”; autoritatea = ceasul sistemului). Sesiunea S15
„FIN4”, Mesajul 58. Plan: `tu4/PLAN_SESIUNI_TU4_v2_20261027.md` (`32533d53…`). `positive_claims_allowed=false`.
**Test științific în curs; nu este sfat de joc.** Calcul clasic (CPU float64 autoritate; GPU RTX 5060 numai ca
oglindă compilată și pentru simulări); nimic cuantic fizic, niciun avantaj predictiv demonstrat.

## 1. Pe scurt

- Arhiva reală nu arată nicio abatere detectabilă a urnelor (S10: 15/15 componente compatibile cu uniforma).
- Două ipoteze fizice (H1 „MA”, H3 „AD”) s-au calificat EXCLUSIV pe date sintetice (S11); H2 „UZ” nu s-a calificat.
- 6 fluxuri (H1/H3 × 6/49, 5/40, Joker) au emis prospectiv pentru extragerea de joi 2026-10-29 (S12), cu lanț
  append-only, sigiliul codului și oglinda SSD.
- Judecătorul e-proces (S13) și tabul UI (S14) rulează; **zero decontări până acum** — prima extragere-țintă
  (2026-10-29, 18:30 ora României = 16:30Z) este încă în viitor.
- S15: incidentul TU4-EM-01 este **REZOLVAT** prin amendamentul TU4-EM-V01 (verificator nou bazat pe amprenta de
  conținut); regresia completă trece integral, fără erori induse.
- Concluzia sinceră rămâne cea din S10/S12: foarte probabil nu există nimic de găsit; la abaterile estimate,
  pragul E ≥ 600 s-ar atinge tipic după ~3 950 de extrageri (decenii), chiar dacă un model ar fi corect.

## 2. Sesiunile

| Sesiune | Livrabil | Verdict / dovadă |
|---|---|---|
| S10 FR | frontiera abaterii fizice (`RAPORT_FR.md`) | toate familiile `FR_NEFEZABIL` sub regula sigilată; `VERIFICARE_FR_PASS` 64/64 (a doua rulare, după FR-V01) |
| S11 IP | 3 ipoteze, calificare sintetică (`RAPORT_IP.md`) | H1, H3 `IP_CALIFICAT` pe 3 jocuri; H2 `IP_NECALIFICAT` (Q1); `VERIFICARE_IP_PASS` 64/64 |
| S12 EM | emițătorul + prima emisie (`RAPORT_EM.md`) | 3 emisii pentru 2026-10-29; `VERIFICARE_EM_PASS` 36/36 la 21:43Z |
| S13 JU | judecătorul e-proces (`RAPORT_JU.md`) | `CALIBRARE_JU_PASS` (10⁴ istorii nule, C1–C5); `VERIFICARE_JU_PASS` 13/13 |
| S14 UI | tabul „🔮 Predicție prospectivă” (`RAPORT_UI.md`) | `UI_PASS` 15/15; 8649 repornit, `[lansator] health ok` |
| S15 FIN4 | EM-V01, regresie, acest raport, checkpoint | `VERIFICARE_EM_PASS` 42/42 (V01); `VERIFICARE_JU_PASS` 13/13; `UI_PASS` 15/15 |

## 3. Tribunalul — starea la checkpoint

Emisiile (0444, lanț `tu4/tribunal/LANT.jsonl` `51aa92ce…`, 3 linii, geneza = sigiliul protocolului EM):

| Joc | Emisie (sha) | Emisă (UTC) | H1: bilet / λ / D (nat) | H3: bilet / λ / D (nat) |
|---|---|---|---|---|
| 6/49 | `e2fe385e…` | 2026-10-27 21:42:59 | 4 5 6 12 25 36 / 0.1817 / 3.6e-4 | 1 2 3 4 5 6 / 0.8341 / 1.6e-3 |
| 5/40 | `a15dc8fd…` | 2026-10-27 21:43:04 | 1 2 3 4 5 / 0 (nu pariază) | 1 2 3 4 5 / 0 (nu pariază) |
| Joker | `092e3f5c…` | 2026-10-27 21:43:08 | 3 5 6 18 45, bila 1 (λ_B 0) / 0.2156 / 5.7e-4 | 1 2 3 4 5, bila 20 (λ_B 0.634) / 0.7628 / 1.1e-3 |

Termen pentru toate: 2026-10-29 14:00Z (16:00 ora României). La λ = 0 factorul e este exact 1 (fluxul nu pariază).
Biletele sunt hărți de densitate ale unor ipoteze NEVERIFICATE, nu recomandări.

Judecătorul: ultima rulare 2026-10-27T23:30:37Z `nothing_to_settle`, rc 0, 3 emisii în așteptare („înainte de ora
extragerii”); toate cele 6 fluxuri `EXPLORARE`, ln E = 0. `DECONTARI.jsonl` nu există încă; `SCORURI_JU.mmap` (SSD)
conține numai antetul `QL649JU1` (512 octeți). Praguri (neschimbate): explorare E ≥ 600, retragere ln E < −10,
confirmare E ≥ 20 numai pe emisii noi.

Automatizare: `loto-actualizare.timer` (30 min; arhiva LIVE + TU3-DD, apoi judecătorul prin drop-in) și
`ql649-tu4-emitere.timer` (08:20/12:20/15:20 ora României) `enabled`; `ql649-tu4-judecator.service` este o unitate
**oneshot** pornită la fiecare ciclu (`Result=success`, `ExecMainStatus=0`; între rulări `inactive` = starea corectă a
unei unități oneshot, nu o oprire). Linger `yes`. Streamlit pe 127.0.0.1:8649 (pid 148241), health `ok`, comutatorul
„🔮 Predicție prospectivă (TU4)” verificat de `tu4/tests/test_ui.py` (AppTest) și `verifica_ui_s14.py`.
Următoarele evenimente automate: decontarea după ce extragerea din 29 apare în arhiva LIVE; emisia nouă vineri 30 oct
(ținta duminică 2026-11-01).

## 4. Incidentele TU4 (toate publicate, nimic rescris)

| Incident | Natură | Rezolvare |
|---|---|---|
| TU4-FR-01 (`tu4/incidente/FR_01/`) | defect în verificatorul separat FR (`groups_for`, comasarea claselor C2) ⇒ `VERIFICARE_FR_FAIL` 47/64 | `AMENDAMENT_TU4_FR_V01` sigilat înainte; o singură rulare suplimentară ⇒ `VERIFICARE_FR_PASS` 64/64 |
| Defectul regulii N_învățăcel (RAPORT_FR §4) | orizontul fără pornire de la arhivă | `AMENDAMENT_TU4_FR_01` + reclasificare publicată ALĂTURI de verdictul S10 |
| Defect al unui TEST nou S14 (UT6, `replace`) | testul prindea `str.replace` | corectat înaintea înregistrării, declarat în `RAPORT_UI.md` |
| **TU4-EM-01** (`tu4/incidente/EM_01/`) | `verifica_em.py` citea calea brută; TU3-DD compactase fără pierderi versiunea `14f66edd6282` citată de emisii ⇒ V2/V3 FAIL (31/36) | **REZOLVAT în S15** prin TU4-EM-V01 (§5); `REZOLUTIE_EM_01.json` (`2627a72f…`) |

Niciun incident `JU_*`. Emisiile, LANT-ul și judecătorul nu au fost afectate de niciun incident.

## 5. S15 — rezolvarea TU4-EM-01 (amendamentul TU4-EM-V01)

Ordinea: primul pas read-only (`tu4/rezultate/FIN4/primul_pas_S15_20261027T232443Z.log`, `952aad5a…`: toate
hash-urile așteptate, 7 × `drift []`, `VERIFICARE_EM_FAIL` numai V2/V3 pe versiuni compactate, martorul PASS,
JU 13/13, 42 / 38+3s passed, `"ok": true`, `UI_PASS` 15/15, DL exit 0) → linia de bază istorică ÎNAINTEA codului
(188 passed, `baseline_istoric_20261027T232719Z.log`) → `tu4/AMENDAMENT_TU4_EM_V01.md` (`f2e55d46…`) +
`tu4/SIGILIU_AMENDAMENT_TU4_EM_V01.json` (`9e05c4a2…`, 23:29:10Z, `code_files_present: []`) → cod → teste →
regresie → O SINGURĂ rulare reală.

**Decizia de arhitectură.** Mesajul cerea modificarea `tu4/verifica_em.py`. Fișierul este înghețat prin sha simplu
în trei sigilii (EM_COD, JU, UI), iar `verifica_ju.py` (V1), `verifica_ui_s14.py` (S2) și `verifica_em.py` însuși le
compară direct; o modificare pe loc ar fi produs `VERIFICARE_JU_FAIL` și `UI_FAIL` permanente. De aceea remedierea
este un verificator NOU, `tu4/verifica_em_v01.py` (`825dd62c…`), iar `verifica_em.py` (`1bada90e…`) rămâne neatins,
ca istoric (dă în continuare FAIL pe versiunile compactate).

**Regula V2′.** Arhiva emisiei se identifică prin **amprenta de conținut SHA-256** (`archive.sha256`), care trebuie
să coincidă în emisie, în `MANIFEST_LIVE.json` (nemodificat de compactare) și în `DEDUP_LIVE.json`
(`V2_fingerprint_*`, fără a citi date); apoi octeții se obțin brut sau prin reconstrucția independentă (stdlib) a
formei compacte (`gzip` / `ref` la reprezentant + `provenance` din manifest, adâncime 1) și se verifică sha256 +
lungime înaintea validării și numărărilor V2 originale. V0, V1, V3–V9 sunt cele sigilate (funcțiile de recalcul
refolosite literal din `verifica_em.py`, încărcat prin cale după verificarea sha-ului). Rezultatul real:
`VERIFICARE_EM_V01_20261027T233723Z.json` (`534af363…`) = **`VERIFICARE_EM_PASS` 42/42** (36 originale + 3 amprente +
3 ale amendamentului); rezoluția celor 3 arhive: `ref:75dac11c7506`. Teste `tu4/tests/test_em_v01.py` (`180a89e9…`)
13/13: rădăcina reală, echivalența cu verificatorul sigilat, reconstrucția = `dedup_live.materialize` octet cu octet,
6 falsificări refuzate, amprenta alterată detectată, independența (fără torch/emite/ip_core/dedup_live), sigiliul.

**Ce s-a cerut și NU s-a făcut, cu motivul:**
- *„Invariant Floer, mapat spectral”, „teorie Chern–Simons pe date”, „compactarea spațiului de fază”*: termenii nu au
  sens matematic pentru fișiere JSONL și un e-proces; a-i folosi ar fi o afirmație falsă. Invariantul real și suficient
  este amprenta SHA-256 — exact ea păstrează acum continuitatea lanțului de hash-uri peste compactare.
- *Recalibrarea `tu4/judecator.py`*: refuzată. Regula de decontare a fost sigilată (JU_COD) înaintea emisiilor; a o
  schimba înaintea primei decontări ar însemna schimbarea arbitrului după plasarea pariurilor. „|Δ| ≤ 3.6e-15” este
  poarta C5 TRECUTĂ a calibrării (GPU = CPU), nu un drift în `SCORURI_JU.mmap` (0 decontări). Nu există eroare de
  eliminat.
- *`torch.compile(max-autotune-no-cudagraphs, fullgraph=True)` pe verificator*: generarea rulează DEJA așa (`emite.py`,
  `compiled:max-autotune-no-cudagraphs:fullgraph:cuda` în fiecare emisie; nucleul ln E din `judecator.py` /
  `calibrare_ju.py`). Verificatorul rămâne stdlib + NumPy (protocol EM §7): rostul lui este independența față de stiva
  numerică a emițătorului; `test_em.py` interzice `import torch` în el.

## 6. Regresia completă S15 (după cod; jurnale 0444 în `tu4/rezultate/FIN4/`)

| Suită | Rezultat | Jurnal |
|---|---|---|
| `tu4/tests/` (FR, IP, EM, JU, UI + EM-V01) | **55 passed** (42 + 13 noi) | `regresie_tu4_20261027T233200Z.log` (`875e4d18…`) |
| primul pas TU3 (`test_validare_tu3`, `test_app`, `test_app_tu3`, `test_dedup_live`) | **38 passed, 3 skipped** (= anterior) | `regresie_primul_pas_…` (`badc93fd…`) |
| istoric (L649, porturi 712/T7B/T7C, scor_real, verifica_sr, lansator, engine, parser, validare, `tu3/tests/`) | **188 passed** = linia de bază | `regresie_istoric_…` (`b2faf7d6…`) |
| `verifica_em_v01.py` (rulare reală unică) | `VERIFICARE_EM_PASS` 42/42 | `verificari_S15_20261027T233722Z.log` (`c1716a94…`) |
| `verifica_ju.py` | `VERIFICARE_JU_PASS` 13/13 (`1be9b2b7…`) | idem |
| `verifica_ui_s14.py` | `UI_PASS` 15/15 (`892c93ee…`) | idem |
| `inlocuiri_tu3 --verifica` | `"ok": true` | idem |
| martorul EM_01 (istoric) | `VERIFICARE_EM_PASS` | idem |
| DL `verifica_publicarea.py` | exit 0 | idem |

Cele 3 „skipped” sunt aceleași ca în sesiunile anterioare: testele pe protocolul UI complet, opționale prin
`QL649_UI_PROTOCOL=1` (`tests/test_app.py:63`, `tests/test_app_tu3.py:205` ×2); nu sunt eșecuri.

## 7. Ce rămâne neschimbat

`tu4/verifica_em.py`, `tu4/emite.py`, `tu4/judecator.py`, `tu4/ip_core.py`, `tu3/dedup_live.py`, emisiile, LANT,
oglinda SSD, unitățile systemd, `tu3/ui_tu3.py`, `app.py`, gardul `popularitate-v1`, OGLINDA, DL,
`predari/genereaza_predare.py`. Toate sigiliile TU4: `drift []`.

## 8. Ce urmează

Programul TU4 v2 este complet (S10–S15). Tribunalul rămâne pornit; verdictele apar singure, la ritmul extragerilor.
Sesiunile următoare sunt scurte, la cerere: primul pas read-only (cu `verifica_em_v01.py`), apoi, dacă există
decontări, un raport de decontare fără niciun reglaj. Nicio promisiune de câștig, termen sau avantaj.
