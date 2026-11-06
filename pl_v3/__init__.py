"""PL-V3 — Dynamic SU(3) Yang-Mills Flow, Exact Hodge Curl & Fermionic Determinantal Engine.

Strict predictive mathematical laboratory module. Classic GPU/CPU computation;
`positive_claims_allowed = False`. Zero commercial/accounting metrics.
"""
from .core import (
    PLV3Params,
    PLV3State,
    SimplicialTopology,
    advance_steps,
    cauchy_binet_exact_ek,
    evaluate_full_space,
    extract_step_slices,
    forward_operators_from_state,
    init_state,
)
from .walkforward import (
    evaluate_full_space_fast,
    get_or_advance_live,
    run_walkforward,
    verify_incremental_regression,
)

__all__ = [
    "PLV3Params",
    "PLV3State",
    "SimplicialTopology",
    "advance_steps",
    "cauchy_binet_exact_ek",
    "evaluate_full_space",
    "evaluate_full_space_fast",
    "extract_step_slices",
    "forward_operators_from_state",
    "get_or_advance_live",
    "init_state",
    "run_walkforward",
    "verify_incremental_regression",
]
