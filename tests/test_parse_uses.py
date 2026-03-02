from gha_update.parse_uses import parse_uses_value


def test_parse_standard_action_reference() -> None:
    parsed, reason = parse_uses_value("actions/checkout@v4")

    assert reason is None
    assert parsed is not None
    assert parsed.owner == "actions"
    assert parsed.repo == "checkout"
    assert parsed.subpath is None
    assert parsed.ref == "v4"


def test_parse_reusable_workflow_subpath() -> None:
    parsed, reason = parse_uses_value(
        "acme/ci/.github/workflows/reusable.yml@v2"
    )

    assert reason is None
    assert parsed is not None
    assert parsed.subpath == ".github/workflows/reusable.yml"


def test_skip_local_action() -> None:
    parsed, reason = parse_uses_value("./.github/actions/custom")

    assert parsed is None
    assert reason == "local_action"


def test_skip_docker_reference() -> None:
    parsed, reason = parse_uses_value("docker://alpine:3.20")

    assert parsed is None
    assert reason == "docker_reference"


def test_skip_expression_reference() -> None:
    parsed, reason = parse_uses_value("actions/checkout@${{ matrix.ref }}")

    assert parsed is None
    assert reason == "expression_reference"
