"""Teste TU4-JU (S13): rădăcini SINTETICE; nu ating lanțul real, decontările reale sau arhiva reală."""
import datetime as dt
import hashlib
import itertools
import json
import math
import os
import stat
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

TU4 = Path(__file__).resolve().parents[1]
QL = TU4.parent
sys.path.insert(0, str(TU4))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import judecator as J  # noqa: E402
import verifica_ju as VJ  # noqa: E402
import calibrare_ju as CJ  # noqa: E402
from test_em import make_live, run as emit  # noqa: E402

NOW_EM = "2026-10-27T21:40:00Z"


def sha(b):
    return hashlib.sha256(b).hexdigest()


def rec(game, date, nums, joker=None, kind="regular", dis=False):
    nums = sorted(nums)
    return {"draw_date": date, "draw_key": f"{game}:{date}:{'-'.join(map(str, nums))}" + (f":J{joker}" if joker else ""),
            "draw_kind": kind, "game": game, "numbers": nums, "joker": joker, "has_source_disagreement": dis,
            "provenance": {"run_id": "test"}}


def add_version(root: Path, additions: dict, version: str):
    live = root / "tu3" / "date" / "live"
    cur = json.loads((live / "CURRENT_LIVE.json").read_text())
    old = live / cur["version_dir"]
    man = json.loads((old / "MANIFEST_LIVE.json").read_text())
    new = live / "versiuni" / version
    new.mkdir(parents=True)
    for g, gm in man["games"].items():
        data = (old / gm["file"]).read_bytes()
        for r in additions.get(g, []):
            data += (json.dumps(r) + "\n").encode()
        (new / gm["file"]).write_bytes(data)
        lines = data.splitlines()
        gm.update(sha256=sha(data), records=len(lines), last_date=max(json.loads(x)["draw_date"] for x in lines),
                  last_key=json.loads(lines[-1])["draw_key"])
    (new / "MANIFEST_LIVE.json").write_text(json.dumps(man))
    cur["version_dir"] = f"versiuni/{version}"
    cur["games"] = {g: {k: man["games"][g][k] for k in ("records", "last_date", "last_key", "sha256")} for g in man["games"]}
    (live / "CURRENT_LIVE.json").write_text(json.dumps(cur))


DRAWS_29 = {"649": [rec("649", "2026-10-29", [3, 11, 19, 27, 35, 44]), rec("649", "2026-10-29", [1, 2, 9, 10, 20, 30], kind="special")],
            "540": [rec("540", "2026-10-29", [2, 5, 13, 21, 33, 40])],
            "joker": [rec("joker", "2026-10-29", [4, 9, 17, 28, 41], joker=7)]}


def judge(root, now, ssd=None, gpu=False):
    args = ["--radacina-test", str(root), "--acum", now]
    args += ["--ssd", str(ssd)] if ssd else ["--fara-ssd"]
    if not gpu:
        args.append("--fara-gpu")
    return J.main(args)


def verify(root, now, ssd=None):
    return VJ.verify(root.resolve(), VJ.T(now), True, ssd, None)


def setup_emissions(tmp_path, tilt=0.25):
    root = tmp_path / "r"
    make_live(root, tilt=tilt)
    for g in ("649", "540", "joker"):
        assert emit(root, g, NOW_EM) == 0
    return root


def decs(root):
    p = root / "tu4" / "tribunal" / "DECONTARI.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


def doc(root, game, D):
    return json.loads((root / "tu4" / "tribunal" / "decontari" / game / f"{D}.json").read_text())


# ---------------------------------------------------------------- factorul e
def test_factor_e_enumerare_exacta_si_newton():
    rng = np.random.default_rng(11)
    for n, k in ((8, 3), (9, 1), (10, 4)):
        lw = list(rng.normal(0, 0.4, n))
        tot_q, tot_e = 0.0, 0.0
        for S in itertools.combinations(range(1, n + 1), k):
            le = J.ln_e_block(lw, list(S), k, True)
            assert abs(le - VJ.ln_e_newton(lw, list(S), k, True)) < 1e-12
            tot_e += math.exp(le)
        assert abs(tot_e / math.comb(n, k) - 1.0) < 1e-12          # E_u[e] = 1 (martingală)


def test_lambda_zero_exact_unu():
    assert J.ln_e_block([0.0] * 49, [1, 2, 3, 4, 5, 6], 6, False) == 0.0
    assert VJ.ln_e_newton([0.3] * 20, [5], 1, False) == 0.0
    assert abs(J.ln_e_block([0.0] * 49, [1, 2, 3, 4, 5, 6], 6, True)) < 1e-12


