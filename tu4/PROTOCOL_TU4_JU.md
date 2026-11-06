# PROTOCOL TU4-JU — sesiunea S13 „JU”: judecătorul e-proces și decontarea automată a emisiilor prospective

Stare: scris și sigilat (`tu4/SIGILIU_TU4_JU.json`) ÎNAINTE de orice cod S13 (`tu4/judecator.py`,
`tu4/calibrare_ju.py`, `tu4/verifica_ju.py`, scriptul de pornire, unitățile systemd, testele) și ÎNAINTE de orice
decontare. Plan: `tu4/PLAN_SESIUNI_TU4_v2_20261027.md` (`32533d53…`) §1–§2 S13. Emițătorul: `tu4/PROTOCOL_TU4_EM.md`
(`146078ef…`), sigiliile `SIGILIU_TU4_EM.json` (`82459f48…`) și `SIGILIU_TU4_EM_COD.json` (`6e4ebf9b…`).
Autoritate: Mesajele 52–56 (Mesajul 56 = cererea S13 din 2026-10-27T21:51Z). `positive_claims_allowed=false`.

## 0. Mesajul 56, cum se aplică (decizii ale agentului, delegate)

- **Pragurile planului §1, NESCHIMBATE:** explorare E ≥ 600 = 100·M (M = 6 fluxuri); retragere imediată și
  absorbantă la ln E < −10; confirmare E ≥ 20 pe extrageri NOI, cu modelul înghețat. Nimic nu se reglează după ce se
  văd decontări. Garanția Ville: sub urna perfectă, P(vreun flux atinge vreodată 600) ≤ 6/600 = 0.01.
- **Judecătorul NU prezice și NU recalculează modelele.** Folosește exclusiv ln ŵ scrise în emisia sigilată. Nu
  importă `ip_core.py`, `emite.py`, nimic din produsul vechi și nicio intrare de popularitate.
- **Zero Alteration Guard:** emisiile (`tu4/tribunal/emisii/`, `LANT.jsonl`, `RULARI.jsonl`) și oglinda lor de pe
  SSD (`./ssd_data/QL649_TU4_EM/`) sunt deschise NUMAI pentru citire. Judecătorul nu le șterge, nu le
  reface, nu le modifică și nu le schimbă modul. Dacă lanțul emisiilor nu se verifică, judecătorul refuză ORICE
  decontare (cod 3) și scrie un incident; nu „repară”.
- **Calibrarea nulă „Wheeler–DeWitt / martor gauge”:** denumirea din cerere este o etichetă. Matematic este o
  calibrare Monte Carlo sub H0 (urna uniformă, extrageri independente): 10⁴ istorii nule de control, cu modelele
  ÎNGHEȚATE și cu exact nucleul e-factorului folosit de judecător (§6). Nu este fizică cuantică, gravitație cuantică
  sau o simetrie gauge reală.
- **GPU + `torch.compile(mode="max-autotune-no-cudagraphs", fullgraph=True)`:** nucleul vectorizat al factorului e
  (float64) este compilat fullgraph pe CUDA (CPU dacă CUDA lipsește) și folosit (a) în calibrarea nulă (≈ 3·10⁷
  factori e) și (b) ca OGLINDĂ a fiecărei decontări reale. Autoritatea decontării reale rămâne calculul CPU float64
  (§4); o decontare are câțiva scalari, deci GPU-ul nu aduce viteză acolo — este martor, nu autoritate. Eșecul
  compilării ⇒ execuție eager, publicată.
- **Serviciu persistent:** unitate NOUĂ `ql649-tu4-judecator.service` (oneshot) + drop-in NOU
  `loto-actualizare.service.d/tu4-judecator.conf` care, după fiecare actualizare a arhivei (după drop-in-urile TU3,
  ordine lexicală), pornește NEBLOCANT judecătorul (`ExecStopPost=-/usr/bin/systemctl --user start --no-block …`;
  prefixul `-` ⇒ un eșec al judecătorului nu schimbă rezultatul serviciului de actualizare). Linger este deja activ.
  ExecStart/gardul prognozei vechi, timerul și drop-in-urile existente rămân neatinse. Cererea explicită a
  utilizatorului (Mesajele 53, 55, 56) autorizează această automatizare a tribunalului; ea nu este un job al
  agentului: nu prezice, nu contactează pe nimeni, nu cheltuie.
