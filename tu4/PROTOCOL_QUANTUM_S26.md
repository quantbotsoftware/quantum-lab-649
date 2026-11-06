# PROTOCOL TU4-S26 — telemetrie pasivă de stabilitate a aplicației 8649 (sesiune mărginită, fără WebKit)

Cererea = Mesajul 77 (2026-10-28T07:42:03-04:00 = 11:42:03Z). Protocolul și sigiliul (`tu4/SIGILIU_TU4_S26.json`) se scriu
ÎNAINTEA oricărui cod S26 (`tu4/s26/`) și a oricărei măsurători S26.

`positive_claims_allowed=false`. S26 e numai infrastructură: măsoară memoria (RSS/HWM/PSS din `/proc`) a arborelui de
procese al aplicației Streamlit 8649 și verifică integritatea. Nu citește extrageri, nu calculează scoruri, nu emite, nu
decontează și nu prezice nimic. Tot ce afișează aplicația rămâne descriere structurală clasică a arhivei, fără avantaj
predictiv.

**Corecții de premisă (declarate, fără a adopta formulările):**
1. `ql649-tu3-8649.service` este `Type=oneshot` fără `RemainAfterExit`: pornește aplicația în scope-ul tranzitoriu
   `run-u194.scope` prin `systemd-run` și apoi se termină. `ActiveState=inactive` cu `Result=success` este starea normală;
   aplicația se verifică prin scope, port și `/_stcore/health`, nu prin `ActiveState` al serviciului.
2. `telemetry.rs` (`rust_core/src/telemetry.rs`, 0444) nu este un proces care rulează singur: e un modul compilat în
   binarul `rust-singularity-core`. „Monitorizarea asincronă” = un fir dedicat al subcomenzii existente
   `rust-singularity-core monitor` (CLI S21, Q9), rulată din binarul înghețat `c20fdcd2…`. Nicio sursă nu se schimbă.
3. Monitorizarea S26 este o **sesiune mărginită** (600 de eșantioane × 1000 ms ≈ 10 min), pornită și urmărită de agent.
   NU se instalează timer/serviciu de supraveghere continuă (ar fi un job autonom și o modificare systemd, interzise
   fără protocol separat). Opțiunea „supravegherea continuă a 8649” rămâne neîncepută.
4. „Fără a încărca WebKitWebProcess”: S26 NU pornește GUI-ul Tauri (`rust-singularity-core gui`); arborele măsurat e cel
   al Streamlit (bash `run_app.sh` → `streamlit`, `tee`). Se verifică explicit absența proceselor WebKit și
   `n_webview = 0` pe fiecare eșantion.
5. „Binarul nativ f25aad0c… / c20fdcd2…”: `c20fdcd2…` este binarul curent (`rust_core/target/release`, compilat S22 cu
   `target-cpu=native`); `f25aad0c…` este copia S21 de pe SSD (`RUST_CORE_S21/bin`), echivalentă funcțional cu cel curent
   numai în sensul martorului A2 (S22: rapoarte de paritate identice). Ambele hash-uri se reverifică; S26 nu rulează
   binarul S21.
6. „AVX2/FMA active”: se verifică (a) că TOATE CPU-urile logice ale gazdei raportează `avx2` și `fma` în
   `/proc/cpuinfo` și (b) că `rust_core/.cargo/config.toml` (`b48f77c0…`) conține `target-cpu=native`. Numărul static de
   instrucțiuni `ymm`/`vfmadd` din binar (objdump) e numai DESCRIPTIV. Nu se afirmă că instrucțiunile FMA/AVX2 se execută
   pe vreun drum anume și nici un câștig de viteză (S20: Rust nu contractă `a*b+c` în FMA fără `mul_add`).
7. Starea pentru decontarea de joi (`DECONTARE_PENDING`) și pentru C1 (emisia de vineri) se **păstrează** prin
   neintervenție, verificată prin hash-uri; S26 nu scrie în `tu4/tribunal/`, în systemd sau în surse.