def test_masina_de_stari_si_reimplementarea():
    rng = np.random.default_rng(2)
    for trial in range(200):
        a = b = J.init_state()
        base = dt.datetime(2026, 11, 1, tzinfo=dt.timezone.utc)
        for t in range(60):
            le = float(rng.normal(0.4 if trial % 3 == 0 else -0.3, 1.0))
            st = ["DECONTAT", "DECONTAT", "VOID"][t % 3] if trial % 5 == 0 else "DECONTAT"
            D = (base + dt.timedelta(days=3 * t)).date().isoformat()
            em = J.iso(base + dt.timedelta(days=3 * t - 1))
            dec = J.iso(base + dt.timedelta(days=3 * t, hours=5))
            a, ca = J.advance(a, st, le, D, em, dec)
            b, cb = VJ.step(b, st, le, D, em, dec)
            assert a == b and ca == cb
    s = J.init_state()
    s, _ = J.advance(s, "DECONTAT", 6.5, "2026-11-01", "2026-10-31T10:00:00.000000Z", "2026-11-01T20:00:00.000000Z")
    assert s["state"] == "CONFIRMARE" and s["conf_start_date"] == "2026-11-01"
    s2, c = J.advance(s, "DECONTAT", 5.0, "2026-11-05", "2026-11-01T19:00:00.000000Z", "2026-11-05T20:00:00.000000Z")
    assert not c and s2["state"] == "CONFIRMARE"                    # emisă înaintea trecerii pragului: nu contează
    s3, c = J.advance(s, "DECONTAT", 3.1, "2026-11-05", "2026-11-02T10:00:00.000000Z", "2026-11-05T20:00:00.000000Z")
    assert c and s3["state"] == "CONFIRMAT"
    r = J.init_state()
    r, _ = J.advance(r, "DECONTAT", -10.5, "2026-11-01", "x", "y")
    assert r["state"] == "RETRAS"
    r2, c = J.advance(r, "DECONTAT", 50.0, "2026-11-05", "x", "y")
    assert r2 == r and not c                                        # retragerea este absorbantă


def test_cuantile_binomiale_independente():
    for R, p in ((10000, 1 / 600), (10000, 0.01), (10000, 0.05), (500, 0.2)):
        assert CJ.q999(R, p) == VJ.q999_ratio(R, p)


# ---------------------------------------------------------------- fluxul complet
def test_flux_complet_decontare_gpu_ssd_verificator(tmp_path):
    root = setup_emissions(tmp_path)
    trib = root / "tu4" / "tribunal"
    ssd = tmp_path / "ssd" / "QL649_TU4_JU"
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in sorted(trib.glob("emisii/*/*.json")) + [trib / "LANT.jsonl"]}
    assert judge(root, "2026-10-28T10:00:00Z", ssd) == 0
    assert decs(root) == []
    runs = [json.loads(x) for x in (trib / "JUDECATOR_RULARI.jsonl").read_text().splitlines()]
    assert len(runs[-1]["observed"]) == 3 and runs[-1]["action"] == "nothing_to_settle"
    assert judge(root, "2026-10-29T20:00:00Z", ssd) == 0               # după extragere, dar încă nu e în arhivă
    assert decs(root) == [] and all("arhiva LIVE" in p["reason"] for p in
                                    json.loads((trib / "JUDECATOR_RULARI.jsonl").read_text().splitlines()[-1])["pending"])
    add_version(root, DRAWS_29, "bbbb00000002")
    assert judge(root, "2026-10-29T21:00:00Z", ssd, gpu=True) == 0
    d = decs(root)
    assert [x["status"] for x in d] == ["DECONTAT"] * 3
    for g in ("649", "540", "joker"):
        x = doc(root, g, "2026-10-29")
        em = json.loads((trib / "emisii" / g / "2026-10-29.json").read_text())
        assert x["corroboration"]["observed_by_judge_before_draw"] is True
        assert x["record"]["canonical"]["draw_kind"] == "regular"
        for m in ("H1", "H3"):
            blk = em["models"][m]
            ref = VJ.ln_e_newton(blk["logw"], x["draw"]["numbers"], em["k"], blk["bet_active"])
            assert abs(x["models"][m]["ln_e_main"] - ref) < 1e-10
            assert abs(x["streams_after"][f"{m}_{g}"]["lnE"] - x["models"][m]["ln_e"]) < 1e-15
        if x["gpu_mirror"] is not None:
            assert x["gpu_mirror"]["pass"] is True, x["gpu_mirror"]
        assert stat.S_IMODE((trib / "decontari" / g / "2026-10-29.json").stat().st_mode) == 0o444
    assert doc(root, "649", "2026-10-29")["draw"]["numbers"] == [3, 11, 19, 27, 35, 44]   # specialul ignorat
    assert judge(root, "2026-10-29T21:30:00Z", ssd) == 0 and len(decs(root)) == 3        # no-op
    after = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before}
    assert after == before                                           # Zero Alteration Guard
    m = (ssd / "SCORURI_JU.mmap").read_bytes()
    assert m[:8] == b"QL649JU1" and len(m) == 512 + 3 * 160
    res = verify(root, "2026-10-29T21:30:00Z", ssd)
    assert res["verdict"] == "VERIFICARE_JU_PASS", [c for c in res["checks"] if c["status"] != "PASS"]


