# PROTOCOL XI-F — registrul de joc pe hârtie (planul V11, faza F / componenta C5)

Scris și sigilat (`xi/SIGILIU_XI_F.json`) ÎNAINTE de orice cod F și de orice înregistrare. Autoritate: Mesajele
107/108, cererea din 2026-10-31 (Mesajul 125: „apoi faza F (registrul pe hârtie)”), `xi/PLAN_V11_QL_XI.md` §2 C5 și §5
faza F (poarta G5: „primele decontări verificate”). `positive_claims_allowed=false`. Calcul clasic, CPU, Python
standard (fără NumPy, fără GPU, fără `quantum_limit`). Fără bani reali, fără timere, fără joburi autonome: fiecare
înregistrare și fiecare decontare se lansează manual de agent într-o sesiune.

## 0. Ce este și ce nu este

- **Este:** un jurnal sigilat, append-only, în care strategiile deja construite (C1, C3) și un control aleator își
  „joacă pe hârtie” biletele pentru o extragere viitoare, ÎNAINTE de cutoff, urmat de decontarea la plățile reale
  publicate. Rezultă un profit/pierdere verificabil pe date viitoare, fără bani.
- **Nu este:** o predicție sau o recomandare. Biletele NU se afișează în aplicație și nu se emit nicăieri; există numai
  în registru, pentru decontare. Toate strategiile au ρ < 1 (C1, C3): pierderea pe hârtie este rezultatul așteptat.
  Un orizont de câteva extrageri este zgomot; nu se trage nicio concluzie din câștiguri sau pierderi izolate.

## 1. Fișiere

- Registrul: `xi/rezultate/F/LANT_STRATEGII.jsonl` (append-only; 0444 între scrieri).
- Decontările: `xi/rezultate/F/DECONTARI_STRATEGII.jsonl` (append-only; 0444 între scrieri).
- Cod: `xi/f/inregistreaza.py` (registratorul) și `xi/f/deconteaza.py` (judecătorul F) — module separate, fără cod
  comun (separarea rolurilor: registratorul nu poate deconta, judecătorul nu poate înregistra); `xi/f/verifica_f.py`
  (verificator independent, nu importă niciunul dintre ele); `xi/f/teste_f.py` (calificare).
- Judecătorul TU4 existent (`tu4/judecator.py`, `tu4/tribunal/`) NU se atinge și NU se refolosește: el decontează
  e-procese H1/H3, are lanț propriu sigilat și face parte din verificările C1; registrul F este un flux separat.

## 2. Formatul registrului (lanț de hash-uri)

Fiecare linie este un obiect JSON canonic (`sort_keys`, separatori `(",", ":")`, UTF-8) cu câmpurile: `seq` (0, 1, …),
`prev_sha256` (sha-ul liniei precedente; 64 de zerouri la prima), `tip` = `INREGISTRARE`, `tinta` = {`data`, `joc`},
`strategie` (identificator §3), `sursa` (fișier + sha256 al sursei biletelor sau regula seed-ului), `bilete` (listă de
liste sortate de numere; la Joker ultimul element este bila Joker, 1..20), `nr_bilete`, `pret_bilet`, `miza`,
`utc_inregistrare`, `cutoff_utc`, `protocol_sha256`, `cod_sha256`, plus `sha256` = sha-ul obiectului fără câmpul
`sha256`. Decontările au același format de lanț (`tip` = `DECONTARE`, `ref_seq`, `ref_sha256`, rezultatul §5).

## 3. Strategiile v1 (ținta 2026-11-01; jocurile 6/49, 5/40, Joker)

| Identificator | Joc | Bilete | Sursa |
|---|---|---|---|
| `C1_SG324Q` | 6/49 | 324 | `xi/rezultate/C1/designuri/SG324Q.json` (`b8305030…`, egal cu `file_sha256` din `C1_EVALUARE.json`) |
| `C1_JS135Q` | Joker | 135 | `xi/rezultate/C1/designuri/JS135Q.json` (`add35bb7…`, idem) |
| `C3_<joc>_B<B>_mu<μ>` | toate | K (C3) | `xi/rezultate/C3/C3_REZULTATE.json` (`01331654…`), varianta P, B ∈ {40, 100, 500}, μ ∈ {0, 1000}: 18 portofolii |
| `RND_<joc>_B<B>` | toate | K (C3) | control aleator, regula de mai jos: 9 portofolii |

- Controlul aleator: pentru (data, joc, B), seed = întregul din `sha256("XI-F|RND|<data>|<joc>|<B>|<protocol_sha256>")`;
  `random.Random(seed)`; K bilete distincte, fiecare `sorted(rnd.sample(range(1, n+1), k))` cu (n, k) = (49, 6),
  (40, 5), (45, 5) (+ `rnd.randint(1, 20)` la Joker); un bilet repetat se re-extrage. Seed-ul depinde de sha-ul acestui protocol, sigilat înaintea extragerii.
- Prețuri: 6/49 8 lei, 5/40 5 lei, Joker 7 lei (aceleași ca în C1/C3/C4). Miza = nr_bilete × preț.
- **Ținte ulterioare:** C1 și RND se pot înregistra de același cod pentru orice extragere regulată viitoare (joi și
  duminică), manual, înaintea cutoff-ului. C3 pentru o altă dată cere un amendament sigilat (sigiliile produsului
  folosite de C3 sunt fixate pe 2026-11-01). O țintă neînregistrată nu se completează retroactiv.

