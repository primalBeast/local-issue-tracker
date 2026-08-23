"""Field definition and item field validation."""

from __future__ import annotations

import re
from typing import Any

CONTROL_TYPES = frozenset(
    {
        "text",
        "textarea",
        "richtext",
        "select",
        "multiselect",
        "checkbox",
        "number",
        "date",
        "datetime",
    }
)

RICHTEXT_SOFT_LIMIT = 1_000_000  # bytes of JSON-ish size


class ValidationError(Exception):
    def __init__(self, message: str, errors: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.errors = errors or [{"message": message}]


def validate_fields_schema(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValidationError("fields document must be an object")
    fields = data.get("fields")
    if not isinstance(fields, list):
        raise ValidationError("fields must be an array")
    seen: set[str] = set()
    for f in fields:
        if not isinstance(f, dict):
            raise ValidationError("each field must be an object")
        fid = f.get("id")
        if not fid or not isinstance(fid, str):
            raise ValidationError("field.id is required")
        if fid in seen:
            raise ValidationError(f"duplicate field id: {fid}")
        seen.add(fid)
        if not f.get("label"):
            raise ValidationError(f"field {fid}: label required")
        ftype = f.get("type")
        if ftype not in CONTROL_TYPES:
            raise ValidationError(f"field {fid}: unsupported type {ftype}")
        if "order" not in f:
            raise ValidationError(f"field {fid}: order required")
        ord_v = f.get("order")
        if not isinstance(ord_v, (int, float, str)):
            raise ValidationError(
                f"field {fid}: order must be a number or string (e.g. 10 or \"10a\")"
            )
        if isinstance(ord_v, str):
            order_s = ord_v.strip()
            if not re.fullmatch(r"\d+[a-zA-Z]*", order_s):
                raise ValidationError(
                    f"field {fid}: order string must look like \"10\" or \"10a\", \"10b\", …"
                )
            f["order"] = int(order_s) if re.fullmatch(r"\d+", order_s) else order_s
        if "width" in f and f.get("width") is not None:
            w = f.get("width")
            if isinstance(w, bool) or not isinstance(w, (int, float)):
                raise ValidationError(f"field {fid}: width must be a number")
            if w <= 0 or w > 100:
                raise ValidationError(f"field {fid}: width must be between 1 and 100")
        if ftype in ("select", "multiselect"):
            opts = f.get("options")
            if not isinstance(opts, list) or len(opts) == 0:
                raise ValidationError(f"field {fid}: options required and non-empty")
    return data


def apply_defaults(field_defs: list[dict[str, Any]], fields: dict[str, Any]) -> dict[str, Any]:
    out = dict(fields)
    for f in field_defs:
        fid = f["id"]
        if fid not in out and "default" in f:
            out[fid] = f["default"]
    return out


def validate_item_fields(
    field_defs: list[dict[str, Any]],
    fields: dict[str, Any],
    *,
    partial: bool,
    require_required: bool,
) -> dict[str, Any]:
    by_id = {f["id"]: f for f in field_defs}
    errors: list[dict[str, Any]] = []

    for key in fields:
        if key not in by_id:
            errors.append({"field": key, "message": f"unknown field: {key}"})

    if errors:
        raise ValidationError("Unknown fields", errors)

    for key, value in fields.items():
        fdef = by_id[key]
        try:
            fields[key] = _coerce_and_check(fdef, value)
        except ValidationError as e:
            errors.extend(e.errors)

    if require_required:
        for fdef in field_defs:
            if fdef.get("required") and fdef["id"] not in fields:
                errors.append({"field": fdef["id"], "message": "required"})
            elif fdef.get("required") and _is_empty(fields.get(fdef["id"]), fdef):
                errors.append({"field": fdef["id"], "message": "required"})

    if errors:
        raise ValidationError("Validation failed", errors)
    return fields


def _is_empty(value: Any, fdef: dict[str, Any]) -> bool:
    if value is None:
        return True
    ftype = fdef.get("type")
    if ftype in ("text", "textarea", "select", "date", "datetime") and value == "":
        return True
    if ftype == "multiselect" and value == []:
        return True
    if ftype == "richtext" and (
        value == {} or value == {"type": "doc", "content": []} or value is None
    ):
        return False
    return False


def _coerce_and_check(fdef: dict[str, Any], value: Any) -> Any:
    fid = fdef["id"]
    ftype = fdef["type"]
    val = fdef.get("validation") or {}

    if ftype == "text":
        if not isinstance(value, str):
            raise ValidationError(f"{fid}: expected string", [{"field": fid, "message": "type"}])
        _check_string_rules(fid, value, val)
        return value

    if ftype == "textarea":
        if not isinstance(value, str):
            raise ValidationError(f"{fid}: expected string", [{"field": fid, "message": "type"}])
        _check_string_rules(fid, value, val)
        return value

    if ftype == "richtext":
        if not isinstance(value, (dict, list)):
            raise ValidationError(f"{fid}: expected object", [{"field": fid, "message": "type"}])
        import json

        raw = json.dumps(value)
        if len(raw) > RICHTEXT_SOFT_LIMIT:
            raise ValidationError(f"{fid}: too large", [{"field": fid, "message": "size"}])
        return value

    if ftype == "select":
        if not isinstance(value, str):
            raise ValidationError(f"{fid}: expected string", [{"field": fid, "message": "type"}])
        opts = fdef.get("options") or []
        if value not in opts and value != "":
            raise ValidationError(
                f"{fid}: not in options", [{"field": fid, "message": "options"}]
            )
        return value

    if ftype == "multiselect":
        if not isinstance(value, list):
            raise ValidationError(f"{fid}: expected array", [{"field": fid, "message": "type"}])
        opts = set(fdef.get("options") or [])
        for v in value:
            if v not in opts:
                raise ValidationError(
                    f"{fid}: {v} not in options", [{"field": fid, "message": "options"}]
                )
        return value

    if ftype == "checkbox":
        if not isinstance(value, bool):
            raise ValidationError(f"{fid}: expected boolean", [{"field": fid, "message": "type"}])
        return value

    if ftype == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValidationError(f"{fid}: expected number", [{"field": fid, "message": "type"}])
        num = float(value) if not isinstance(value, int) else value
        if "min" in val and num < val["min"]:
            raise ValidationError(f"{fid}: min", [{"field": fid, "message": "min"}])
        if "max" in val and num > val["max"]:
            raise ValidationError(f"{fid}: max", [{"field": fid, "message": "max"}])
        return num if isinstance(value, float) else int(value) if float(value) == int(value) else value

    if ftype == "date":
        if not isinstance(value, str):
            raise ValidationError(f"{fid}: expected string", [{"field": fid, "message": "type"}])
        if value and not re.match(r"^\d{4}-\d{2}-\d{2}$", value):
            raise ValidationError(f"{fid}: date format", [{"field": fid, "message": "format"}])
        return value

    if ftype == "datetime":
        if not isinstance(value, str):
            raise ValidationError(f"{fid}: expected string", [{"field": fid, "message": "type"}])
        return value

    raise ValidationError(f"{fid}: unsupported type")


def _check_string_rules(fid: str, value: str, val: dict[str, Any]) -> None:
    if "min_length" in val and len(value) < val["min_length"]:
        raise ValidationError(f"{fid}: min_length", [{"field": fid, "message": "min_length"}])
    if "max_length" in val and len(value) > val["max_length"]:
        raise ValidationError(f"{fid}: max_length", [{"field": fid, "message": "max_length"}])
    if "pattern" in val and value:
        if not re.fullmatch(val["pattern"], value):
            raise ValidationError(f"{fid}: pattern", [{"field": fid, "message": "pattern"}])
