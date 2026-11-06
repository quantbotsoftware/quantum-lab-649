"""HS-V4 (O2) — Achiziție, calcul densitate aer umed ρ_air și cache verificabil ERA5 București.

Sursă deschisă fără cheie API: https://archive-api.open-meteo.com/v1/archive
Coordonate București: 44.43°N, 26.10°E, ora extragerii 18:00 Europe/Bucharest, 1993-08-01 → azi.
Include fallback determinist strict cauzal (< d) pentru latența de capăt ERA5 sau mod offline.
Protocol: hs_v4/PROTOCOL_HSV4.md · positive_claims_allowed = False.
"""
from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
import math
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

import numpy as np

HERE = Path(__file__).resolve().parent
METEO_DIR = HERE / "date_meteo"
CACHE_JSONL = METEO_DIR / "bucuresti_era5_18h.jsonl"
PROVENANCE_JSON = METEO_DIR / "PROVENIENTA_METEO.json"

BUCHAREST_LAT = 44.43
BUCHAREST_LON = 26.10
BUCHAREST_TZ = "Europe/Bucharest"
START_DATE = dt.date(1993, 8, 1)
ARCHIVE_ENDPOINT = "https://archive-api.open-meteo.com/v1/archive"

# Constante termodinamice CODATA / WMO (PROTOCOL_HSV4.md §2.2)
R_DRY_AIR = 287.058       # J / (kg · K)
R_WATER_VAPOR = 461.495   # J / (kg · K)


def compute_moist_air_density(temp_c: float, pressure_hpa: float, rh_pct: float) -> float:
    """Calculează exact densitatea aerului umed ρ_air(T_C, P_surface, RH) în kg/m³ (Tetens–Magnus + Dalton)."""
    t_c = float(temp_c)
    p_pa = 100.0 * float(pressure_hpa)
    phi = min(max(float(rh_pct) / 100.0, 0.0), 1.0)
    p_sat_pa = 610.94 * math.exp((17.625 * t_c) / (t_c + 243.04))
    p_v = min(phi * p_sat_pa, 0.99 * p_pa)
    p_d = p_pa - p_v
    t_k = t_c + 273.15
    return float((p_d / (R_DRY_AIR * t_k)) + (p_v / (R_WATER_VAPOR * t_k)))


def _harmonic_bucharest_climatology(d: dt.date) -> Tuple[float, float, float]:
    """Climatologie armonică deterministă București 18:00 (depinde exclusiv de ziua din an, zero viitor)."""
    doy = d.timetuple().tm_yday
    angle = 2.0 * math.pi * (doy - 200.0) / 365.25
    temp_c = 13.8 + 12.4 * math.cos(angle)
    pressure_hpa = 1006.2 - 2.6 * math.cos(angle)
    rh_pct = 58.0 - 16.0 * math.cos(angle)
    return temp_c, pressure_hpa, rh_pct


def _causal_fallback_values(
    d: dt.date,
    prior_records: List[Dict],
) -> Tuple[float, float, float]:
    """Imputare deterministă strict cauzală folosind EXCLUSIV înregistrările din zilele < d."""
    if not prior_records:
        return _harmonic_bucharest_climatology(d)

    prev = prior_records[-1]
    doy = d.timetuple().tm_yday
    # Medie sezonieră strict din anii anteriori (< d - 30 zile pentru a evita dublarea regimului sinoptic curent)
    cutoff_ord = d.toordinal() - 30
    seas_t: List[float] = []
    seas_p: List[float] = []
    seas_rh: List[float] = []
    for rec in prior_records:
        if rec["_ord"] > cutoff_ord:
            break
        diff = abs(rec["_doy"] - doy)
        circ_diff = min(diff, 365 - diff)
        if circ_diff <= 7:
            seas_t.append(rec["temp_2m_c"])
            seas_p.append(rec["surface_pressure_hpa"])
            seas_rh.append(rec["rh_2m_pct"])

    if seas_t:
        st_c = sum(seas_t) / len(seas_t)
        sp_hpa = sum(seas_p) / len(seas_p)
        srh_pct = sum(seas_rh) / len(seas_rh)
    else:
        st_c, sp_hpa, srh_pct = _harmonic_bucharest_climatology(d)

    # Combinație cauzală persistență sinoptică (0.70) + ciclu sezonier istoric (0.30)
    t_c = 0.70 * float(prev["temp_2m_c"]) + 0.30 * st_c
    p_hpa = 0.70 * float(prev["surface_pressure_hpa"]) + 0.30 * sp_hpa
    rh_pct = min(max(0.70 * float(prev["rh_2m_pct"]) + 0.30 * srh_pct, 5.0), 100.0)
    return t_c, p_hpa, rh_pct