- **„Matricea MMAP pe SSD, ocolind RAM-ul”:** se implementează o matrice binară cu aspect fix pe SSD
  (`QL649_TU4_JU/SCORURI_JU.mmap`, §8) actualizată prin `mmap` + `flush` + `fsync`. Declarat sincer: `mmap` trece
  prin memoria paginilor nucleului (page cache, adică RAM); ocolirea completă a RAM-ului NU este posibilă și NU se
  afirmă. Autoritatea rămâne decontarea canonică din depozit (`tu4/tribunal/decontari/`), deoarece SSD-ul nu este
  montat persistent după repornire; matricea este o oglindă reconstruibilă byte-exact.
- Calcul CLASIC (CPU/GPU, virgulă mobilă). Fără hardware cuantic, avantaj cuantic, noutate mondială sau promisiune
  de câștig. Fără subagenți. Git numai `./dev-git`, fără add/commit. Sigilii locale, fără atestare externă a timpului.

## 1. Fluxurile și factorul e (autoritate CPU float64)

Fluxuri (ordinea fixă): `H1_649, H1_540, H1_joker, H3_649, H3_540, H3_joker`. Pentru o emisie admisă a jocului g
(n, k: 6/49 n 49 k 6; 5/40 n 40 k 6; Joker n 45 k 5 + bila n 20 k 1) și modelul m, cu ln ŵ citit din
`models[m].logw` și extragerea S (k numere distincte):

- ln e_main = Σ_{i∈S} ln ŵ_i − ln e_k(ŵ) + ln C(n,k), unde e_k = polinomul simetric elementar (recurența
  e_j ← e_j + ŵ_i e_{j−1}, float64), ln C(n,k) prin `lgamma`.
- Joker: ln e_ball = ln ŵ^B_J − ln Σ_l ŵ^B_l + ln 20, cu ln ŵ^B din `models[m].ball.logw` și J bila extrasă.
- ln e = ln e_main (+ ln e_ball la Joker).
- Dacă `bet_active` este fals pentru un bloc (λ = 0), termenul acelui bloc este EXACT 0.0 (legea emisă este uniformă).
- Validitate: q(S) = Π_{i∈S} ŵ_i / e_k(ŵ) este o lege pe toate cele C(n,k) rezultate, fixată ÎNAINTE de extragere;
  E_u[q/u] = 1 ⇒ produsul factorilor e este martingală nenegativă sub H0, pentru orice regulă de oprire.

## 2. Admisibilitatea emisiilor

Integritate (globală; orice eșec ⇒ refuz total, cod 3, incident `tu4/incidente/JU_INTEGRITATE_<UTC>.json`):
- I1 `LANT.jsonl`: indicii 0,1,2,… consecutivi; `prev_line_sha256` = sha256 al liniei precedente (fără newline),
  geneza = sha256 al `tu4/SIGILIU_TU4_EM.json`; sha256 al fișierului emisiei = cel din linie; nicio pereche
  (joc, dată) dublată.
- I2 lanțul per joc: `chain.index` consecutiv; `chain.prev_sha256` = sha256 al emisiei precedente a aceluiași joc
  (geneza = sha256 al sigiliului EM); `emitted_utc` din fișier = cel din linie.
- I3 cele 3 emisii din 2026-10-29 au exact sha-urile înghețate în sigiliul JU.

Admisibilitate (per emisie; eșec ⇒ decontare `RESPINS`, e = 1, necontorizată, incident
`tu4/incidente/JU_RESPINS_<joc>_<D>.json`):
- A1 `emitted_utc < cutoff_utc < draw_utc` (comparare pe timp UTC).
- A2 calendarul: data D este joi sau duminică; `draw_utc` = 18:30 Europe/Bucharest în D; `cutoff_utc` = 16:00
  Europe/Bucharest în D.
- A3 `protocol` = "TU4-EM", `target_kind` = "regular", `positive_claims_allowed` = false, `test_mode` = false
  (în modul de test al judecătorului se cere `test_mode` = true).
- A4 codul: `code.emite_sha256` = valoarea din `SIGILIU_TU4_EM_COD.json`; `code.ip_core_sha256` = `ab3e1de9…`;
  `code.code_seal_sha256` = sha256 al `SIGILIU_TU4_EM_COD.json`; `code.protocol_seal_sha256` = `82459f48…`.
- A5 `archive.last_date` < D (arhiva de start nu conține extragerea judecată).
- A6 blocurile H1 și H3: `logw` cu exact n valori finite; la Joker `ball.logw` cu 20 de valori finite; `bet_active`
  boolean.
- Martor de coroborare (raportat, NU condiție): intrarea din `JURNAL_EMISII.jsonl` de pe SSD are
  `mirrored_utc < draw_utc`; observațiile proprii ale judecătorului (§7) au văzut emisia înainte de `draw_utc`.

