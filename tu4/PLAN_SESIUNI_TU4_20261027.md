# PLAN PE SESIUNI — TU4 „Pauli–Born Lab” (redactat 2026-10-27, Mesajul 51, după `FIN_PASS` al TU3)

Document de planificare (NU protocol, NU cod, NU rezultat). Deciziile aparțin agentului (Mesajul 51: „nu mă întreba
nimic … deciziile îți aparțin 100%”). Fiecare sesiune = UN submodul, cu protocol scris și sigilat ÎNAINTE de cod,
cod + teste + verificator SEPARAT, apoi oprire + `predari/OPERATIV.md` + supliment + `predari/genereaza_predare.py`.
`positive_claims_allowed=false`. Calcul clasic (CPU/GPU); „cuantic” = matematică exactă a statisticilor cuantice,
nu hardware cuantic.

## 1. De ce TU4 și nu „LQG v10” (demolarea, pe scurt)

1. Sub ipoteza extragerilor independente și uniforme, P(extragerea t+1 | tot istoricul) = 1/C(n,k). Nicio
   transformare a istoricului (rețea de spin, CFT, polinom Jones, MPS) nu creează informație. Depozitul a verificat
   empiric asta de zeci de ori (DL, PG, CF, RH, LS, FS, AT, EC, QL649, BO/WU/GL/SE/CS/PL649, S8 5/40 + Joker):
   0 promovări. Încă o reformulare ar fi o „familie redenumită”.
2. Ce rămâne ADEVĂRAT și nefolosit până acum: (a) legea EXACTĂ a câștigurilor pentru unul sau mai multe bilete;
   (b) faptul că, pentru un PORTOFOLIU de m bilete, media câștigurilor nu depinde de alegere, dar FORMA distribuției
   (probabilitatea de a câștiga ceva, varianța, coada) depinde numai de suprapunerile dintre bilete; (c) singura cale
   onestă de a detecta vreodată o urnă părtinitoare este un test SECVENȚIAL valid oricând (martingale de testare),
   pornit ÎNAINTE de datele pe care le judecă.
3. Aici statisticile cuantice sunt exacte, nu decorative: biletele de 6 din 49 sunt exact stările a 6 FERMIONI în
   49 de moduri (determinanți Slater, excluziunea Pauli = un număr nu apare de două ori); spațiul biletelor este
   schema de asociere Johnson J(n,k), al cărei spectru se cunoaște EXACT (polinoamele Eberlein / Hahn duale);
   „repulsia Pauli” între bilete = procese punctuale determinantale (Macchi 1975; Hough–Krishnapur–Peres–Virág 2006;
   Kulesza–Taskar 2012); „observatorul” onest = e-procesele Shafer–Vovk / Ville 1939 / Ramdas et al. 2023.

## 2. Arhitectura (nou, aditiv; nimic înghețat nu se atinge)

- Director nou `tu4/` (module, teste, verificatori, rezultate); UI prin inserții în `tu3/ui_tu3.py` numai cu înregistrări
  `tu3/inlocuiri/INLOCUIRE_TU4_<cod>_<UTC>Z.json` (mecanismul `inlocuiri_tu3/v1`), taburile 13–15 în toate 3 modurile.
- `engine.py`, `parser.py`, `tu3/parser_multi.py`, `tu3/motor_n.py`, `tu3/motor_joker.py`, `app.py`, `validare.py`,
  `tu3/scor_real.py`, `tu3/verifica_sr.py`, pistele închise, rezultatele publicate: BYTE-IDENTICE.
- Exactitate: numărări în întregi (`int64`/Python `int`), probabilități ca `fractions.Fraction`; GPU numai pentru
  enumerări complete (popcount pe măști de 64 de biți), cu verificator CPU independent (NumPy, fără torch).
- Datele: numai citire din arhivele existente (înghețate pentru calibrare, LIVE pentru auditorul prospectiv).

## 3. Sesiunile

