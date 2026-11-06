# PLAN PE SESIUNI — TU4 v2 „Tribunalul Predictiv” (redactat 2026-10-27T20:30Z, Mesajul 52)

Document de planificare (NU protocol, NU cod, NU rezultat). **Înlocuiește** `tu4/PLAN_SESIUNI_TU4_20261027.md`
(`fed6f657…`, păstrat neschimbat ca istoric). Mesajul 52: utilizatorul NU vrea distribuția biletelor pentru câștig
maxim (acceptă împărțirea câștigului); îl interesează **numai predicția**. Deciziile aparțin agentului.
`positive_claims_allowed=false` până când un criteriu prospectiv de mai jos este atins și confirmat.

## 0. Adevărul de pornire (fără el planul ar fi o promisiune falsă)

- Predicția există NUMAI dacă urna nu este perfect aleatoare (bile/mașini cu abateri fizice, dependențe între
  extrageri). Dacă extragerile sunt independente și uniforme, NICIUN algoritm nu poate prezice — teoremă, nu opinie.
- Pe arhiva actuală, zeci de modele preînregistrate (DL, PG, CF, RH, LS, FS, AT, EC, QL649, BO/WU/GL/SE/CS/PL649,
  S8 5/40 + Joker) au dat 0 promovări. Asta nu dovedește că urna e perfectă; arată că o eventuală abatere este MICĂ.
- Arhiva e deja explorată: orice „succes” nou găsit retrospectiv pe ea e suspect (prea multe încercări). De aceea
  TU4 v2 mută judecata pe **viitor**: predicția se emite și se sigilează ÎNAINTE de extragere și se judecă DUPĂ.
- Planul nu promite că va găsi predicție. Promite cel mai riguros mod de a o găsi dacă există și de a o demonstra
  fără autoînșelare — și de a spune clar când nu există.

## 1. Arhitectura „Tribunalului”

```
arhiva LIVE (timer 30 min) ──► modele calificate ──► EMITERE (înainte de extragere, sigilată SHA-256, append-only)
                                                          │
extragerea oficială ──► arhiva LIVE ──► JUDECĂTOR (e-proces valid oricând, vs uniform) ──► verdict în UI
```

- **Predicția** unui model = o distribuție de probabilitate pe numere (și pe bila Joker) + biletul ei „top” pentru
  extragerea următoare a fiecărui joc (6/49, 5/40, Joker).
- **Judecătorul** = e-proces (Ville 1939; Shafer–Vovk; Ramdas et al. 2023): E_T = Π_t q_t(extragerea t)/u(extragerea t),
  cu q_t legea VALIDĂ emisă înainte (normalizare exactă pe toate C(n,k) rezultatele) și u legea uniformă. Sub urna
  perfectă, P(E_T ajunge vreodată ≥ 1/α) ≤ α, oricând te-ai uita — deci se poate opri DEVREME fără trișare.
  Viteza: dacă modelul are cu adevărat informația D = KL(q‖u) pe extragere, durata tipică ≈ ln(1/α)/D extrageri.
- **Praguri fixate acum:** α_explorare = 0.01 (E ≥ 100) cu corecție pentru numărul de modele (E ≥ 100·M pentru M
  modele concurente); la atingere ⇒ faza de **confirmare**: model ÎNGHEȚAT, aceeași regulă, extrageri NOI, prag
  E ≥ 20. Numai după confirmare: afirmația „evidență statistică de predictibilitate pentru modelul X”.
  Închiderea: un model cu log E_T < −10 (evidență puternică împotriva lui față de uniform) se retrage; nu se reglează.

## 2. Sesiunile

| Sesiune | Cod | Submodul | Livrabil verificabil |
|---|---|---|---|
| S10 | FR | Frontiera predictibilității pe cele 3 arhive | cât de mare poate fi o abatere încă nedetectată; câte extrageri viitoare ar cere demonstrarea ei |
| S11 | IP | 3 ipoteze predictive NOI și DISTINCTE, preînregistrate, calificate pe sintetic | modele cu martor de informație + martor de decizie; numai cele calificate intră în tribunal |
| S12 | EM | Emițătorul prospectiv | `tu4/emite.py`: predicția pentru extragerea următoare, sigilată înaintea orei extragerii, jurnal append-only |
| S13 | JU | Judecătorul e-proces + decontarea automată după fiecare extragere | `tu4/judecator.py` + verificator separat; calibrare sintetică (10⁴ istorii nule) |
| S14 | UI | Tabul „Predicție prospectivă” în toate 3 modurile | predicțiile curente, ora sigiliului, traiectoria log E, starea fiecărui model |
| S15 | FIN4 | Regresie, raport, tribunalul rămâne PORNIT | checkpoint; apoi sesiuni scurte de decontare/raport la cerere |

**S10 — FR (frontiera).** Pentru fiecare joc: (a) posterior Dirichlet exact pe abaterile marginale ale fiecărui
număr/bile (și pe bila Joker), (b) dependența dintre extrageri consecutive (suprapunerea față de legea hipergeometrică
exactă), (c) dependența între numere în aceeași extragere. Rezultat: limita superioară credibilă (95%) a informației
D_max pe care orice model de acest tip ar putea-o avea și, de aici, numărul de extrageri viitoare necesare pentru
E ≥ 100 dacă abaterea ar fi la limită. Dacă D_max ⇒ ani de așteptare, se spune deschis. Inventar, nu selecție.

