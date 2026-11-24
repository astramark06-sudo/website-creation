# Original section components

The structured website generator supports six independently authored component types: card, article, callout, FAQ, list and steps. Choose a component type on each section in the studio, write original content, and reorder it using the drag handle or the existing Move section up/down buttons. Lists and steps accept up to 30 nonempty lines, one item per line. FAQs use native HTML details and summary rather than a JavaScript dependency. The optional `kind` field preserves existing project specifications and old card output. All text is escaped and arbitrary HTML, code or CSS is rejected by the structured schema.

Component output is included in the existing verified ZIP and the reviewed static publication path. The library uses only project-owned CSS and native HTML. These are reusable building blocks, not complete replicas of third-party component marketplaces. Review content, responsiveness, accessibility and rights before publishing.

Regression tests cover all six kinds, legacy compatibility, escaping and invalid fields. Browser tests exercise selection, ordering and FAQ expansion; full accessibility review and drag-and-drop testing remain separate.
