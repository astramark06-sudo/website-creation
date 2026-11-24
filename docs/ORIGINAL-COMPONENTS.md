# Original section components

The structured website generator supports six independently authored component types: card, article, callout, FAQ, list and steps. Choose a component type on each section in the studio, write original content, and reorder it using the drag handle or the existing Move section up/down buttons. Lists and steps accept up to 30 nonempty lines, one item per line. FAQs use native HTML details and summary rather than a JavaScript dependency. The optional `kind` field preserves existing project specifications and old card output. All text is escaped and arbitrary HTML, code or CSS is rejected by the structured schema.

Component output is included in the existing verified ZIP and the reviewed static publication path. The library uses only project-owned CSS and native HTML. These are reusable building blocks, not complete replicas of third-party component marketplaces. Review content, responsiveness, accessibility and rights before publishing.

Regression tests cover all six kinds, legacy compatibility, escaping and invalid fields. Browser tests exercise selection, ordering and FAQ expansion; full accessibility review and drag-and-drop testing remain separate.

## Searchable pages

Select the `search` interaction for a page to add a browser-local section filter. It searches the generated section text with case-insensitive Unicode normalization, reports matching section counts, and supports clearing the search. No input leaves the page; no remote search service is used. All sections remain available without JavaScript. The studio preview remains inert; test the exported page or use project-specific browser checks. The cross-browser design suite exercises search across all four layouts. The existing `tasks` interaction remains a separate per-page choice.
