from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import Any, MutableMapping

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq


def load_workflow_yaml(path: Path) -> Any:
    yaml = _build_yaml_parser()
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.load(handle)
    if data is None:
        return CommentedMap()
    return data


def write_workflow_yaml(path: Path, data: Any) -> None:
    yaml = _build_yaml_parser()
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump(data, handle)


def iter_uses_nodes(node: Any) -> Generator[tuple[MutableMapping[str, Any], str, str], None, None]:
    if isinstance(node, CommentedMap):
        for key, value in node.items():
            if key == "uses" and isinstance(value, str):
                yield node, "uses", value
            yield from iter_uses_nodes(value)
        return

    if isinstance(node, CommentedSeq):
        for item in node:
            yield from iter_uses_nodes(item)


def _build_yaml_parser() -> YAML:
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.width = 4096
    return yaml