def test_void_ambiguu_absent_dezacord_si_ordinea(tmp_path):
    root = setup_emissions(tmp_path)
    add_version(root, {"649": [rec("649", "2026-10-29", [1, 2, 3, 4, 5, 6]), rec("649", "2026-10-29", [7, 8, 9, 10, 11, 12])],
                       "540": [rec("540", "2026-10-29", [1, 2, 3, 4, 5, 6], dis=True)]}, "cccc00000003")
    assert judge(root, "2026-10-29T21:00:00Z") == 0
    st = {x["game"]: x["status"] for x in decs(root)}
    assert st == {"649": "VOID"}
    x = doc(root, "649", "2026-10-29")
    assert x["models"]["H1"]["ln_e"] == 0.0 and x["streams_after"]["H1_649"]["lnE"] == 0.0
    # a doua emisie (01 nov) pentru joker și 540, în fereastra finală (arhiva nu are 29 pentru joker)
    for g in ("540", "joker"):
        assert emit(root, g, "2026-11-01T13:30:00Z") == 0
    add_version(root, {"joker": [rec("joker", "2026-11-01", [1, 2, 3, 4, 5], joker=3)]}, "dddd00000004")
    assert judge(root, "2026-11-01T20:00:00Z") == 0
    assert not any(x["target_date"] == "2026-11-01" for x in decs(root))   # blocat în spatele lui 29 (ordine)
    assert judge(root, "2026-11-12T17:00:00Z") == 0                       # 29 + 14 zile
    got = {(x["game"], x["target_date"]): x["status"] for x in decs(root)}
    assert got[("540", "2026-10-29")] == "VOID" and got[("joker", "2026-10-29")] == "VOID"
    assert got[("joker", "2026-11-01")] == "DECONTAT" and ("540", "2026-11-01") not in got
    res = verify(root, "2026-11-12T17:00:00Z")
    assert res["verdict"] == "VERIFICARE_JU_PASS", [c for c in res["checks"] if c["status"] != "PASS"]


def test_integritate_refuz_total_si_incident(tmp_path):
    root = setup_emissions(tmp_path)
    trib = root / "tu4" / "tribunal"
    f = trib / "emisii" / "540" / "2026-10-29.json"
    os.chmod(f, 0o644)
    f.write_bytes(f.read_bytes().replace(b'"lambda": 0.0', b'"lambda": 0.5', 1) + b" ")
    add_version(root, DRAWS_29, "eeee00000005")
    assert judge(root, "2026-10-29T21:00:00Z") == 3
    assert decs(root) == []
    assert list((root / "tu4" / "incidente").glob("JU_INTEGRITATE_*.json"))
    assert verify(root, "2026-10-29T21:00:00Z")["verdict"] == "VERIFICARE_JU_FAIL"


def rebuild_lant(trib: Path):
    """Simulează un emițător defect care a scris o emisie târzie DAR cu lanțul consistent."""
    lant = trib / "LANT.jsonl"
    lines = [json.loads(x) for x in lant.read_text().splitlines()]
    prev = sha((TU4 / "SIGILIU_TU4_EM.json").read_bytes())
    out = []
    for r in lines:
        b = (trib / r["file"]).read_bytes()
        r.update(sha256=sha(b), emitted_utc=json.loads(b)["emitted_utc"], prev_line_sha256=prev)
        ln = json.dumps(r, ensure_ascii=False, sort_keys=True).encode()
        prev = sha(ln)
        out.append(ln)
    os.chmod(lant, 0o644)
    lant.write_bytes(b"\n".join(out) + b"\n")


def test_emisie_tarzie_respinsa(tmp_path):
    root = setup_emissions(tmp_path)
    trib = root / "tu4" / "tribunal"
    f = trib / "emisii" / "joker" / "2026-10-29.json"
    em = json.loads(f.read_text())
    em["emitted_utc"] = "2026-10-29T14:30:00.000000Z"                  # după termen
    os.chmod(f, 0o644)
    f.write_text(json.dumps(em, indent=1, ensure_ascii=False) + "\n")
    rebuild_lant(trib)
    add_version(root, DRAWS_29, "ffff00000006")
    assert judge(root, "2026-10-29T21:00:00Z") == 0
    got = {x["game"]: x["status"] for x in decs(root)}
    assert got == {"649": "DECONTAT", "540": "DECONTAT", "joker": "RESPINS"}
    assert doc(root, "joker", "2026-10-29")["admissibility"]["A1_cronologie"] is False
    assert (root / "tu4" / "incidente" / "JU_RESPINS_joker_2026-10-29.json").exists()
    res = verify(root, "2026-10-29T21:00:00Z")
    assert res["verdict"] == "VERIFICARE_JU_PASS", [c for c in res["checks"] if c["status"] != "PASS"]