## 0. Inventar read-only (făcut înainte de protocol, baza B0)

| Element | Valoare constatată |
|---|---|
| Predarea `113522Z` | HANDOFF `6d1d06cc…`, PROMPT `903e026a…` = `VERIFICARE_PREDARE_20261028T113522Z.json` |
| Primul pas (B0) | `tu4/rezultate/S25/primul_pas_S26_20261028T114309Z.log` (`4540744f…`): 14 × `drift []`, `LANT_PREFIX_S20 OK linii 3`, EM 42/42, JU 13/13, 130 passed, 38 + 3s, UI 15/15, `SURSE_RUST_OK 27`, 61/61, `c20fdcd2…`, 587/587, M2 15/15, G0 17/17, `DL_RC=0`, Q0 12/12, Q1 10/10, Q4 `UNKNOWN`, `DECONTARE_PENDING`, `B5_PENDING` + `B2_RC=0`, `SCUT_LANT OK linii 3 []`, A0 13/13 |
| V0L / Q7L | `V0L_VERIFICARE_20261028T114548Z.json` (`9aa12c4f…`) 28/29, singurul FAIL `incidente` (identic cu `113350Z`); `Q7L_VERIFICARE_20261028T114548Z.json` (`e5c2134b…`) PASS 11/11 |
| Incidente | `EM_01 FR_01 S19_01 S20_01 S23_01 S23_02 S23_03 S24_01 SM1_01` |
| Serviciul 8649 | `enabled`, `Type=oneshot`, `Result=success`; unitatea `b6836780…` (copie = `tu4/systemd/`); scope `run-u194.scope` activ: 12020 `run_app.sh`, 12143 `streamlit` (LISTEN 127.0.0.1:8649), 12144 `tee`; `/_stcore/health` = `ok` |
| WebKit | niciun proces WebKit, niciun `rust-singularity-core gui` |
| Telemetrie | `TEL_ROOT=./telemetry` (27 de sesiuni), SSD `/dev/sda1` ext4, 1.8T liberi; subcomanda `monitor --pid --interval-ms --samples [--root]`, mod producție cu verificarea montării |
| Binare | curent `c20fdcd2…`; copia S21 SSD `f25aad0c…` |
| Gazda | 24 CPU logice, `avx2` 24/24, `fma` 24/24; `.cargo/config.toml` `b48f77c0…` cu `target-cpu=native` |
| Timere | `loto-actualizare.timer` (30 min), `ql649-tu4-emitere.timer` (următoarea 13:20Z); `ql649-tu4-judecator.service` static |

## 1. Ferestre interzise (fixate)

Nicio măsurătoare/verificare S26 în ±15 min față de emisiile 08:20/12:20/15:20 Europe/Bucharest (azi: 06:20Z, 10:20Z,
13:20Z) sau de decontarea de joi 16:30Z. T0 refuză pornirea sesiunii dacă intervalul [acum, acum + 600 s + 600 s marjă]
intersectează o fereastră.

## 2. Sesiunea de telemetrie (fixată)

Comanda (o singură dată; un eșec NU se repetă cu alți parametri, ci deschide incidentul `S26_01`):

```
./rust_core/target/release/rust-singularity-core monitor --pid <P> --interval-ms 1000 --samples 600
```

`P` = PID-ul principal al `run-u194.scope` (bash `run_app.sh`, azi 12020), deci arborele {P} ∪ descendenți cuprinde
`streamlit` și `tee`. Rădăcina implicită (SSD, cu verificarea montării). stdout (agregatul JSON) și stderr se salvează în
`tu4/rezultate/S26/`. Procesul de monitorizare nu este descendent al lui P (nu se măsoară pe sine).

## 3. Criterii (praguri fixate înainte)

