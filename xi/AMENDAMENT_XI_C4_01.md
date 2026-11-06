# AMENDAMENT XI-C4_01 — simulare exactă pe măști în locul aproximării de independență (înainte de cod)

Scris și sigilat ÎNAINTE de orice cod sau rulare C4. Motivul este o analiză exactă pe hârtie, nu un rezultat: pentru două bilete
6/49 disjuncte, P(ambele ≥ 3 nimeriri în aceeași extragere) = C(6,3)²·C(37,0)/C(49,6) = 400/13 983 816 ≈ 2.9·10⁻⁵,
față de produsul independent p² ≈ 3.5·10⁻⁴, adică de circa 12 ori mai mic. Aproximarea de independență din §5 ar
denatura deci varianța strategiilor cu mai multe bilete.

**Modificare.** Pentru TOATE strategiile, fiecare dată simulată trage o **extragere uniformă reală**:
- 6/49: o 6-mulțime;
- 5/40: o permutare din care se rețin primele 6 bile în ordine;
- Joker: o 5-mulțime plus Joker ∈ 1..20.

Numerele de nimeriri ale fiecărui bilet se calculează exact, prin măști pe biți (popcount pe int64, pe GPU).
Categoriile rezultă exact, inclusiv corelațiile dintre biletele aceleiași date și regula „primele 5” de la 5/40.

**Biletele** fiecărei strategii sunt o mulțime fixă de bilete distincte, trasă o singură dată cu seed-ul 20261030 + indicele
strategiei, și jucată la fiecare dată. Biletul Joker are numărul Joker tras uniform.

Restul protocolului rămâne neschimbat: plățile §4, fereastra, porțile V1–V3, M = 10⁶ sezoane și orizonturile.
Orizonturile 1 și 5 ani sunt prefixele sezoanelor de 10 ani; datele sunt independente între ele.
