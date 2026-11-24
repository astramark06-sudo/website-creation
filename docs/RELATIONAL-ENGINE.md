# Local relational data engine

The local relational engine is also available as a separate application export. The existing single-workspace export and its migrations are unchanged.

Use Python 3.10 or newer with its standard SQLite module. No network requests, packages or external database service are required.

Create an empty database from the example schema:

```sh
python scripts/creator_relational.py --schema projects/relational-example.json --output example.sqlite3
```

The engine creates 2–4 physical SQLite tables with 1–8 typed fields each. Text, bounded nonnegative integers, choices and optional cross-table relations are supported. Relations use SQLite foreign keys with SET NULL on target deletion. IDs are stable, non-reused and bounded for future JavaScript interoperability. Existing schema definitions must match exactly; the engine rejects unknown tables, fields and relation targets. Writes use parameterized values and transactional validation. Table and field identifiers are restricted and prefixed.

The Python functions create_database, add_record, edit_record, delete_record and list_records provide the initial data layer. Only use trusted local workspace files. Each table is limited to 1,000 records. The schema example is [projects/relational-example.json](../projects/relational-example.json). Regression tests exercise actual tables, foreign keys, invalid input, rollback behavior and CLI creation. No arbitrary SQL input is accepted.

## Handoff

Scope: backend-only, independently authored, no visual design source needed. Selected tool: existing Python standard library SQLite; no new license or service requirements. Alternatives such as external database platforms are deferred because the current acceptance criteria are local relational storage. Next stage: project-specific release evidence and relational migration planning; schema migrations, multi-user security and deployment are separate work. Current CI status must be checked before treating this feature as verified.

## Standalone application export

In Studio open Multi-table relational application, load the example schema or edit the JSON, then export. Extract the ZIP and run `python server.py` (default loopback port 8768). The generated app includes the same relational engine, its configuration, a table selector, typed record editor, relationship dropdowns and record editing/deletion. A separate command-line exporter is available:

```sh
python scripts/creator_relational_export.py --title Inventory --description 'Local inventory' --schema projects/relational-example.json --output relational.zip
```

The server initializes a new database only if absent and verifies schema compatibility on restart. Its HTTP interface is local only, with exact host, origin and session-token checks, bounded JSON bodies, strict routes and no external resources. Existing exports remain separate. The visual designer and advanced JSON editor share the same validated schema. Data is limited to 1,000 records per table; production accounts and hosting are not supported. Additive offline schema migration is documented separately; destructive or in-place migrations are unsupported. CI tests the exported application, including actual Studio export, cross-table relations and persistence across server restart. Verify current CI before claiming support.

## No-code schema design

In the relational Studio panel, start a new schema or load the example. Add tables and fields, edit their labels, select text, integer, choice or relation types, enter choice options one per line, and select the related table. IDs are generated automatically and remain stable while labels change. The designer prevents removing a referenced table until its inbound relationships have been removed or redirected. The limits remain 2–4 tables and 1–8 fields per table. The advanced JSON panel exposes the same schema; editing JSON temporarily hides the visual editor until the local server validates and applies it. A schema download is validated by the same backend and contains no records. Existing database schema compatibility rules still apply. No schema migration or public hosting is performed by this designer.

Design source: original Studio controls and existing design tokens. No third-party UI libraries, paid APIs or new runtime dependencies. Keyboard-operable native form controls and server validation are the acceptance criteria; the browser regression suite exercises all three configured engines. CI must pass before claiming verified support.

## Schema evolution

Use the [additive relational migration guide](RELATIONAL-MIGRATIONS.md) to migrate into a separate exported workspace. Existing tables and field definitions must remain unchanged; new fields require explicit defaults and newly added tables start empty. CI verification of this feature is required before use.


## Project-specific application verification

Use the optional installed Playwright browser tool (the repository pins playwright==1.51.0). Install the desired engine separately. From the repository, run:

```sh
python scripts/creator_relational_check.py --title Inventory --description 'Local inventory' --schema projects/relational-example.json --engine chromium --report relational-report.json
```

The verifier generates a fresh trusted bundle in a temporary directory, fingerprints every generated file, and runs the bundled server and actual browser in an isolated worker process. It tests every table and declared field, inserts synthetic records, creates cross-table relationships after all targets exist (including cyclic schemas), edits records, checks three viewport widths, checks missing-session requests, restarts the server, verifies persisted values, deletes records and checks reference clearing. Browser requests are restricted to the temporary loopback server and generated application routes. The worker has a bounded execution time; a failed check exits nonzero and reports diagnostics. The report path is never overwritten.

This CLI tests a fresh export of the supplied schema and title/description, not an arbitrary executable ZIP or a user's live database. It does not certify comprehensive accessibility, production security, performance, hosting, or real data. No paid service or new runtime dependency is required. The browser regression test exercises this verifier on all three configured engines. Studio integration is a separate follow-up.
