"""MkDocs hooks: the README is the home page, and the panel's fonts come along."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from mkdocs.config.defaults import MkDocsConfig
from mkdocs.structure.files import File, Files

ROOT = Path(__file__).resolve().parents[2]
BLOB = "https://github.com/oberon-systems/awg-keeper/blob/main/"
LINK = re.compile(r"\]\((?!https?://|#)([^)]+)\)")


def _link(match: re.Match[str]) -> str:
    target = match.group(1)
    if target.startswith("docs/"):
        return f"]({target.removeprefix('docs/')})"
    return f"]({BLOB}{target})"


def on_files(files: Files, config: MkDocsConfig) -> Files:
    """Serve README.md as index.md, its links pointed at the site or at GitHub."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    page = "---\ntitle: Home\n---\n\n" + LINK.sub(_link, readme)
    home = File.generated(config, "index.md", content=page)
    # edit_uri is relative to docs/, and "Edit on GitHub" has to open the README.
    home.edit_uri = "../README.md"
    files.append(home)
    return files


def on_post_build(config: MkDocsConfig) -> None:
    """Copy the fonts the panel vendors, so the site is set in the same faces."""
    assets = Path(config.site_dir) / "assets"
    shutil.copytree(ROOT / "web/ui/src/fonts", assets / "fonts", dirs_exist_ok=True)
    shutil.copy2(ROOT / "web/ui/src/fonts.css", assets / "fonts.css")
