from core.exclusion_state import apply_point_exclusion


def test_id_level_exclude_and_include_roundtrip():
    excluded_ids = set()
    excluded_member_keys = set()

    changed = apply_point_exclusion(
        excluded_ids,
        excluded_member_keys,
        point_id="42",
        member_key="",
        exclude=True,
    )
    assert changed is True
    assert "42" in excluded_ids
    assert 42 in excluded_ids

    changed = apply_point_exclusion(
        excluded_ids,
        excluded_member_keys,
        point_id="42",
        member_key="",
        exclude=False,
    )
    assert changed is True
    assert "42" not in excluded_ids
    assert 42 not in excluded_ids


def test_member_level_exclude_does_not_add_id_level():
    excluded_ids = set()
    excluded_member_keys = set()

    changed = apply_point_exclusion(
        excluded_ids,
        excluded_member_keys,
        point_id="A1",
        member_key="A1::17",
        exclude=True,
    )
    assert changed is True
    assert "A1::17" in excluded_member_keys
    assert "A1" not in excluded_ids


def test_member_level_include_clears_matching_id_level():
    excluded_ids = {"A1"}
    excluded_member_keys = {"A1::17"}

    changed = apply_point_exclusion(
        excluded_ids,
        excluded_member_keys,
        point_id="A1",
        member_key="A1::17",
        exclude=False,
    )
    assert changed is True
    assert "A1::17" not in excluded_member_keys
    assert "A1" not in excluded_ids
