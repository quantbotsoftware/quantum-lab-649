# PROTOCOL TU4-EM — sesiunea S12 „EM”: emițătorul prospectiv al tribunalului (H1 „MA”, H3 „AD”)

Stare: scris și sigilat (`tu4/SIGILIU_TU4_EM.json`) ÎNAINTE de orice cod S12 (`tu4/emite.py`, scriptul de pornire,
unitățile timerului, testele, verificatorul) și ÎNAINTE de orice calcul de model pe arhiva reală.
Plan: `tu4/PLAN_SESIUNI_TU4_v2_20261027.md` (`32533d53…`) §1–§2 S12. Calificare: `tu4/rezultate/IP/CALIFICARE_IP.json`
(`23daff34…`), verificată separat `VERIFICARE_IP.json` (`437d2b20…`, `VERIFICARE_IP_PASS`). Autoritate: Mesajele 52–55
(Mesajul 55 = cererea S12 din 2026-10-27T21:30Z). `positive_claims_allowed=false`.

## 0. Mesajul 55, cum se aplică (decizii ale agentului, delegate)

- **Modelele:** NUMAI cele calificate și ÎNGHEȚATE: H1 „MA” (asimetrie de masă, James–Stein pe numărări) și H3 „AD”
  (dinamica aerului, proiecție netedă pe K = 4 moduri cosinus + James–Stein), din `tu4/ip_core.py`
  (`ab3e1de93d8e5ae537a8c80599905aaa19cc103602f9b18f4b7f7f6f8a48c302`), importate fără nicio modificare. H2 „UZ”
  (necalificat) NU se emite. Fluxuri: M = 6 (H1, H3) × (6/49, 5/40, Joker); la Joker un flux = urna principală + bila.
- **Pragul tribunalului:** E ≥ 100·M = 600 (planul §1: α_explorare 0.01 cu corecția pentru M modele); ln 600 se
  înregistrează în fiecare emisie. Judecata, retragerea la ln E_T < −10 și confirmarea (E ≥ 20, extrageri noi) aparțin
  S13; S12 NU decontează nimic. Calificarea S11 a folosit ln 900 (M_max = 9); 600 < 900, aceeași garanție Ville
  (P(vreun flux atinge vreodată 600) ≤ 6/600 = 0.01 sub urna perfectă).
- **„Warm start real”:** arhiva LIVE (`tu3/date/live/`), citită pentru PRIMA dată de un model în S12. Se folosește
  NUMAI ca stare de start (numărările), nu pentru alegerea sau reglarea vreunui model, parametru ori prag.
- **Inventar declarat înainte de sigiliu (nu calcul de model):** agentul a citit structura arhivei LIVE: versiunea
  curentă `14f66edd6282`, numărul de înregistrări (6/49 2597, 5/40 2490, Joker 2202), distribuția `draw_kind`,
  data ultimei extrageri (2026-10-25 la toate) și ultimele 5 extrageri ale fiecărui joc. Nu s-a calculat nicio
  numărare, statistică X², λ, ŵ sau bilet pe arhiva reală înainte de sigiliu.
- **`torch.complex64` + `torch.compile(mode="max-autotune-no-cudagraphs", fullgraph=True)`:** se implementează ca
  OGLINDĂ de fază complexă (§4): aceleași ecuații H1/H3 evaluate printr-un algoritm diferit (transformată de fază
  e^{−iπm(i−½)/n} pentru coeficienții cosinus; energia spectrală FFT/Parseval pentru X²), în complex64, compilată
  fullgraph. Autoritatea emisiei rămâne calculul float64 al nucleului înghețat (hash-ul de mai sus); o reprezentare
  complexă nu adaugă informație despre urnă, iar complex64 are precizie ~1e-7. Sondă de unelte (date aleatoare, fără
  arhivă, 21:33Z): compilarea fullgraph reușește pe RTX 5060; Inductor avertizează că NU generează cod pentru
  operatorii complecși (aceștia rulează ca nuclee ATen în graful compilat) — declarat, nu ascuns.
