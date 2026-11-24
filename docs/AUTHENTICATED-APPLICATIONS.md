# Authenticated application profile: architecture contract

Status: separate local Django staging profile with built-in login, sessions, workspace memberships and scoped data API. Production deployment remains disabled. Existing local-only exports retain their current behavior. A loopback workspace token is not a user identity and must never be treated as one.

## Scope and decisions

The future profile is a separately generated single-organization application with workspace-scoped memberships. The initial data boundary is the entire workspace, not individual rows or tables. Do not advertise tenant isolation until persistence and server integration verify it. Each operation receives its workspace from a trusted server-side resource lookup and resolves the caller's active membership for that workspace on every request. Never accept role, membership, ownership, or authenticated subject from a browser payload. The UI may hide unavailable actions, but the server must enforce them independently.

| Operation | Viewer | Editor | Owner |
| --- | --- | --- | --- |
| Read records and relation options | Yes | Yes | Yes |
| Add and edit records | No | Yes | Yes |
| Delete records | No | No | Yes |
| Export data | No | No | Yes |
| Manage members | No | No | Yes |
| Manage schema | No | No | Yes |

Deletion is owner-only because it can clear references in other tables. Owner-only operations are separate policy decisions, not automatic access to account credentials or other workspaces. A viewer can read visible workspace records and could manually copy them; export permission governs the bulk export operation only. Unknown operations, anonymous identities, inactive memberships and mismatched workspaces are denied.

## Tool choice and cost

