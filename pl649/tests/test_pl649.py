"""Teste unitare PL649 (motorul pl_core; rapide; CUDA dacă există, altfel CPU)."""
import sys
from pathlib import Path

import numpy as np
import pytest
import torch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import pl_core as C  # noqa: E402
import pl649 as P  # noqa: E402

DEV = C.resolve_device()


def _rand_steps(seed, n=25):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        a = np.zeros((1, 49))
        a[0, rng.choice(49, 6, replace=False)] = 1
        out.append(a)
    return out


def test_kicks_are_su3():
    E = C.kick_matrices(DEV)
    I = torch.eye(3, dtype=E.dtype, device=DEV)
    assert float((E.conj().transpose(-1, -2) @ E - I).abs().max()) < 1e-14
    assert float((torch.linalg.det(E) - 1).abs().max()) < 1e-14
    for k in range(8):
        assert np.allclose(E[k].cpu().numpy(), P._exp_closed(k), atol=1e-14)


def test_gpu_m2_equals_triangle_reference():
    steps = _rand_steps(7)
    st = P.state_after(steps, DEV)
    g = C.geometry(st.U, st.n)
    kr, er = P.ref_curvature(*P.ref_links(steps))
    assert np.abs(g["kappa"][0].cpu().numpy() - kr).max() < 1e-12
    assert np.abs(g["eps_edge"][0].cpu().numpy() - er).max() < 1e-12


def test_gauge_invariance():
    steps = _rand_steps(8)
    st = P.state_after(steps, DEV)
    rng = np.random.default_rng(3)
    G = torch.as_tensor(np.stack([P.random_su3(rng) for _ in range(49)]), device=DEV)
    pa, pb = torch.as_tensor(C.PA, device=DEV), torch.as_tensor(C.PB, device=DEV)
    Ug = G[pa][None] @ st.U @ G[pb][None].conj().transpose(-1, -2)
    a, b = C.geometry(st.U, st.n), C.geometry(Ug, st.n)
    assert float((a["kappa"] - b["kappa"]).abs().max()) < 1e-10


def test_flat_history_is_uniform_and_order_matters():
    Hp = P.onehot_sets([P.D1, P.D2, P.D3])
    Hm = P.onehot_sets([P.D1, P.D3, P.D2])
    pm = P.predict_at(Hm, DEV)["pi"][0].cpu().numpy()
    pp = P.predict_at(Hp, DEV)["pi"][0].cpu().numpy()
    assert np.abs(pm - 1 / 49).max() < 1e-12
    assert pp[1] > pp[12] > pp[0]


@pytest.mark.skipif(not torch.cuda.is_available(), reason="enumerarea completă cere CUDA pentru viteză")
def test_enumeration_matches_cpu_and_variants_unique():
    steps = _rand_steps(9)
    enum = C.Enumerator(DEV)
    r = P.predict_at(steps, DEV, enum)
    h, J = r["h"][0], r["J"][0]
    rc = P.cpu_enumerate(h.cpu().numpy(), J.cpu().numpy())
    assert r["qubo"][0]["ticket"] == rc["ticket"]
    v = enum.variants(h, J, 3)
    assert len({tuple(x["ticket"]) for x in v}) == 3
