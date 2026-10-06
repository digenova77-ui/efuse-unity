"""
DCLM TOKENIZATION — public path (PEP-562 shim).

The implementation lives in `token_engine.py`, NOT here, for one honest
engineering reason: a module named `tokenize.py` shadows the STDLIB
`tokenize` module that `linecache` / `traceback` / `unittest` import at
their top level. With this directory on sys.path, the shadow turns
`import dataclasses` into a circular-import ImportError and every
sibling test suite fails before its first test (verified 2026-10-06).
So this file is a thin, import-cycle-safe shim:

  * At import time it does NOTHING that can trigger an import cycle:
    it loads the real stdlib `tokenize` from its file location (so
    linecache's runtime use of `tokenize.open` keeps working) and
    defines __getattr__ only.
  * Attribute access for the engine API (`tokenize`, `set_peg_ratio`,
    `Tokenizer`, `merit_transfer`, `standing`, …) lazily imports
    `token_engine` and delegates. `from tokenize import tokenize` works
    as specified. (The dead `bound_sale` is gone — Unity never transfers.)
  * Any other attribute (e.g. stdlib's `tokenize.open`, `generate_tokens`)
    resolves against the REAL stdlib module — this shim is transparent
    to stdlib consumers.

Public API (all implemented in token_engine.py):
  tokenize(receipt) -> TokenBundle
  merit_transfer(from_id, to_id, amount, reason, auth) -> signed
    MERIT_TRANSFER envelope (the SOLE legal Merit ownership-transfer
    path; auth is the sender's REQUIRED Ed25519 transfer authorization —
    unsigned transfers are refused; origin immutable, standing never
    moves)
  standing(identity) -> earned standing (origin-based; never moves on
    transfer) / merit_balance(identity) -> owned Merit (economic value)
  set_peg_ratio(E, authority) / peg_ratio()
  Tokenizer, TokenBundle, TokenizeError, TokenizeRefused, UnityMintRefused
  EFuseToken, MeritRecord, HonorRecord, UnityToken, UnityHolding,
  TransferReceipt
  assert_single_mint_path(), assert_no_unity_rebind(),
  assert_single_merit_transfer_path()
  mint_paths(), unity_transfer_paths(), merit_transfer_paths()
  KIND_*/REASON_*/SCHEMA/NETWORK constants

  Unity is NON-TRANSFERABLE — no transfer path exists (the bound sale is
  dead). Merit is TRANSFERABLE (David's word, 2026-10-06); transfers move
  economic value only, never standing.

TESTNET ONLY.
"""

import importlib.util as _ilu
import os as _os
import sysconfig as _sc

# The real stdlib tokenize, loaded from its file location so this shim's
# name never poisons stdlib consumers (linecache uses tokenize.open at
# runtime when formatting tracebacks).
_stdlib_spec = _ilu.spec_from_file_location(
    "_dclm_stdlib_tokenize_real",
    _os.path.join(_sc.get_path("stdlib"), "tokenize.py"),
)
_stdlib_tokenize = _ilu.module_from_spec(_stdlib_spec)
_stdlib_spec.loader.exec_module(_stdlib_tokenize)


def __getattr__(name):
    # Dunder probes (copy, pickle, inspect) must not trigger engine loads.
    if name.startswith("__") and name.endswith("__"):
        raise AttributeError(name)
    try:
        import importlib as _importlib

        _eng = _importlib.import_module("token_engine")
    except ImportError:
        _eng = None
    if _eng is not None and hasattr(_eng, name):
        return getattr(_eng, name)
    # Transparent to stdlib consumers: tokenize.open, generate_tokens, …
    return getattr(_stdlib_tokenize, name)


def __dir__():
    try:
        import importlib as _importlib

        _eng = _importlib.import_module("token_engine")
        engine_names = [n for n in dir(_eng) if not n.startswith("_")]
    except ImportError:
        engine_names = []
    return sorted(set(engine_names) | set(dir(_stdlib_tokenize)))