## 4. Regula cutoff-ului

Cutoff = **16:00 Europe/Bucharest** în ziua extragerii (aceeași regulă ca TU4; extragerea este la 18:30). Registratorul
refuză: (a) după cutoff; (b) dacă baza curentă (`loto_romania/data/CURRENT.json` → snapshot) conține deja extragerea
regulată pentru (data, joc); (c) dacă (data, strategie) este deja înregistrată; (d) dacă sha-ul unei surse diferă.
Ținta 2026-11-01 are cutoff 2026-11-01T14:00:00Z. Sha-ul capului lanțului se scrie în `OPERATIV.md` și în predare
(martor cu marcaj temporal independent de registru).

## 5. Decontarea (judecătorul F)

- Date: snapshot-ul din `CURRENT.json` (sqlite, `mode=ro`): `draws` (game, draw_date, draw_kind = `regular`, n1..n6,
  joker, `has_source_disagreement`, `selected_observation`) și `prizes` (pe `observation_id = selected_observation`).
- Condiții: extragerea regulată există, `has_source_disagreement = 0`, toate categoriile jocului prezente cu `status` ∈
  {`paid`, `rollover`}. Altfel: `IN_ASTEPTARE` (nu se scrie nimic). După 14 zile fără date valide: `VOID` (se scrie).
- Categoriile (ca în C4; baza păstrează ordinea extragerii n1..n6): 6/49 (bilet de 6) I–IV = 6/5/4/3 nimeriri;
  5/40 (bilet de 5, se extrag 6 numere) I = toate cele 5 numere ale biletului printre primele 5 extrase (n1..n5),
  II = 5 nimeriri printre cele 6 extrase, altfel decât I, III = 4 nimeriri; Joker (bilet de 5 + bila) I = 5+J, II = 5,
  III = 4+J, IV = 4, V = 3+J, VI = 3, VII = 2+J, VIII = 1+J (5 din 45 + bila 1 din 20). Fiecare bilet primește cel mult
  o categorie (cea mai înaltă).
- Plata pe categorie c, cu m bilete proprii câștigătoare (m ≥ 1): categoria fixă (6/49 IV): m · ppw; categorie
  `paid` cu w câștigători oficiali: m · ppw · w / (w + m) (biletele proprii se adaugă fondului oficial); categorie
  `rollover`: fondul reportat `carryover` (o singură dată, împărțit între biletele proprii) — convenția C4. Valorile
  lipsă (`ppw`/`carryover` nule acolo unde sunt necesare, `w` nul la `paid`) ⇒ `IN_ASTEPTARE`.
- Ieșire per înregistrare: numerele extrase, numărul de bilete pe categorie, plata totală, net = plată − miză, sha-ul
  snapshot-ului, `utc_decontare`. Agregatul pe strategie (miză, plăți, net cumulat, fracție returnată) în raport.

## 6. Verificarea și porțile

- `verifica_f.py registru`: lanțul (prev/sha), câmpurile, reproducerea biletelor din surse (sha) și din seed (RND),
  `utc_inregistrare < cutoff_utc`, extragerea absentă din baza la înregistrare (consemnat de registrator), cele 29 de
  strategii pentru 2026-11-01, modurile 0444. **G5a = PASS** dacă trec toate.
- `verifica_f.py decontare`: recalcul independent al categoriilor și plăților din baza (alt cod), lanțul decontărilor.
  **G5 (poarta planului) = PASS** la primele decontări verificate (într-o sesiune ulterioară extragerii).
- Calificare (`teste_f.py`, înainte de sigilarea codului; numai directoare temporare): T1 categoriile pe extrageri
  sintetice construite pentru fiecare categorie a fiecărui joc; T2 regula de plată pe un tabel sintetic (fix, `paid`
  cu m = 1 și m = 2, `rollover`); T3 refuzul după cutoff și la extragere deja existentă; T4 detectarea alterării
  lanțului; T5 reluare istorică într-un registru temporar: designurile C1 decontate pe ultima extragere din baza
  curentă au plată ≥ premiul minim garantat (`E1 = 0`), iar judecătorul și verificatorul dau același rezultat.

## 7. Ordinea

1. Acest protocol + sigiliu. 2. Cod + calificare + sigiliul codului `xi/f/SIGILIU_COD_F.json`. 3. Înregistrarea
pentru 2026-11-01 (o singură rulare, înainte de cutoff) + `verifica_f.py registru`. 4. După extragere și publicarea
plăților: decontarea + `verifica_f.py decontare` + `RAPORT_F.md`. Orice defect după sigilare ⇒ incident + amendament
sigilat înainte de corecție; liniile scrise nu se modifică niciodată (corecțiile sunt linii noi).

## 8. Interpretare (fixată)

Registrul arată pe date viitoare ce face fiecare strategie, nu ce promite. Așteptarea, din C1/C3: pierdere medie
(fracție returnată ~0.3–0.5), cu designurile C1 câștigând ceva la fiecare extragere. Nicio diferență între strategii pe
câteva extrageri nu este semnificativă; controlul aleator există tocmai pentru comparație. Nu se afirmă avantaj,
profit sau noutate.