## 3. Regula de potrivire pentru extragerea REGULATĂ a datei D (fixată înaintea primei decontări)

Arhiva folosită: versiunea LIVE CURENTĂ (`tu3/date/live/CURRENT_LIVE.json`), validată ca în EM §1 (sha fișier =
manifest = curent, număr de înregistrări, validarea fiecărei extrageri). Arhivă invalidă ⇒ nicio decontare în rularea
respectivă (cod 3, consemnat), nu VOID.

Pentru emisia (g, D), după `draw_utc` (ceasul real):
1. R = înregistrările jocului g cu `draw_date` = D și `draw_kind` = "regular". Înregistrările `special`/`unknown`
   din aceeași dată sunt IGNORATE (o dată poate avea mai multe extrageri).
2. |R| = 1, `has_source_disagreement` ≠ true și extragerea validă ⇒ **DECONTAT** cu acea înregistrare.
3. |R| ≥ 2 ⇒ **VOID** („ambiguu”), e = 1 pe ambele modele, decis fără a privi numerele.
4. |R| = 0, sau |R| = 1 cu dezacord între surse ⇒ **în așteptare**; dacă acum ≥ `draw_utc` + 14 zile ⇒ **VOID**
   („absentă” sau „dezacord persistent”), e = 1.
5. Înainte de `draw_utc` nu se decontează nimic; o înregistrare regulată cu data D văzută înainte de `draw_utc`
   ⇒ incident `JU_CEAS_<joc>_<D>.json` (nicio decontare până după `draw_utc`).
Decizia VOID/așteptare depinde numai de prezența/clasificarea înregistrării, nu de numerele extrase, deci păstrează
validitatea e-procesului. Decontarea este FINALĂ: se scrie o singură dată (O_EXCL, 0444). La fiecare rulare, judecătorul
compară subsetul canonic al înregistrărilor decontate (`game`, `draw_date`, `draw_kind`, `numbers`, `joker`) cu arhiva
curentă; o revizie ulterioară a sursei ⇒ incident `JU_REVIZIE_<joc>_<D>.json` (o dată), fără rescrierea decontării.

## 4. Procesele E și mașina de stări (per flux)

Ordinea contorizării: pe fiecare flux, decontările în ordinea crescătoare a datei D. Stări: `EXPLORARE` →
`CONFIRMARE` → `CONFIRMAT`; orice stare activă → `RETRAS`.
- `EXPLORARE`: ln E ← ln E + ln e (DECONTAT); VOID/RESPINS contribuie 0. Dacă ln E ≥ ln 600 ⇒ `CONFIRMARE`, cu
  ln E_conf = 0 și momentul de pornire = `decided_utc` al decontării care a trecut pragul. Dacă ln E < −10 ⇒ `RETRAS`.
- `CONFIRMARE`: contorizează NUMAI emisiile cu D > data trecerii pragului ȘI `emitted_utc` > momentul de pornire
  (extrageri noi, model înghețat). ln E_conf ≥ ln 20 ⇒ `CONFIRMAT`; ln E_conf < −10 ⇒ `RETRAS`.
- `RETRAS` și `CONFIRMAT` sunt absorbante. După retragere, factorii e se calculează și se publică informativ, dar nu se
  mai contorizează. `CONFIRMAT` NU schimbă singur `positive_claims_allowed`: este nevoie de un raport separat,
  verificat, care repetă calculul (sesiune ulterioară). Pragul 20 se aplică fluxului înghețat, ca în plan (fără
  corecție suplimentară; declarat).

## 5. Ieșirile canonice (depozit, append-only)

- `tu4/tribunal/decontari/<joc>/<D>.json` (O_CREAT|O_EXCL, 0444, fsync): `status` (DECONTAT/VOID/RESPINS) și motivul,
  emisia (fișier, sha256, indexul din LANT), arhiva (version_dir, sha fișier, `draw_key`, subsetul canonic al
  înregistrării), numerele și bila, pe model: ln e_main, ln e_ball, ln e, `bet_active`, `counted`; stările și ln E /
  ln E_conf ale fluxurilor jocului înainte/după; oglinda GPU (§6); `decided_utc`; `positive_claims_allowed: false`.
- `tu4/tribunal/DECONTARI.jsonl` (O_APPEND, 0444 între scrieri): o linie per decontare cu `i`, `game`,
  `target_date`, `status`, `file`, `sha256`, `prev_line_sha256` (geneza = sha256 al `tu4/SIGILIU_TU4_JU.json`).
