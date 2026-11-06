# PROTOCOL TU4-UI — sesiunea S14 „UI”: tabul „🔮 Predicție prospectivă” (citire exclusivă din `tu4/tribunal/`)

Scris și sigilat (`tu4/SIGILIU_TU4_UI.json`, mecanismul `inlocuiri_tu3/v1`) ÎNAINTE de orice modificare de cod.
Program: `tu4/PLAN_SESIUNI_TU4_v2_20261027.md` (`32533d53…`) §2 S14. Cererea: mesajul utilizatorului din S14
(„EXECUTION COMMAND OVERRIDE: S14 UI”). `positive_claims_allowed=false`. Calcul clasic; interfața NU calculează
predicții, NU rulează modele și NU decontează: afișează exact ce au sigilat emițătorul (S12) și judecătorul (S13).

## 0. Starea de pornire (primul pas, 2026-10-27T22:35–22:40Z)

- Ceasul sistemului (autoritate): 2026-10-27T22:3xZ (marți). Mesajul indică „28 octombrie”; se folosește ceasul real.
  Extragerea țintă este joi 2026-10-29 18:30 Europe/Bucharest (16:30Z) ⇒ **nicio decontare din 29 nu poate exista încă**;
  `DECONTARI.jsonl` absent (0 linii), ultima rulare a judecătorului 22:30:37Z `nothing_to_settle`, rc 0.
- Perechea de predare 223230Z = `VERIFICARE_PREDARE` (toate sha256 identice). 6 × `drift []`; LANT 3 linii (e2fe385e,
  a15dc8fd, 092e3f5c). `tu4/incidente/`: numai `FR_01` moștenit — **niciun `JU_*`**.
- `VERIFICARE_JU_PASS` 13/13 (`VERIFICARE_JU_20261027T223738Z.json`); `tu4/tests/` 33 passed; TU3 38 passed + 3 skipped;
  `inlocuiri_tu3 --verifica` `"ok": true`; DL exit 0.
- **Incident nou TU4-EM-01** (`tu4/incidente/EM_01/`): `VERIFICARE_EM_FAIL` 31/36 la 22:35:55Z. Cauza: TU3-DD a compactat
  FĂRĂ PIERDERI versiunea LIVE `14f66edd6282` citată de emisii (22:30:37Z, după publicarea `474afc41a77e`); V2 citește
  calea brută. Martorul (`martor_em01.py`, `verify()` sigilat NEMODIFICAT pe rădăcină-suprapunere cu versiunea
  materializată byte-exact) = `VERIFICARE_EM_PASS` 36/36. Emisiile, LANT-ul și judecătorul neafectate. Remedierea
  (amendament EM-V01) NU se face în S14; decizie pentru S15. S14 nu depinde de fișierul arhivei emisiei.

## 1. Decizia de arhitectură (de ce comutator + tab, nu al 13-lea tab în `app.py`)

- Calea 6/49 este randată de `app.py` (12 taburi literale), înghețat în ≥ 10 sigilii (VS, DD, LN, L649, SR, SR_R, T7A–C,
  FIN, TU4-FR) și apărat de testele de identitate U1 (instantaneu complet al vederii principale față de
  `tests/baseline/app_v2_649.py`), U8/L3 („numai inserții”) și `tests/test_app.py` (`len(at.tabs) == 12`). Un al 13-lea
  tab în `app.py` ar cere modificarea unei linii existente (lista literală) și ar rupe U1/test_app ⇒ respins.
- Soluția polimorfă, numai prin inserții în `tu3/ui_tu3.py`: în `sidebar_selector()` (apelat de `app.py` în TOATE
  cele 3 moduri, înaintea oricărui motor) se inserează comutatorul `st.toggle("🔮 Predicție prospectivă (TU4)",
  key="tu4_prosp")`, implicit OPRIT (vederea implicită rămâne byte-identică ⇒ U1/U8/test_app neatinse). Pornit ⇒ pentru
  modul ales se randează `st.tabs(["🔮 Predicție prospectivă"])` cu tot conținutul §3, apoi `st.stop()`: niciun motor GPU,
  niciun set de date încărcat, nicio variantă. Aceeași funcție `tu4_render_prospectiv(mode)` servește 6/49, 5/40 și Joker.
