# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Regenerate index.html from tools.toml.

The manifest (tools.toml) is the single source of truth for what appears on the
landing page and how it is grouped. This script renders a categorized index that
preserves the repo's dark theme, and refuses to run if a tool file at the repo
root is missing from the manifest — so the index can't silently rot.

    uv run scripts/build_index.py            # regenerate index.html
    uv run scripts/build_index.py --check     # fail (exit 1) if index.html is stale

Files are NEVER moved or renamed by this script: a tool's filename is its public
GitHub Pages URL, and planten.html is a wired PWA (sw.js / manifest.json).
"""

from __future__ import annotations

import html
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "tools.toml"
OUTPUT = ROOT / "index.html"

# The dark theme, kept verbatim from the original hand-built index.html so the
# generated page is visually identical. Edit here to restyle every render.
CSS = """
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --bg: #0d1117;
      --surface: #161b22;
      --surface-2: #1c2230;
      --border: #30363d;
      --text: #e6edf3;
      --text-dim: #8b949e;
      --text-faint: #484f58;
      --accent: #1f6feb;
      --green: #238636;
      --green-border: #2ea043;
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background:
        radial-gradient(1200px 600px at 50% -200px, rgba(31,111,235,0.18), transparent 70%),
        var(--bg);
      color: var(--text);
      min-height: 100vh;
      padding: 3rem 1.5rem 4rem;
    }

    .wrap { max-width: 960px; margin: 0 auto; }

    header.intro { text-align: center; margin-bottom: 3rem; }

    .badge {
      display: inline-block;
      background: rgba(31,111,235,0.15);
      color: #79c0ff;
      font-size: 0.72rem;
      font-weight: 600;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      padding: 0.3rem 0.85rem;
      border: 1px solid rgba(31,111,235,0.4);
      border-radius: 999px;
      margin-bottom: 1.25rem;
    }

    header.intro h1 {
      font-size: 2.5rem;
      font-weight: 800;
      color: #f0f6fc;
      letter-spacing: -0.02em;
      margin-bottom: 0.75rem;
    }

    header.intro p {
      font-size: 1.05rem;
      line-height: 1.7;
      color: var(--text-dim);
      max-width: 560px;
      margin: 0 auto;
    }

    /* Featured app */
    .featured {
      position: relative;
      background:
        linear-gradient(135deg, rgba(35,134,54,0.18), rgba(31,111,235,0.10)),
        var(--surface);
      border: 1px solid var(--green-border);
      border-radius: 16px;
      padding: 2.5rem;
      margin-bottom: 3rem;
      overflow: hidden;
    }

    .featured::before {
      content: "";
      position: absolute;
      inset: 0;
      background: radial-gradient(600px 300px at 100% 0%, rgba(46,160,67,0.25), transparent 70%);
      pointer-events: none;
    }

    .featured .star {
      display: inline-block;
      font-size: 0.72rem;
      font-weight: 700;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: #7ee787;
      margin-bottom: 0.85rem;
    }

    .featured h2 {
      font-size: 1.9rem;
      font-weight: 700;
      color: #f0f6fc;
      margin-bottom: 0.75rem;
      position: relative;
    }

    .featured p {
      font-size: 1.05rem;
      line-height: 1.7;
      color: #c9d1d9;
      max-width: 600px;
      margin-bottom: 1.75rem;
      position: relative;
    }

    /* Grid of other apps */
    .section-label {
      font-size: 0.8rem;
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--text-faint);
      margin-bottom: 1rem;
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      gap: 1.25rem;
    }

    .app-card {
      display: flex;
      flex-direction: column;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.5rem;
      transition: border-color 0.15s, transform 0.15s;
    }

    .app-card:hover { border-color: #58a6ff; transform: translateY(-2px); }

    .app-card .icon { font-size: 1.6rem; margin-bottom: 0.85rem; }

    .app-card h3 {
      font-size: 1.15rem;
      font-weight: 700;
      color: #f0f6fc;
      margin-bottom: 0.5rem;
    }

    .app-card p {
      font-size: 0.92rem;
      line-height: 1.6;
      color: var(--text-dim);
      margin-bottom: 1.25rem;
      flex: 1;
    }

    /* Buttons */
    a.btn {
      display: inline-flex;
      align-items: center;
      gap: 0.45rem;
      padding: 0.6rem 1.3rem;
      border-radius: 7px;
      font-size: 0.92rem;
      font-weight: 600;
      text-decoration: none;
      transition: opacity 0.15s, background 0.15s;
      align-self: flex-start;
    }

    a.btn:hover { opacity: 0.88; }

    /* Distinct color for the featured map app */
    .btn-featured {
      background: var(--green);
      color: #fff;
      border: 1px solid var(--green-border);
      box-shadow: 0 4px 14px rgba(35,134,54,0.35);
    }

    .btn-app {
      background: var(--surface-2);
      color: var(--text);
      border: 1px solid var(--border);
    }
    .btn-app:hover { border-color: #58a6ff; opacity: 1; }

    .links-row {
      display: flex;
      gap: 0.85rem;
      justify-content: center;
      flex-wrap: wrap;
      margin-top: 3rem;
    }

    .btn-ghost {
      background: transparent;
      color: var(--text-dim);
      border: 1px solid var(--border);
    }

    .btn-ccv {
      background: rgba(45,106,79,0.2);
      color: #7ee787;
      border: 1px solid rgba(45,106,79,0.5);
    }
    .btn-ccv:hover { border-color: #56ab8a; opacity: 1; }

    .section-divider {
      border: none;
      border-top: 1px solid var(--border);
      margin: 2.5rem 0 2rem;
    }

    footer {
      margin-top: 3.5rem;
      text-align: center;
      font-size: 0.8rem;
      color: var(--text-faint);
    }
"""


def esc(text: str) -> str:
    """Escape text for HTML body content, leaving quotes intact."""
    return html.escape(text, quote=False)


def load_manifest() -> dict:
    with MANIFEST.open("rb") as fh:
        return tomllib.load(fh)


def discover_root_tools() -> set[str]:
    """Every *.html at the repo root except the generated index.html."""
    return {p.name for p in ROOT.glob("*.html") if p.name != "index.html"}


REQUIRED_TOP = ("site_title", "heading", "intro", "github_url", "footer")
REQUIRED_TOOL_FIELDS = ("file", "title", "description", "icon", "category")


def validate(manifest: dict) -> list[dict]:
    """Cross-check manifest against the filesystem. Returns the tool list.

    Every "bad manifest" condition exits through this one human-readable path,
    so the renderer can assume a well-formed manifest and never raises a bare
    KeyError at the user.
    """
    tools = manifest.get("tool", [])

    errors_early = [k for k in REQUIRED_TOP if k not in manifest]
    if errors_early:
        print(
            "build_index.py: tools.toml is missing required top-level key(s): "
            + ", ".join(errors_early),
            file=sys.stderr,
        )
        sys.exit(1)

    field_errors = [
        f"  - {t.get('file', '(entry with no file)')}: missing "
        + ", ".join(k for k in REQUIRED_TOOL_FIELDS if k not in t)
        for t in tools
        if any(k not in t for k in REQUIRED_TOOL_FIELDS)
    ]
    if field_errors:
        print(
            "build_index.py: these [[tool]] entries are missing required "
            "field(s) (" + ", ".join(REQUIRED_TOOL_FIELDS) + "):\n"
            + "\n".join(field_errors),
            file=sys.stderr,
        )
        sys.exit(1)

    manifest_files = {t["file"] for t in tools}
    on_disk = discover_root_tools()

    missing_from_manifest = sorted(on_disk - manifest_files)
    missing_on_disk = sorted(manifest_files - on_disk)

    errors = []
    if missing_from_manifest:
        errors.append(
            "These tool files exist at the repo root but have no [[tool]] entry "
            "in tools.toml (add them, or the index would silently omit them):\n  - "
            + "\n  - ".join(missing_from_manifest)
        )
    if missing_on_disk:
        errors.append(
            "These [[tool]] entries point at files that do not exist at the repo "
            "root (fix the filename or remove the entry):\n  - "
            + "\n  - ".join(missing_on_disk)
        )

    cat_keys = {c["key"] for c in manifest.get("category", [])}
    for t in tools:
        if t.get("category") not in cat_keys:
            errors.append(
                f"Tool {t['file']!r} has category {t.get('category')!r}, which is "
                f"not a defined [[category]] key ({sorted(cat_keys)})."
            )

    featured = [t for t in tools if t.get("featured")]
    if len(featured) > 1:
        errors.append(
            "More than one tool sets featured = true: "
            + ", ".join(t["file"] for t in featured)
        )

    if errors:
        print("build_index.py: manifest validation failed.\n", file=sys.stderr)
        print("\n\n".join(errors), file=sys.stderr)
        sys.exit(1)

    return tools


def render_card(tool: dict, button_class: str, cta: str) -> str:
    return f"""      <div class="app-card">
        <div class="icon">{esc(tool["icon"])}</div>
        <h3>{esc(tool["title"])}</h3>
        <p>{esc(tool["description"])}</p>
        <a class="btn {button_class}" href="{esc(tool["file"])}">{esc(cta)}</a>
      </div>"""


def render_featured(tool: dict, cfg: dict) -> str:
    return f"""    <section class="featured">
      <span class="star">{esc(cfg.get("star", "★"))}</span>
      <h2>{esc(tool["title"])}</h2>
      <p>{esc(tool["description"])}</p>
      <a class="btn {cfg.get("button_class", "btn-featured")}" href="{esc(tool["file"])}">{esc(cfg.get("cta", "Open →"))}</a>
    </section>"""


def render(manifest: dict, tools: list[dict]) -> str:
    featured = next((t for t in tools if t.get("featured")), None)
    regular = [t for t in tools if t is not featured]
    body_parts: list[str] = []

    if featured:
        body_parts.append(render_featured(featured, manifest.get("featured", {})))

    first_section = True
    for cat in manifest.get("category", []):
        cat_tools = [t for t in regular if t.get("category") == cat["key"]]
        if not cat_tools:
            continue
        if not first_section:
            body_parts.append('    <hr class="section-divider">')
        first_section = False
        cards = "\n\n".join(
            render_card(t, cat["button_class"], cat["cta"]) for t in cat_tools
        )
        body_parts.append(
            f'    <p class="section-label">{esc(cat["label"])}</p>\n'
            f'    <div class="grid">\n{cards}\n    </div>'
        )

    body = "\n\n".join(body_parts)
    title = esc(manifest["site_title"])

    return f"""<!DOCTYPE html>
<html lang="nl">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <style>{CSS}  </style>
</head>
<body>
  <div class="wrap">
    <header class="intro">
      <span class="badge">{title}</span>
      <h1>{esc(manifest["heading"])}</h1>
      <p>{esc(manifest["intro"])}</p>
    </header>

{body}

    <div class="links-row">
      <a class="btn btn-ghost" href="{esc(manifest["github_url"])}">GitHub-repository</a>
    </div>

    <footer>{esc(manifest["footer"])}</footer>
  </div>
</body>
</html>
"""


def main() -> None:
    check_only = "--check" in sys.argv[1:]
    manifest = load_manifest()
    tools = validate(manifest)
    output = render(manifest, tools)

    current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else None

    if check_only:
        if current != output:
            print(
                "build_index.py --check: index.html is stale. "
                "Run `uv run scripts/build_index.py` and commit.",
                file=sys.stderr,
            )
            sys.exit(1)
        print("index.html is up to date.")
        return

    if current == output:
        print(f"index.html already up to date ({len(tools)} tools).")
        return

    OUTPUT.write_text(output, encoding="utf-8")
    print(f"Wrote {OUTPUT.name} ({len(tools)} tools).")


if __name__ == "__main__":
    main()