- `tu4/tribunal/JUDECATOR_RULARI.jsonl` (O_APPEND): fiecare rulare, cu sha256 al `LANT.jsonl` observat, lista
  emisiilor în așteptare și motivele (martor de observare înaintea extragerii).
- Excludere reciprocă cu emițătorul: `flock` exclusiv pe `tu4/tribunal/.lock` pe durata unei rulări.
- Codurile de ieșire: 0 (inclusiv „nimic de decontat”), 3 (refuz: integritate/arhivă invalidă).

## 6. Nucleul GPU compilat și calibrarea nulă (10⁴ istorii)

Nucleul: `ln_e(logw (B,n) f64, x (B,n) f64 ∈ {0,1}, active (B,) bool)` = active · (Σ x·logw − ln e_k(e^{logw}) +
ln C(n,k)), compilat `torch.compile(mode="max-autotune-no-cudagraphs", fullgraph=True, dynamic=False)`.
Poarta oglinzii în decontarea reală: |ln e_GPU − ln e_CPU| ≤ 1e-9 pe fiecare bloc; eșec ⇒ decontarea CPU rămâne
autoritatea, `gpu_mirror.pass = false`, incident declarat; nimic nu se reglează.

Calibrarea `tu4/calibrare_ju.py` (rulată O SINGURĂ DATĂ, după sigiliul codului, înaintea instalării serviciului):
- R = 10 000 istorii nule, sămânța 2026102713 (+ indexul jocului), cele 3 jocuri independente în fiecare istorie.
- Start: N_g extrageri uniforme sintetice (N = `warm_start.N` din emisiile înghețate din 29: 2597, 2490, 2202),
  apoi orizontul H = 520 de extrageri uniforme. Înaintea extragerii t, modelele H1/H3 (funcțiile ÎNGHEȚATE
  `logw_h1`, `logw_h3`, `dct_basis` din `ip_core.py ab3e1de9…`, importate fără modificare) folosesc toate extragerile
  anterioare (exact ca emițătorul); la Joker și bila (n 20, k 1). λ = 0 ⇒ factor exact 1.
- Factorii e prin nucleul compilat al judecătorului; mașina de stări §4 (retragere absorbantă, confirmare după
  trecerea pragului de explorare).
- Porți (fixate acum; q₀.₉₉₉(Bin(R, p)) = cuantila 0.999 binomială exactă):
  - C1 pe fiecare flux: numărul istoriilor care ating ln 600 ≤ q₀.₉₉₉(Bin(10⁴, 1/600));
  - C2 familie (6 fluxuri, aceeași istorie): numărul istoriilor în care vreun flux atinge ln 600 ≤ q₀.₉₉₉(Bin(10⁴, 0.01));
  - C3 pe fiecare flux: numărul istoriilor cu sup ln E ≥ ln 20 (cu retragerea absorbantă) ≤ q₀.₉₉₉(Bin(10⁴, 0.05));
  - C4 martingala: pentru fiecare flux, |media_r(media_t e_{r,t}) − 1| ≤ 5·sd_r/√R;
  - C5 nucleul GPU = autoritatea CPU pe 1 000 de perechi aleatoare (ln ŵ, extragere) din fiecare (n, k):
    |Δ| ≤ 1e-9.
- Se raportează („zgomotul de fond” sub H0): cuantilele 1/5/50/95/99% ale ln E_H, maximul sup ln E, P(retragere
  până la H), media ln e pe extragere, P(confirmare | H0), starea compilării.
- Traiectoriile ln E (6 × 10⁴ × 520, float32) se scriu prin `numpy.memmap` pe SSD
  (`QL649_TU4_JU/calibrare/lnE_null_f32.mmap`, sha256 în rezultat) dacă SSD-ul este montat.
- Rezultat `tu4/rezultate/JU/CALIBRARE_JU.json` (0444). `CALIBRARE_JU_PASS` numai dacă C1–C5 trec. Dacă nu trece:
  serviciul NU se instalează, incident declarat, fără reglaj.

## 7. Serviciul

- `tu4/porneste_judecator.sh` (0555): verifică/montează SSD-ul (UUID `5af1b939-865f-4eab-bf45-38983451b704`, ca la
  EM), apoi rulează `tu4/judecator.py` cu `--ssd <mount>/QL649_TU4_JU` sau `--fara-ssd`.
- `tu4/systemd/ql649-tu4-judecator.service` (oneshot, `Nice=5`, `TimeoutStartSec=20min`) și
  `tu4/systemd/tu4-judecator.conf` (drop-in pentru `loto-actualizare.service`). Copiile instalate sunt 0444 și
  identice cu cele sigilate. Fără timer propriu (arhiva LIVE se schimbă numai prin `loto-actualizare`).
