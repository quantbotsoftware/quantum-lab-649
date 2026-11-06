# AMENDAMENT TU4-EM-V01 — verificarea arhivei emisiei după amprenta de conținut (remedierea incidentului TU4-EM-01)

Scris și sigilat (`tu4/SIGILIU_AMENDAMENT_TU4_EM_V01.json`) ÎNAINTE de orice cod al remedierii. Sesiunea S15 „FIN4”
(Mesajul 58, 2026-10-27, ceasul real 23:28Z). `positive_claims_allowed=false`.

## 1. Fapte

- Incidentul `tu4/incidente/EM_01/INCIDENT_TEHNIC_EM_01.json` (`78f82989…`): emisiile din 2026-10-29 citează arhiva
  LIVE `versiuni/14f66edd6282`; TU3-DD (`tu3/dedup_live.py`, `33c212a8…`) a compactat FĂRĂ PIERDERI acea versiune
  (JSONL → `ref` la reprezentantul `75dac11c7506` + `provenance` din manifest). `tu4/verifica_em.py` (`1bada90e…`)
  citește calea brută ⇒ V2 FAIL ×3 + V3 FAIL derivat (numărări zero).
- Reconfirmat în primul pas S15: `VERIFICARE_EM_20261027T232443Z.json` (`a20f4c1f…`) = `VERIFICARE_EM_FAIL` 31/36,
  eșecuri NUMAI `V2_archive_*` / `V3_recompute_*`; martorul EM_01 = `VERIFICARE_EM_PASS`; `VERIFICARE_JU_PASS` 13/13;
  `UI_PASS` 15/15; 7 × `drift []`; DL exit 0. Nicio decontare (extragerea joi 29 oct, 16:30Z, nu a avut loc).

## 2. Decizia de arhitectură: fișier NOU `tu4/verifica_em_v01.py`, `tu4/verifica_em.py` rămâne NEATINS

Mesajul 58 cere modificarea `tu4/verifica_em.py` după sigiliu. Faptele din depozit o fac imposibilă fără erori induse:
`tu4/verifica_em.py` este înghețat prin sha simplu în TREI sigilii (`SIGILIU_TU4_EM_COD.json` `files`,
`SIGILIU_TU4_JU.json` și `SIGILIU_TU4_UI.json` `frozen_hashes`), iar verificatoarele sigilate le compară direct, fără
lanțul `inlocuiri_tu3`: `tu4/verifica_ju.py` (`24216394…`, V1 ⇒ `VERIFICARE_JU_FAIL`), `verifica_ui_s14.py`
(`008edaff…`, S2 ⇒ `UI_FAIL`) și chiar `verifica_em.py` (V1_code_seal). O modificare pe loc ar transforma un defect de
citire într-un FAIL permanent al tribunalului și al UI — exact „erorile secundare induse” pe care mesajul le interzice.
Prin urmare, remedierea este un verificator NOU, `tu4/verifica_em_v01.py`, care:

- încarcă `tu4/verifica_em.py` sigilat NUMAI prin cale, ca bibliotecă, după ce îi verifică sha-ul `1bada90e…`, și
  refolosește NEMODIFICATE funcțiile lui de recalcul (`models`, `incl_D`, `top`, `utc`, `V`) și constantele
  (`GAMES`, `NB`, `SEAL_SHA`, `IP_CORE_SHA`, `UNITS`) — matematica V3 rămâne literal aceeași;
- reproduce verificările V0, V1, V3–V9 cu aceleași nume, toleranțe și reguli; schimbă NUMAI sursa octeților la V2;
- adaugă verificările de sigiliu ale amendamentului (V1_amendment_*) și verificarea amprentei (V2_fingerprint_*).

`tu4/verifica_em.py`, rezultatele lui (inclusiv cele trei FAIL publicate), martorul EM_01 și incidentul rămân
nerescrise, ca istoric.

## 3. Regula nouă V2′ — arhiva identificată prin amprenta de conținut (SHA-256), nu prin cale

Invariantul pe care compactarea fără pierderi îl conservă este **amprenta de conținut**: sha256 al octeților exacți ai
fișierului JSONL citat de emisie (`archive.sha256`), înregistrat și în `MANIFEST_LIVE.json` (pe care TU3-DD nu-l
modifică niciodată) și în intrarea `DEDUP_LIVE.json`. Pentru fiecare emisie, cu `vd = root/tu3/date/live/<version_dir>`
și `name = basename(archive.file)`:

1. **V2_fingerprint_<joc>/<dată>** (înainte de orice reconstrucție): sha256(`vd/MANIFEST_LIVE.json`) =
   `archive.manifest_sha256`; `manifest.games[<joc>].file` = `name` și `manifest.games[<joc>].sha256` =
   `archive.sha256`; dacă versiunea e compactă: `DEDUP_LIVE.json.schema` = `tu3-dedup-live/1`,
   `manifest_sha256` = același, `files[name].sha256` = `archive.sha256`. Lanțul de hash-uri emisie → manifest →
   intrarea de compactare e continuu fără a citi niciun octet de date.
