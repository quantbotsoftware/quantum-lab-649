# PROTOCOL TU4-SM1 — montarea automată, la pornirea laptopului, a SSD-ului extern LOTO_SSD

Cererea = Mesajul 70 (2026-10-28T06:34:21-04:00 = 10:34:21Z): „pregătește protocol de montare ssd”. Cererea urmează
propunerii din răspunsul la Mesajul 69 (incidentul de mediu `S23_01`). Protocolul și sigiliul
(`tu4/SIGILIU_TU4_SM1.json`) se scriu ÎNAINTEA oricărui script sau modificări de sistem.

**Acest protocol nu modifică încă sistemul.** Aplicarea (§4) cere comenzi `sudo`, pe care le rulează UTILIZATORUL în
propriul terminal. Agentul nu cere, nu vede și nu stochează parola. `positive_claims_allowed=false`: SM1 este numai
infrastructură; nu calculează, nu emite și nu prezice nimic.

## 0. Inventar read-only (făcut înainte de protocol)

| Element | Valoare constatată |
|---|---|
| Dispozitiv | `/dev/sda1`, USB (`TRAN=usb`, `HOTPLUG=1`), ext4, eticheta `LOTO_SSD`, **UUID `5af1b939-865f-4eab-bf45-38983451b704`** (același UUID pe care îl folosesc deja `tu4/porneste_emitere.sh` și `tu4/porneste_judecator.sh`) |
| Montarea curentă | prin udisks (montată manual în S23): `./ssd_data`, `rw,nosuid,nodev,relatime,errors=remount-ro`; rădăcina sistemului de fișiere aparține `tony:tony` (0755) |
| `/etc/fstab` | 2 intrări (`/boot/efi`, `/`), sha `1ace1eac…`; nicio intrare pentru SSD |
| polkit `org.freedesktop.udisks2.filesystem-mount` | `active: yes`, `inactive: auth_admin`, `any: auth_admin` |
| `sudo` | cere parolă (`sudo -n true` → „a password is required”) |
| systemd | 255; Linger=yes pentru `tony`; timerele `ql649-tu4-emitere`, `loto-actualizare` → `ql649-tu4-judecator` |

**Dovada cauzei (repornirea din 2026-10-28):**

- 05:39:30 EDT: pornirea laptopului.
- **05:40:02:** `ql649-tu4-judecator` (pornit prin Linger) a încercat `udisksctl mount … --no-user-interaction`, a eșuat
  și a scris `[judecator] SSD indisponibil`.
- **05:40:28:** a început sesiunea grafică a utilizatorului (`loginctl`, sesiunea 4).

Înaintea autentificării nu există sesiune activă, deci polkit cere `auth_admin` și refuză montarea fără interacțiune.
Concluzie: **o soluție la nivel de utilizator (udisks) NU poate monta SSD-ul înaintea autentificării.** Doar o montare
de sistem, făcută de systemd la boot, acoperă și timerele care rulează înainte de login.

Efectul actual al lipsei SSD-ului:
- tribunalul continuă fără oglindă (`--fara-ssd`, „oglinda se completează la rularea următoare”);
- fereastra Tauri pornește cu telemetria `INDISPONIBIL`;
- primul pas pică (ca în `S23_01`).

## 1. Variante comparate

| | A. Intrare în `/etc/fstab` (sistem) — **RECOMANDATĂ** | B. Serviciu systemd de utilizator cu `udisksctl` | C. Fără schimbare (procedura manuală) |
|---|---|---|---|
| Montează înainte de login | DA (systemd, la boot) | NU (polkit `auth_admin` până la login; dovada 05:40:02) | NU |
| Necesită root | da, o singură dată (utilizatorul rulează `sudo`) | nu | nu |
| SSD absent la boot | boot-ul continuă (`nofail`, așteptare de cel mult 10 s) | reîncercări până la login sau conectare | — |
| Reversibil | da: copia de siguranță a `fstab` + `daemon-reload` | da: `disable` + ștergerea unității | — |

**Decizie:** varianta A. Varianta B nu rezolvă cazul observat (timerul de la 05:40:02) și nu se implementează. Varianta
C rămâne procedura de rezervă, documentată în predare.

## 2. Specificația fixată (varianta A)

Linia adăugată în `/etc/fstab`, una singură, cu un comentariu deasupra:

```
# QL649 SM1 (tu4/PROTOCOL_MONTARE_SSD_SM1.md): SSD extern LOTO_SSD; nofail = boot-ul nu se blochează dacă lipsește
UUID=5af1b939-865f-4eab-bf45-38983451b704  ./ssd_data  ext4  rw,nosuid,nodev,relatime,errors=remount-ro,nofail,x-systemd.device-timeout=10s  0  0
```

