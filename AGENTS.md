# AGENTS.md — building tools for this repo

This repo (`Hopsakee/Toolstemp`) is a collection of small, single-file, in-browser
HTML tools, served as a static site on **GitHub Pages**. If you are an AI agent (or a
human) about to add or change a tool, read this file first. It is the single source
of truth for the conventions here.

The methodology is Simon Willison's, from his write-up on building HTML tools with
LLMs → <https://simonwillison.net/2025/Dec/10/html-tools/>. Read it once for the full
reasoning; the rules below are the distilled, repo-specific version.

---

## What a tool here is

A **single, self-contained `.html` file** at the repo root. Four rules, straight from
Simon:

1. **One file.** Inline the JavaScript and CSS in the `.html`. "Inline JavaScript and
   CSS in a single HTML file means the least hassle in hosting or distributing them."
2. **No build step.** No JSX, no bundler, no npm. Prompt for **"no React"**. The file
   you commit is the file the browser runs.
3. **CDN dependencies only.** If you need a library, load it from cdnjs / jsDelivr /
   esm.sh with a `<script>` or `import` — never a local `node_modules`.
4. **Small scope.** A few hundred lines. "A few hundred lines means the maintainability
   of the code doesn't matter too much." If it wants to grow into an app, it probably
   belongs in its own repo, not here.

### Useful patterns (also from the post)

- **State in the URL** for shareable / bookmarkable state (query string or hash).
- **`localStorage`** for secrets (API keys) and larger state — keeps everything
  client-side, no server.
- **Copy-to-clipboard** buttons (mobile-friendly), **file input** read directly in JS
  (no upload), **download** generated files via Blob URLs.
- **CORS-enabled APIs** can be called straight from the page (GitHub, PyPI, iNaturalist,
  Bluesky, Mastodon, …). LLM APIs too, with the key in `localStorage`.
- For heavy lifting: **Pyodide** (Python + pandas/matplotlib in-browser),
  **WebAssembly**, or **MicroPython** as a lighter option.
- **Remix existing tools.** Before building, look at the sibling `.html` files here —
  they are documentation of patterns that already work in this repo.

---

## Layout — flat on purpose, files never move

Every tool lives **at the repo root**, not in a subfolder. This is deliberate:

- On GitHub Pages **the filename _is_ the public URL** (`…/grondwater-trends.html`).
  Moving a file into a folder changes its URL and breaks every existing bookmark/share.
- **`planten.html` is an installed PWA.** `sw.js` caches `./planten.html`,
  `./manifest.json`, `./icons/*` and `manifest.json` has `start_url: planten.html`,
  `scope: ./`. Moving any of those breaks the installed app on people's phones.

So: **never rename or move an existing tool file.** Organization is done in the
*index*, not the *filesystem* (see below).

### Naming new tools

Give a **new** tool a category prefix so the root stays readable and the file is
self-describing:

| Prefix    | For                                              | Example                 |
|-----------|--------------------------------------------------|-------------------------|
| `work-`   | WDODelta / Datalab / hydrology tools             | `work-peilbuis-check.html` |
| `ccv-`    | Cent Cols de Vosges (cycling) docs               | `ccv-route-nl.html`     |
| `util-`   | General-purpose utilities                        | `util-json-to-yaml.html` |

(Existing files predate this convention and keep their names — see "never move".)
The prefix is a human convenience; the *category that drives the index* is set in the
manifest, not inferred from the filename.

---

## The index regenerates itself — don't hand-edit `index.html`

`index.html` is **generated** from `tools.toml` by `scripts/build_index.py`. Do not edit
`index.html` by hand — your changes will be overwritten on the next regenerate.

To add a tool:

1. Drop the new `<prefix>-<name>.html` file at the repo root.
2. Add a `[[tool]]` block to **`tools.toml`** (`file`, `title`, `description`, `icon`,
   `category`). Use an existing category `key`, or add a new `[[category]]` section.
3. Regenerate:

   ```bash
   uv run scripts/build_index.py
   ```

The generator **errors out** if any root `*.html` (other than `index.html`) is missing
from `tools.toml` — that check is what stops the index from rotting. `--check` verifies
the index is up to date without writing (useful in CI).

The script keeps the dark theme. To restyle the whole page, edit the `CSS` constant in
`scripts/build_index.py`, not the generated output.

---

## Shipping — branch, PR, then Pages deploys

This is a real public site, so:

- **Work on a feature branch**, never commit straight to `main`.
- Open a **PR** (`gh pr create --fill`). Merging to `main` triggers
  `.github/workflows/static.yml`, which deploys the whole repo to GitHub Pages.
- Follow Simon's habit: record the **prompt or chat transcript** in the commit message
  so each tool's origin stays traceable.
- If you touched `tools.toml` or added a tool, make sure you committed the regenerated
  `index.html` alongside it.
