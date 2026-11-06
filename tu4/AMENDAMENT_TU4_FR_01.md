# AMENDAMENT TU4-FR-01 — orizontul cu pornire de la arhivă (reclasificare publicată ALĂTURI de verdictul sigilat S10)

Stare: scris și sigilat (`tu4/SIGILIU_AMENDAMENT_TU4_FR_01.json`) la începutul sesiunii S11 „IP”, ÎNAINTE de orice cod
S11, înainte de protocolul ipotezelor și înainte de calculul reclasificării. Autoritate: Mesajul 54 (2026-10-27T21:01Z,
„Scrie ÎNTÂI … AMENDAMENT_TU4_FR_01.md … orizontul cu pornire de la arhivă și reclasificarea publicată alături de
verdictul sigilat S10”) și decizia din `tu4/rezultate/FR/RAPORT_FR.md` §4 și §6. Primul pas read-only al sesiunii
(`/tmp/ql649_s11/primul_pas.log`): toate hash-urile ok, `drift []`, `VERIFICARE_FR_PASS`, 5 / 32 / 38+3s passed,
`"ok": true`, DL exit 0. `positive_claims_allowed=false`.

## 1. Defectul (declarat în RAPORT_FR §4, nerescris)

Regula sigilată S10 (protocol FR §4) definește N_învățăcel ca cel mai mic N cu `N·D_max − (df/2)·ln N ≥ ln(100·M)`
(α = 0.01, M = 3). Termenul `(df/2)·ln N` este costul unui amestec bayesian care învață de la ZERO. Un model care
pornește de la arhiva de lungime T are deja posteriorul după T extrageri, iar costul de învățare pe următoarele N
extrageri este (aceeași aproximare Laplace/BIC, declarată) `(df/2)·ln((T + N)/T) = (df/2)·ln(1 + N/T)`. Regula sigilată
este deci prea pesimistă pentru orice familie al cărei model pornește de la arhivă.

## 2. Regula amendată (singura schimbare)

`N_cald` = cel mai mic întreg N ≥ 1 cu `N·D_max − (df/2)·ln(1 + N/T) ≥ ln(100·M)`, cu α = 0.01, M = 3
(pragul ln 300, NESCHIMBAT), T = lungimea arhivei jocului din `FR_REZULTATE.json` (6/49 2595, 5/40 2490, Joker 2202).
Clasele rămân cele sigilate: `FR_FEZABIL` ≤ 520 extrageri (5 ani), `FR_LENT` ≤ 2 080 (20 ani), altfel `FR_NEFEZABIL`.
Ani = N/104 (declarat ca în S10). Se aplică tuturor celor 8 familii cu frontieră din `FR_REZULTATE.json`: C1 și C2
pentru 6/49, 5/40, Joker; B1 (bila Joker, marginal) și B2 (repetarea bilei).

## 3. Intrări (numai valori deja publicate, fără nicio statistică nouă pe arhivă)

Din `tu4/rezultate/FR/FR_REZULTATE.json` (`04f1e730…`, NESCHIMBAT): pentru fiecare familie `D_max`, `df`, `T`.
Nicio extragere din arhive nu este recitită; nicio valoare p, frontieră sau D_max nu se recalculează.

## 4. Publicare (alături, fără rescriere)

- `FR_REZULTATE.json`, `RAPORT_FR.md`, `VERIFICARE_FR.json`, verdictele `FR_NEFEZABIL` sigilate rămân byte-identice
  și rămân verdictul OFICIAL al regulii S10.
- Reclasificarea se scrie ALĂTURI: `tu4/rezultate/FR/RECLASIFICARE_FR01.json` (0444) cu, pentru fiecare familie,
  `feasibility_sealed` (copiat din S10), `N_learner_M3_sealed`, `N_cald`, `years_cald`, `feasibility_amended`.
  Calcul: `tu4/reclasificare_fr01.py` (numai biblioteca standard; scanare liniară în N). Verificare independentă
  (bisecție pe funcția crescătoare după minimul ei) în verificatorul S11 `tu4/verifica_ip.py`.
- Valori așteptate, deja anunțate descriptiv în RAPORT_FR §4 scenariul 3 (≈153 / 206 / 136 pentru C1, ≈357 pentru
  B1): dacă reclasificarea dă altceva, se publică valoarea calculată și diferența se declară, fără ajustare.

## 5. Ce schimbă și ce NU schimbă

- Schimbă NUMAI martorul de decizie S10 (protocol FR §5): S11 poate alege ipoteze din familiile `FR_FEZABIL`/`FR_LENT`
  după regula amendată, cu abaterea implantată la `D_max` pentru calibrarea puterii pe date SINTETICE.
- NU schimbă: statisticile, valorile p, D_max, verdictele pe componente (`FR_COMPATIBIL_UNIFORM` ×15), pragurile
  claselor, α, M. NU afirmă că vreo abatere există: `D_max` este marginea regiunii de încredere 95%, iar estimarea
  centrală (RAPORT_FR §4.2) dă ani/decenii sau nimic. Avertismentul empiric RAPORT_FR §4 (direcția frecvențelor
  observate nu a bătut uniformul retrospectiv) rămâne în vigoare: reclasificarea este o MARGINE SUPERIOARĂ optimistă.
- O familie reclasificată `FR_FEZABIL` înseamnă doar: „dacă abaterea ar fi la marginea încă permisă de date, un
  învățăcel care pornește de la arhivă ar putea s-o demonstreze prospectiv în ≤ 5 ani”. Nu înseamnă predicție.
