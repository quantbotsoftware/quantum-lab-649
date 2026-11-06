# PROTOCOL XI-P2 — ANEXA SURSE (treapta B)

Scrisă din inventarul `xi/p2/INVENTAR_P2.json` (20:08–20:11Z, 2026-10-31; numai HEAD pe fișiere de date și extragerea
legăturilor din pagini HTML, fără afișarea textului; nicio expunere la numere extrase consemnată) și sigilată
(`xi/SIGILIU_XI_P2_SURSE.json`) ÎNAINTE de orice cod de analiză P2 și de orice descărcare de fișier de date.
Lista exactă, mașină-citibilă: `xi/p2/SURSE_P2.json` (fișier sigilat împreună cu această anexă). Treapta A
(`xi/PROTOCOL_XI_P2.md`, `01ff6235…`) rămâne neschimbată.

## Jocuri incluse (6; numărul final G se stabilește după numărarea extragerilor, pragul ≥ 1 000)

| Joc | Operator / autoritate | Fișier(e) | Subjocuri (n, k) | Perioadă stabilă (documentație) |
|---|---|---|---|---|
| HU_otos | Szerencsejáték Zrt. | `bet.szerencsejatek.hu/cmsfiles/otos.csv` (240 429 o, LM 2026-10-30) | 5 din 90 | toată arhiva: 5/90 de la prima extragere (1957) |
| HU_hatos | Szerencsejáték Zrt. | `…/cmsfiles/hatos.csv` (185 540 o, LM 2026-10-30) | 6 din 45 | toată arhiva: 6/45 de la lansare (1988) |
| FR_loto | FDJ | `media.fdj.fr/static-draws/csv/loto/loto_200810.zip`, `loto_201703.zip`, `loto_201902.zip`, `loto_201911.zip` | 5 din 49 + numéro chance 1 din 10 | de la 2008-10-06 (noua formulă 5/49 + 1/10); `loto_197605.zip` (6/49 vechi) exclus după dată |
| DE_6aus49_sambata | WestLotto (societate de stat NRW, DLTB) | `westlotto.de/…/gewinnzahlendownload/lotto6aus49.zip` (1 033 287 o, LM 2026-09-02) | 6 din 49 | de la 1955-10-09 (prima extragere 6aus49), numai sâmbăta; Zusatzzahl/Superzahl ignorate |
| US_powerball | NY State Gaming Commission, data.ny.gov | `data.ny.gov/api/views/d6yy-54nr/rows.csv?accessType=DOWNLOAD` | 5 din 69 + Powerball 1 din 26 | de la 2015-10-07 (matricea 5/69 + 1/26) |
| US_megamillions | NY State Gaming Commission, data.ny.gov | `data.ny.gov/api/views/5xaw-6ayf/rows.csv?accessType=DOWNLOAD` | 5 din 70 + Mega Ball 1 din 25 | 2017-10-31 … 2025-04-04 (după aceea Mega Ball 1/24: alt format); se așteaptă < 1 000 ⇒ probabil exclus la numărare |

Regulile de citire (delimitator, coloane/poziții, formatele datei, ordinea) sunt în `SURSE_P2.json`. Pentru
**DE_6aus49_sambata** structura arhivei nu se poate cunoaște fără descărcare: regula se fixează printr-un amendament
de citire după listarea membrilor arhivei și a rândului de antet (fără valori), conform protocolului A §3; calificarea
Q4 a acelei reguli se face înaintea separării jocului. Cel mult un amendament de citire per joc; dacă nici acela nu
permite citirea cu biblioteca standard Python, jocul este exclus și consemnat.

Ungaria: rândurile vechi pot avea data goală; ordinea este (an, săptămână, dată), cu egalitățile în ordinea fișierului
orientat cronologic (dacă rândurile datate sunt descrescătoare, fișierul se inversează întâi). Rândurile dinaintea
datei de început și după data de sfârșit se exclud după dată, nu după conținut.

## Jocuri excluse (consemnate, fără înlocuire)

- **Marea Britanie Lotto / Thunderball:** fișierul oficial (draw-history/csv, redirecționat la xml) are 2 425 / 1 641
  octeți — numai ultimele extrageri; pragul de 1 000 este imposibil.
- **Polonia Lotto:** lotto.pl răspunde 403; fișier public descărcabil negăsit (API cu cheie). Fără ocolire.
- **Italia SuperEnalotto:** 403; arhivă HTML pe ani, nu fișier.
- **Spania La Primitiva / Bonoloto:** SELAE nu publică un fișier al istoricului (numai consultare HTML); agregatoarele
  (lotoideas, laprimitiva.info) sunt interzise de plan.
- **Canada Lotto 6/49:** fișierul oficial BCLC (`playnow.com/resources/documents/downloadable-numbers/649.zip`) este
  blocat în România de ONJN (conexiunea primește certificatul autosemnat „MFP/ONJN 213.177.28.90”); blocarea nu se
  ocolește. OLG, Loto-Québec, WCLC: fără legături spre fișiere de date.

## Test global și familia Holm

Testul global E_{★,X} = ∏_g E_{g,X} se face pe jocurile rămase după numărare (G ≥ 2). M = 5·G + 5, α = 0.01.
Cu G = 5 (dacă Mega Millions cade la numărare): M = 30, pragul Bonferroni al celui mai mic p: E ≥ 3 000.

## Precedente pentru datele de început

Szerencsejáték Zrt. (Ötöslottó din 1957, Hatoslottó din 1988); FDJ (noua formulă Loto din 6 octombrie 2008);
DLTB / Lotto Bayern (prima extragere 6aus49 la 9 octombrie 1955); Multi-State Lottery Association (Powerball 5/69 +
1/26 din 7 octombrie 2015; Mega Millions 5/70 + 1/25 din 31 octombrie 2017, Mega Ball 1/24 din aprilie 2025).
