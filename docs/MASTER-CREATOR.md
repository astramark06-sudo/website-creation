# Master website creator

This is a reusable zero-spend planning layer, not a deployed website or a hosted AI service.

## Discover and adopt

- Search the [source catalog](contracts/free-source-catalog.json) and the existing [tool registry](contracts/toolchain.registry.json).
- Use 21st.dev's official search and authorized free retrieval only. As of 2026-11-24 its [MCP documentation](https://21st.dev/mcp) lists two free code retrievals per day across clients; confirm the current allowance before each use.
- Follow the [marketplace terms](https://21st.dev/terms) and the selected item's license. Free access does not mean unrestricted redistribution. Do not mirror the site, extract gated content, collect previews or redistribute third-party components as a library.
- Prefer original implementations and permissively licensed upstream sources. Record upstream revision, item URL, license, copyright notice, dependencies, and adoption rationale before importing selected code into an actual product.
- No account credentials, paid API requests, automatic downloads, or background network actions are used by the planner.

## Offline planning

Use Python 3.10+ from the repository root:

```sh
python scripts/creator_plan.py --validate
python scripts/creator_plan.py --list
python scripts/creator_plan.py --profile interactive --objective "A task dashboard"
python -m unittest discover -s tests -v
```

The six [profiles](contracts/creator-profiles.json) provide a proposed stack and source references. Candidates are not installed or connected. Keep one framework, primitive baseline, design source and motion owner. A real product brief must be approved before selecting the final framework or scaffolding a site.

## Feature handoff

Start with [the product brief](project/PRODUCT-BRIEF.template.md), record decisions in [the ADR template](project/ADR.template.md), and use the existing [UI handoff](contracts/ui-handoff.template.json) for per-feature evidence.

After selection, implement project-owned tokens and components, confirm licenses, and run the existing quality workflows. Do not deploy a site until its purpose and release criteria are approved.

## Expansion roadmap

- Add formal JSON schemas for feature contracts and evidence records.
- Add source-specific integrations only when their official APIs and terms permit the intended usage.
- Add reusable original responsive templates and design tokens after a product scope is approved.
- Add app-specific cross-browser, accessibility, performance and release gates after scaffolding.
