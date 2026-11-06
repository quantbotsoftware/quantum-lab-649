# PROTOCOL TU3-UI — modulul UI: selector global de univers (6/49 · 5/40 · Joker), 12 taburi × 3 moduri

Sesiunea 2026-10-26 (start ~17:49Z), continuare din checkpoint-ul 20261026T173154Z, la cererea utilizatorului (Mesajul 33).
Scris și sigilat ÎNAINTE de orice cod al modulului (`tu3/ui_tu3.py`, `tests/test_app_tu3.py`, `tests/baseline/` nu există
la sigilare, iar `app.py` are încă hash-ul de mai jos). Subordonat `PROTOCOL_TU3_P1.md` (§0 abateri, §1 ordinea
modulelor: „UI — selector global, 12 taburi × 3 moduri”), `PROTOCOL_TU3_P.md` (surse), `PROTOCOL_TU3_E40.md` și
`PROTOCOL_TU3_EJ.md` (produsele); nu modifică nimic din modulele J, P, E40, E-J.

## 0. Încadrare onestă

- Calcul CLASIC (PyTorch, CUDA pe RTX 5060 Laptop; fallback CPU jurnalizat). UI-ul doar AFIȘEAZĂ ieșirile produselor
  existente; nu introduce niciun model, niciun scor, niciun prag nou. `positive_claims_allowed=false`, afișat permanent
  în fiecare mod. Variantele sunt minime de energie ale modelului, NU predicții, NU combinații cu șanse mai mari; nu se
  compară cu nicio extragere. Orice scor pe istoria reală 5/40 sau Joker cere protocol separat, sigilat înainte.
- NEMODIFICATE (hash-uri în sigiliu): `engine.py`, `parser.py`, `tu3/parser_multi.py`, `tu3/motor_n.py`,
  `tu3/motor_joker.py`, `tu3/joker_entanglement.py`, `validare.py`, `pl649/ui_pl649.py`, `run_app.sh`,
  `tests/test_app.py`. UI nu atinge colectorul/baza, arhiva LIVE și `arhiva_live.py` (deduplicarea versiunilor rămâne
  submodul separat, numai la cererea utilizatorului), protocolul prospectiv și gardul lui (decizia utilizatorului),
  OGLINDA, DL, modelele închise.
- În această sesiune: protocol → cod → teste (sintetice/FAST + fum pe LIVE, fără a tipări, salva sau compara variantele
  reale) → predare. Serverul `./run_app.sh` pe 127.0.0.1:8649 și matricea de inițializare aparțin modulului următor
  („Validare + server”), NU acestuia.

## 1. Calea 6/49 — identitate (cerință tare)

- Modul implicit este 🌌 6/49. Pe această cale `app.py` execută EXACT codul actual (sha `app.py` în sigiliu): aceeași
  sursă `parser.DEFAULT_SOURCE` (înghețată, QL649 sigilat), același `engine.run_full`, aceleași cache-uri
  (`get_dataset`, `run_engine`, `get_sci`), aceleași 12 taburi, același sigiliu (fișiere `SIGILIU_*.json` direct în
  `QL649_SEAL_DIR`). Abatere declarată față de „produsul LIVE”: 6/49 rămâne pe sursa înghețată, deoarece trecerea la
  LIVE ar schimba vizual calea 6/49 (interzis aici); o eventuală comutare 6/49→LIVE cere amendament și cererea
  utilizatorului.
- Modificarea `app.py` este strict ADITIVĂ: un singur bloc inserat după funcțiile ajutătoare (`card`, `fig`) și înaintea
  antetului: selectorul din sidebar, eliberarea la schimbarea modului și, NUMAI pentru 5/40 / Joker, delegarea către
  `tu3/ui_tu3.py` urmată de `st.stop()`. Toate liniile existente rămân byte-identice și în aceeași ordine (verificat în
  test prin diferența de linii: numai inserții). CSS-ul global nu se schimbă (stilurile noi se injectează numai în modurile
  5/40 / Joker). `initial_sidebar_state="collapsed"` rămâne (pagina 6/49 identică); selectorul se deschide din săgeata
  sidebar-ului (abatere de ergonomie declarată).
