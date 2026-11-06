# PROTOCOL TU3-DD — submodulul „Deduplicarea versiunilor arhivei LIVE” (compactare FĂRĂ PIERDERI, verificabilă)

Sesiunea 2026-10-26 (start ~18:36Z), continuare din checkpoint-ul 20261026T182614Z. Utilizatorul a cerut un singur
submodul și a delegat alegerea (Mesajul 35 + răspunsul „da unul singur alege tu”, Mesajul 36); agentul a ales deduplicarea (Observația din
163435Z; `versiuni/` = 20 MB la 18:36Z, +~3 MB/ciclu de 30 min ≈ 160 MB/zi). Scris și sigilat ÎNAINTE de orice cod:
`tu3/dedup_live.py`, `tests/test_dedup_live.py`, `tu3/rezultate/DD/` și drop-in-ul `tu3-dedup-live.conf` NU există la
sigilare (verificat în `tu3/SIGILIU_TU3_DD.json`).

## 0. Încadrare onestă

- Submodul de STOCARE. Nu introduce niciun model, niciun scor, nicio variantă; nu citește extragerile în alt scop decât
  verificarea octet-cu-octet. Doar biblioteca standard (rulează cu `/usr/bin/python3`, ca `arhiva_live.py`).
  `positive_claims_allowed=false`. Calcul clasic; nu se rulează niciun motor.
- NEMODIFICATE (hash-uri în sigiliu): cele 21 de fișiere înghețate din `SIGILIU_TU3_VS.json` (inclusiv
  `tu3/arhiva_live.py`, `engine.py`, `parser.py`, `app.py`, `tu3/parser_multi.py`, `tu3/motor_n.py`, `tu3/motor_joker.py`,
  `tu3/ui_tu3.py`), plus `run_app.sh` (`a8f38cea…`), `run_app_tu3.sh`, `tu3/matrice_init.py`, `tu3/validare_tu3.py`,
  `tests/test_validare_tu3.py`, protocoalele/sigiliile/rapoartele VS și drop-in-ul existent `tu3-arhiva-live.conf`.
  Integritatea matricei (21 de fișiere) trebuie să rămână `OK`.
- Neatinse: colectorul și baza lui (`loto_romania/`), `CURRENT_LIVE.json`, `ISTORIC_LIVE.jsonl`, exporturile înghețate,
  protocolul prospectiv și GARDUL lui (kernel 7.0.11→7.2.6 — decizia utilizatorului), OGLINDA, DL (numai read-only).
- 6/49 pe LIVE și matricea în lansatorul pictogramei rămân submodule separate, neîncepute.

## 1. Observația care motivează (inventar, nu experiment)

Fiecare ciclu publică `versiuni/<sha12>/` complet (≈3.3 MB: `extrageri_{649,540,joker}.jsonl` ≈ 3.2 MB + `decision.json`
≈ 110 KB + `colectare.json` ≈ 16 KB + `MANIFEST_LIVE.json`). Baza colectorului se reconstruiește la fiecare rulare, deci
`database_sha256` se schimbă chiar fără extrageri noi; fiecare rând JSONL poartă
`provenance = {"database_sha256", "run_id"}`, deci fișierele diferă la fiecare ciclu deși extragerile sunt identice.
Hardlink-urile la nivel de fișier NU ajută; redundanța este la nivel de conținut (rânduri fără `provenance`).

## 2. Regula de compactare (determinist, fără pierderi)

Definiții, pentru `versiuni/` (numai directoare cu `MANIFEST_LIVE.json`; directoarele ascunse `.tmp_*` ale arhivei sunt
ignorate):
- **Protejate** (niciodată compactate; dacă sunt găsite compactate, sunt REHIDRATATE byte-exact): versiunea din
  `CURRENT_LIVE.json["version_dir"]` și `CURRENT_LIVE.json["previous"]` (un cititor poate citi încă versiunea precedentă
  imediat după mutarea pointerului).
- **Cheia de conținut** K(V) = sha256 peste, pentru jocurile `649`, `540`, `joker` în această ordine, rândurile JSONL cu
  cheia `provenance` eliminată, re-serializate exact ca în `arhiva_live.py`
  (`json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n"`).