2. **Sursa octeților** (`resolution` în detaliu): (a) `raw` dacă `vd/name` există; altfel (b) versiune compactă, metoda
   intrării: `gzip` (sha256 al fișierului stocat = `stored_sha256`, `stored` = `name + ".gz"`, decomprimare stdlib)
   sau `ref` (reprezentantul `ref` din același `versiuni/`, nume simplu, fără `.`; sha256 al manifestului lui =
   `ref_manifest_sha256`; reprezentantul NU poate fi la rândul lui `ref` — adâncime 1; octeții lui `raw` sau `gzip`
   verificați; apoi fiecare rând nevid primește `provenance = {"database_sha256", "run_id"}` din manifestul versiunii
   citate și se serializează `json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n"`). Reconstrucția este o
   reimplementare INDEPENDENTĂ (stdlib), fără import din `tu3/dedup_live.py`; oricare altă metodă / abatere ⇒ FAIL.
3. **V2_archive_<joc>/<dată>**: sha256(octeți) = `archive.sha256` și lungimea = `files[name].bytes` (la compact);
   apoi EXACT validarea și numărările V2 originale (k numere distincte în 1..n, bila Joker în 1..20, `N` =
   `archive.records` = `warm_start.N`, numărările = `warm_start.counts` / `ball_counts`).
4. V3 recalculează pe aceste numărări, neschimbat.

Nu se folosesc „invarianți Floer”, „mapare spectrală”, „teorie Chern–Simons” ori „compactarea spațiului de fază”:
datele (rânduri JSON) nu au structura topologică sau simplectică pe care acești termeni o presupun, iar a le invoca ar
fi o afirmație matematică falsă. Amprenta SHA-256 este invariantul real și suficient: orice octet schimbat o schimbă.

## 4. Ce NU se schimbă (declarat explicit, cu motive)

- `tu4/judecator.py` (`8117e8a3…`, sigilat în `SIGILIU_TU4_JU_COD.json` ÎNAINTEA primei decontări) NU se recalibrează:
  regula de decontare a fost fixată înaintea emisiilor; a o schimba acum ar însemna schimbarea arbitrului după ce
  pariurile sunt plasate. Valoarea |Δ| ≤ 3.6e-15 din `RAPORT_JU.md` este poarta C5 TRECUTĂ a calibrării (GPU = CPU,
  rotunjire float64), NU un drift prezent în `SCORURI_JU.mmap` (care conține numai antetul `QL649JU1`, 512 octeți,
  0 decontări). Nu există eroare de eliminat.
- `torch.compile(mode="max-autotune-no-cudagraphs", fullgraph=True)` rulează DEJA pe generare: `emite.py` (oglinda
  c64, `compiled:max-autotune-no-cudagraphs:fullgraph:cuda` în fiecare emisie) și `judecator.py`/`calibrare_ju.py`
  (nucleul ln E), conform sigiliilor S12/S13. Verificatorul rămâne, prin `PROTOCOL_TU4_EM.md` §7, stdlib + NumPy, FĂRĂ
  torch: rostul lui este independența față de stiva numerică a emițătorului (un recalcul pe aceeași stivă GPU nu
  verifică nimic), iar `tu4/tests/test_em.py` impune absența `import torch`. Volumul (≈ 7 000 de rânduri) nu
  justifică GPU.
- `tu4/emite.py`, `tu3/dedup_live.py`, emisiile, `LANT.jsonl`, oglinda SSD, unitățile systemd, `tu3/ui_tu3.py`,
  `app.py`, gardul, OGLINDA, DL, `genereaza_predare.py`: neschimbate.

## 5. Teste (cod, după acest sigiliu) — `tu4/tests/test_em_v01.py`

- A1 rădăcina reală, fără scriere: `VERIFICARE_EM_PASS`; toate `V2_*`/`V3_*` PASS; `resolution` ∈ {raw, gzip, ref:*}.
- A2 echivalență: pe aceleași emisii, toate verificările comune cu `verifica_em.verify` care NU sunt `V2_`/`V3_` au
  același status; numele verificărilor originale ⊂ numele noi.
- A3 reconstrucția independentă = `tu3/dedup_live.materialize` octet cu octet, pentru toate versiunile citate.
- A4 sintetic: versiune brută A + versiune compactă B (`ref` → A, `gzip` pentru alt fișier) ⇒ octeții originali exacți;
  falsificări (un octet al reprezentantului, `stored_sha256`, manifestul, `ref` în lanț de adâncime 2, metodă
  necunoscută, nume cu `/`) ⇒ refuz.
- A5 amprenta: emisie cu `archive.sha256` alterat ⇒ `V2_fingerprint` FAIL și `V2_archive` FAIL.
- A6 independența: sursa nu conține `import torch`, `ip_core`, `emite`, `dedup_live`; `verifica_em.py` sha `1bada90e…`.
- A7 sigiliul amendamentului: sha-ul documentului = cel din sigiliu; `code_files_present` = [] la sigilare.

## 6. Acceptare și o singură rulare reală

După testele A1–A7 și regresie, O SINGURĂ rulare reală: `/usr/bin/python3 -B tu4/verifica_em_v01.py` ⇒
`tu4/rezultate/EM/VERIFICARE_EM_V01_<UTC>.json` (0444), verdict publicat oricare ar fi. Așteptat
`VERIFICARE_EM_PASS` (36 verificări originale + 3 amprente + verificările amendamentului). Orice FAIL ⇒ incident
nou, publicat, fără reparare ascunsă. Primul pas al sesiunilor viitoare folosește `verifica_em_v01.py` (martorul
EM_01 rămâne istoric, opțional). Incidentul EM-01 se marchează REZOLVAT prin acest amendament numai dacă rularea reală
trece.