**S11 — IP (ipoteze).** Agentul verifică lista familiilor închise (AGENTS.md; fără redenumiri, fără HMM/restart/
solver/adaptor/generator) și alege 3 ipoteze cu sursă de informație DIFERITĂ, de exemplu: (1) abatere fizică
staționară cu contracție bayesiană optimă (estimator James–Stein / Dirichlet ierarhic), calibrată de S10, nu
frecvența brută B; (2) schimbare lentă a urnei (drift al bilelor: model cu stare continuă, fără regimuri discrete);
(3) cuplaj fizic în aceeași seară între jocuri (dacă S10 arată că datele o permit și familia nu e închisă). Pentru
fiecare: protocol + sigiliu ÎNAINTE de cod, martori de informație/decizie pe date sintetice cu abatere implantată
(putere ≥ 0.8 la abaterea-limită S10), fals-pozitive ≤ α pe date nule. Fără calificare ⇒ nu intră în tribunal.
Arhiva reală servește NUMAI la antrenarea stării de start, nu la alegerea modelului.

**S12 — EM (emitere).** `tu4/emite.py --joc {649,540,joker}`: citește arhiva LIVE, rulează modelele calificate
ÎNGHEȚATE, scrie `tu4/tribunal/emisii/<joc>/<data_extragerii>.json` (0444) cu distribuțiile, biletele top,
`emitted_utc` < ora oficială a extragerii, sha-ul arhivei folosite și sha-ul codului; lanț append-only (fiecare emisie
conține sha-ul celei precedente). Emisia se pornește printr-o comandă (sau pictogramă). **Emisia automată din timer
cere ridicarea gardului prognozei automate (D1), care rămâne decizia explicită a utilizatorului** — fără ea, agentul
nu-l atinge; sistemul funcționează și manual.

**S13 — JU (judecător).** După fiecare extragere nouă apărută în arhiva LIVE, decontarea calculează factorul e al
fiecărui model numai pentru emisiile sigilate ÎNAINTEA extragerii (emisiile întârziate sunt respinse automat),
actualizează E_T, scrie `tu4/tribunal/decontari/…` (0444). Verificator separat (stdlib + NumPy, fără importuri din
modele). Decontarea poate rula din timerul existent (citește, nu prezice) printr-un drop-in nou, sigilat.

**S14 — UI.** Tab nou „Predicție prospectivă”: pentru extragerea următoare a jocului ales — biletul top al fiecărui
model + distribuția pe numere, ora sigiliului; dedesubt, istoricul emisiilor decontate, numărul de potriviri,
traiectoria log E_T față de pragul de explorare și de confirmare. Etichetă permanentă: „test științific în curs;
nu este sfat de joc”.

**S15 — FIN4.** Regresie completă TU3 + TU4, raport, checkpoint. Tribunalul rămâne pornit; verdictele apar singure,
la ritmul extragerilor (6/49 și 5/40 de 2 ori pe săptămână, Joker de 2 ori).

## 3. Ce NU face planul

- Nu antrenează și nu selectează modele pe arhiva veche pentru a le declara „bune” (o asemenea „predicție” s-a dovedit
  iluzorie de zeci de ori). Nu reia modelele închise. Nu reglează nimic după ce vede emisiile decontate.
- Nu promite câștig sau termen. Dacă urna e corectă, tribunalul va arăta E_T ≈ fluctuând sub 1 — și acesta este, la
  rândul lui, un rezultat corect și publicat.
- Nu modifică gardul D1, linger-ul sau pista OGLINDA (separată, cu regulile ei).

## 4. Prompturile pentru chat nou

**S10 (FR):**
> Continuă pista QL649 din ${QL649_ROOT:-.} ca același agent. Citește ÎNTÂI partea
> operativă din cel mai nou `predari/HANDOFF_QL649_*.md`, verifică `predari/VERIFICARE_PREDARE_*.json` și rulează
> „Primul pas exact” (read-only). Apoi TU4 v2 S10 „FR” după `tu4/PLAN_SESIUNI_TU4_v2_20261027.md` §2: protocol
> `tu4/PROTOCOL_TU4_FR.md` + sigiliu ÎNAINTE de cod; frontiera predictibilității pe 6/49, 5/40, Joker (posterior
> exact, D_max, extrageri necesare pentru E ≥ 100); verificator separat. Fără subagenți, git numai ./dev-git fără
> add/commit, positive_claims_allowed=false, nimic înghețat atins. Deciziile îți aparțin; nu mă întreba. La final:
> OPERATIV.md, mesajele mele în supliment, genereaza_predare.py, promptul pentru S11.

**S11 (IP):** > Continuă … (același antet). TU4 v2 S11 „IP”: verifică familiile închise; 3 ipoteze distincte, fiecare cu
> protocol + sigiliu înainte de cod, martori de informație/decizie, calificare pe sintetic calibrată de S10. La final:
> predarea + promptul pentru S12.

**S12 (EM):** > Continuă … TU4 v2 S12 „EM”: protocol + sigiliu; `tu4/emite.py` cu lanț append-only sigilat înaintea
> orei extragerii; prima emisie reală pentru extragerile următoare ale celor 3 jocuri. La final: predarea + S13.

**S13 (JU):** > Continuă … TU4 v2 S13 „JU”: protocol + sigiliu (praguri din plan §1, neschimbate); `tu4/judecator.py`,
> verificator separat, calibrare nulă 10⁴, drop-in de decontare sigilat. La final: predarea + S14.

**S14 (UI):** > Continuă … TU4 v2 S14 „UI”: protocol + sigiliu (lista replaceable exactă); tabul „Predicție prospectivă”
> prin inserții în `tu3/ui_tu3.py` + `INLOCUIRE_TU4_UI_<UTC>Z.json`; AppTest; repornire 8649 cu bucla health ok.

**S15 (FIN4):** > Continuă … TU4 v2 S15 „FIN4”: regresie TU3 + TU4, `tu4/RAPORT_TU4.md`, checkpoint; tribunalul rămâne
> pornit.