- **Același punct de montare și aceleași opțiuni ca acum.** Căile din cod (`telemetry.rs` `DEFAULT_ROOT`, scripturile
  tribunalului, arhivele `RUST_CORE_S*`) rămân valabile fără nicio modificare de cod.
- `nofail` + `x-systemd.device-timeout=10s`: dacă SSD-ul lipsește la pornire, boot-ul continuă după cel mult 10 s.
- `0 0`: fără `dump` și fără `fsck` la boot (ca la udisks azi). Verificarea `fsck` rămâne manuală, cu SSD-ul demontat.
- **Fără `x-systemd.automount`.** Un punct autofs ar apărea „montat” chiar și cu SSD-ul absent, iar scrierile s-ar bloca
  până la expirare. Comportamentul ar fi mai puțin determinist pentru testele S21–S23 (verificarea punctului de montare).
- Unitatea generată de systemd se numește `media-tony-LOTO_SSD.mount`.
- **Limită declarată (se măsoară, nu se presupune):** dacă SSD-ul e conectat DUPĂ boot, montarea automată nu e garantată
  de această specificație. Remediul rămâne `udisksctl mount -b /dev/sda1 --no-user-interaction` (în sesiunea activă)
  sau `sudo systemctl start media-tony-LOTO_SSD.mount`. Criteriul M6 doar raportează ce se întâmplă.

## 3. Fișiere

- NOI (agentul, după sigiliu):
  - `tu4/sm1/aplica_sm1.sh`: rulat de utilizator cu `sudo`. Face exclusiv:
    1. verifică UUID-ul, tipul ext4 și eticheta;
    2. refuză dacă `fstab` conține deja `LOTO_SSD` sau UUID-ul;
    3. salvează o copie byte-identică în `/etc/fstab.SM1.<UTC>.bak` și afișează sha-ul ei;
    4. adaugă cele 2 linii din §2;
    5. rulează `findmnt --verify` pe noul `fstab`; la eroare, restaurează automat copia;
    6. rulează `systemctl daemon-reload`.
  - `tu4/sm1/revino_sm1.sh`: restaurarea copiei + `daemon-reload` (rulat de utilizator cu `sudo`).
  - `tu4/sm1/verifica_sm1.py`: criteriile M0–M7, rulat de agent fără root.
  - `tu4/rezultate/SM1/*`, eventual `tu4/incidente/SM1_NN/`.
- MODIFICAT (de utilizator, prin script): `/etc/fstab`, cu exact 2 linii adăugate la sfârșit. Nimic altceva din sistem.
- ÎNGHEȚATE (în sigiliu): toate sursele `rust_core` (manifestul S22), sigiliul/protocolul S23, scripturile
  `tu4/porneste_emitere.sh` și `tu4/porneste_judecator.sh`, unitățile systemd de utilizator ale pistei (inclusiv
  drop-in-urile), `porneste_rust_core.sh`, `porneste_aplicatia_tu3.sh`, `genereaza_predare.py`. Sha-ul `/etc/fstab` de
  dinainte e fixat ca pre-condiție.
- În afara domeniului: pornirea automată a Streamlit 8649 (cealaltă jumătate a `S23_01`). Ea cere un protocol separat.

## 4. Procedura (ordinea fixată)

1. **Pregătire (agent):** după sigiliu, scrierea celor 3 scripturi și M0.
2. **Închiderea consumatorilor SSD (utilizator sau agent):** fereastra Tauri se închide din buton, ca să se scrie
   `rezumat.json`; se verifică faptul că niciun proces nu ține fișiere deschise pe SSD (`fuser -vm ./ssd_data`).
3. **Aplicarea (utilizator, terminal propriu):**
   ```
   cd ${QL649_ROOT:-.} && sudo bash tu4/sm1/aplica_sm1.sh
   ```
4. **Test fără repornire (utilizator, 2 comenzi):**
   ```
   udisksctl unmount -b /dev/sda1 && sudo systemctl start media-tony-LOTO_SSD.mount
   ```
   Apoi agentul rulează M1–M3.
5. **Test cu repornire (utilizator):** o repornire normală a laptopului, la momentul ales de utilizator. După login,
   agentul rulează M4–M5.
6. Opțional: M6 (SSD conectat după boot) și M7 (boot cu SSD absent). Se fac numai dacă utilizatorul acceptă să scoată
   fizic SSD-ul; altfel rămân `UNKNOWN`, declarat.
