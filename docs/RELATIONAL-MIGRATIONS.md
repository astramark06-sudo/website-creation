# Additive relational workspace migrations

This command is for trusted local databases. Stop both local application servers and retain a private backup of the original database and config.json before migration. Use the latest migration-capable exporter for both workspaces.

Export a new, separate workspace using a schema that preserves the old tables and fields exactly, in their original order, and appends new fields or new tables. Supply a JSON object whose keys are the IDs of existing tables receiving appended fields. Each nested object contains exactly the new field IDs and their defaults. New relation fields require null; new tables are empty and require no defaults. An empty defaults object is valid when only adding tables.

Example defaults for a new cost field and supplier relation in items:

```json
{"items":{"cost":0,"supplier":null}}
```

From the original extracted workspace run:

```sh
python server.py --migrate-to ../new-export --defaults defaults.json
```

The source is opened read-only in a consistent transaction, checked for integrity and valid foreign keys, and read into a bounded snapshot. A new destination is created exclusively. Existing record IDs, cross-table references, cyclic relationships, and SQLite autoincrement high-water marks are preserved. All inserted data and sequences are compared against the expected records and explicit defaults. The destination is checked again before success. A failed migration removes its newly created output; an existing destination is never replaced.

Start the new application only after migration completes, inspect its data, and retain the old workspace. No live schema alteration, table/field deletion, renaming, field type conversion, changed choice lists, in-place migration, public API or production data migration is supported. The existing single-table application migration remains separate. CI includes real database and exported-command regression tests; check the exact commit before claiming verification.
