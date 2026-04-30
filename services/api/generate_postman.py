"""Generate Postman Collection from slate-api FastAPI app."""

import inspect
import json
from pathlib import Path

from slate_api.main import app

BASE_URL = "http://localhost:8000"

# Endpoints that don't require Authorization header
_UNPROTECTED = {"/health", "/"}


def generate_postman_collection() -> dict:
    openapi_schema = app.openapi()
    components = openapi_schema.get("components", {})
    schemas = components.get("schemas", {})

    collection = {
        "info": {
            "name": openapi_schema.get("info", {}).get("title", "Slate API"),
            "description": openapi_schema.get("info", {}).get("description", ""),
            "version": openapi_schema.get("info", {}).get("version", "0.1.0"),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "variable": [
            {"key": "base_url", "value": BASE_URL, "type": "string"},
            {"key": "bearer", "value": "", "type": "string"},
        ],
        "item": [],
    }

    tag_groups: dict[str, dict] = {}

    for path, methods in openapi_schema.get("paths", {}).items():
        for method, details in methods.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue

            tags = details.get("tags", ["Default"])
            tag = tags[0] if tags else "Default"

            item: dict = {
                "name": details.get("summary", path),
                "request": {
                    "method": method.upper(),
                    "header": [],
                    "url": {
                        "raw": f"{{{{base_url}}}}{path}",
                        "host": ["{{base_url}}"],
                        "path": path.strip("/").split("/"),
                        "query": [],
                    },
                },
            }

            # Auth header for protected endpoints
            if path not in _UNPROTECTED:
                item["request"]["header"].append(
                    {
                        "key": "Authorization",
                        "value": "Bearer {{bearer}}",
                        "description": "Google ID token",
                    }
                )

            # Description
            desc_parts = []
            if "description" in details:
                desc_parts.append(details["description"])

            operation_id = details.get("operationId", "")
            if operation_id:
                for route in app.routes:
                    if hasattr(route, "endpoint"):
                        name = getattr(route.endpoint, "__name__", "")
                        if name == operation_id or operation_id.endswith(name):
                            docstring = inspect.getdoc(route.endpoint)
                            if docstring and docstring not in desc_parts:
                                desc_parts.append(
                                    f"\n**Function Documentation:**\n```\n{docstring}\n```"
                                )
                            break

            # Query + path parameters
            for param in details.get("parameters", []):
                param_in = param.get("in", "")
                param_name = param.get("name", "")
                param_schema = param.get("schema", {})
                param_required = param.get("required", False)
                param_description = param.get("description", "")

                if param_in == "query":
                    example = _example(param_schema, {}, param_name)
                    type_info = param_schema.get("type", "string")
                    constraints = []
                    for k, label in [
                        ("minimum", "min"),
                        ("maximum", "max"),
                        ("minLength", "min length"),
                        ("maxLength", "max length"),
                    ]:
                        if k in param_schema:
                            constraints.append(f"{label}: {param_schema[k]}")
                    if "enum" in param_schema:
                        constraints.append(f"values: {', '.join(map(str, param_schema['enum']))}")
                    if "default" in param_schema:
                        constraints.append(f"default: {param_schema['default']}")

                    full_desc = " | ".join(
                        filter(None, [param_description, f"Type: {type_info}"] + constraints)
                    )
                    item["request"]["url"]["query"].append(
                        {
                            "key": param_name,
                            "value": str(example),
                            "description": full_desc,
                            "disabled": not param_required,
                        }
                    )

                elif param_in == "path":
                    example = _example(param_schema)
                    raw = item["request"]["url"]["raw"]
                    item["request"]["url"]["raw"] = raw.replace(f"{{{param_name}}}", str(example))

            # Request body
            if "requestBody" in details:
                content = details["requestBody"].get("content", {})
                if "application/json" in content:
                    schema = content["application/json"].get("schema", {})
                    item["request"]["header"].append(
                        {
                            "key": "Content-Type",
                            "value": "application/json",
                        }
                    )
                    example_body = _example(schema, schemas)
                    item["request"]["body"] = {
                        "mode": "raw",
                        "raw": json.dumps(example_body, indent=2),
                        "options": {"raw": {"language": "json"}},
                    }

                    body_docs = _body_docs(schema, schemas)
                    if body_docs:
                        desc_parts.append(f"\n**Request Body Fields:**\n{body_docs}")

            if desc_parts:
                item["request"]["description"] = "\n\n".join(desc_parts)

            if tag not in tag_groups:
                tag_groups[tag] = {"name": tag, "item": []}
            tag_groups[tag]["item"].append(item)

    collection["item"] = list(tag_groups.values())
    return collection


# ── Schema helpers ────────────────────────────────────────────────────────────


def _example(schema: dict, all_schemas: dict | None = None, prop_name: str | None = None):
    all_schemas = all_schemas or {}

    for key in ("example", "examples"):
        if key in schema:
            val = schema[key]
            return val[0] if isinstance(val, list) and val else val

    if "$ref" in schema:
        name = schema["$ref"].split("/")[-1]
        return _example(all_schemas.get(name, {}), all_schemas)

    if "anyOf" in schema:
        return _example(schema["anyOf"][0], all_schemas)
    if "oneOf" in schema:
        return _example(schema["oneOf"][0], all_schemas)
    if "allOf" in schema:
        merged: dict = {}
        for s in schema["allOf"]:
            ex = _example(s, all_schemas)
            if isinstance(ex, dict):
                merged.update(ex)
        return merged

    t = schema.get("type", "object")
    fmt = schema.get("format", "")

    if t == "object":
        props = schema.get("properties", {})
        required = schema.get("required", [])
        result: dict = {}
        for name, sub in props.items():
            if name in required or len(result) < 5:
                result[name] = _example(sub, all_schemas, name)
        return result

    if t == "array":
        return [_example(schema.get("items", {}), all_schemas, prop_name)]

    if t == "string":
        if "enum" in schema:
            return schema["enum"][0]
        examples_by_name = {
            "email": "user@example.com",
            "password": "secret",
            "token": "{{bearer}}",
        }
        if prop_name and prop_name.lower() in examples_by_name:
            return examples_by_name[prop_name.lower()]
        fmt_map = {
            "email": "user@example.com",
            "date": "2026-01-01",
            "date-time": "2026-01-01T00:00:00Z",
            "uuid": "123e4567-e89b-12d3-a456-426614174000",
            "uri": "https://example.com",
            "password": "secret",
        }
        return fmt_map.get(fmt, schema.get("default", "string"))

    if t == "integer":
        if "enum" in schema:
            return schema["enum"][0]
        return schema.get("default", schema.get("minimum", 1))

    if t == "number":
        if "enum" in schema:
            return schema["enum"][0]
        return schema.get("default", schema.get("minimum", 0.0))

    if t == "boolean":
        return schema.get("default", True)

    return None


def _body_docs(schema: dict, all_schemas: dict, indent: int = 0) -> str:
    lines: list[str] = []
    pad = "  " * indent

    if "$ref" in schema:
        name = schema["$ref"].split("/")[-1]
        return _body_docs(all_schemas.get(name, {}), all_schemas, indent)

    if "allOf" in schema:
        return "\n".join(_body_docs(s, all_schemas, indent) for s in schema["allOf"])

    props = schema.get("properties", {})
    required = schema.get("required", [])

    for prop, sub in props.items():
        t = sub.get("type", "object")
        fmt = sub.get("format", "")
        type_str = f"{t}({fmt})" if fmt else t
        req = " (required)" if prop in required else ""
        desc = sub.get("description", "")
        line = f"{pad}- **{prop}**{req}: `{type_str}`"
        if desc:
            line += f" — {desc}"
        lines.append(line)

        if t == "object" and "properties" in sub:
            lines.append(_body_docs(sub, all_schemas, indent + 1))
        elif t == "array" and "items" in sub:
            items = sub["items"]
            if items.get("type") == "object" or "$ref" in items:
                lines.append(f"{pad}  Array items:")
                lines.append(_body_docs(items, all_schemas, indent + 2))

    return "\n".join(lines)


if __name__ == "__main__":
    collection = generate_postman_collection()

    out_dir = Path(__file__).parent / "postman"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / "slate_api.postman_collection.json"

    with open(out_file, "w") as f:
        json.dump(collection, f, indent=2)

    print(f"✓ Postman collection generated: {out_file}")