- Bara laterală: `app.py` o pornește restrânsă (`initial_sidebar_state="collapsed"`); selectorul de mod este deja acolo.

## 2. Sursa datelor și integritatea (citire exclusivă)

- Directorul: `tu4/tribunal/` (implicit). Fișiere citite NUMAI în mod binar: `LANT.jsonl`, `emisii/<joc>/<D>.json`,
  `DECONTARI.jsonl`, `decontari/<joc>/<D>.json`, `JUDECATOR_RULARI.jsonl`. Nicio scriere, niciun `chmod`, niciun lacăt,
  niciun import din `tu4/` (judecător, emițător, `ip_core`), niciun fișier din `tu4/rezultate/`, nicio arhivă LIVE.
- Suprascriere NUMAI pentru teste: variabila de mediu `QL649_TU4_TRIBUNAL` (director de test). Când e setată, tabul afișează
  un avertisment „MOD TEST — tribunal de test”. Lansatorul de producție NU o setează.
- Verificări în UI (refuz explicit, nu reparare):
  - I1 LANT: `i == indice`; `prev_line_sha256` înlănțuit de la geneza `82459f48…` (sha `SIGILIU_TU4_EM.json`);
    sha256(emisie) = `sha256` din linie; `game`/`target_date`/`emitted_utc` egale cu emisia. Eșec ⇒ `st.error`, NICIO
    emisie afișată.
  - I2 DECONTARI: `i == indice`; `prev_line_sha256` înlănțuit de la geneza `5dcc0a42…` (sha `SIGILIU_TU4_JU.json`);
    sha256(decontare) = linia; `game`/`target_date`/`status` egale. Eșec ⇒ `st.error` în secțiunea decontărilor
    (emisia curentă rămâne afișată; traiectoria NU se desenează).
  - I3 pragurile din emisie (`tribunal.threshold_ln`, `retire_ln`) și din decontări (`thresholds`) trebuie să fie
    ln 600, −10 (și ln 20); diferență ⇒ avertisment.
- Constantele afișate (fixate aici, identice cu `tu4/judecator.py`): ln 600 = 6.396929655…, ln 20 = 2.995732273…,
  retragere ln E < −10; M = 6 fluxuri (H1/H3 × 6/49, 5/40, Joker).

## 3. Conținutul tabului (în ordinea afișării)

- C1 Eticheta permanentă **„Test științific în curs; nu este sfat de joc”**: în bara laterală, sub comutator (mereu
  vizibilă, în toate modurile) și în capul tabului (`st.warning`), plus `positive_claims_allowed=false`.
- C2 Emisia curentă a jocului ales = emisia din LANT cu `target_date` maximă: data țintă, `emitted_utc` EXACT (șirul din
  fișier) = ora sigiliului, sha256 (12 hex + complet în legendă), indicele LANT/lanț, `cutoff_utc`, `draw_utc` (și ora
  București), starea: „înainte de extragere” / „extragere trecută — în așteptarea decontării” / „decontată: STATUS”.
- C3 Pentru fiecare model (H1, H3): biletul top exact cum e emis (`top_ticket`; Joker: + `ball.top_ball`), λ, X², df,
  `bet_active` (principal și bilă), D (nats/extragere); **harta densității π** (heatmap pe grila biletului, 10 coloane,
  culoare = π_i / (k/n), text = numărul și π_i); Joker: bara q(bilă) față de 1/20. Biletul structural 1 2 3 4 5 6 (H3 6/49)
  se afișează ca atare, cu nota că provine din baza cosinus netedă (tendință monotonă), nu dintr-o selecție.