**T0 — starea înainte (toate):** (1) hash-urile predării = fișierul de verificare; (2) B0: log `4540744f…`, Q7L
`e5c2134b…` PASS 11/11, V0L 28/29 numai `incidente`; (3) binarul curent `c20fdcd2…` și copia SSD `f25aad0c…`, ambele
executabile; (4) `avx2` și `fma` pe toate CPU-urile logice (număr = `os.cpu_count()`); `.cargo/config.toml` `b48f77c0…`
conține `target-cpu=native`; (5) serviciul `enabled`, `Type=oneshot`, `Result=success`, unitatea `b6836780…` în ambele
locuri; scope-ul activ; P și `streamlit` în cgroup-ul scope-ului; 8649 ascultă (LISTEN) prin `streamlit`;
`/_stcore/health` = `ok`; (6) zero procese WebKit și zero `rust-singularity-core gui`; (7) `findmnt` = `/dev/sda1`,
`TEL_ROOT` director; (8) 27/27 surse Rust 0444 cu sha = manifestul S22; (9) fereastra §1 liberă; (10) incidentele = cele
9 cunoscute; (11) toate `frozen_hashes` din sigiliul S26 = valorile curente.

**T1 — sesiunea (toate):** (1) exit 0, `stare = COMPLET`, `rezumat` prezent; (2) directorul sesiunii are părintele
`TEL_ROOT` și numele `*_pid<P>`; (3) exact 600 de linii complete, toate obiecte JSON, `seq` = 1…600, `pid` = P,
`citiri_esuate` = 0; (4) pe fiecare eșantion `n_procese` ≥ 2 și `rss_principal` ≠ null (arborele viu tot timpul);
(5) pe fiecare eșantion `n_webview` = 0 și `webview_rss` = 0; zero procese WebKit după sesiune; (6) după sesiune
`streamlit` are același PID, 8649 ascultă, `/_stcore/health` = `ok`; (7) consistența agregat ↔ JSONL:
`rss_total_varf` din agregat = max(`rss_total`) din JSONL (dacă agregatul expune câmpul).

**Descriptiv (fără prag, nu intră în verdict):** min/max/prima/ultima valoare `rss_total`, `pss_total`, `hwm_total`;
panta OLS a `rss_total` (octeți/min); numărul static de instrucțiuni cu `ymm` și `vfmadd` din binar (objdump).
O pantă pozitivă pe 10 min NU e declarată „scurgere”, iar una plată NU e declarată „stabilitate garantată”.

**T2 — neintervenție după (toate):** (1) toate `frozen_hashes` din sigiliul S26 neschimbate; (2) `verifica_s25.py scut`
tipărește `SCUT_LANT OK`; (3) fișierele `tu4/tribunal/RULARI.jsonl` și `JUDECATOR_RULARI.jsonl` au ca prefix octeții
din sigiliu (append-only); (4) `ql649-tu4-emitere.timer` și `loto-actualizare.timer` `active` + `enabled`; (5) 27/27
surse 0444 neschimbate; (6) binarul tot `c20fdcd2…`; (7) incidentele = cele 9 (sau + `S26_*` declarate).

**Q7L final:** după T2, primul pas S26 (`primul_pas_S26.sh`, neschimbat) rulat din nou, în afara ferestrelor ⇒
Q7L PASS 11/11, V0L 28/29 numai `incidente`, `DECONTARE_PENDING`, `B5_PENDING` + `B2_RC=0`.

## 4. Verdict

- `S26_PASS` = T0 ∧ T1 ∧ T2 ∧ Q7L final.
- `S26_FAIL` = oricare FAIL; deschide `tu4/incidente/S26_NN/`, fără reglaje, fără repetare cu alți parametri.
- `UNKNOWN` (ex. fereastră interzisă, SSD nemontat) nu devine PASS.

Raport: `tu4/rezultate/S26/RAPORT_S26.md`. Fișiere noi permise: `tu4/rezultate/S26/*`, `tu4/s26/verifica_s26.py`,
`tu4/incidente/S26_*/`, directorul sesiunii pe SSD. Fără `sudo`, fără `chmod u+w`, fără scrieri în tribunal/systemd/surse.
Git: numai `./dev-git status`.
