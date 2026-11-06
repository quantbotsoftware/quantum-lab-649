# PROTOCOL TU4-S32 — joi seara după extragere: starea reală a arhivei, cauza gărzii `gpu-v1` și ce rămâne de decis

Cererea = Mesajul 84 (2026-10-29T20:44:54+02:00 = 18:44:54Z). `positive_claims_allowed=false`. Calcul clasic. Fără afirmații
predictive. Acest protocol este scris DUPĂ rulările din §1 (care au fost rulări S31 preînregistrate și o pornire manuală a
pipeline-ului produsului) și după un diagnostic read-only (§2). Le declară, nu le legitimează retroactiv. Pentru S32 nu
există sigiliu sau verificator: S32 nu are criterii PASS/FAIL proprii pentru §1–§2. Fixează numai regulile pentru pașii
următori (§4).

**Ce nu adoptă S32 din formularea cererii (corecții de premisă):**
1. `loto_romania/cohorta.py:163` NU este o gardă hardware sau GPU. Este verificarea identității modelului față de protocolul
   înghețat al cohortei active a produsului: `model_identity(model) != cohort['protocol']['models'][model]` ⇒
   `ValueError('Model/environment changed after protocol freeze')`. Numele `gpu-v1` vine de la model, nu de la placa video.
2. „Starea PENDING se sparge forțat”: S32 nu forțează decontarea. Judecătorul înghețat decontează numai o înregistrare
   `draw_kind == "regular"` (`tu4/judecator.py:421, 438`). Forțarea ar însemna schimbarea unei reguli înghețate după extragere.
3. „Validează liniile noi LANT fără eșecuri formale sau alerte de drift”: LANT are tot 3 linii (`LANT_PREFIX_S20 OK linii 3`,
   `SCUT_LANT OK linii 3 []`). Nu există linii noi. Eșecurile formale nu se suprimă.
4. „Menține 587/587”: paritatea a ieșit 552/552 PASS (§1). Numărul 587 nu poate fi „menținut” fără a schimba datele sau
   pragul. Niciuna dintre aceste variante nu s-a aplicat.
5. „61/61 Rust passed”: rezultatul a fost măsurat, nu presupus: `test result: ok. 61 passed; 0 failed`.
6. „Eliminarea ferestrelor orare interzise”: ferestrele rămân valabile pentru verificatorii înghețați. Ele nu au blocat nimic
   în această sesiune (toate rulările au fost la :45–:52).

## 1. Ce s-a rulat (în ordine, ora UTC)

| Moment | Acțiune | Rezultat |
|---|---|---|
| 18:45:57Z | primul pas exact din predarea `173618Z`: sha-urile celor 10 fișiere | toate = predarea |
| 18:45:57Z | sonda S27 | `SONDA_RC=0`, `FAZA_0_ASTEAPTA_DECONTAREA`, `AVERTISMENT_DECONTARE_BLOCATA` prezent, T2 `DECONTARE_PENDING 0/3`, T3 0/3, G2 27/27 0444+sha |
| 18:45:58Z | `verifica_s31.py m2` (o singură dată) | **PASS 6/6**, `H_BLOCAT`, `CONFIRMAT_PENDING_CU_AVERTISMENT` (`d019c097…`) |
| 18:45:58–18:49:06Z | `primul_pas_S26.sh` neschimbat + Q7L | 14 × `drift []`, 61/61, `c20fdcd2…`, **paritate 552/552 PASS**, `DL_RC=0`, A0 PASS; **Q7L FAIL 9/11**, **V0L FAIL 27/29** ⇒ `INCIDENT_S31_01.json` |
| 18:50:31Z | `systemctl --user start loto-actualizare.service` (cererea „forțează actualizarea”) | **eșec**: `Model/environment changed after protocol freeze: gpu-v1`; arhiva LIVE refuză versiunea nouă (`snapshot canonic … diferă în baza nouă` pentru 649 și Joker 29 oct); snapshotul anterior rămâne activ; judecătorul 18:51:01Z: nimic de decontat |

Arhiva LIVE la 18:30:45Z (`versiuni/70b3e7630ef6`): 649 până la 2026-10-29 (`7-30-34-40-42-45`), Joker până la
2026-10-29 (`18-21-37-42-43`, J1), 5/40 tot 2026-10-25 („Sursă secundară indisponibilă”). Înregistrările din 29 oct au
`draw_kind: "unknown"`, deci judecătorul le tratează ca absente. Numerele sunt citate numai ca stare a arhivei, fără scoruri.

## 2. Diagnostic read-only al gărzii (inventar, nu experiment)