- Când nu există nimic de decontat, judecătorul NU importă torch (rulare rapidă); scrie doar observația.

## 8. Oglinda SSD (matricea MMAP)

Director `./ssd_data/QL649_TU4_JU/`:
- `decontari/<joc>/<D>.json` copii byte-identice (O_EXCL, 0444); `JURNAL_DECONTARI.jsonl` prin `mmap` (extindere,
  scriere, flush, fsync).
- `SCORURI_JU.mmap`: antet 512 octeți (magic `QL649JU1`, versiune 1, lungimea rândului 160, numărul de rânduri,
  ordinea fluxurilor), apoi câte un rând de 160 octeți per decontare (little-endian): int64 secvența, int64 data
  AAAALLZZ, int64 indexul jocului (649 0, 540 1, joker 2), int64 status (DECONTAT 0, VOID 1, RESPINS 2), float64[2] ln e
  (H1, H3), float64[6] ln E, float64[6] ln E_conf, int8[6] starea (EXPLORARE 0, CONFIRMARE 1, CONFIRMAT 2, RETRAS 3),
  completare cu zero. Rândurile existente nu se rescriu; se adaugă numai rânduri noi și se actualizează contorul din
  antet. Dacă prefixul existent diferă de recalculare ⇒ incident, matricea nu se atinge.

## 9. Verificator SEPARAT `tu4/verifica_ju.py`

Numai biblioteca standard + NumPy (fără torch, fără import din `tu4/`). V1 sigiliile JU (protocol, cod) și fișierele
înghețate neschimbate; V2 lanțul emisiilor (I1–I3) recalculat independent; V3 fiecare decontare: admisibilitatea
(A1–A6) și regula §3 refăcute pe arhiva LIVE curentă (sau incidentul de revizie existent); ln e recalculat cu
identitățile lui Newton (sume de puteri, `math.fsum`), |Δ| ≤ 1e-10, termen exact 0 la λ = 0; V4 procesele E și
stările §4 recalculate; V5 `DECONTARI.jsonl` (lanț, unicitate, sha); V6 modurile 0444; V7 nicio emisie trecută de
`draw_utc` + 14 zile fără decontare; V8 oglinda SSD (copii, jurnal, matricea recalculată byte-exact; `UNKNOWN` dacă
SSD-ul nu este montat); V9 unitățile instalate = cele sigilate; V10 calibrarea: porțile refăcute din numărările
publicate, cuantilele binomiale recalculate independent, iar dacă SSD-ul e montat, rezumatul refăcut din memmap;
V11 analiza AST: `judecator.py` nu importă `ip_core`, `emite`, `ip_run`, `frontiera` sau nume cu „popular”.
`VERIFICARE_JU_PASS` numai dacă V1–V7, V9–V11 trec și V8 este PASS sau `UNKNOWN` cu motiv. Rezultat:
`tu4/rezultate/JU/VERIFICARE_JU_<UTC>.json` (0444).

## 10. Ordinea de execuție S13

1. Acest protocol + `tu4/SIGILIU_TU4_JU.json` (înainte de cod). 2. Cod + teste pe rădăcini SINTETICE
(`tu4/tests/test_ju.py`). 3. Testele trec ⇒ `tu4/SIGILIU_TU4_JU_COD.json` înaintea calibrării și a oricărei rulări pe
lanțul real; un defect găsit înainte se repară și se declară. 4. Calibrarea nulă (o rulare). 5. Dacă
`CALIBRARE_JU_PASS`: instalarea serviciului și a drop-in-ului (copii 0444), `daemon-reload`, o rulare manuală pe
lanțul real (așteptat: 3 emisii în așteptare, extragerea din 29 nu a avut loc). 6. Verificare SEPARATĂ. 7. Raport
`tu4/rezultate/JU/RAPORT_JU.md`. Prima decontare reală: extragerea din joi 2026-10-29, automat, după ce apare în
arhiva LIVE.

## 11. Ce NU face S13

Nu emite, nu modifică emisiile sau emițătorul, nu reglează praguri ori modele, nu decontează retroactiv pe arhiva
veche, nu afirmă că vreo abatere există, nu promite câștig sau termen, nu filtrează după popularitate, nu atinge TU3,
S10/S11, pistele închise, produsul vechi, gardul, ExecStart-ul `loto-actualizare` sau drop-in-urile lui existente.
Estimarea centrală rămâne: probabil nu există nimic de găsit; dacă urna este corectă, ln E va fluctua și va coborî
lent (media ln e < 0 sub H0), iar acesta este un rezultat corect, publicat.
