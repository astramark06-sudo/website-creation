# Project release readiness

The studio generates a local report against the current draft. It builds into a temporary directory and verifies the result, records a SHA-256 fingerprint of the structured draft, and reports known placeholder text and duplicate headings. Download the JSON evidence if needed. Editing the project invalidates the displayed report.

The report distinguishes automated observations from human declarations and untested requirements. It does not certify originality, legal rights, accessibility, performance or security. It never publishes a website. The existing manual reviewed GitHub Pages workflow remains separate, and production backend release requires a suitable hosting environment and security review.

CLI usage:

```sh
python scripts/creator_release.py --spec projects/example.json
```

Use the report alongside real project-specific browser, accessibility and deployment checks. Generic repository CI is not evidence that an arbitrary generated project has passed those checks.
