# AMENDAMENT 01 la PREINREGISTRARE_QL649.md (protocol QL649-P1)

Scris: 2026-10-25, ÎNAINTE de backtestul unic pe istoria reală (`rezultate/backtest_unic`
nu există) și fără să fi văzut vreun scor de performanță pe istoria reală.

## Motiv (cost de calcul măsurat pe date NULE, nu pe istoria reală)

§5 cere, descriptiv, „pipeline complet pe 64 universuri nule”. Prima rulare la scară
completă a pipeline-ului protocolului pe un univers nul sintetic (`rezultate/multivers_pipeline/u000`,
aceeași structură de zile, extrageri uniforme) arată un cost de ordinul a ~30 de minute
pe univers pe RTX 5060 Laptop (O1: 48 × ~2427 descompuneri proprii complex128 + Newton;
O6: 3 × 10 000 pași MCMC pe ~621 000 de lanțuri). 64 de universuri ≈ 32 de ore.

## Modificare

- `M_PIPE_NULL`: 64 → **4** universuri nule (u000–u003), seed-uri `[649, u]`, configurația exactă a protocolului.
- Rolul rămâne strict DESCRIPTIV (nu intră în nicio poartă, nu schimbă verdictul).
- Neschimbate: datele, curățarea, operatorii O1–O6 și toți hiperparametrii, comparatorii,
  legile marginale, scorurile, cele 6 porți, încălzirea, Multiversul Nul pentru SCI (M=8192),
  regula „o singură rulare”.
- Universurile suplimentare (u004…) pot fi rulate ulterior cu
  `validare.py --null-pipeline M --start-u 4`, tot descriptiv, raportate separat.
