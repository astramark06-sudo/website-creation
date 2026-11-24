# Local full-stack workspace

The Master Creator studio can export an original standalone Python/SQLite application using the project title and description. It supports adding, editing, completing, deleting, searching and filtering records. Extract the ZIP to a new folder and run `python server.py`. Open the printed loopback address. No external dependencies or paid service are needed. The application uses parameterized SQL, bounded input, same-origin request checks and a session token. Database persistence is local, not browser storage.

This is a single-user local starter, not an arbitrary backend generator or a production internet service. Do not expose it to the internet, tunnel its port, or store sensitive information. Public full-stack release requires independently implemented authentication, authorization, TLS, deployment configuration, backup and operational review. GitHub Pages cannot execute Python or host SQLite. The export does not publish anything.

CLI usage:

```sh
python scripts/creator_fullstack.py --title "My records" --description "Original workspace" --output workspace.zip
```

The regression tests validate ZIP content and database operations. A dedicated Chromium integration test exports the actual app from the studio, exercises create/edit/complete/filter/search/delete, checks unauthenticated requests are rejected, and restarts the local server against the same database. Verify the current CI result before claiming the browser test passed. Public deployment remains separate and unsupported.

## Typed data-model presets

Choose General records, Inventory, Issue tracking or Reading catalogue before exporting. Inventory adds quantity and storage location; Issue tracking adds priority and category; Reading catalogue adds pages and format. The generated form and list are driven by bounded model fields in config.json. Integers are validated as integers from 0 to 1,000,000; text is bounded; choices must match the configured options. The database stores model fields as structured JSON alongside existing records and rejects mismatched model definitions. Search includes field values. Existing general-record databases remain compatible. Use a new export folder and database for a different model. No arbitrary SQL, multi-user authentication, external data or production hosting is provided.

CLI: `python scripts/creator_fullstack.py --title "Inventory" --description "Local supplies" --model inventory --output inventory.zip`.