- **Reprezentantul** clasei K = cea mai veche versiune cu cheia K (ordinea: `created_utc` din manifest, apoi numele).
  Pentru că versiunile doar se adaugă, reprezentantul unei clase nu se mai schimbă.

Forma compactă a unei versiuni V ne-protejate (directorul rămâne `versiuni/<sha12>/`, 0755, fișiere 0444):
- `MANIFEST_LIVE.json` — NESCHIMBAT (aceiași octeți, deci același `manifest_sha256`).
- `decision.json.gz`, `colectare.json.gz` — gzip determinist (`mtime=0`, nivel 9) al originalelor.
- JSONL: dacă V este reprezentantul clasei → `extrageri_<joc>.jsonl.gz` (gzip, autonom); altfel → nimic stocat, ci
  referință `ref` la reprezentant: reconstrucția = rândurile reprezentantului (materializate) cu
  `provenance := {"database_sha256": manifest(V).database_sha256, "run_id": manifest(V).run_id}`, re-serializate ca mai sus.
- `DEDUP_LIVE.json` — schema `tu3-dedup-live/1`: pentru FIECARE fișier original: `sha256`, `bytes`, `method`
  (`gzip` / `ref`), `stored` + `stored_sha256` (la gzip), `ref` + `ref_manifest_sha256` (la ref); cheia de conținut;
  `compacted_utc`; `positive_claims_allowed=false`. Adâncimea referințelor = 1 (un `ref` indică numai un reprezentant
  care își stochează singur datele — complet sau gzip — niciodată alt `ref`).

**Invariant (poarta de siguranță):** o versiune se compactează NUMAI dacă materializarea formei compacte (construită
într-un director temporar) dă exact octeții originali pentru TOATE fișierele (sha256 egal cu originalul și, la JSONL, cu
manifestul). Altfel versiunea rămâne completă și se jurnalizează motivul. Nimic nu se șterge ireversibil: orice octet al
oricărei versiuni rămâne reconstructibil (`--reconstruieste`).

**Înlocuire atomică + recuperare:** temporar `.dedup_tmp_<nume>_<pid>` → `rename(V, .dedup_old_<nume>)` →
`rename(tmp, V)` → ștergerea `.dedup_old_<nume>`. La fiecare pornire (sub lacăt): `.dedup_old_X` cu `X` absent ⇒ redenumit
înapoi; cu `X` prezent și valid ⇒ șters; cu `X` prezent și invalid ⇒ `X` mutat în `.dedup_bad_X`, `.dedup_old_X` redenumit
înapoi; `.dedup_tmp_*` rămase ⇒ șterse. Concurență: același lacăt `tu3/date/live/.lock` (flock exclusiv) ca
`arhiva_live.py`.

Coliziune declarată: dacă vreodată colectorul ar produce o bază cu sha identic unei versiuni deja compactate,
`arhiva_live.py` (nemodificat) ar refolosi directorul compact; `parser_multi.resolve_live` ar refuza explicit
(„JSONL LIVE absent” — fail-closed), iar următoarea trecere `dedup_live.py` (imediat după, în același lanț
`ExecStopPost`) rehidratează versiunea protejată. Probabilitate practic nulă; tratată, nu ignorată.

## 3. Interfața `tu3/dedup_live.py`

`--simulare` (nu scrie nimic; raportează acțiunile și economia), `--automat` (recuperare → rehidratare protejate →
compactare; cod de ieșire mereu 0, ca `arhiva_live.py --automat`), `--verifica` (materializează TOATE versiunile și
compară cu manifestul și cu `DEDUP_LIVE.json`; ieșire 0/1), `--reconstruieste <sha12> --out <dir>` (scrie fișierele
originale byte-exact în afara arhivei), `--live-root <cale>` (pentru teste). Jurnal: linii
`[tu3-dedup-live <UTC>] …` pe stdout și `tu3/date/live/DEDUP_LIVE.jsonl` (o linie per acțiune: versiune, metodă,
octeți înainte/după).

## 4. Automatizare

