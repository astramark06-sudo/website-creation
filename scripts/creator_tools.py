"""Shared, read-only tool discovery and project planning for the studio.

No SDK, external tools, remote requests, or installation needed.
"""
try:
    from .creator_plan import load_catalog, plan, validate, IMPORT_POLICY
    from .creator_utcp import ROUTES, dispatch, manual
    from .creator_project import require_text
except ImportError:
    from creator_plan import load_catalog, plan, validate, IMPORT_POLICY
    from creator_utcp import ROUTES, dispatch, manual
    from creator_project import require_text


def overview(port):
    sources, profiles, tools = load_catalog()
    validate(sources, profiles, tools)
    return {
        "counts": {"sources": len(sources), "profiles": len(profiles), "registered_tools": len(tools)},
        "profiles": [{"id": p["id"], "framework": p["framework"]} for p in profiles],
        "native_tools": [{"name": t["name"], "description": t["description"]} for t in manual(port)["tools"]],
        "import_policies": sorted(IMPORT_POLICY),
        "state": "catalogue-only; external integrations are not automatically connected",
    }


def query_tool(payload):
    if not isinstance(payload, dict) or set(payload) != {"tool", "arguments"}:
        raise ValueError("Invalid tool request")
    name, args = payload["tool"], payload["arguments"]
    if not isinstance(name, str) or name not in ROUTES or not isinstance(args, dict):
        raise ValueError("Unknown native tool or invalid arguments")
    if any(not isinstance(k, str) or not isinstance(v, str) for k, v in args.items()):
        raise ValueError("Arguments must be strings")
    return dispatch(ROUTES[name], {k: [v] for k, v in args.items()})


def propose_plan(payload):
    if not isinstance(payload, dict) or set(payload) != {"profile", "objective"}:
        raise ValueError("Invalid planning request")
    objective = require_text(payload["objective"], "Objective", 1000)
    profile = require_text(payload["profile"], "Profile", 80)
    sources, profiles, tools = load_catalog()
    return plan(profile, objective, sources, profiles, tools)
