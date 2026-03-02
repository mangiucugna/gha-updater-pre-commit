from __future__ import annotations

from dataclasses import dataclass
import re


_REPO_PART_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


@dataclass(frozen=True)
class ParsedUses:
    owner: str
    repo: str
    subpath: str | None
    ref: str

    @property
    def repo_key(self) -> str:
        return f"{self.owner}/{self.repo}".lower()

    def with_ref(self, new_ref: str) -> str:
        prefix = f"{self.owner}/{self.repo}"
        if self.subpath:
            prefix = f"{prefix}/{self.subpath}"
        return f"{prefix}@{new_ref}"


def parse_uses_value(raw_value: str) -> tuple[ParsedUses | None, str | None]:
    if raw_value.startswith("./"):
        return None, "local_action"

    if raw_value.startswith("docker://"):
        return None, "docker_reference"

    if "${{" in raw_value:
        return None, "expression_reference"

    if "@" not in raw_value:
        return None, "malformed_uses"

    action_path, ref = raw_value.rsplit("@", 1)
    if not action_path or not ref:
        return None, "malformed_uses"

    parts = action_path.split("/")
    if len(parts) < 2:
        return None, "malformed_uses"

    owner = parts[0]
    repo = parts[1]
    subpath_parts = parts[2:]

    if not _REPO_PART_PATTERN.fullmatch(owner):
        return None, "malformed_uses"
    if not _REPO_PART_PATTERN.fullmatch(repo):
        return None, "malformed_uses"

    if any(not part for part in subpath_parts):
        return None, "malformed_uses"

    subpath = "/".join(subpath_parts) if subpath_parts else None

    return ParsedUses(owner=owner, repo=repo, subpath=subpath, ref=ref), None