- C4 Istoricul decontărilor jocului ales (toate stările `DECONTAT` / `VOID` / `RESPINS`): data, starea, motivul,
  `decided_utc`, extragerea, potrivirile biletului top (descriptiv; e-factorul folosește toată distribuția), ln e per
  model, „numărat”; plus un expander cu toate jocurile și ultima rulare a judecătorului (`utc`, `action`, `rc`, motive).
- C5 **Traiectoria ln E_t** a celor 6 fluxuri (cele 2 ale jocului ales evidențiate): ln E (explorare) linie continuă,
  ln E_conf (confirmare pe emisii noi) întreruptă, punctul de start 0; liniile orizontale ln 600, ln 20 și −10; tabel
  cu starea fiecărui flux (EXPLORARE / CONFIRMARE / CONFIRMAT / RETRAS), ln E, ln E_conf, distanța până la praguri.
- C6 Reîmprospătare: secțiunile C4–C5 într-un `st.fragment(run_every="60s")` (recitesc tribunalul; nicio scriere).
- Zero popularitate: nicio penalizare de mulțime, nicio optimizare de bilete, niciun bilet al clienților, nicio
  recalculare a π sau a biletelor (afișare exactă a emisiei).

## 4. Fișierele (listă închisă)

`replaceable` (exact, cu sha-ul de dinainte):
- `tu3/ui_tu3.py` `b334f7d943aca11a3d9868cc974f069bf509acd344b432d0382e55515f0f2f6f`
- `tests/test_scor_real.py` `cf4b55bd8d7581eac0a1c654ff95c550d57cf960a8617f4564a73fb8d06dbb4b`

Patch-urile de inserție (difflib ⊆ {equal, insert} față de sha-urile de mai sus; nicio linie existentă schimbată):
- P1 `tu3/ui_tu3.py`, în `sidebar_selector()`, după linia `                   "positive_claims_allowed=false")`
  (linia 68, în blocul `with st.sidebar:`): `        tu4_on = tu4_sidebar_switch()  # TU4-UI (inserție) …`.
- P2 `tu3/ui_tu3.py`, imediat înaintea liniei `    return mode` (linia 69):
  `    if tu4_on:` / `        tu4_render_prospectiv(mode)` / `        st.stop()` (cu comentariu `# TU4-UI (inserție)`).
- P3 `tu3/ui_tu3.py`, la sfârșitul fișierului: blocul `# TU4-UI (S14)` cu constantele §2 și funcțiile
  `tu4_tribunal_dir`, `tu4_sidebar_switch`, `tu4_load` (I1–I3), `tu4_render_prospectiv` și ajutoarele lor
  (numai stdlib + numpy + pandas + plotly + streamlit, deja importate în modul).
- P4 `tests/test_scor_real.py`, imediat după linia 436
  `    valid_r = [r for r in INL.load_records(ROOT)[0] if r["seal"] == "tu3/SIGILIU_TU3_SR_R.json"]`:
  `    valid_r += [r for r in INL.load_records(ROOT)[0] if r["seal"] == "tu4/SIGILIU_TU4_UI.json"]  # TU4-UI (S14) …`.
  Motiv: W11 (S8) acceptă înlocuiri NUMAI din lanțul SR_R; o înlocuire ulterioară sigilată (S14) ar face W11 să eșueze
  fără niciun defect real. Extinderea e îngustă (numai sigiliul TU4-UI), declarată aici, nu o relaxare generală.

Fișiere noi: `tests/baseline/ui_tu3_pre_tu4ui.py` (copie byte-identică `b334f7d9…`, 0444, înaintea codului),
`tu4/tests/test_ui.py`, `tu3/inlocuiri/INLOCUIRE_TU4_UI_<UTC>Z.json` (scris DUPĂ teste, prin
`tu3/inlocuiri_tu3.py --inregistreaza tu4/SIGILIU_TU4_UI.json TU4_UI`), `tu4/rezultate/UI/` (jurnale AppTest/regresie,
`VERIFICARE_UI_<UTC>Z.json`, `RAPORT_UI.md`), `jurnal/` (lansator). NEATINSE: `app.py`, `tests/test_app.py`,
`tests/test_app_tu3.py`, `tu4/` cod/sigilii/emisii/unități, `tu3/inlocuiri_tu3.py`, gardul, OGLINDA, DL.