| Sesiune | Cod | Submodul | Livrabil verificabil |
|---|---|---|---|
| S10 | EX | Legea exactă „Born” a câștigurilor, 3 jocuri, 1..m bilete | `tu4/lege_exacta.py` + `tu4/verifica_ex.py` + teste; tabele exacte |
| S11 | JS | Schema Johnson: spectrul exact și tabelul de covarianță pe suprapuneri | `tu4/schema_johnson.py` + verificator; teoreme-martor |
| S12 | FE | Portofolii fermionic / bosonic / clasic + certificate Delsarte | `tu4/portofoliu.py` + verificator; comparația exactă |
| S13 | EA | Auditorul valid oricând (e-procese) pe 6/49, 5/40, Joker | `tu4/auditor_e.py` + calibrare sintetică + start prospectiv sigilat |
| S14 | UI | Taburile 13–15 „Pauli–Born” în toate modurile + repornire 8649 | inserții `ui_tu3.py` + `INLOCUIRE_TU4_UI_*` + AppTest |
| S15 | FIN4 | Regresie completă, `tu4/RAPORT_TU4.md`, checkpoint final | raport 0444 + predare |

**S10 — EX.** Regulile fiecărui joc (bile extrase, bile pe bilet, categoriile de câștig) se citesc din regulament și se
citează în protocol; dacă regulamentul nu e accesibil, categoriile = numărul de potriviri (declarat). Pentru un bilet:
legea hipergeometrică în `Fraction` (Joker = produsul EXACT 5/45 × 1/20, cuplaj zero). Pentru un portofoliu de m bilete
(m ≤ 16): enumerarea COMPLETĂ a rezultatelor (6/49: 13 983 816; 5/40: 3 838 380; Joker: 1 221 759 × 20) pe GPU, cu
histograma exactă (potrivirea maximă, numărul de bilete câștigătoare pe categorii). Martori: suma = C(n,k); media
potrivirilor = m·k·b/n EXACT pentru orice portofoliu (teorema invarianței mediei); GPU = CPU bit cu bit.

**S11 — JS.** Pentru J(n,k) din fiecare joc: numerele de intersecție, valorile proprii Eberlein și multiplicitățile,
exacte în `Fraction`; martor prin forță brută pe scheme mici (J(8,3), J(10,4)). Rezultat central (de demonstrat și
verificat): pentru orice prag t, Var(numărul de bilete cu ≥ t potriviri) = Σ_{i,j} c_t(|T_i ∩ T_j|), unde c_t(o) e un
tabel exact de k+1 valori ⇒ riscul unui portofoliu depinde NUMAI de distribuția suprapunerilor. Martor: formula =
enumerarea S10 pentru 200 de portofolii aleatoare.

**S12 — FE.** Trei familii cu aceeași medie (demonstrat în S10): **fermionic** (repulsie: suprapuneri mici —
maximizează P(cel puțin un câștig)), **bosonic** (aglomerare: suprapuneri mari — maximizează varianța, „totul pe o
carte”), **clasic** (bilete independente uniforme). Construcții: căutare exactă cu certificat pentru m mic; pentru m
mai mare, k-DPP cu nucleu în algebra Bose–Mesner, eșantionat prin lanțul de schimb (aproximativ, declarat), dar EVALUAT
exact (S10/S11). Certificate de optimalitate: marginea de programare liniară Delsarte pe schema Johnson (limita
superioară a numărului de bilete cu suprapuneri ≤ s). Afirmații permise numai matematice („portofoliul X are
P(≥ 1 câștig) = p exact”); NU „câștigi mai des la loterie” în sensul mediei.

**S13 — EA.** H0 = extrageri iid uniforme. E-proces = produsul factorilor q_t(extragere)/u, unde q_t este o lege
predictivă VALIDĂ pe cele C(n,k) rezultate (normalizare exactă prin polinoamele simetrice elementare e_k(w)), amestec
fixat dinainte de 3 pariori (frecvențe Laplace, suprapunere cu extragerea precedentă, bila Joker). Garanția Ville:
P_H0(sup_t E_t ≥ 1/α) ≤ α, α = 0.01 fixat. Calibrare sintetică (10⁴ istorii nule: alarme ≤ α + eroarea MC) și putere
pe urne părtinitoare sintetice (γ). Pe arhiva deja explorată valoarea e este DESCRIPTIVĂ; componenta care contează
pornește la sigilare (`START_PROSPECTIV.json`) și acumulează numai extragerile LIVE ulterioare — fără setare,
fără oprire opțională interzisă (validă oricând prin construcție).

