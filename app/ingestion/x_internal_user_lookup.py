from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit


@dataclass(frozen=True)
class XInternalUserLookupTemplate:
    base_url: str
    query_id: str | None
    operation_name: str | None
    variables: dict[str, Any]
    features: dict[str, Any] | None
    field_toggles: dict[str, Any] | None


def parse_user_lookup_url(url: str) -> XInternalUserLookupTemplate:
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

    return XInternalUserLookupTemplate(
        base_url=urlunsplit((parts.scheme, parts.netloc, parts.path, "", parts.fragment)),
        query_id=query_id,
        operation_name=operation_name,
        variables=variables,
        features=features,
        field_toggles=field_toggles,
    )


def build_user_lookup_url(template: XInternalUserLookupTemplate, handle: str) -> str:
    variables = deepcopy(template.variables)
    screen_name = handle.lstrip("@")
    if "screen_name" in variables:
        variables["screen_name"] = screen_name
    elif "screenName" in variables:
        variables["screenName"] = screen_name
    else:
        variables["screen_name"] = screen_name

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


def extract_user_id_from_user_lookup_json(payload: Any) -> str | None:
    result = _as_dict(_as_dict(_as_dict(payload).get("data")).get("user")).get("result")
    user = _as_dict(result)
    legacy = _as_dict(user.get("legacy"))
    for value in (
        user.get("rest_id"),
        user.get("id"),
        legacy.get("id_str"),
        legacy.get("user_id_str"),
    ):
        if isinstance(value, str) and value:
            return value
        if isinstance(value, int):
            return str(value)
    return None


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


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