7. Raportul `tu4/rezultate/SM1/RAPORT_SM1.md` și predarea.

**Momente interzise:** aplicarea și testele nu se fac în jurul emisiilor programate (08:20, 12:20 și 15:20 Europe/Bucharest,
adică 02:20, 06:20 și 09:20 EDT) sau al decontării de după extragere (joi 29 oct, seara). Fereastra de siguranță e de
±15 minute.

## 5. Criterii (fixate înainte de cod)

| Id | Criteriu | PASS dacă |
|---|---|---|
| M0 | Pre-condiții | sha-ul `/etc/fstab` = `1ace1eac…` (din sigiliu); UUID, ext4 și `LOTO_SSD` neschimbate; nicio intrare existentă pentru SSD; drift S23 gol |
| M1 | Aplicarea | `/etc/fstab` = copia de siguranță + EXACT cele 2 linii din §2 (diff verificat octet cu octet); copia are sha-ul `1ace1eac…`; `findmnt --verify` fără erori; `systemctl cat media-tony-LOTO_SSD.mount` arată `SourcePath=/etc/fstab` |
| M2 | Montarea de către systemd (fără repornire) | `findmnt ./ssd_data`: `SOURCE=/dev/sda1`, opțiunile `rw,nosuid,nodev,relatime` prezente; `systemctl is-active media-tony-LOTO_SSD.mount` = `active`; `tony` poate crea și șterge un fișier-test în `QL649_SM1_TEST/` |
| M3 | Fără regresie, imediat | `primul_pas_S24.sh` + `verifica_s23.py v0`: 27/28, cu singurul FAIL cunoscut `incidente` (S23_02/S23_03) plus, așteptat, `SM1_*` dacă apare vreun incident; fereastra Tauri repornită din pictogramă scrie telemetrie pe SSD (sesiune nouă, ≥ 10 linii) |
| M4 | După repornire: montat înainte de login | `journalctl -b -u media-tony-LOTO_SSD.mount` arată „Mounted” cu un timestamp ANTERIOR începutului sesiunii utilizatorului (`loginctl show-session … -p Timestamp`) |
| M5 | După repornire: tribunalul vede SSD-ul | prima rulare `ql649-tu4-judecator` sau `ql649-tu4-emitere` din boot-ul nou scrie „SSD montat” (nu „SSD indisponibil”, ca la 05:40:02) |
| M6 | (informativ) SSD conectat după boot | se raportează dacă montarea a fost automată sau a cerut remediul din §2; fără verdict |
| M7 | (opțional) Boot cu SSD absent | boot-ul ajunge la login; `systemd-analyze blame` arată întârzierea montării ≤ 15 s; după conectare + remediu, M2 trece |

Verdicte:
- `SM1_PASS`: M0–M5 PASS (M6 informativ, M7 PASS sau UNKNOWN declarat).
- `SM1_PARTIAL`: M0–M3 PASS, dar repornirea (M4–M5) nu a fost încă făcută.
- `SM1_FAIL`: oricare dintre M0–M5 e FAIL. Atunci urmează imediat restaurarea (`revino_sm1.sh`) și un incident
  `tu4/incidente/SM1_NN/`, fără reglaje.

UNKNOWN nu devine PASS.

## 6. Riscuri și revenire

- **O linie `fstab` greșită poate bloca boot-ul.** Măsuri: `nofail`, `findmnt --verify` înainte de `daemon-reload`, copie
  byte-identică și restaurare automată la eroarea de verificare. Recuperare manuală (de exemplu din consola de
  recuperare): `cp /etc/fstab.SM1.<UTC>.bak /etc/fstab`.
- **Deconectarea SSD-ului în timpul scrierii** (risc existent și azi): `errors=remount-ro`. Se închid întâi fereastra și
  timerele în curs.
- **udisks** va trata dispozitivul ca „gestionat prin fstab”. Montarea/demontarea din managerul de fișiere poate cere
  autentificare.
- Revenirea completă: `sudo bash tu4/sm1/revino_sm1.sh`. Apoi SSD-ul se montează din nou manual, prin udisks, ca înainte
  de SM1.

## 7. Interpretare

PASS înseamnă: după orice repornire, SSD-ul LOTO_SSD e montat de sistem înaintea timerelor și a autentificării, la același
punct de montare și cu aceleași opțiuni, iar dacă lipsește, boot-ul nu se blochează. Nu înseamnă pornirea automată a
Streamlit 8649 și nu are nicio legătură cu vreo putere predictivă.