def _fetch_era5_chunk(start_d: dt.date, end_d: dt.date, timeout: float = 30.0) -> Tuple[Dict[str, Tuple[float, float, float]], str]:
    params = {
        "latitude": f"{BUCHAREST_LAT:.2f}",
        "longitude": f"{BUCHAREST_LON:.2f}",
        "start_date": start_d.isoformat(),
        "end_date": end_d.isoformat(),
        "hourly": "temperature_2m,relative_humidity_2m,surface_pressure",
        "timezone": BUCHAREST_TZ,
    }
    url = f"{ARCHIVE_ENDPOINT}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept-Encoding": "gzip",
            "User-Agent": "QuantumLab649-HSV4-Research/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        if resp.headers.get("Content-Encoding", "").lower() == "gzip":
            raw = gzip.decompress(raw)
    payload = json.loads(raw.decode("utf-8"))
    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    rhs = hourly.get("relative_humidity_2m", [])
    press = hourly.get("surface_pressure", [])

    out: Dict[str, Tuple[float, float, float]] = {}
    for t_str, tc, rh, sp in zip(times, temps, rhs, press):
        if isinstance(t_str, str) and t_str.endswith("T18:00"):
            if tc is not None and rh is not None and sp is not None:
                day_key = t_str[:10]
                out[day_key] = (float(tc), float(sp), float(rh))
    return out, url