- **„Rescriere blocată hardware”:** NU este disponibilă: `chattr +i/+a` cere CAP_LINUX_IMMUTABLE (root), iar `sudo`
  cere parolă (verificat 21:33Z); niciun mediu WORM nu este atașat. Se aplică garanția cea mai tare disponibilă fără
  root: fișiere create exclusiv (`O_CREAT|O_EXCL`, mod 0444, refuz de suprascriere), lanț SHA-256 (fiecare emisie
  conține sha-ul precedentei), registru global `LANT.jsonl` deschis numai `O_APPEND`, copie oglindă pe SSD-ul extern.
  Rezultatul este EVIDENȚĂ la falsificare (orice rescriere rupe lanțul și e prinsă de verificator), nu imposibilitate
  fizică. Utilizatorul poate adăuga manual imutabilitatea (`sudo chattr +i` pe emisii, `+a` pe `LANT.jsonl`); agentul
  nu o face și nu o afirmă.
- **SSD + MMAP:** scriptul de pornire verifică montarea SSD-ului (`UUID 5af1b939-865f-4eab-bf45-38983451b704`,
  `./ssd_data`); dacă lipsește, încearcă `udisksctl mount … --no-user-interaction`. Un fir de scriere
  ASINCRON copiază fiecare emisie pe SSD (`QL649_TU4_EM/emisii/<joc>/<data>.json`, O_EXCL, 0444) și adaugă înregistrarea
  în `QL649_TU4_EM/JURNAL_EMISII.jsonl` prin `mmap` (fișierul se extinde, regiunea nouă se mapează, se scrie, `flush`
  + `fsync`). Lanțul canonic rămâne în depozit (`tu4/tribunal/`): SSD-ul nu este montat persistent după repornire,
  deci emisia nu depinde de el; o oglindă ratată se completează la rularea următoare (recuperare idempotentă).
- **Timer/drop-in propriu:** unitățile NOI `~/.config/systemd/user/ql649-tu4-emitere.{service,timer}` (0444, hash în
  sigiliul de cod). Mesajul 53 (cererea explicită „predicțiile … se vor emite singure, din timer”) și Mesajul 55 o
  autorizează pentru tribunalul TU4. Gardul prognozei produsului vechi (conține `popularitate-v1`), timerul
  `loto-actualizare` și drop-in-urile lui rămân NEATINSE.
- **Zero popularitate:** nicio intrare despre biletele/preferințele altor jucători; singura intrare este lista
  extragerilor. Un test verifică absența oricărui import din produsul vechi.
- Calcul CLASIC (CPU/GPU, virgulă mobilă). Fără hardware cuantic, avantaj cuantic, noutate mondială sau promisiune de
  câștig. Fără subagenți. Git numai `./dev-git`, fără add/commit.

## 1. Arhiva LIVE (warm start)

1. Se citește `tu3/date/live/CURRENT_LIVE.json` → `version_dir`; se citește `MANIFEST_LIVE.json` din versiune.
2. Pentru jocul cerut: sha256 al fișierului `extrageri_<joc>.jsonl` = cel din manifest = cel din `CURRENT_LIVE.json`;
   numărul de înregistrări = `records`. Orice nepotrivire ⇒ refuz (cod 3), nicio emisie.
3. Validare pe fiecare înregistrare (ca în S10 `frontiera.load`): `numbers` are exact k întregi distincți în 1..n
   (6/49: k 6, n 49; 5/40: k 6, n 40; Joker: k 5, n 45), bila Joker întreagă în 1..20. Orice abatere ⇒ refuz (cod 3).
4. Se folosesc TOATE înregistrările (regular, special, unknown), exact ca definiția lui T în S10/S11 (ordinea nu
   contează: H1 și H3 sunt staționare). N = numărul înregistrărilor; c_i = numărările; la Joker și c^B_j ale bilei.

## 2. Ținta, ora oficială, termenul de sigilare

- Calendarul: extrageri joi și duminică (weekday 3 și 6), ora oficială 18:30 Europe/Bucharest (convenția proiectului,
  `loto_romania`; calendarul extern NU este reverificat aici; extragerile speciale/sărbătorile nu sunt prevăzute).
- Termenul de sigilare (cutoff) = 16:00 Europe/Bucharest în ziua țintei (aceeași marjă ca termenul `prognoze.deadline`
  al proiectului). Ținta D = prima zi joi/duminică cu cutoff(D) > acum (ceasul real al sistemului, UTC).
- Emisia este permisă NUMAI dacă `emitted_utc < cutoff_utc(D) < draw_utc(D)`; altfel refuz. Un ceas fals (`--acum`)
  este acceptat NUMAI cu o rădăcină de test (`--radacina-test`), niciodată pe lanțul real.