Script: `tu4/rezultate/S32/diag_gpu_v1.py` (rerulat pentru ieșirea salvată `DIAG_GPU_V1_*.txt`). Deschide `data/registru/evenimente.sqlite` în modul `ro`, nu scrie nimic și compară
identitatea înghețată `gpu-v1` a cohortei active `221a3a10…` (start 2026-10-04) cu `model_identity('gpu-v1')` curentă.

Obiectul de protocol `eaf533d1…` a fost citit dintr-o copie de backup a registrului. Fișierul are sha256 egal cu numele
său adresat prin conținut, deci are aceiași octeți ca obiectul canonic.

**Singura diferență este `environment/platform`: `Linux-7.0.11-76070011-generic…` (înghețat) față de
`Linux-7.2.6-76070206-generic…` (acum).** Hash-urile fișierelor de cod, Python, numpy și firele de execuție sunt identice.
Kernelul 7.2.6 a fost instalat prin apt și a pornit la 2026-10-28 12:52 (ora locală). Kernelul 7.0.11 este încă în `/boot`.

Consecință observată: garda se declanșează numai când rularea ajunge la prognoza cohortei, adică atunci când apar date noi
(dimineață până la 13:30Z și din nou la 18:50Z). În acel moment, toată actualizarea eșuează, iar arhiva LIVE rămâne la versiunea
anterioară. **Cât timp identitatea diferă, varianta „regular” a rezultatelor din 29 oct nu poate fi publicată în arhiva
LIVE, iar decontarea rămâne PENDING.** Deci premisa „garda blochează decontarea” este acum susținută de dovezi, chiar dacă garda nu
are legătură cu hardware-ul.

## 3. Opțiunile pentru gardă (decizia utilizatorului; S32 NU aplică niciuna)

| Opțiune | Ce face | Cost |
|---|---|---|
| A. Repornire în kernelul 7.0.11 (meniul de boot) | identitatea coincide din nou; zero modificări de cod; Q4 (S24) primește și repornirea așteptată | acțiune fizică a utilizatorului; driverul NVIDIA nu intră în identitate (`production-cpu`) |
| B. Înlocuirea cohortei prin mecanismul produsului (`replace_active` + motiv), cu identitatea 7.2.6 | cohorta nouă, protocol nou, trasabil în registru | cohorta 2026-10-04 se închide; începe o cohortă descriptivă nouă |
| C. Modificarea gărzii (de ex. excluderea șirului de kernel din `platform`) | deblochează imediat | schimbă produsul înghețat; cele 13 hash-uri externe S30/S31 nu mai coincid; prognozele intră într-o cohortă cu o identitate verificată mai slab; cere protocol și amendament separate |
| D. Ștergerea/dezactivarea gărzii (cererea literală) | deblochează | prognozele unui mediu schimbat ar intra ca eligibile în registrul append-only al unei cohorte înghețate, ceea ce este greu de reparat; **nerecomandat** |

## 4. Reguli pentru pașii următori (fixate acum)

- Până la decizia utilizatorului, `cohorta.py` rămâne neatins (13 hash-uri externe = S31).
- Pragul 587 din Q7L/V0L nu se mai poate atinge cât timp arhiva conține 29 oct. C1/B5 (duminică 13:36–13:57Z) cu
  `verifica_s25.py` neschimbat va da FAIL formal pe `paritate_587`. O verificare C1 validă cere un verificator nou, cu
  protocol și sigiliu ÎNAINTE de rulare. Criteriul propus: `n_pass == n_checks`, `verdict_B2_B7 == PASS`, iar `n_checks`
  trebuie egal cu valoarea obținută de același binar `c20fdcd2…` pe referința generată din aceeași versiune LIVE (cu
  defalcarea pe grupe salvată). Pragul nu se coboară retroactiv pentru rularea din 18:46Z.
- Decontarea rămâne exclusiv a judecătorului înghețat. Fără forțări.
- Incidentele: cele 9 directoare + `S31_01` în `tu4/rezultate/S31/` (directoarele `S26_*`/`S28_01` rămân necreate până la C1).

## 5. Verdict S32

`S32_DECLARATIV`: nu este PASS sau FAIL. Rezultatul S31 trece din `S31_PARTIAL` în **`S31_FAIL` formal** (M0/M1/M2/M3 PASS,
Q7L final FAIL; `INCIDENT_S31_01`). Total proiect: NU zero incidente. Fără sudo, fără `chmod u+w` pe fișiere înghețate,
fără scrieri în tribunal, surse Rust sau `loto_romania/`. Git: numai `./dev-git status`.