def test_verificatorul_prinde_decontarea_alterata_si_matricea(tmp_path):
    root = setup_emissions(tmp_path)
    ssd = tmp_path / "ssd" / "QL649_TU4_JU"
    add_version(root, DRAWS_29, "abab00000007")
    assert judge(root, "2026-10-29T21:00:00Z", ssd) == 0
    mp = ssd / "SCORURI_JU.mmap"
    os.chmod(mp, 0o644)
    b = bytearray(mp.read_bytes())
    b[512 + 40] ^= 1
    mp.write_bytes(bytes(b))
    res = verify(root, "2026-10-29T21:00:00Z", ssd)
    assert {c["id"]: c["status"] for c in res["checks"]}["V8_ssd"] == "FAIL"
    p = root / "tu4" / "tribunal" / "decontari" / "649" / "2026-10-29.json"
    os.chmod(p, 0o644)
    p.write_text(p.read_text().replace('"status": "DECONTAT"', '"status": "DECONTAT" ', 1))
    res = verify(root, "2026-10-29T21:00:00Z")
    assert {c["id"]: c["status"] for c in res["checks"]}["V5_lant_decontari"] == "FAIL"


def test_revizie_sursa_incident_fara_rescriere(tmp_path):
    root = setup_emissions(tmp_path)
    add_version(root, DRAWS_29, "acac00000008")
    assert judge(root, "2026-10-29T21:00:00Z") == 0
    b0 = (root / "tu4" / "tribunal" / "decontari" / "540" / "2026-10-29.json").read_bytes()
    live = root / "tu3" / "date" / "live"
    cur = json.loads((live / "CURRENT_LIVE.json").read_text())
    vd = live / cur["version_dir"]
    lines = (vd / "extrageri_540.jsonl").read_text().splitlines()
    lines[-1] = json.dumps(rec("540", "2026-10-29", [2, 5, 13, 21, 33, 39]))
    new = live / "versiuni" / "adad00000009"
    new.mkdir()
    for g in ("649", "joker"):
        (new / f"extrageri_{g}.jsonl").write_bytes((vd / f"extrageri_{g}.jsonl").read_bytes())
    data = ("\n".join(lines) + "\n").encode()
    (new / "extrageri_540.jsonl").write_bytes(data)
    man = json.loads((vd / "MANIFEST_LIVE.json").read_text())
    man["games"]["540"]["sha256"] = sha(data)
    (new / "MANIFEST_LIVE.json").write_text(json.dumps(man))
    cur["version_dir"] = "versiuni/adad00000009"
    cur["games"]["540"]["sha256"] = sha(data)
    (live / "CURRENT_LIVE.json").write_text(json.dumps(cur))
    assert judge(root, "2026-10-30T09:00:00Z") == 0
    assert (root / "tu4" / "incidente" / "JU_REVIZIE_540_2026-10-29.json").exists()
    assert (root / "tu4" / "tribunal" / "decontari" / "540" / "2026-10-29.json").read_bytes() == b0
    assert verify(root, "2026-10-30T09:00:00Z")["verdict"] == "VERIFICARE_JU_PASS"


def test_fara_torch_cand_nu_e_nimic_de_decontat(tmp_path):
    root = setup_emissions(tmp_path)
    code = ("import sys; sys.path.insert(0, %r); import judecator as J; "
            "rc = J.main(['--radacina-test', %r, '--acum', '2026-10-28T10:00:00Z', '--fara-ssd']); "
            "print('TORCH' if 'torch' in sys.modules else 'NOTORCH', rc)") % (str(TU4), str(root))
    out = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True, timeout=120)
    assert out.stdout.strip().splitlines()[-1] == "NOTORCH 0", out.stdout + out.stderr


def test_refuzuri_pe_lantul_real():
    assert J.main(["--acum", "2026-10-29T20:00:00Z", "--fara-ssd"]) == 3
    assert J.main(["--fara-gpu", "--fara-ssd"]) == 3
    assert J.main(["--radacina-test", str(QL), "--fara-ssd"]) == 3


def test_ast_fara_modele_si_popularitate():
    res = VJ.verify(QL, dt.datetime(2026, 10, 28, tzinfo=dt.timezone.utc), True, None, None)
    assert {c["id"]: c["status"] for c in res["checks"]}["V11_ast"] == "PASS"
