from gha_update.versions import (
    is_commit_sha,
    parse_tag,
    select_latest_ref,
    select_update_ref,
)


def test_parse_tag_handles_semver_prefix_and_components() -> None:
    parsed = parse_tag("v4.2.1")

    assert parsed is not None
    assert parsed.normalized == (4, 2, 1)
    assert parsed.component_count == 3
    assert parsed.prerelease is False


def test_is_commit_sha_detects_sha_pins() -> None:
    sha = "a" * 40
    assert is_commit_sha(sha)
    assert not is_commit_sha("v4")


def test_select_update_ref_allows_major_update() -> None:
    selection = select_update_ref(
        current_ref="v4",
        available_tags=["v4", "v5"],
        include_prereleases=False,
        update_scope="major",
    )

    assert selection.new_ref == "v5"
    assert selection.reason == "update_available"


def test_select_update_ref_major_pin_ignores_minor_and_patch_updates() -> None:
    selection = select_update_ref(
        current_ref="v4",
        available_tags=["v4.1.0", "v4.9.9"],
        include_prereleases=False,
        update_scope="major",
    )

    assert selection.new_ref is None
    assert selection.reason == "already_latest"


def test_select_update_ref_respects_minor_patch_scope() -> None:
    selection = select_update_ref(
        current_ref="v4.1",
        available_tags=["v4.2", "v5", "v5.1.0"],
        include_prereleases=False,
        update_scope="minor_patch",
    )

    assert selection.new_ref == "v4.2"


def test_select_update_ref_minor_pin_ignores_patch_only_updates() -> None:
    selection = select_update_ref(
        current_ref="v4.1",
        available_tags=["v4.1.1", "v4.1.9", "v5.0"],
        include_prereleases=False,
        update_scope="major",
    )

    assert selection.new_ref is None
    assert selection.reason == "already_latest"


def test_select_update_ref_minor_pin_updates_on_minor_bump() -> None:
    selection = select_update_ref(
        current_ref="v4.1",
        available_tags=["v4.1.9", "v4.2.0", "v5.0"],
        include_prereleases=False,
        update_scope="major",
    )

    assert selection.new_ref == "v4.2.0"
    assert selection.reason == "update_available"


def test_select_update_ref_ignores_prereleases_by_default() -> None:
    selection = select_update_ref(
        current_ref="v4",
        available_tags=["v4", "v5.0.0-rc.1"],
        include_prereleases=False,
        update_scope="major",
    )

    assert selection.new_ref is None
    assert selection.reason == "already_latest"


def test_select_latest_ref_includes_prerelease_when_enabled() -> None:
    selection = select_latest_ref(
        available_tags=["v4", "v5.0.0-rc.1"],
        include_prereleases=True,
    )

    assert selection.new_ref == "v5.0.0-rc.1"


def test_select_update_ref_major_pin_does_not_fallback_to_patch_tag() -> None:
    selection = select_update_ref(
        current_ref="v4",
        available_tags=["v4.2.1"],
        include_prereleases=False,
        update_scope="major",
    )

    assert selection.new_ref is None
    assert selection.reason == "already_latest"


def test_select_update_ref_patch_pin_updates_on_any_newer_version() -> None:
    selection = select_update_ref(
        current_ref="v4.1.1",
        available_tags=["v4.1.2", "v4.2.0", "v5"],
        include_prereleases=False,
        update_scope="major",
    )

    assert selection.new_ref == "v5"
    assert selection.reason == "update_available"


def test_select_update_ref_patch_pin_with_only_current_tag_is_already_latest() -> None:
    selection = select_update_ref(
        current_ref="v4.1.1",
        available_tags=["v4.1.1"],
        include_prereleases=False,
        update_scope="major",
    )

    assert selection.new_ref is None
    assert selection.reason == "already_latest"


def test_select_update_ref_returns_no_candidates_for_non_semver_tags() -> None:
    selection = select_update_ref(
        current_ref="v1",
        available_tags=["not-a-tag"],
        include_prereleases=False,
        update_scope="major",
    )

    assert selection.new_ref is None
    assert selection.reason == "no_candidate_tags"


def test_select_latest_ref_returns_no_candidates_when_empty() -> None:
    selection = select_latest_ref(
        available_tags=[],
        include_prereleases=False,
    )

    assert selection.new_ref is None
    assert selection.reason == "no_candidate_tags"
