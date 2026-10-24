"""Tests for the pure Unity key design."""

import pytest

from unity_keys import (
    UnityStore,
    unity_bind,
    unity_key,
    merit_pay,
    unity_unbind,
)


def test_bind_sets_current_and_records():
    st = UnityStore()
    unity_bind(st, "u1", "pk1", "sig-pk1")
    u = st.get("u1")
    assert u is not None
    assert u.pubkey == "pk1"
    assert u.keys_used == ["pk1"]
    assert u.bound is True


def test_rotate_appends_and_changes_current():
    st = UnityStore()
    unity_bind(st, "u1", "pk1", "sig-pk1")
    unity_key(st, "u1", "pk2", "sig-pk1")
    u = st.get("u1")
    assert u.pubkey == "pk2"
    assert u.keys_used == ["pk1", "pk2"]


def test_unity_key_reused_refuses_old_key():
    st = UnityStore()
    unity_bind(st, "u1", "pk1", "sig-pk1")
    unity_key(st, "u1", "pk2", "sig-pk1")
    with pytest.raises(ValueError, match="UNITY_KEY_REUSED"):
        unity_key(st, "u1", "pk1", "sig-pk2")


def test_merit_pay_accepts_current_key():
    st = UnityStore()
    unity_bind(st, "u1", "pk1", "sig-pk1")
    unity_bind(st, "u2", "pk2", "sig-pk2")
    merit_pay(st, "u1", "u2", 10, "n1", "sig-pk1")
    assert "n1" in st.nonces


def test_merit_pay_refuses_old_key():
    st = UnityStore()
    unity_bind(st, "u1", "pk1", "sig-pk1")
    unity_bind(st, "u2", "pk2", "sig-pk2")
    unity_key(st, "u1", "pk3", "sig-pk1")
    with pytest.raises(ValueError, match="PAY_BAD_SIGNATURE"):
        merit_pay(st, "u1", "u2", 10, "n2", "sig-pk1")


def test_unbind_leaves_keys():
    st = UnityStore()
    unity_bind(st, "u1", "pk1", "sig-pk1")
    unity_key(st, "u1", "pk2", "sig-pk1")
    unity_unbind(st, "u1")
    u = st.get("u1")
    assert u.bound is False
    assert u.pubkey == "pk2"
    assert u.keys_used == ["pk1", "pk2"]


def test_pay_needs_current_key():
    st = UnityStore()
    unity_bind(st, "u1", "pk1", "sig-pk1")
    unity_bind(st, "u2", "pk2", "sig-pk2")
    st.get("u1").pubkey = None
    with pytest.raises(ValueError, match="PAY_NEEDS_KEY"):
        merit_pay(st, "u1", "u2", 1, "n3", "sig-anything")
