#!/usr/bin/env python3
"""Build catalog.json from apps.json and the GitHub releases of this repo.

Release convention (written by each app's release-android.yml):
  tag:    <app-id>-v<semver>        e.g. hydrobot-v1.2.0, hydrobot-v1.3.0-beta.1
  asset:  one .apk file
  body:   contains the lines "versionCode: <int>" and "sha256: <64 hex>"
  prerelease flag set for beta builds (any tag with a "-" suffix)

Usage:
  python scripts/build_catalog.py --repo jlguieb/jan-releases            # live, uses GITHUB_TOKEN if set
  python scripts/build_catalog.py --releases-file tests/releases.json    # offline test
No third-party packages needed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from typing import Any

SCHEMA = 1
VERSION_CODE_RE = re.compile(r"^\s*versionCode:\s*(\d+)\s*$", re.MULTILINE | re.IGNORECASE)
SHA_RE = re.compile(r"^\s*sha256:\s*([0-9a-fA-F]{64})\s*$", re.MULTILINE)
META_LINE_RE = re.compile(r"^\s*(versionCode|sha256):.*$\n?", re.MULTILINE | re.IGNORECASE)
MAX_NOTES = 2000
MAX_HISTORY = 10
# Optional store fields copied from apps.json as they are.
PASSTHROUGH = ("developer", "category", "minSdk")


def fetch_releases(repo: str, token: str | None) -> list[dict[str, Any]]:
    releases: list[dict[str, Any]] = []
    page = 1
    while True:
        url = f"https://api.github.com/repos/{repo}/releases?per_page=100&page={page}"
        req = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "jan-releases-catalog",
        })
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=30) as resp:
            batch = json.load(resp)
        releases.extend(batch)
        if len(batch) < 100:
            return releases
        page += 1


def tag_pattern(app_id: str) -> re.Pattern[str]:
    return re.compile(rf"^{re.escape(app_id)}-v(\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?)$")


def parse_release(app_id: str, rel: dict[str, Any]) -> dict[str, Any] | None:
    """Return a catalog release entry, or None if the release is not usable."""
    if rel.get("draft"):
        return None
    m = tag_pattern(app_id).match(rel.get("tag_name", ""))
    if not m:
        return None
    body = rel.get("body") or ""
    apk = next((a for a in rel.get("assets", []) if a.get("name", "").lower().endswith(".apk")), None)
    vc = VERSION_CODE_RE.search(body)
    if apk is None or vc is None:
        print(f"warn: {rel.get('tag_name')}: missing .apk asset or versionCode line, skipped", file=sys.stderr)
        return None

    sha = None
    digest = apk.get("digest") or ""
    if digest.startswith("sha256:"):
        sha = digest.split(":", 1)[1]
    if not sha:
        sm = SHA_RE.search(body)
        sha = sm.group(1) if sm else None
    if not sha:
        print(f"warn: {rel.get('tag_name')}: no sha256, skipped", file=sys.stderr)
        return None

    notes = META_LINE_RE.sub("", body).strip()[:MAX_NOTES]
    return {
        "version": m.group(1),
        "versionCode": int(vc.group(1)),
        "url": apk["browser_download_url"],
        "sha256": sha.lower(),
        "size": apk.get("size", 0),
        "published": rel.get("published_at") or rel.get("created_at") or "",
        "notes": notes,
        "prerelease": bool(rel.get("prerelease")),
    }


def build_catalog(apps_doc: dict[str, Any], releases: list[dict[str, Any]], repo: str, branch: str) -> dict[str, Any]:
    out_apps = []
    newest = ""
    for meta in apps_doc["apps"]:
        entry: dict[str, Any] = {
            "id": meta["id"],
            "name": meta["name"],
            "type": meta.get("type", "android"),
            "description": meta.get("description", ""),
        }
        def raw_url(path: str) -> str:
            return path if path.startswith("http") else f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"

        icon = meta.get("icon")
        if icon:
            entry["icon"] = raw_url(icon)
        for key in PASSTHROUGH:
            if meta.get(key) is not None:
                entry[key] = meta[key]
        if meta.get("screenshots"):
            entry["screenshots"] = [raw_url(s) for s in meta["screenshots"]]

        if entry["type"] == "web":
            entry["url"] = meta["url"]
            out_apps.append(entry)
            continue

        entry["package"] = meta["package"]
        parsed = [p for p in (parse_release(meta["id"], r) for r in releases) if p]
        stable = max((p for p in parsed if not p["prerelease"]), key=lambda p: p["versionCode"], default=None)
        beta = max((p for p in parsed if p["prerelease"]), key=lambda p: p["versionCode"], default=None)
        if beta and stable and beta["versionCode"] <= stable["versionCode"]:
            beta = None  # an older beta is pointless once stable has passed it
        newest_first = sorted(parsed, key=lambda p: p["versionCode"], reverse=True)

        def public(rel: dict[str, Any] | None) -> dict[str, Any] | None:
            return None if rel is None else {k: v for k, v in rel.items() if k != "prerelease"}

        for rel in (stable, beta):
            if rel:
                newest = max(newest, rel["published"])
        entry["stable"] = public(stable)
        entry["beta"] = public(beta)
        entry["history"] = [public(p) for p in newest_first[:MAX_HISTORY]]
        out_apps.append(entry)

    return {"schema": SCHEMA, "updated": newest, "apps": out_apps}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "jlguieb/jan-releases"))
    ap.add_argument("--branch", default="main")
    ap.add_argument("--apps", default="apps.json")
    ap.add_argument("--out", default="catalog.json")
    ap.add_argument("--releases-file", help="read releases from a JSON file instead of the GitHub API")
    args = ap.parse_args()

    with open(args.apps, encoding="utf-8") as f:
        apps_doc = json.load(f)
    if args.releases_file:
        with open(args.releases_file, encoding="utf-8") as f:
            releases = json.load(f)
    else:
        releases = fetch_releases(args.repo, os.environ.get("GITHUB_TOKEN"))

    catalog = build_catalog(apps_doc, releases, args.repo, args.branch)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
        f.write("\n")
    for app in catalog["apps"]:
        s = app.get("stable") or {}
        b = app.get("beta") or {}
        print(f"{app['id']}: stable={s.get('version', '-')} beta={b.get('version', '-')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