- Martor de identitate (U1): o copie byte-identică a `app.py` actual se păstrează în `tests/baseline/app_v2_649.py`
  (același sha). Testul randează copia (cu `ROOT` rescris spre directorul aplicației, singura substituție) și noul
  `app.py` în modul implicit, în configurația FAST, și cere egalitate pe zona principală: etichetele celor 12 taburi,
  secvența de markdown/caption/info (exact, cu excepția elementelor volatile declarate: cardul „timp motor GPU” și
  widgetul VRAM, comparate cu cifrele mascate), numărul de dataframe-uri și titlurile graficelor Plotly, cele 3 cărți de
  variante identice. `tests/test_app.py` rămâne nemodificat și trebuie să treacă.

## 2. Selectorul global și ciclul de viață al tensorilor

- `st.sidebar.selectbox` (cheie `tu3_mode`) cu exact 3 opțiuni, în ordine: `🌌 Mode: Loto 6/49` (`649`),
  `🌀 Mode: Loto 5/40` (`540`), `🃏 Mode: Joker` (`joker`).
- Cache pe mod (`st.cache_resource`): 6/49 — cache-urile existente; 5/40 / Joker — `get_game_dataset(mode, src_key)` cu
  `max_entries=1` (setul activ pe GPU) și `run_engine_mode(mode, cfg_json, src_key)` (rezultatele convertite în NumPy pe
  CPU, fără tensori GPU reținuți). `src_key` = sha256 al JSONL-ului LIVE rezolvat prin `parser_multi.resolve_live`
  (lanțul pointer → manifest → JSONL verificat; `IntegrityError` ⇒ eroare afișată și oprire, fără date).
- La schimbarea modului (modul precedent din `st.session_state`): se golesc cache-urile de set ale modului părăsit
  (`get_dataset.clear()` pentru 6/49, `get_game_dataset.clear()` pentru 5/40 / Joker), apoi `gc.collect()` și
  `torch.cuda.empty_cache()`; evenimentul (mod vechi → nou, VRAM alocată înainte/după) se jurnalizează în
  `st.session_state["tu3_release_log"]`. Rezultatele NumPy rămân în cache (revenirea nu recalculează motorul).
- Martor fără scurgeri (U6): ciclul 6/49 → 5/40 → Joker → 6/49 → 5/40 → Joker; VRAM alocată după a doua trecere prin
  Joker ≤ cea după prima + 8 MiB; câte un eveniment de eliberare la fiecare schimbare; nicio excepție.

## 3. Produsele pe mod (fixate)

| mod | set | produs | config protocol | config FAST (numai test) |
|---|---|---|---|---|
| 6/49 | `parser.build_dataset(DEFAULT_SOURCE)` | `engine.run_full` | `engine.PROTOCOL` | ca acum (`QL649_CONFIG=fast`) |
| 5/40 | `parser_multi.build_game_dataset("540", "live")` | `motor_n.run_full_540` | `motor_n.PROTOCOL_540` | aceleași 5 suprascrieri ca 6/49 |
| Joker | `parser_multi.build_game_dataset("joker", "live")` | `motor_joker.run_full_joker` | `motor_joker.PROTOCOL_JOKER` | aceleași 5 suprascrieri ca 6/49 |

Suprascrierile FAST (identice cu `app.py`): `mcmc_steps=300, replicas=4000, poincare_iters=100, kur_steps=60,
gamma_grid=12`; în FAST `is_protocol=False` și UI-ul afișează „MOD FAST (test)”. Porțile produselor (E40_PASS / EJ_PASS)
rămân în produse; dacă lipsesc, UI-ul afișează eroarea, fără variante.

## 4. Cele 12 taburi în modurile 5/40 și Joker (aceleași etichete ca 6/49)

1. ⚛ Colaps — top-10 P = |Ψ|² (linia uniformă 1/n), planul complex al lui Ψ (n noduri), tabelul top-10 (P, |Ψ|, arg Ψ,
   π, fracția top-k, nucleu, θ, r), R(t) Kuramoto, cercul de fază.
2. 🌀 Singularitate & Amplituhedron — γ_EP, λ_EP, γ_q, ancore; discul Poincaré + perechi; holograma 3D; S_ij;
   perechile; decalajul spectral; traiectoriile λ(γ). Joker: în plus tensorul comun J (hartă N 45×20) și descriptorii
   S_E, K_S, I, Φ din `run_full_joker` (descriptivi).