Drop-in NOU, separat (cel existent rămâne byte-identic):
`~/.config/systemd/user/loto-actualizare.service.d/tu3-dedup-live.conf` cu
`ExecStopPost=/usr/bin/python3 -B …/tu3/dedup_live.py --automat`, apoi `systemctl --user daemon-reload`.
Ordinea lexicală a drop-in-urilor (`tu3-arhiva-live.conf` < `tu3-dedup-live.conf`) face ca deduplicarea să ruleze DUPĂ
publicare. Se verifică cu `systemctl --user show loto-actualizare.service -p ExecStopPost` (două intrări, în această
ordine). Nu atinge `ExecStart`, prognoza sau gardul ei. Dezactivare: ștergerea fișierului + `daemon-reload`.

## 5. Teste `tests/test_dedup_live.py` (pe o arhivă LIVE SINTETICĂ în director temporar, construită cu exact formatul
`arhiva_live.py`) — toate 11 trebuie să treacă

T1 compactare fără pierderi (materializare = octeții originali, toate fișierele, toate versiunile); T2 protejatele
(curentă + precedentă) rămân byte-identice, fără `DEDUP_LIVE.json`; T3 reprezentantul = cea mai veche din clasă, gzip
autonom; restul `ref`; clase diferite nu se referă reciproc; adâncime 1; T4 refuz: reprezentant falsificat ⇒ nicio
compactare peste el, originalul păstrat; `--verifica` dă 1 pe o versiune compactă falsificată; T5 idempotență (a doua
trecere nu schimbă nimic); T6 recuperare după întrerupere (cele trei stări din §2); T7 rehidratarea unei protejate
găsite compacte ⇒ fișiere byte-exacte, `parser_multi.resolve_live` trece; T8 `--reconstruieste` byte-exact; T9
`--simulare` nu scrie nimic (arborele identic, octet cu octet); T10 `parser_multi.resolve_live("540")` și `("joker")` trec
pe arhiva sintetică după compactare; T11 fișierele înghețate au hash-urile din sigiliu și `dedup_live.py` importă numai
biblioteca standard (niciun motor, niciun model).

## 6. Rularea reală (UNICĂ) pe `tu3/date/live/` — praguri fixate acum

R1 inventar înainte: sha256 + mărimea fiecărui fișier din fiecare versiune completă; fiecare JSONL = sha din manifestul
lui (altfel STOP). R2 `--simulare` (descriptiv). R3 o singură trecere reală (`--automat`, sub lacăt), cu raport
`tu3/rezultate/DD/DEDUP_TU3_<UTC>Z.json` (0444, refuz de suprascriere). R4 după: `--verifica` = 0 și, pentru FIECARE
fișier inventariat la R1, octeții materializați au exact sha-ul de la R1 (100 %, fără excepție); protejatele au octeți
și inode-uri neschimbate; `CURRENT_LIVE.json` și `ISTORIC_LIVE.jsonl` byte-identice. R5 mărimea `versiuni/` după
≤ 50 % din mărimea de la R1 (descriptiv suplimentar: estimarea creșterii pe ciclu). R6 produsul: `parser_multi`
rezolvă 540 și Joker pe LIVE; matricea „TOATE 3 MODURILE READY” + integritate `OK`; pytest-ul din „Primul pas”
**22 passed, 3 skipped**; `tu3/tests` **53 passed**; `tests/test_dedup_live.py` **11 passed**. R7 drop-in-ul instalat,
ordinea `ExecStopPost` corectă.

Verdict: `DD_PASS` numai dacă T1–T11 și R1–R7 trec; altfel `DD_FAIL`, publicat ca atare, fără retuning; orice a doua
rulare reală cere amendament sigilat înainte. Observarea primului ciclu automat (linia `[tu3-dedup-live …]` după
`[tu3-arhiva-live …] PUBLICAT`) este descriptivă (depinde de durata sesiunii) și se raportează dacă are loc.

## 7. Artefacte

`tu3/PROTOCOL_TU3_DD.md` + `tu3/SIGILIU_TU3_DD.json` (înainte de cod), `tu3/dedup_live.py`, `tests/test_dedup_live.py`,
`tu3/rezultate/DD/DEDUP_TU3_*.json`, drop-in-ul `tu3-dedup-live.conf`, `tu3/date/live/DEDUP_LIVE.jsonl`; apoi
`predari/OPERATIV.md`, Mesajele 35–36 în supliment, `predari/genereaza_predare.py` (pereche nouă, același UTC).
