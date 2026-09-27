# JSON Schema

- `common.json`：所有分类共有字段（视频号公约必填项等）。
- `rental.json` / `resale.json` / `new-home.json`：`allOf` 引用 `common.json` 并追加分类字段。
- 由 `pipeline/check/jsonschema_lite.py`（标准库实现的子集校验器）执行，支持：`type`、`required`、`properties`、`items`、`enum`、`const`、`pattern`、`minLength`、`minItems`、`minimum`、`exclusiveMinimum`、`allOf`、`$ref`（本地 `#/$defs/..` 与同目录文件）。
- 新增字段时同步修改：`templates/` → 本目录 → `remotion/src/types.ts` → `check.py`。