- Completitudinea warm start-ului: P = ziua joi/duminică precedentă lui D. Dacă `last_date` al arhivei ≥ P ⇒
  `warm_start_complete = true`. Dacă nu: emisia se AMÂNĂ (cod 75) până la fereastra finală (acum ≥ 15:00 local în
  ziua D); în fereastra finală se emite cu `warm_start_complete = false` (declarat în emisie).
- Ținta emisiei este extragerea REGULATĂ din data D. Regula de potrivire în cazul mai multor extrageri în aceeași dată
  se fixează în protocolul S13 (judecătorul), înaintea primei decontări.

## 3. Conținutul emisiei (autoritate: float64, nucleul înghețat)

Pentru fiecare model m ∈ {H1, H3} (funcțiile `logw_h1`, `logw_h3`, `dct_basis`, `esp`, `info_D`, `ticket` din
`ip_core`, neschimbate; formulele din protocoalele H1/H3):
- `logw` (ln ŵ, n valori float64, reprezentare JSON exactă dus-întors), `lambda`, `X2` (H1: X², df n−1; H3: X²_s,
  K = 4), `bet_active = lambda > 0`;
- harta de densitate: `pi_i = ŵ_i e_{k−1}(ŵ_{−i}) / e_k(ŵ)` (probabilitatea de includere a numărului i sub legea
  Fisher emisă; Σπ = k), `D_nats = KL(q‖u)` pe extragere;
- `top_ticket` = cele b etichete cu ŵ maxim (egalitate ⇒ eticheta mai mică), sortate; la Joker și blocul `ball`
  (n 20, k 1): `logw`, `lambda`, `X2`, `q` (= ŵ_j/Σŵ), `top_ball` (argmax, egalitate ⇒ eticheta mai mică), `D_nats`.
- Dacă `lambda = 0` modelul NU pariază (q = uniform; e-factorul va fi exact 1), iar biletul „top” este numai
  artefactul regulii de egalitate (etichetele cele mai mici) — se scrie explicit `ticket_note`.
- Metadate: `protocol`, `game`, `target_date`, `draw_utc`, `cutoff_utc`, `emitted_utc`, `warm_start_complete`,
  `archive` (database_sha256, version_dir, manifest_sha256, sha256 fișier, records, last_date, last_key),
  `code` (sha256 `emite.py`, `ip_core.py`, sigiliul protocolului, sigiliul codului), `tribunal`
  (M 6, prag 600, ln 600, fluxurile), `chain` (indexul în jocul respectiv, `prev_sha256`), `c64_mirror` (§4),
  `positive_claims_allowed: false`, eticheta „test științific în curs; nu este sfat de joc”.

## 4. Oglinda de fază complexă (complex64, compilată)

- z_i = √((n−1)/n)(c_i − Np)/√(Np(1−p)) se calculează în float64 și se convertește în complex64.
- H1: X²_c = (1/n)·Σ_f |FFT(z)_f|² (Parseval); θ̂_c = κ·z cu κ = √((n−1)/n)/√(N p(1−p)) (identic cu
  θ̂_i = (n−1)/n·(c_i/N − p)/(p(1−p)), rescris prin z); λ_c = max(0, 1 − (n−3)/X²_c).
- H3: a_m = √(2/n)·Re Σ_i z_i e^{−iπ m (i−½)/n} (m = 1..4); X²_{s,c} = Σ a_m²; θ̂_s prin aceleași faze aplicate lui θ̂
  și reconstrucția Σ_m b_m a_m(θ̂); λ_{s,c} = max(0, 1 − 2/X²_{s,c}).
- Funcția este compilată cu `torch.compile(mode="max-autotune-no-cudagraphs", fullgraph=True, dynamic=False)` pe
  CUDA (CPU dacă CUDA lipsește); eșecul compilării ⇒ execuție eager, publicată în `compile_status`.
- Poarta C64 (fixată acum): |λ_c − λ| ≤ 1e-4 și max_i |ln ŵ_c − ln ŵ| ≤ 1e-5 + 1e-4·max_i |ln ŵ|, pentru fiecare
  model și (la Joker) și pentru bilă. Se raportează și dacă biletul top al oglinzii coincide. Dacă poarta eșuează,
  emisia float64 se face totuși (modelul înghețat este autoritatea), cu `c64_mirror.pass = false` și un incident tehnic
  declarat în `tu4/incidente/`; nimic nu se reglează.

