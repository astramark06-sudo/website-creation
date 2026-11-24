# Master website creator

This is a reusable zero-spend planning and original website generation toolkit, not a deployed website or a hosted AI service.

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
python scripts/creator_plan.py --search dashboard --import-policy eligible-upstream-review
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

## Commercial and free template discovery

The catalogue now includes 31 source records. Search by purpose and import policy, then open the original source. Reference-only providers cannot be imported. Metered providers use only official retrieval and current allowances. Upstream-review candidates require item-level license and asset checks. The catalogue stores original metadata and links only; it does not mirror template code or designs.

For a standalone free stack, choose a reviewed static generator or frontend framework, original components or a permissively licensed upstream source, and local editing/build tools. Paid marketplace assets, paid export features and hosted AI credits are not dependencies. Reconstruct authorized sites with original code and user-owned content, not proprietary demos, branding or protected assets. Public previews cannot reveal private server logic.

## Original website builder and offline HTML inspection

Generate a starter in a new directory with Python 3.10+:

```sh
python scripts/creator_build.py build --mode landing --title "My studio" --description "Original website starter" --output build/studio
python scripts/creator_build.py build --mode task-dashboard --title "My tasks" --description "A local task workspace" --output build/tasks
python scripts/creator_build.py inspect build/studio/index.html
```

The four modes are landing, portfolio, documentation and task-dashboard. The first three generate static HTML/CSS; task-dashboard adds original JavaScript for adding, completing and removing tasks with browser-local persistence. All outputs use system fonts, responsive layouts, no external requests and no paid dependencies. Use a new output directory; the generator refuses to overwrite existing files. Review placeholders before publishing. Serve generated files locally or deploy static output only after approval.

Inspect only authorized local HTML. The inspector reports element counts, headings, language, viewport, missing alt attributes, script references counts and form-control counts. It never runs the document, requests external URLs, or returns text, asset URLs or form values. This is structural inspection, not visual reconstruction, a browser accessibility audit, screenshot-to-code, or backend recovery. The generated task dashboard is client-side only, not a shared database or authenticated backend.

The repository tests validate generation and analysis; browser interaction verification remains a separate requirement. Do not claim full website replication from these starter capabilities.

## Integrated project-to-publishing workflow

The [example project](../projects/example.json) demonstrates a multi-page site with original content and optional browser-local interactions. It is deliberately not approved for publication. Copy it to a new project file, replace the example content with your own independently written content, select one of the three themes, and define each page's sections and interaction mode. Up to 20 pages are supported. No imported HTML, JavaScript or external URLs are interpreted as markup.

```sh
python scripts/creator_project.py build --spec projects/example.json --output build/preview
python scripts/creator_project.py verify --spec projects/example.json --output build/preview
python -m http.server 8000 --bind 127.0.0.1 --directory build/preview
```

Open localhost port 8000 to review the generated website. Confirm rights to all content, original composition, navigation, responsive appearance, keyboard access and functional interactions before publication. Compare any authorized reference using its general requirements, not copied source, text, branding or protected assets. The approval fields record human review; they are not plagiarism detection or a legal certification. Do not claim browser or device checks passed unless performed.

To publish an approved project, commit its specification as `projects/publish.json` with all three review fields set to true. In GitHub repository settings enable Pages with GitHub Actions as the source. On main, manually dispatch the **Publish reviewed creator project** workflow and explicitly confirm publication. It runs the regression tests, generates and verifies the static output, then deploys through the GitHub Pages environment. It will fail if the specification is missing, unapproved or invalid. The public URL must be verified from the deployment result. No site is published by default; existing manual static-site deployment is unchanged.

GitHub Pages supports static files and browser-side interactions, not private server code, login systems or shared databases. Full-stack apps, independently generated multi-user backends, visual editing and browser-rendered reference analysis require separate future modules and a suitable reviewed hosting profile. No paid service is introduced by this workflow.

## Local graphical workspace

Run `python scripts/creator_studio.py` from the repository root, then open the printed loopback address in your browser. Edit project details, add or remove pages and sections, select a theme, import and save draft JSON, preview at three viewport widths, and export a verified ZIP. Preview is deliberately non-interactive; test the exported site locally. Imported and exported projects remain unapproved drafts; publishing uses the separate reviewed GitHub Pages workflow.

The studio binds only to IPv4 loopback, checks Host and Origin headers and requires a per-run request token. Do not forward its port or expose it publicly. Save the JSON or export before closing; the server does not retain drafts. Browser end-to-end and accessibility verification remain separate checks. No additional dependencies or paid services are required.

## Reference-informed original drafts

The studio accepts an authorized, locally saved HTML file up to 64 KiB. Provide your own website name and objective, confirm permission, and choose Analyze reference and propose draft. The report retains only standard element counts and limited structural indicators, not source text, assets, URLs, scripts, or custom tag names. It suggests general content organization and creates an independent, unapproved starter only if you confirm replacing the current project. This is structural planning, not visual replication, plagiarism detection, AI inference or a live website crawler. The user must write original content, create a distinct design and approve the release separately.

## Optional local AI drafting

The default studio requires no AI model. If you already have Ollama and a suitable downloaded local model, configure Ollama for local-only operation (disable cloud features in Ollama and use offline networking where appropriate). Start the studio with `python scripts/creator_studio.py --local-model YOUR_LOCAL_MODEL_NAME`. The AI panel then accepts a website brief and generates a structured draft using the fixed loopback Ollama API. No model is installed or downloaded automatically, no paid key is used, and proxies and redirects are disabled. Model inventory checks exclude obvious cloud models but cannot independently guarantee the behavior of a separately configured Ollama service. See the [Ollama generate API](https://docs.ollama.com/api/generate) and [model inventory API](https://docs.ollama.com/api/tags).

The model returns page text and structure only. The generator validates the response, rejects extra fields, never executes model-generated code, and requires separate approval before replacing a draft. Output is unapproved and may contain errors or unsupported requirements. Review it before building and publishing. The regression tests use a fake transport; actual inference quality depends on the locally installed model and available hardware.
