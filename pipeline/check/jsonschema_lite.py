"""Minimal JSON Schema validator (subset of draft 2020-12), stdlib only.

Supported keywords: type, required, properties, items, enum, const, pattern,
minLength, minItems, minimum, exclusiveMinimum, allOf, $ref (local "#/..."
and sibling files like "common.json" / "common.json#/$defs/x").
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "null": type(None),
}


def _is_type(value, t: str) -> bool:
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, _TYPES[t])


class Validator:
    def __init__(self, schema_dir: Path):
        self.schema_dir = Path(schema_dir)
        self._cache: dict[str, dict] = {}

    def load(self, name: str) -> dict:
        if name not in self._cache:
            with open(self.schema_dir / name, "r", encoding="utf-8") as f:
                self._cache[name] = json.load(f)
        return self._cache[name]

    def _resolve(self, ref: str, doc: dict) -> tuple[dict, dict]:
        file_part, _, pointer = ref.partition("#")
        target_doc = self.load(file_part) if file_part else doc
        node = target_doc
        for part in [p for p in pointer.split("/") if p]:
            node = node[part]
        return node, target_doc

    def validate(self, instance, schema_name: str) -> list[str]:
        doc = self.load(schema_name)
        errors: list[str] = []
        self._validate(instance, doc, doc, "$", errors)
        return errors

    def _validate(self, inst, schema: dict, doc: dict, path: str, errors: list[str]) -> None:
        if "$ref" in schema:
            sub, sub_doc = self._resolve(schema["$ref"], doc)
            self._validate(inst, sub, sub_doc, path, errors)
        for sub in schema.get("allOf", []):
            self._validate(inst, sub, doc, path, errors)
        if "type" in schema:
            types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
            if not any(_is_type(inst, t) for t in types):
                errors.append(f"{path}: 类型应为 {'/'.join(types)}，实际为 {type(inst).__name__}")
                return
        if "const" in schema and inst != schema["const"]:
            errors.append(f"{path}: 应为 {json.dumps(schema['const'], ensure_ascii=False)}，实际为 {json.dumps(inst, ensure_ascii=False)}")
        if "enum" in schema and inst not in schema["enum"]:
            errors.append(f"{path}: 应为 {schema['enum']} 之一，实际为 {json.dumps(inst, ensure_ascii=False)}")
        if isinstance(inst, str):
            if "minLength" in schema and len(inst) < schema["minLength"]:
                errors.append(f"{path}: 长度至少 {schema['minLength']}")
            if "pattern" in schema and not re.search(schema["pattern"], inst):
                errors.append(f"{path}: 格式不符（{schema['pattern']}），当前值 “{inst}”")
        if isinstance(inst, (int, float)) and not isinstance(inst, bool):
            if "minimum" in schema and inst < schema["minimum"]:
                errors.append(f"{path}: 不能小于 {schema['minimum']}")
            if "exclusiveMinimum" in schema and inst <= schema["exclusiveMinimum"]:
                errors.append(f"{path}: 必须大于 {schema['exclusiveMinimum']}")
        if isinstance(inst, list):
            if "minItems" in schema and len(inst) < schema["minItems"]:
                errors.append(f"{path}: 至少需要 {schema['minItems']} 项")
            if "items" in schema:
                for i, item in enumerate(inst):
                    self._validate(item, schema["items"], doc, f"{path}[{i}]", errors)
        if isinstance(inst, dict):
            for key in schema.get("required", []):
                if key not in inst:
                    errors.append(f"{path}: 缺少必填字段 “{key}”")
            for key, sub in schema.get("properties", {}).items():
                if key in inst:
                    self._validate(inst[key], sub, doc, f"{path}.{key}", errors)