## 5. Testele (AppTest; `tu4/tests/test_ui.py`) — scrise înaintea înregistrării

- UT1 comutatorul există în bara laterală (cheia `tu4_prosp`), implicit oprit; eticheta C1 în bara laterală.
- UT2 × 3 moduri, tribunalul REAL, comutator pornit: fără excepții; exact 1 tab „🔮 Predicție prospectivă”; eticheta C1;
  `emitted_utc` exact; biletele afișate = `top_ticket` (+ `top_ball` Joker) ale emisiei pentru H1 și H3; λ și
  `bet_active` afișate; 2 hărți π (+ 1 bară bilă la Joker); graficul ln E cu cele 3 praguri (6.3969, 2.9957, −10);
  niciun card `ql-variant` (motorul nu a rulat).
- UT3 tribunal sintetic (tmp, lanțuri valide, copii ale emisiilor reale): 3 decontări 6/49 `DECONTAT`/`VOID`/`RESPINS` ⇒
  toate 3 stările în tabel, potrivirile corecte, traiectoria cu puncte, tabelul stărilor.
- UT4 emisie alterată (sha ≠ LANT) ⇒ `st.error`, niciun bilet afișat.
- UT5 lanț DECONTARI rupt ⇒ `st.error` în secțiunea decontărilor; emisia curentă rămâne afișată.
- UT6 citire exclusivă: arborele `tu4/tribunal/` (nume, sha256, mtime) identic înainte/după; AST al blocului TU4-UI:
  fără importuri din `tu4`/`judecator`/`emite`/`ip_core`, fără `open(…, "w"/"a"/"x")`, fără `write_*`/`chmod`/`unlink`,
  fără `crowd_penalty`.
- UT7 „numai inserții” față de `tests/baseline/ui_tu3_pre_tu4ui.py`; inserțiile conțin P1, P2 și blocul P3.
- UT8 avertismentul „MOD TEST” când `QL649_TU4_TRIBUNAL` e setată.

## 6. Acceptarea

`UI_PASS` ⇔ UT1–UT8 trec; regresia (primul pas: `tu4/tests/`, `tests/test_validare_tu3.py tests/test_app.py
tests/test_app_tu3.py tests/test_dedup_live.py`; istoricul: `tests/test_l649.py tests/test_porturi_712.py
tests/test_porturi_t7b.py tests/test_porturi_t7c.py tests/test_scor_real.py tests/test_verifica_sr.py
tests/test_lansator_tu3.py tests/test_engine.py tests/test_parser.py tests/test_validare.py tu3/tests/`) are aceleași
rezultate ca linia de bază rulată înaintea codului (22:43Z); înregistrarea `INLOCUIRE_TU4_UI_*` validă și
`inlocuiri_tu3 --verifica` `"ok": true`; matricea de inițializare READY. Altfel `UI_FAIL`, publicat, fără reparare
ascunsă (orice remediere = incident + amendament sigilat înainte).

## 7. Repornirea serverului (după `UI_PASS`)

`systemd-run --user --scope --collect -q gtk-launch quantum-lab-649` (lansatorul pictogramei: oprește serverul vechi,
pornește `run_app_tu3.sh` pe 127.0.0.1:8649), apoi bucla pe jurnalul NOU `jurnal/lansator_tu3_<UTC>Z.log` până la
`[lansator] health ok` (limită 300 s), `ss` numai 127.0.0.1:8649 și `GET /_stcore/health` = `ok`.

## 8. Ce NU face S14

Nu emite, nu decontează, nu recalculează e-factori, nu atinge emisiile/decontările, nu modifică pragurile, nu
remediază EM-01, nu ridică gardul, nu atinge OGLINDA/DL, nu adaugă filtre de popularitate sau optimizări de bilete.
Fără subagenți; git numai `./dev-git`, fără add/commit.
