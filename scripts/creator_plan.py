"""Offline, zero-spend website planning. Does not install or contact services."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs" / "contracts"
ACCESS = {"open-source", "mixed-directory", "metered-free", "reference"}


def load_catalog():
    sources = json.loads((ROOT / "free-source-catalog.json").read_text(encoding="utf-8"))["sources"]
    profiles = json.loads((ROOT / "creator-profiles.json").read_text(encoding="utf-8"))["profiles"]
    tools = json.loads((ROOT / "toolchain.registry.json").read_text(encoding="utf-8"))["tools"]
    return sources, profiles, tools


def validate(sources, profiles, tools):
    source_ids = {s["id"] for s in sources}
    tool_ids = {t["id"] for t in tools}
    if len(source_ids) != len(sources):
        raise ValueError("Duplicate source id")
    for s in sources:
        if s["access"] not in ACCESS or s["adoption"] != "review-required":
            raise ValueError("Invalid source policy: " + s["id"])
        if not all(s[k].startswith("https://") for k in ("url", "upstream", "license_url")):
            raise ValueError("Missing HTTPS provenance: " + s["id"])
        if not s["tags"] or not s["notes"]:
            raise ValueError("Missing source metadata: " + s["id"])
    if len({p["id"] for p in profiles}) != len(profiles):
        raise ValueError("Duplicate profile id")
    for p in profiles:
        if not set(p["required"] + p["optional"]) <= tool_ids:
            raise ValueError("Unknown tool in " + p["id"])
        if not set(p["sources"]) <= source_ids:
            raise ValueError("Unknown source in " + p["id"])
        if p["framework"] not in p["required"]:
            raise ValueError("Framework must be explicit")
        if set(p["required"]) & set(p["optional"]):
            raise ValueError("Overlapping required/optional tools")


def plan(profile_id, objective, sources, profiles, tools):
    validate(sources, profiles, tools)
    if not objective.strip():
        raise ValueError("An explicit project objective is required")
    p = next((p for p in profiles if p["id"] == profile_id), None)
    if p is None:
        raise ValueError("Unknown profile: " + profile_id)
    by_id = {s["id"]: s for s in sources}
    return {
        "objective": objective,
        "profile": p["id"],
        "framework_candidate": p["framework"],
        "required_tool_candidates": p["required"],
        "optional_tool_candidates": p["optional"],
        "source_references": [by_id[k] for k in p["sources"]],
        "state": "proposal-only",
        "gates": ["user-approved brief", "cost and license review", "tool availability check",
                  "one design source and motion owner", "responsive and accessibility tests",
                  "security and performance review", "verified build and deployment approval"],
        "network_calls": 0,
        "paid_services": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="List website profiles")
    parser.add_argument("--validate", action="store_true", help="Validate catalog references")
    parser.add_argument("--profile")
    parser.add_argument("--objective")
    args = parser.parse_args()
    sources, profiles, tools = load_catalog()
    try:
        validate(sources, profiles, tools)
        if args.validate:
            print(f"Validated {len(sources)} source records and {len(profiles)} profiles.")
        elif args.list:
            print(json.dumps(profiles, indent=2))
        elif args.profile and args.objective:
            print(json.dumps(plan(args.profile, args.objective, sources, profiles, tools), indent=2))
        else:
            parser.error("use --list, --validate, or --profile with --objective")
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
