# Local relational data engine

This is a separate backend foundation, not a generated web application yet. The existing single-workspace export and its migrations are unchanged.

Use Python 3.10 or newer with its standard SQLite module. No network requests, packages or external database service are required.

Create an empty database from the example schema:

```sh
python scripts/creator_relational.py --schema projects/relational-example.json --output example.sqlite3
```

The engine creates 2–4 physical SQLite tables with 1–8 typed fields each. Text, bounded nonnegative integers, choices and optional cross-table relations are supported. Relations use SQLite foreign keys with SET NULL on target deletion. IDs are stable, non-reused and bounded for future JavaScript interoperability. Existing schema definitions must match exactly; the engine rejects unknown tables, fields and relation targets. Writes use parameterized values and transactional validation. Table and field identifiers are restricted and prefixed.

The Python functions create_database, add_record, edit_record, delete_record and list_records provide the initial data layer. Only use trusted local workspace files. Each table is limited to 1,000 records. The schema example is [projects/relational-example.json](../projects/relational-example.json). Regression tests exercise actual tables, foreign keys, invalid input, rollback behavior and CLI creation. No UI or HTTP API is included in this milestone; no arbitrary SQL input is accepted.

## Handoff

Scope: backend-only, independently authored, no visual design source needed. Selected tool: existing Python standard library SQLite; no new license or service requirements. Alternatives such as external database platforms are deferred because the current acceptance criteria are local relational storage. Next stage: verified relational export and accessible collection editor; schema migrations, multi-user security and deployment are separate work. Current CI status must be checked before treating this feature as verified.
