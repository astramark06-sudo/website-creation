# Project release readiness

The studio generates a local report against the current draft. It builds into a temporary directory and verifies the result, records a SHA-256 fingerprint of the structured draft, and reports known placeholder text and duplicate headings. Download the JSON evidence if needed. Editing the project invalidates the displayed report.

The report distinguishes automated observations from human declarations and untested requirements. It does not certify originality, legal rights, accessibility, performance or security. It never publishes a website. The existing manual reviewed GitHub Pages workflow remains separate, and production backend release requires a suitable hosting environment and security review.

CLI usage:

```sh
python scripts/creator_release.py --spec projects/example.json
```

Use the report alongside real project-specific browser, accessibility and deployment checks. Generic repository CI is not evidence that an arbitrary generated project has passed those checks.

## Optional project-specific browser evidence

Install the pinned optional browser test tool (`python -m pip install playwright==1.51.0`) and install Chromium (`python -m playwright install chromium`). On supported Linux CI environments the existing browser workflow installs system dependencies. Start the studio with `python scripts/creator_studio.py --browser-checks` to enable the separate browser report controls. The normal studio still needs no extra runtime dependencies.

CLI: `python scripts/creator_browser.py --spec projects/example.json --report browser-report.json`. Use `--output` to verify an existing generated directory. Use `--engine firefox` or `--engine webkit` only after installing the corresponding Playwright browser; Chromium is the default local engine; Firefox and WebKit also have dedicated CI jobs. The smoke checks test all generated pages at 360, 768 and 1440 CSS pixels, navigation, heading and landmark structure, stylesheet loading, keyboard skip link, FAQ disclosures, task interactions and persistence, overflow, uncaught errors and unexpected requests. Browser requests are intercepted and served only with the verified generated content at a reserved synthetic origin. No external site is loaded. The report includes exact project and file fingerprints and engine version. Editing the project invalidates both studio reports. The reviewed GitHub Pages workflow now requires the Chromium check of its exact output before artifact upload. It still needs explicit publication approval and configured Pages hosting; no actual deployment is performed by the check.

These checks are not a comprehensive accessibility, security, performance, cross-browser or public deployment certification. The cross-browser CI matrix exercises Firefox and WebKit against the example project and all four layout presets with all six section types. These are representative generated projects, not exhaustive coverage of every design combination. The publication gate remains Chromium-only.
