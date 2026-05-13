"""Helpers for include/exclude state mutations."""

from __future__ import annotations


def apply_point_exclusion(
    excluded_ids: set,
    excluded_member_keys: set,
    *,
    point_id: str,
    member_key: str = "",
    exclude: bool = True,
) -> bool:
    """
    Mutate exclusion sets and return whether any state changed.

    Rules:
    - If member_key is provided: apply member-level exclusion.
    - If member_key is empty: apply ID-level exclusion.
    - Member-level include also clears ID-level exclusion for that ID.
    """
    pid = str(point_id or "").strip()
    mkey = str(member_key or "").strip()
    changed = False

    if mkey:
        if exclude:
            if mkey not in excluded_member_keys:
                excluded_member_keys.add(mkey)
                changed = True
        else:
            if mkey in excluded_member_keys:
                excluded_member_keys.discard(mkey)
                changed = True
            if pid:
                if pid in excluded_ids:
                    excluded_ids.discard(pid)
                    changed = True
                try:
                    ipid = int(pid)
                    if ipid in excluded_ids:
                        excluded_ids.discard(ipid)
                        changed = True
                except Exception:
                    pass
        return changed

    if not pid:
        return changed

    if exclude:
        if pid not in excluded_ids:
            changed = True
        excluded_ids.add(pid)
        try:
            ipid = int(pid)
            if ipid not in excluded_ids:
                changed = True
            excluded_ids.add(ipid)
        except Exception:
            pass
        return changed

    if pid in excluded_ids:
        excluded_ids.discard(pid)
        changed = True
    try:
        ipid = int(pid)
        if ipid in excluded_ids:
            excluded_ids.discard(ipid)
            changed = True
    except Exception:
        pass
    return changed

