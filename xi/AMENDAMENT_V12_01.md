# AMENDAMENT V12_01 — decizia despre un predictor se ia PE ARHIVE; extragerile viitoare nu mai sunt poartă

Plan amendat: `xi/PLAN_V12_PREDICTIE.md` (`a675289e…`, NEMODIFICAT). Protocol vizat: `xi/PROTOCOL_XI_P2.md` §8.
Scris și sigilat la 2026-11-01, înaintea oricărui cod, calcul sau acces la rezerve. `positive_claims_allowed=false`.

## Motiv

Utilizatorul a cerut explicit testarea pe arhive, nu așteptarea extragerilor viitoare (Mesajele 120–121 și 132 din
supliment). Planul V12 a respectat asta în P1 (arhiva RO) și P2 (arhive străine cu parte rezervată oarbă), dar a
păstrat P3 (confirmare prospectivă, minim 104 extrageri) ca poartă obligatorie înaintea integrării. Partea rezervată
oarbă, separată la descărcare și necitită, este deja un test de confirmare pe date pe care nu le-am văzut; P3 nu adaugă
o garanție statistică de alt tip, doar timp.

## Schimbarea (exactă)

1. **Confirmarea se face pe arhive.** Un predictor care respinge uniformul pe dezvoltare (pragurile XI-P2, neschimbate)
   ȘI apoi pe partea rezervată oarbă (o singură rulare, Holm, pragurile XI-P2 §7–8, neschimbate) primește verdictul
   **`CONFIRMAT_PE_ARHIVA`** (în loc de „candidat pentru P3”).
2. **Integrarea nu mai așteaptă P3.** Un predictor `CONFIRMAT_PE_ARHIVA` poate intra direct în motorul C3 (probabilități
   modificate în locul uniformului) și pe ecran, cu eticheta exactă „confirmat pe arhivă (test orb), neconfirmat
   prospectiv”.
3. **P3 devine monitorizare opțională**, în paralel, fără să blocheze nimic: dacă există un predictor confirmat, emisiile
   lui se înregistrează și se decontează ca în faza F, numai informativ.
4. Pentru o **ipoteză nouă și distinctă** (rezervele sunt de unică folosință): protocol nou sigilat înainte de cod →
   dezvoltare pe partea deja citită a arhivelor → o singură rulare pe rezerva sigilată → verdict imediat. Durata
   depinde de calcul, nu de calendar.

## Ce NU se schimbă

- Pragurile, separarea dezvoltare/rezervă, corecția pentru testări multiple, o singură folosire a rezervei.
- Rezultatele P1/P2 deja publicate (niciun supraviețuitor). Amendamentul nu are efect retroactiv și nu „salvează”
  niciun predictor închis.
- `positive_claims_allowed=false`: chiar `CONFIRMAT_PE_ARHIVA` nu înseamnă câștig sau profit garantat. Abaterea
  găsită poate fi prea mică pentru profit după reținerea operatorului; se raportează câștigul așteptat calculat.
- Faza F (registrul pe hârtie) nu este un test de predicție; măsoară strategii de împărțire a bugetului (C1/C3/RND).