## 5. Lanțul append-only

- Canonic: `tu4/tribunal/emisii/<joc>/<D>.json`, creat cu `O_CREAT|O_EXCL`, mod 0444, `fsync`. O emisie existentă
  pentru (joc, D) nu se reface și nu se înlocuiește: rularea repetată este no-op (cod 0, „deja emis”).
- `chain.prev_sha256` = sha256 al emisiei precedente a aceluiași joc; pentru prima emisie = sha256 al
  `tu4/SIGILIU_TU4_EM.json` (geneza). `chain.index` = 0, 1, 2, …
- Registrul global `tu4/tribunal/LANT.jsonl` (O_APPEND): o linie per emisie cu `i`, `game`, `target_date`, `file`,
  `sha256`, `emitted_utc`, `prev_line_sha256` (sha256 al liniei precedente, fără newline; geneza = sha256 al
  sigiliului). Jurnalul rulărilor `tu4/tribunal/RULARI.jsonl` (O_APPEND) consemnează și amânările/refuzurile/no-op.
- Excludere reciprocă prin `flock` pe `tu4/tribunal/.lock`.

## 6. Ordinea de execuție S12

1. Acest protocol + `tu4/SIGILIU_TU4_EM.json` (înainte de cod). 2. Cod: `tu4/emite.py`, `tu4/porneste_emitere.sh`,
`tu4/systemd/ql649-tu4-emitere.{service,timer}`, `tu4/tests/test_em.py` (arhive SINTETICE într-o rădăcină de test),
`tu4/verifica_em.py`. 3. Testele trec ⇒ `tu4/SIGILIU_TU4_EM_COD.json` (hash-urile codului și unităților) ÎNAINTE de
prima emisie reală; orice defect găsit înainte se repară și se declară. 4. Prima emisie reală, manual, prin scriptul de
pornire, pentru cele 3 jocuri (ținta așteptată: joi 2026-10-29). 5. Instalarea timerului (copii 0444 ale unităților
sigilate). 6. Verificare SEPARATĂ. 7. Raport `tu4/rezultate/EM/RAPORT_EM.md`.

## 7. Verificator SEPARAT `tu4/verifica_em.py`

Numai biblioteca standard + NumPy (fără torch, fără import din `tu4/`). V1 sigiliile (protocol, cod) și sha-urile
fișierelor înghețate neschimbate; V2 pentru fiecare emisie: sha256 al fișierului arhivei referite (din `versiuni/`) =
cel înregistrat, iar validarea §1 trece; V3 recalculează independent numărările, θ̂, X², λ, ln ŵ (H1, H3, bila) în NumPy
(|Δ| ≤ 1e-12), π prin enumerare-recurență proprie în spațiul logaritmic (|Δ| ≤ 1e-10), D (|Δ| ≤ 1e-10), biletul top și
bila top (egalitate exactă); V4 cronologia `emitted_utc < cutoff_utc < draw_utc`, ținta joi/duminică, ora 18:30 locală,
cutoff 16:00 locală; V5 lanțul per joc și `LANT.jsonl` (prev-sha, indici, unicitate); V6 modurile 0444; V7 oglinda SSD
byte-identică (dacă SSD-ul e montat; altfel `UNKNOWN`, nu PASS) și jurnalul mmap consistent; V8 `code.emite_sha256` =
sha-ul din sigiliul de cod; V9 unitățile instalate = cele sigilate. `VERIFICARE_EM_PASS` numai dacă V1–V6, V8 trec și
V7/V9 sunt PASS sau declarate `UNKNOWN` cu motiv. Rezultat: `tu4/rezultate/EM/VERIFICARE_EM_<UTC>.json` (0444).

## 8. Ce NU face S12

Nu decontează, nu calculează e-factori pe extrageri reale, nu afirmă că vreo abatere există, nu promite câștig sau
termen, nu filtrează după popularitate, nu atinge TU3, S10/S11 (rezultate), pistele închise, produsul vechi, gardul sau
timerul `loto-actualizare`. Estimarea centrală S10 rămâne: probabil nu există nimic de găsit; emisiile sunt hărți de
densitate ale unor ipoteze fizice NEVERIFICATE, judecate numai prospectiv de S13.
