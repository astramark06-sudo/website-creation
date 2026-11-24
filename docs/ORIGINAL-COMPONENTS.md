# Original section components

The structured website generator supports ten independently authored component types: card, article, callout, FAQ, list, steps, metrics, timeline, table and page links. Choose a component type on each section in the studio, write original content, and reorder it using the drag handle or the existing Move section up/down buttons. Lists and steps accept up to 30 nonempty lines, one item per line. Metrics use `Label | Value` lines with up to 12 values; timelines use the same format with up to 20 events; tables use a pipe-separated header followed by 1 to 30 equally sized rows with 2 to 6 columns. FAQs use native HTML details and summary rather than a JavaScript dependency. The optional `kind` field preserves existing project specifications and old card output. All text is escaped and arbitrary HTML, code or CSS is rejected by the structured schema.

Component output is included in the existing verified ZIP and the reviewed static publication path. The library uses only project-owned CSS and native HTML. These are reusable building blocks, not complete replicas of third-party component marketplaces. Review content, responsiveness, accessibility and rights before publishing.

Regression tests cover all ten kinds, legacy compatibility, escaping, structured-row validation and invalid fields. Browser tests exercise selection, ordering and FAQ expansion; full accessibility review and drag-and-drop testing remain separate.

## Searchable pages

Select the `search` interaction for a page to add a browser-local section filter. It searches the generated section text with case-insensitive Unicode normalization, reports matching section counts, and supports clearing the search. No input leaves the page; no remote search service is used. All sections remain available without JavaScript. The studio preview remains inert; test the exported page or use project-specific browser checks. The cross-browser design suite exercises search across all four layouts. The existing `tasks` interaction remains a separate per-page choice.

## Structured information components

Metrics render as a semantic description list, timelines as an ordered list, and tables use column headers with `scope="col"`, a hidden caption and a horizontally scrollable wrapper for narrow viewports. Cells and labels are escaped as plain text; the syntax does not permit HTML, scripts, URLs or formulas. The Firefox and WebKit coverage suite includes these component types across every supported layout.

## Page links and calls to action

Choose the `links` component and enter up to eight `Link label | page-address` lines, for example `Explore the workspace | workspace` or `Back home | home`. Each target must be an existing generated page address; URLs, arbitrary markup and missing pages are rejected. Links use native anchors with the existing accent and focus styles. The preview remains inert; exported sites support normal navigation. In Studio, commit a valid page address by leaving its field: incoming and self-links are updated while their labels are retained. Invalid or duplicate addresses are rejected without changing links. Removal is blocked while another page links to the target; remove or redirect those links first. Direct JSON edits still require the author to maintain valid destinations. Browser checks follow each authored link at every supported viewport. No new libraries or external services are required.
