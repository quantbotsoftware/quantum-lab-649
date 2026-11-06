# AMENDAMENT SM1-A01 — cine rulează pașii `sudo` (înaintea oricărui cod SM1)

Cererea = Mesajul 71 (2026-10-28T06:41:08-04:00 = 10:41:08Z). Utilizatorul a dat parola `sudo` și a cerut „memorează și
transmite mai departe”. Amendamentul și sigiliul lui (`tu4/SIGILIU_TU4_SM1_A01.json`) se scriu înaintea scripturilor
din `tu4/sm1/`. Criteriile M0–M7, specificația `fstab` din §2 și verdictele NU se schimbă.

## Ce se schimbă

1. **Executantul pașilor root** (protocolul §4, pașii 3–4): îi rulează AGENTUL, nu utilizatorul. Parola dată de utilizator
   ajunge exclusiv în intrarea standard (stdin) a comenzii `sudo -S`, câte o dată pentru fiecare comandă. Apare deci în
   argumentele acelor apeluri de unealtă. Nu se transmite altui program.
2. **Parola NU se scrie în niciun fișier** al proiectului sau al predării: scripturi, loguri, rapoarte, sigilii,
   `OPERATIV.md`, HANDOFF/PROMPT, `MESAJE_UTILIZATOR_QL649.md`. În consecință, partea „transmite mai departe” a cererii
   NU se execută. Motive:
   - fiecare predare include integral suplimentul de mesaje, iar perechile precedente se arhivează byte-identic și
     permanent. O parolă scrisă acolo s-ar multiplica în fiecare predare viitoare și nu ar mai putea fi ștearsă fără
     rescrierea probelor istorice, lucru interzis de reguli;
   - o parolă de administrator în text clar, în fișiere citite de agenți, înseamnă acces root pentru oricine le citește.
3. **Mesajul 71 se înregistrează în supliment cu parola înlocuită prin `[parolă redactată]`.** E singura abatere de la
   textul integral și e declarată aici și în mesaj.
4. Închiderea ferestrei Tauri (§4, pasul 2) rămâne la utilizator, din butonul ferestrei, ca să se scrie `rezumat.json`.
   Pe acest sistem nu există `wmctrl`/`xdotool`, iar sesiunea e Wayland. Abia apoi agentul face pasul 4 al
   protocolului (`udisksctl unmount` + `sudo systemctl start media-tony-LOTO_SSD.mount`).

## Recomandări pentru utilizator (fără acțiune automată)

- Parola rămâne, inevitabil, în jurnalul conversației (`~/.gemini/…/transcript*.jsonl`). Recomandare: după SM1, schimbă
  parola (`passwd`) și alege una mai lungă decât 3 cifre.
- Dacă o sesiune viitoare are nevoie de root fără parolă, alternativa sigură este o regulă `sudoers` îngustă (de exemplu
  `NOPASSWD` numai pentru `tu4/sm1/revino_sm1.sh`). Ea ar cere un protocol separat și acordul explicit al utilizatorului.

`positive_claims_allowed=false`.