3. ♾ Convergența terminală — EXACT 3 variante unice după regula activă: 5 numere distincte 1..40 (5/40); 5 numere
   distincte 1..45 + 1 Joker 1..20 (Joker). Pe fiecare carte: energia (Joker: principală, E_J, totală, q_V(a*), |h_V|);
   avertismentul de energie; profilul GPU. Dacă regula sau unicitatea nu se verifică ⇒ eroare afișată, fără cărți.
   Sigiliul SHA-256 de timp (commit–reveal local, buton `seal_btn_<mod>`): payload canonic JSON (`sort_keys`,
   separatori compacți) cu `game`, `variants` (Joker: `[[5 numere], joker]`), `after_last_date`, `config_digest`,
   `is_protocol`, `protocol_sha256`, `source_sha256`, `source_kind`, `sealed_at_utc`, `positive_claims_allowed=false`;
   fișierul `QL649_SEAL_DIR/<mod>/SIGILIU_<mod>_<UTC>Z.json` cu `{"payload", "sha256"}` (subdirector separat, deci
   tabelul 6/49 nu se schimbă). Nu este evaluare prospectivă și nu se verifică automat.
4. 🌌 Multiversul Nul — universurile SINTETICE ale verificării de putere (`PUTERE_E40.json` / `PUTERE_EJ.json`,
   read-only): verdict, porțile G1/G2 (Joker și GJ1/GJ2), tabelul seturilor; SCI pe istoria reală 5/40 / Joker este
   NERULAT (`validare.py` e definit pe 6/49; cere protocol). Frecvențele reale vs așteptarea uniformă r·N/n (și Joker
   N/20), descriptiv.
5. ⏳ Mașina Timpului — backtest pe istoria reală NERULAT în acest mod (cere protocol separat); inventarul setului LIVE
   (`GameDataset.summary()`, descriptiv).
6. 🧪 Ablație & Sigiliu — ablația NON-protocol (aceiași 5 comutatori, chei `abl_*_<mod>`) prin același produs al
   modului cu config modificată; distanța TV π protocol ↔ ablație; registrul sigiliilor modului.
7–12. BO649, WU649, GL649, SE649, CS649, PL649 — piste definite și închise NUMAI pe 6/49: în modurile 5/40 / Joker
   tabul afișează explicit „NEAPLICABIL — fără protocol propriu în acest mod; orice transpunere cere protocol nou
   sigilat înainte”, fără calcul și fără a citi artefactele 6/49. (Abatere declarată față de „fără placeholdere” din
   Mesajul 25: inventarea unui conținut pentru aceste piste ar fi un model nou fără protocol, interzis de AGENTS.md.)

## 5. Teste (`tests/test_app_tu3.py`, AppTest, mod FAST) — toate trebuie să treacă

U1 identitate 6/49 (§1); U2 selector: 3 opțiuni în ordine, implicit 6/49, în sidebar; U3 5/40: fără excepții,
12 taburi, exact 3 cărți, 5 distincte în 1..40, unice, `positive_claims_allowed=false` în text; U4 Joker: idem cu
5 distincte 1..45 + Joker 1..20; U5 sigiliu 5/40 și Joker: fișier în subdirectorul modului, sha256 recalculat din
payload-ul canonic, forma variantelor, nimic nou în rădăcina sigiliilor 6/49; U6 ciclu fără scurgeri (§2); U7 ablație
5/40: 6 cărți după recalculare; U8 hash-urile fișierelor NEMODIFICATE (§0) și `app.py` = baseline + numai inserții.
Testele NU tipăresc, NU salvează (în afara directorului temporar de sigilii) și NU compară variantele reale.
Plus: `tests/test_app.py` 2 passed (+1 skip protocol), suita `tu3/tests` 53/53, `py_compile` pe fișierele atinse.

## 6. Artefacte

`tu3/PROTOCOL_TU3_UI.md` + `tu3/SIGILIU_TU3_UI.json` (înainte de cod), `tests/baseline/app_v2_649.py` (copie byte),
`tu3/ui_tu3.py`, `app.py` (bloc aditiv), `tests/test_app_tu3.py`; apoi `predari/OPERATIV.md`, Mesajul 33 în supliment,
`predari/genereaza_predare.py` (pereche nouă, același UTC).
