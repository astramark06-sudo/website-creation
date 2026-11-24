# UTCP integration

Master Creator provides an opt-in Universal Tool Calling Protocol (UTCP) HTTP discovery endpoint alongside the existing MCP configuration. The implementation follows the [official Python UTCP provider example](https://github.com/universal-tool-calling-protocol/python-utcp/tree/main/core) using the manual fields documented for the 1.0 series. It uses Python's standard library, not an installed UTCP SDK.

## Start the native provider

```sh
python scripts/creator_utcp.py
```

The discovery URL is `http://127.0.0.1:8767/utcp`. It is only reachable on the local machine. A compatible UTCP client can register the HTTP discovery manual using this URL and restrict communication protocols to HTTP. The native tools are:

| Tool | Purpose |
| --- | --- |
| list_profiles | Review the existing six development profiles |
| list_design_options | Discover supported original design presets |
| search_sources | Search the local source metadata with optional import-policy filtering |

No credentials, paid services, external API calls, file writes or subprocess execution are involved. The provider never exposes studio session tokens, project drafts, generated files or deployment controls. Do not expose or tunnel the local port to the internet. The unit tests exercise real loopback HTTP discovery and invocation, but compatibility with third-party UTCP clients has not yet been verified.

## Integration policy

Use native HTTP for bounded tool discovery and keep existing MCP integrations for supported design and documentation providers. For browser testing use the repository's existing Playwright workflow; for AI drafting use the optional configured offline Ollama model. A future reviewed UTCP client or MCP bridge must be opt-in and limited to specific approved providers, operations and transports. Do not automatically register remote manuals, CLI commands, arbitrary URLs, credential-bearing tools, paid APIs, or deployment actions. Tool discovery is not proof of installation, authorization, licensing or availability.

See the [official UTCP introduction](https://www.utcp.io/docs/), [protocols](https://www.utcp.io/protocols), and [security guidance](https://www.utcp.io/next/security). The existing catalogue licensing restrictions and explicit publishing approval apply regardless of calling protocol.