**S14 — UI.** Tab 13 „Legea exactă” (calculator de portofoliu), tab 14 „Pauli–Born” (fermionic / bosonic / clasic,
spectrul Johnson, certificatul Delsarte), tab 15 „Auditorul” (traiectoria log E_t, pragul 1/α, data START). Toate
etichetate „matematică exactă, fără avantaj predictiv”. AppTest pentru fiecare tab × 3 moduri; repornire 8649 cu
bucla `[lansator] health ok`.

**S15 — FIN4.** Toate suitele TU3 + TU4, verificatorii separați, matricea, DL read-only, `tu4/RAPORT_TU4.md` (0444),
checkpoint final.

## 4. Criterii comune de calitate (fiecare sesiune)

Protocol + sigiliu înaintea codului; verificator separat fără importuri din modulul verificat; rezultate 0444;
incidente publicate, nerescrise; primul pas read-only la început (hash-uri + suite + DL); servicii în fundal
verificate (timerul LIVE, `--verifica` dedup); nicio rulare reală pe istoric pentru selecție de bilete; nicio
promisiune de câștig.

## 5. Prompturile pentru chat nou (câte unul pe sesiune; perechea HANDOFF/PROMPT generată la fiecare checkpoint le
completează cu starea exactă)

**S10 (EX):**
> Continuă pista QL649 din ${QL649_ROOT:-.} ca același agent. Citește ÎNTÂI partea
> operativă din cel mai nou `predari/HANDOFF_QL649_*.md`, verifică `predari/VERIFICARE_PREDARE_*.json` și rulează
> „Primul pas exact” (read-only). Apoi TU4 S10 „EX” după `tu4/PLAN_SESIUNI_TU4_20261027.md` §3: protocol
> `tu4/PROTOCOL_TU4_EX.md` + sigiliu ÎNAINTE de cod; `tu4/lege_exacta.py` (Fraction + enumerare completă GPU),
> `tu4/verifica_ex.py` (CPU NumPy, independent), teste; martorii din plan. Fără subagenți, git numai ./dev-git fără
> add/commit, positive_claims_allowed=false, nimic înghețat atins. Deciziile îți aparțin; nu mă întreba. La final:
> OPERATIV.md, mesajele mele în supliment, genereaza_predare.py, promptul pentru S11.

**S11 (JS):**
> Continuă pista QL649 … (același antet ca S10). TU4 S11 „JS”: protocol `tu4/PROTOCOL_TU4_JS.md` + sigiliu înainte de
> cod; `tu4/schema_johnson.py` (numere de intersecție, valori proprii Eberlein exacte, tabelul c_t(o)), verificator
> separat prin forță brută pe J(8,3)/J(10,4) și prin enumerarea S10 pe 200 de portofolii. La final: predarea + promptul
> pentru S12.

**S12 (FE):**
> Continuă pista QL649 … TU4 S12 „FE”: protocol `tu4/PROTOCOL_TU4_FE.md` + sigiliu; `tu4/portofoliu.py` cu familiile
> fermionic / bosonic / clasic, evaluare exactă (S10/S11), certificatul Delsarte LP, k-DPP prin lanț de schimb
> (aproximare declarată); verificator separat. La final: predarea + promptul pentru S13.

**S13 (EA):**
> Continuă pista QL649 … TU4 S13 „EA”: protocol `tu4/PROTOCOL_TU4_EA.md` + sigiliu (α = 0.01, cei 3 pariori, amestecul
> fixat) ÎNAINTE de cod; `tu4/auditor_e.py`, calibrarea sintetică (10⁴ istorii nule) și puterea, apoi
> `START_PROSPECTIV.json` sigilat; valoarea pe arhiva veche = descriptivă. La final: predarea + promptul pentru S14.

**S14 (UI):**
> Continuă pista QL649 … TU4 S14 „UI”: protocol + sigiliu (lista `replaceable` exactă) înainte de cod; taburile 13–15
> prin inserții în `tu3/ui_tu3.py`, înregistrarea `tu3/inlocuiri/INLOCUIRE_TU4_UI_<UTC>Z.json` după teste, AppTest pe
> 3 moduri, repornirea 8649 cu bucla `[lansator] health ok`. La final: predarea + promptul pentru S15.

**S15 (FIN4):**
> Continuă pista QL649 … TU4 S15 „FIN4”: protocol scurt sigilat; regresia completă TU3 + TU4, verificatorii separați,
> matricea, DL; `tu4/RAPORT_TU4.md` (0444); checkpoint final.