Reuse the existing Python standard library for the pure authorization policy and tests. The GitHub connector can edit repository files and read CI; no new identity service or specialist design tool has been connected. No external component is copied. The existing ecosystem catalogue lists Supabase and Appwrite as candidates for integrated authentication and storage; both are deferred pending a real deployment environment, license/version review, storage ownership and explicit cost controls. An open-source identity provider still requires a host. Prefer a maintained framework or identity provider for actual authentication and session security rather than building a password protocol in this repository. No paid service is selected or provisioned. Django 5.2.19 LTS is pinned for this optional local profile; see the [official release support table](https://www.djangoproject.com/download/).

## Required integration gates

| Boundary | Required implementation and evidence |
| --- | --- |
| Identity | Verify identity through a maintained provider or framework; no browser-supplied identity |
| Membership | Trusted workspace lookup on every operation; deny inactive or unknown membership |
| Authorization | Central server guard for every data, relation, export and administrative route |
| Persistence | Explicit workspace scoping for every lookup and write, including linked records and bulk operations |
| Session | Provider-managed secure sessions, expiry, rotation, logout and revocation |
| Request safety | TLS, cookie flags, CSRF protection for state changes, request limits and rate limiting |
| Account administration | Invitation and revocation controls; prevent removal of the last active owner |
| Audit | Minimal administrative event records without passwords, session secrets or private payloads |
| Verification | Negative cross-workspace and role tests, session tests, concurrent revocation tests, authorized integration review |
| Deployment | Separate staging configuration, backups, dependency review, TLS and operational ownership |

Role or membership changes must be coordinated transactionally with protected writes where needed; a stale membership snapshot is not a sufficient authorization guarantee. A provider adapter must distinguish authentication from authorization, fail closed on identity-provider or membership-store failure, and prevent privilege escalation. The policy does not prove those integration properties.

## Current implementation

The pure policy module scripts/creator_access.py defines the exact action set, roles, principal contract and deny-by-default decision. Unit tests enumerate every role/action pair and test inactive, cross-workspace, malformed and anonymous requests. The policy is also integrated into the separate staging profile described below. Existing local exports do not import it. No real accounts, credentials or deployment operations have been created.

Do not publish the current local HTTP servers.

## Optional Django staging profile

The separate staging_auth package uses Django's built-in account and session system, password validators, CSRF middleware, and SQLite. It exposes sign-in, workspace navigation, generated typed record forms, relationship selectors, owner-only membership management and a schema-aware JSON API. It is now available as a separate generated local application export, not a replacement for the existing physical-table relational engine. This prototype stores each workspace's schema and scoped JSON records using Django ORM models. Every protected operation rechecks current membership and active account status in one SQLite transaction using IMMEDIATE transaction mode. Related-record checks and deletion cleanup use the same workspace and table scope. The owner-only member endpoint prevents demoting or disabling the last active owner through that endpoint and records minimal membership-change events.

Use a private local Python environment and install the optional requirements. Create a private .local-staging directory, set CREATOR_STAGING_SECRET to a locally generated random secret of at least 50 characters (do not commit or share it), then use Django's interactive createsuperuser command for a synthetic local test account. That framework superuser has no application access until membership is explicitly provisioned. No password or secret is passed in command-line arguments.

```sh
python -m pip install -r staging_auth/requirements.txt
python -m django migrate --settings=staging_auth.settings
python -m django createsuperuser --settings=staging_auth.settings
python -m django provision_workspace --slug example --title Example --schema projects/relational-example.json --owner TEST_USERNAME --settings=staging_auth.settings
python -m django runserver 127.0.0.1:8769 --noreload --settings=staging_auth.settings
```

The server is for loopback HTTP only. Use synthetic data. Cookie Secure flags are intentionally disabled for loopback HTTP; there is no production TLS configuration, distributed production login rate limiter, MFA, recovery, invitation service, public deployment, or tenant-isolation certification. The last-owner protection applies only to the member endpoint, not out-of-band account/database administration. Sessions are provided by Django and have a 30-minute age; revocation by membership is checked on each protected operation. Do not expose this development server to the internet. The local middleware rejects non-loopback client addresses. A file-backed concurrency regression exercises revocation before a competing write. Production still needs a separate deployment review, distributed session tests and broader concurrency testing.

Run the isolated integration suite without existing accounts or databases:

```sh
python -m django test staging_auth --settings=staging_auth.test_settings -v 2
```

The optional dedicated CI job installs Django, checks migration consistency and runs tests for real login/logout, CSRF, membership changes, cross-workspace record and relation isolation, role permissions, scoped exports, malformed inputs, local provisioning, role-aware HTML operations and concurrent revocation. The base generator retains its standard-library runtime. Transitive dependency locking and current vulnerability review are separate release gates. Check the exact commit's CI results.

The browser interface uses native Django forms and explicit confirmation before record deletion. Relation options and display labels are scoped to the selected workspace. The UI and JSON API share the same transaction-bound access and mutation services. The application has no client-side JavaScript dependency. Membership administration accepts existing local account IDs, not new passwords. The operator remains responsible for account provisioning and recovery.

## Authenticated application export

Use the relational schema designer in Studio, then choose **Export authenticated staging app** and confirm the local-only scope. Or use `python scripts/creator_authenticated_export.py --title Example --description 'Local test' --schema projects/relational-example.json --output staging.zip`. The deterministic bundle contains the explicitly allowlisted Django source files, dependencies, configuration and setup README. It never includes a database, accounts, credentials, environment files or tests. The SHA-256 manifest fingerprints each included file. The separate `provision_export` command provisions the exported schema and an existing local test-account owner, refusing to replace an existing workspace. The generated app uses the same schema and permission services tested in staging. It still requires a private local Python environment and explicit operator setup; no public hosting is enabled.

## Local operational safeguards

The staging login view reserves an installation-wide budget of ten attempts per minute before Django authenticates. Successful and unsuccessful submissions count equally; inherited CSRF validation remains in force. The singleton SQLite budget stores only a time window and attempt count, not usernames, addresses or passwords. A full budget returns HTTP 429 with Retry-After. Database failure denies sign-in. This bounded local safeguard is not a production distributed abuse-prevention system; all local users share it and can temporarily exhaust it.

Stop the local server before running `python -m django backup_staging --output PRIVATE_NEW.sqlite3 --settings=staging_auth.settings`. Choose a private new path outside source control. The command opens the source read-only, uses SQLite's snapshot API, verifies integrity and required tables, removes copied sessions and verifies the resulting database again. It never overwrites a destination or changes the original database. The snapshot retains account hashes, permissions and records; it must be protected like the original database. Use a separate stopped local installation and explicit operator review for recovery; point-in-time restore can restore old memberships, and automatic in-place restore is deliberately unsupported. Session rows are absent from the snapshot, but the installation secret remains an independent operator-managed credential. No private data is uploaded or tested in CI.

## Authenticated project verification

Start Studio with `python scripts/creator_studio.py --browser-checks` and open the multi-table relational application panel. Choose an installed browser and **Verify authenticated application**. The check requires the optional Django and Playwright dependencies, uses fresh synthetic accounts and records, and offers an `authenticated-report.json` download. Changing the application or browser invalidates the displayed report. The check is disabled unless browser checks are explicitly enabled. It never approves a public release.

With the optional Django and pinned Playwright packages and a browser engine installed, use `python scripts/creator_authenticated_check.py --title Example --description 'Synthetic audit' --schema projects/relational-example.json --engine chromium --report authenticated-report.json`. The check generates and fingerprints a new trusted bundle, migrates a temporary database and creates synthetic accounts. It verifies real login, cookie attributes, anonymous denial, editor forms, viewer restrictions, workspace isolation, CSRF, owner export, membership revocation, linked-record cleanup and logout using the selected browser. Every table is tested at three viewport widths. Browser navigation is limited to the temporary loopback app. Temporary credentials and raw worker logs are not included in the report. The existing browser matrix installs Django for this optional regression; the base generator still needs only the standard library. This report is not a public-release approval or security certification. Check current CI before using the feature.
