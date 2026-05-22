from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit


@dataclass(frozen=True)
class XInternalTimelineTemplate:
    base_url: str
    query_id: str | None
    operation_name: str | None
    variables: dict[str, Any]
    features: dict[str, Any] | None
    field_toggles: dict[str, Any] | None


def parse_timeline_url(url: str) -> XInternalTimelineTemplate:
    parts = urlsplit(url)
    query = parse_qs(parts.query, keep_blank_values=True)
    variables = _decode_json_query_object(query, "variables", required=True)
    features = _decode_json_query_object(query, "features", required=False)
    field_toggles = _decode_json_query_object(query, "fieldToggles", required=False)
    path_parts = [part for part in parts.path.split("/") if part]
    operation_name = path_parts[-1] if path_parts else None
    query_id = None
    if len(path_parts) >= 2 and path_parts[-2] != "graphql":
        query_id = path_parts[-2]

    return XInternalTimelineTemplate(
        base_url=urlunsplit((parts.scheme, parts.netloc, parts.path, "", parts.fragment)),
        query_id=query_id,
        operation_name=operation_name,
        variables=variables,
        features=features,
        field_toggles=field_toggles,
    )


def build_timeline_url(
    template: XInternalTimelineTemplate,
    user_id: str,
    count: int | None = None,
) -> str:
    variables = deepcopy(template.variables)
    variables["userId"] = user_id
    if count is not None:
        variables["count"] = count

    query = {"variables": _compact_json(variables)}
    if template.features is not None:
        query["features"] = _compact_json(template.features)
    if template.field_toggles is not None:
        query["fieldToggles"] = _compact_json(template.field_toggles)

    parts = urlsplit(template.base_url)
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query),
            parts.fragment,
        )
    )


def extract_user_id_from_timeline_url(url: str) -> str | None:
    try:
        template = parse_timeline_url(url)
    except ValueError:
        return None
    user_id = template.variables.get("userId")
    return user_id if isinstance(user_id, str) else None


def _decode_json_query_object(
    query: dict[str, list[str]],
    name: str,
    *,
    required: bool,
) -> dict[str, Any] | None:
    values = query.get(name)
    if not values:
        if required:
            raise ValueError(f"missing {name} query parameter")
        return None

    raw = values[-1]
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid {name} JSON: {exc}") from exc

    if not isinstance(decoded, dict):
        raise ValueError(f"{name} query parameter must decode to a JSON object")
    return decoded


def _compact_json(value: dict[str, Any]) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)
