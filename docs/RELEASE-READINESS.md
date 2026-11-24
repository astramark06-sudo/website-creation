# Project release readiness

The studio generates a local report against the current draft. It builds into a temporary directory and verifies the result, records a SHA-256 fingerprint of the structured draft, and reports known placeholder text and duplicate headings. Download the JSON evidence if needed. Editing the project invalidates the displayed report.

The report distinguishes automated observations from human declarations and untested requirements. It does not certify originality, legal rights, accessibility, performance or security. It never publishes a website. The existing manual reviewed GitHub Pages workflow remains separate, and production backend release requires a suitable hosting environment and security review.

CLI usage:

```sh
python scripts/creator_release.py --spec projects/example.json
```

For one combined JSON evidence report, use `python scripts/creator_release.py --spec projects/example.json --engine chromium --engine firefox --engine webkit --report release-evidence.json` after installing the optional browser tools and each selected engine. Omit unwanted engines; the default still performs build checks only. The command runs fresh checks against the same verified temporary output, matches project and file fingerprints, and checks coverage of every page at each supported width. A failed browser check is retained in the report and returns a nonzero exit status. Existing report files are never overwritten. Even a passing combined report does not approve publication or establish full accessibility, security or performance.

Use the report alongside real project-specific browser, accessibility and deployment checks. Generic repository CI is not evidence that an arbitrary generated project has passed those checks.

To verify an existing reviewed build without changing it, add `--output build/publish --require-reviewed --engine chromium --report release-evidence.json`. This requires all three explicit human review flags, at least one installed browser engine and no known starter-content or repeated-heading warnings. A known warning blocks the reviewed release gate; revise the content or heading structure and rerun. The evidence still does not certify originality, accessibility or production readiness. The command itself never deploys.

## Downloadable draft preflight from GitHub

In the repository's Actions tab, choose **Build and check a portable draft (no deployment)**, select the main branch, and select the committed example or publication candidate. The candidate option requires an existing `projects/publish.json`; the example is fictional and does not require publication approval. Do not commit or process private content in a public repository.

The workflow installs the existing pinned Playwright version and runs Chromium, Firefox and WebKit against the verified portable draft. It retains a downloadable artifact for seven days containing `preflight-report.json` and, if browser checks pass, `creator-project.zip`. The ZIP is an unapproved, reopenable Studio draft, even if the source had review flags. Both reports identify the same draft and generated file hashes. Known content warnings remain review items; successful preflight is not publication approval. The workflow has no deployment job or Pages write permissions.

Local equivalent (create a new output directory in an existing parent):

```sh
python scripts/creator_preflight.py --spec projects/example.json --output preflight --engine chromium --engine firefox --engine webkit
```

A failed browser result retains diagnostic evidence but no ZIP. Missing input, unavailable browser dependencies or invalid evidence can fail before a report exists. No existing output directory is overwritten.

### Verify a downloaded preflight

After downloading and unpacking the outer GitHub artifact into a private directory, leave the inner `creator-project.zip` unextracted. From the matching repository revision, run:

```sh
python scripts/creator_preflight_verify.py preflight --engine chromium --engine firefox --engine webkit
```

The verifier checks the archive against the current generator, recomputes static release gates, and checks reported browser coverage, individual checks and matching fingerprints. It needs no installed browser, modifies neither input file, and rejects mismatched, incomplete or failing reports. The optional repeated engine argument requires an exact set of reported engines. Omit it to accept any supported nonempty engine set. The manual workflow runs this independent consistency check before uploading a passing draft.

A passing consistency check does not authenticate a report, prove that a browser actually ran, or authorize publication. An unsigned report can be fabricated; use trusted CI results or rerun browser tests for execution evidence. Older artifacts may require the generator revision that produced them.

## Optional project-specific browser evidence

Install the pinned optional browser test tool (`python -m pip install playwright==1.51.0`) and install Chromium (`python -m playwright install chromium`). On supported Linux CI environments the existing browser workflow installs system dependencies. Start the studio with `python scripts/creator_studio.py --browser-checks` to enable the separate browser report controls. Select Chromium, Firefox or WebKit in the static-site browser panel and confirm the check. Choose **Run combined release check** to generate a single build and browser report for the selected engine; download it using **Download review report**. Install the selected engine before use. Changing the selected engine or editing the project invalidates its report; downloaded files identify the engine. The normal studio still needs no extra runtime dependencies.

CLI: `python scripts/creator_browser.py --spec projects/example.json --report browser-report.json`. Use `--output` to verify an existing generated directory. Use `--engine firefox` or `--engine webkit` only after installing the corresponding Playwright browser; Chromium is the default local engine; Firefox and WebKit also have dedicated CI jobs. The smoke checks test all generated pages at 360, 768 and 1440 CSS pixels, navigation, heading and landmark structure, stylesheet loading, keyboard skip link, FAQ disclosures, task interactions and persistence, overflow, uncaught errors and unexpected requests. Browser requests are intercepted and served only with the verified generated content at a reserved synthetic origin. No external site is loaded. The report includes exact project and file fingerprints and engine version. Editing the project invalidates both studio reports. The reviewed GitHub Pages workflow requires a clean known-starter-content and repeated-heading review plus the Chromium check of its exact output before Pages artifact upload. The combined release evidence is retained separately for seven days, even if the review gate fails after writing its report; it is not published with the site. It still needs explicit publication approval and configured Pages hosting; no actual deployment is performed by the check.

These checks are not a comprehensive accessibility, security, performance, cross-browser or public deployment certification. The CI matrix is configured to exercise the same Studio, exported local application and generated website browser regression suite in Chromium, Firefox and WebKit, along with all four layout presets and all ten section types. Check the exact commit's CI results before claiming any engine passed. These are representative generated projects, not exhaustive coverage of every design combination. The publication gate remains Chromium-only.

## Basic accessibility and diagnostic checks

The generated site includes an original local favicon and an explicitly focusable skip-link destination. Browser reports record bounded console and operation diagnostics instead of only reporting that an error occurred. The project-specific check verifies keyboard activation of the skip link, unique IDs, labeled native form controls, nonempty document metadata, and basic names on links and buttons. These are targeted checks for the generator's known components, not an accessible-name implementation, screen-reader review or WCAG conformance audit. The favicon is included in the verified output and permitted only from the synthetic local origin during browser tests. Older exported websites should be rebuilt to use the new output format.

## Reliability boundaries

Project validation enforces a canonical UTF-8 size limit in addition to input file limits. Generated filenames reject reserved Windows device names. Exported draft JSON uses compact UTF-8 to preserve the project size bound. Integrity verification compares the complete manifest against the expected manifest, not only generated file hashes. The starter-content report includes the exact HTML-reference and screenshot-reference template wording. Search smoke tests now include a positive heading match as well as empty results and clearing. These checks do not independently certify content rights or completeness.

JSON input rejects duplicate object keys and non-finite numbers. Generated file comparison reads at most the expected file length plus one byte. Studio requests allow a small envelope around the separately validated project size limit. Browser regression coverage includes matching across neighboring metric label/value elements and Unicode canonical equivalence.
