"""Field definition and item field validation."""

from __future__ import annotations

import math
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
        "url",
    }
)

RICHTEXT_SOFT_LIMIT = 1_000_000  # bytes of JSON-ish size
ABSOLUTE_STRING_MAX = 200_000
FIELD_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_DATETIME_RE = re.compile(r"^[0-9T:\-+Zz. ]{0,40}$")


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
        if FIELD_ID_RE.fullmatch(fid) is None:
            raise ValidationError(f"field id is not allowed: {fid}")
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
        if "width_lock" in f and f.get("width_lock") is not None:
            if not isinstance(f.get("width_lock"), bool):
                raise ValidationError(f"field {fid}: width_lock must be a boolean")
        if "width" in f and f.get("width") is not None:
            w = f.get("width")
            if isinstance(w, bool) or not isinstance(w, (int, float)):
                raise ValidationError(f"field {fid}: width must be a number")
            if w <= 0 or w > 100:
                raise ValidationError(f"field {fid}: width must be between 1 and 100")
        if ftype in ("select", "multiselect"):
            opts = f.get("options")
            if opts is None:
                f["options"] = []
                opts = []
            if not isinstance(opts, list) or any(not isinstance(o, str) for o in opts):
                raise ValidationError(f"field {fid}: options must be a list of strings")
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
        # PATCH leaves require_required off so an omitted key is fine, but an
        # explicit null/blank must not clear a required number (priority).
        # Optional numbers (urgency) still store null.
        # Other required types stay as they were: ticket_key is required text
        # and the title editor PATCHes "" while that box is empty, and null is
        # already a type error for every non-number field.
        if (
            partial
            and not require_required
            and fdef.get("required")
            and fdef.get("type") == "number"
            and _is_blank_number(value)
        ):
            errors.append({"field": key, "message": "required"})
            continue
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


def _is_blank_number(value: Any) -> bool:
    if value is None:
        return True
    return isinstance(value, str) and value.strip() == ""


def _is_empty(value: Any, fdef: dict[str, Any]) -> bool:
    if value is None:
        return True
    ftype = fdef.get("type")
    if ftype in ("text", "textarea", "select", "date", "datetime", "url") and value == "":
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

    if ftype in ("text", "url"):
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
        # JSON null clears the field. Required checks use _is_empty afterwards.
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValidationError(f"{fid}: expected number", [{"field": fid, "message": "type"}])
        num = float(value) if not isinstance(value, int) else value
        if not math.isfinite(float(num)) or abs(float(num)) > 1e15:
            raise ValidationError(f"{fid}: out of range", [{"field": fid, "message": "range"}])
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
        if not _DATETIME_RE.fullmatch(value):
            raise ValidationError(f"{fid}: date format", [{"field": fid, "message": "format"}])
        return value

    raise ValidationError(f"{fid}: unsupported type")


def _check_string_rules(fid: str, value: str, val: dict[str, Any]) -> None:
    if "min_length" in val and len(value) < val["min_length"]:
        raise ValidationError(f"{fid}: min_length", [{"field": fid, "message": "min_length"}])
    declared = val.get("max_length")
    if isinstance(declared, int) and not isinstance(declared, bool) and len(value) > declared:
        raise ValidationError(f"{fid}: max_length", [{"field": fid, "message": "max_length"}])
    if len(value) > ABSOLUTE_STRING_MAX:
        raise ValidationError(f"{fid}: too large", [{"field": fid, "message": "size"}])
    if "pattern" in val and value:
        pattern = val["pattern"]
        if not isinstance(pattern, str) or len(pattern) > 128:
            raise ValidationError(f"{fid}: pattern", [{"field": fid, "message": "pattern"}])
        try:
            compiled = re.compile(pattern)
        except re.error as exc:
            raise ValidationError(f"{fid}: pattern", [{"field": fid, "message": "pattern"}]) from exc
        if not compiled.fullmatch(value):
            raise ValidationError(f"{fid}: pattern", [{"field": fid, "message": "pattern"}])