def build_or_load_bucharest_meteo(
    end_date: Optional[dt.date] = None,
    force_refresh: bool = False,
) -> Dict:
    """Descarcă (sau încarcă din cache verificat SHA-256) seria meteo București 1993-08-01 → azi la 18:00."""
    METEO_DIR.mkdir(parents=True, exist_ok=True)
    if end_date is None:
        end_date = dt.datetime.now(ZoneInfo(BUCHAREST_TZ)).date()

    if not force_refresh and CACHE_JSONL.is_file() and PROVENANCE_JSON.is_file():
        prov = json.loads(PROVENANCE_JSON.read_text(encoding="utf-8"))
        actual_sha = hashlib.sha256(CACHE_JSONL.read_bytes()).hexdigest()
        if prov.get("sha256") == actual_sha and prov.get("end_date", "") >= end_date.isoformat():
            return prov

    # Limita superioară ERA5 este cel mult data curentă UTC; dacă API-ul semnalează latență, coborâm automat
    utc_today = dt.datetime.now(dt.timezone.utc).date()
    era5_target_end = min(end_date, utc_today)

    chunk_ranges: List[Tuple[dt.date, dt.date]] = [
        (dt.date(1993, 8, 1), dt.date(1999, 12, 31)),
        (dt.date(2000, 1, 1), dt.date(2006, 12, 31)),
        (dt.date(2007, 1, 1), dt.date(2013, 12, 31)),
        (dt.date(2014, 1, 1), dt.date(2020, 12, 31)),
    ]
    if era5_target_end >= dt.date(2021, 1, 1):
        chunk_ranges.append((dt.date(2021, 1, 1), era5_target_end))

    era5_map: Dict[str, Tuple[float, float, float]] = {}
    queried_urls: List[str] = []
    network_errors: List[str] = []

    for c_start, c_end in chunk_ranges:
        if c_start > end_date:
            break
        cur_end = min(c_end, end_date)
        fetched = False
        for backoff_days in (0, 1, 2, 5, 10):
            adj_end = cur_end - dt.timedelta(days=backoff_days)
            if adj_end < c_start:
                break
            try:
                part, u_str = _fetch_era5_chunk(c_start, adj_end)
                era5_map.update(part)
                queried_urls.append(u_str)
                fetched = True
                break
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
                err_msg = f"{c_start}..{adj_end}: {type(exc).__name__}: {exc}"
                if backoff_days == 10:
                    network_errors.append(err_msg)
        if not fetched and not network_errors:
            network_errors.append(f"{c_start}..{cur_end}: chunk_unavailable")

    # Construcție strict cauzală zi cu zi: 1993-08-01 → end_date
    records_internal: List[Dict] = []
    lines_out: List[str] = []
    era5_count = 0
    fallback_count = 0

    total_days = (end_date - START_DATE).days + 1
    for offset in range(total_days):
        cur_d = START_DATE + dt.timedelta(days=offset)
        d_iso = cur_d.isoformat()
        if d_iso in era5_map:
            t_c, p_hpa, rh_pct = era5_map[d_iso]
            src_tag = "era5_18h"
            era5_count += 1
        else:
            t_c, p_hpa, rh_pct = _causal_fallback_values(cur_d, records_internal)
            src_tag = "causal_fallback"
            fallback_count += 1

        rho_air = compute_moist_air_density(t_c, p_hpa, rh_pct)
        prev_p = records_internal[-1]["surface_pressure_hpa"] if records_internal else p_hpa
        dp_24h = p_hpa - prev_p

        public_rec = {
            "date": d_iso,
            "hour_local": "18:00",
            "temp_2m_c": round(t_c, 4),
            "surface_pressure_hpa": round(p_hpa, 4),
            "rh_2m_pct": round(rh_pct, 4),
            "rho_air_kg_m3": round(rho_air, 6),
            "dp_24h_hpa": round(dp_24h, 4),
            "source": src_tag,
        }
        lines_out.append(json.dumps(public_rec, ensure_ascii=False, sort_keys=True))
        records_internal.append({
            **public_rec,
            "_ord": cur_d.toordinal(),
            "_doy": cur_d.timetuple().tm_yday,
        })

    raw_bytes = ("\n".join(lines_out) + "\n").encode("utf-8")
    CACHE_JSONL.write_bytes(raw_bytes)
    sha_hex = hashlib.sha256(raw_bytes).hexdigest()

    rho_vals = [r["rho_air_kg_m3"] for r in records_internal]
    prov = {
        "protocol": "HSV4-P1",
        "dataset": "Open-Meteo ERA5 Bucharest 18:00 Europe/Bucharest",
        "endpoint": ARCHIVE_ENDPOINT,
        "latitude": BUCHAREST_LAT,
        "longitude": BUCHAREST_LON,
        "timezone": BUCHAREST_TZ,
        "hour_local": "18:00",
        "start_date": START_DATE.isoformat(),
        "end_date": end_date.isoformat(),
        "total_days": total_days,
        "era5_18h_days": era5_count,
        "causal_fallback_days": fallback_count,
        "cache_file": "hs_v4/date_meteo/bucuresti_era5_18h.jsonl",
        "sha256": sha_hex,
        "bytes": len(raw_bytes),
        "constants": {
            "R_dry_air_J_kgK": R_DRY_AIR,
            "R_water_vapor_J_kgK": R_WATER_VAPOR,
            "tetens_magnus": "610.94 * exp(17.625 * T_C / (T_C + 243.04))",
        },
        "summary_stats": {
            "rho_air_min_kg_m3": round(min(rho_vals), 6),
            "rho_air_mean_kg_m3": round(sum(rho_vals) / len(rho_vals), 6),
            "rho_air_max_kg_m3": round(max(rho_vals), 6),
        },
        "queried_urls": queried_urls,
        "network_warnings": network_errors,
        "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "positive_claims_allowed": False,
    }
    PROVENANCE_JSON.write_text(json.dumps(prov, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return prov


def load_meteo_lookup() -> Dict[str, Tuple[float, float, float]]:
    """Încarcă dicționarul {YYYY-MM-DD: (rho_air_kg_m3, rh_2m_pct, dp_24h_hpa)} cu verificare SHA-256."""
    if not (CACHE_JSONL.is_file() and PROVENANCE_JSON.is_file()):
        build_or_load_bucharest_meteo()
    prov = json.loads(PROVENANCE_JSON.read_text(encoding="utf-8"))
    raw = CACHE_JSONL.read_bytes()
    got_sha = hashlib.sha256(raw).hexdigest()
    if got_sha != prov.get("sha256"):
        raise RuntimeError(f"Integritate meteo eșuată: {got_sha} != {prov.get('sha256')}")

    lookup: Dict[str, Tuple[float, float, float]] = {}
    for line in raw.decode("utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        lookup[obj["date"]] = (
            float(obj["rho_air_kg_m3"]),
            float(obj["rh_2m_pct"]),
            float(obj["dp_24h_hpa"]),
        )
    return lookup


def load_meteo_features_for_dates(step_dates: Sequence[str]) -> np.ndarray:
    """Aliniază strict cauzal invariantele (ρ_air, RH, ΔP_24h) [S, 3] în float64 pentru o listă ordonată de date."""
    lookup = load_meteo_lookup()
    out = np.zeros((len(step_dates), 3), dtype=np.float64)
    last_vec: Optional[Tuple[float, float, float]] = None
    for idx, d_str in enumerate(step_dates):
        key = str(d_str)[:10]
        if key in lookup:
            vec = lookup[key]
        elif last_vec is not None:
            # Persistență strict cauzală (ΔP_24h = 0)
            vec = (last_vec[0], last_vec[1], 0.0)
        else:
            d_obj = dt.date.fromisoformat(key)
            tc, phpa, rh = _harmonic_bucharest_climatology(d_obj)
            vec = (compute_moist_air_density(tc, phpa, rh), rh, 0.0)
        out[idx, 0] = vec[0]
        out[idx, 1] = vec[1]
        out[idx, 2] = vec[2]
        last_vec = vec
    return out


if __name__ == "__main__":
    info = build_or_load_bucharest_meteo()
    print(json.dumps({k: v for k, v in info.items() if k != "queried_urls"}, indent=2, ensure_ascii=False))
