# Authenticated application profile: architecture contract

Status: authorization policy foundation only. No authentication provider, login form, session implementation, protected HTTP routes, or production deployment is enabled. Existing local-only exports retain their current behavior. A loopback workspace token is not a user identity and must never be treated as one.

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

Reuse the existing Python standard library for the pure authorization policy and tests. The GitHub connector can edit repository files and read CI; no new identity service or specialist design tool has been connected. No external component is copied. The existing ecosystem catalogue lists Supabase and Appwrite as candidates for integrated authentication and storage; both are deferred pending a real deployment environment, license/version review, storage ownership and explicit cost controls. An open-source identity provider still requires a host. Prefer a maintained framework or identity provider for actual authentication and session security rather than building a password protocol in this repository. No paid service is selected or provisioned.

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

The pure policy module scripts/creator_access.py defines the exact action set, roles, principal contract and deny-by-default decision. Unit tests enumerate every role/action pair and test inactive, cross-workspace, malformed and anonymous requests. This is not a working login system. The local app is not changed by importing or adding this module. No credentials, secrets, accounts, external URLs or deployment operations are added.

Next stage: choose an actual maintained authentication framework/provider and persistence strategy for an explicitly scoped local staging environment; integrate and verify its session and membership adapters before exposing any network service. Do not publish the current local HTTP servers.
