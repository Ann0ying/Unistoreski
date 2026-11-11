#!/usr/bin/env python3
import json, os, re, urllib.request
from urllib.parse import urlparse

REPO = "Ann0ying/Unistoreski"
STORE_FILE = "unistore.unistore"
STORE_URL = f"https://raw.githubusercontent.com/{REPO}/main/{STORE_FILE}"
NOTE_VERSIONS = 3       # releases shown in the changelog
NOTE_MAX_CHARS = 1500   # per release
TOKEN = os.environ.get("GITHUB_TOKEN")


def api(path):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "unistore-gen"}
    if TOKEN:
        headers["Authorization"] = "Bearer " + TOKEN
    req = urllib.request.Request("https://api.github.com" + path, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def pick_releases(repo):
    rels = [r for r in api(f"/repos/{repo}/releases?per_page=30") if not r["draft"]]
    return [r for r in rels if not r["prerelease"]] or rels


def scripts_for(rel):
    out = {}
    for a in rel["assets"]:
        name, url = a["name"], a["browser_download_url"]
        low = name.lower()
        if low.endswith(".3dsx"):
            out[name] = [{"type": "downloadFile", "file": url,
                          "output": "%3DSX%/" + name,
                          "message": f"Downloading {name}..."}]
        elif low.endswith(".cia"):
            out[name] = [
                {"type": "downloadFile", "file": url, "output": "sdmc:/" + name,
                 "message": f"Downloading {name}..."},
                {"type": "installCia", "file": "/" + name},
                {"type": "deleteFile", "file": "sdmc:/" + name}]
    return out


def clean_md(text):
    text = text.replace("\r\n", "\n")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)       # images
    text = re.sub(r"<[^>]+>", "", text)                      # html tags
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)     # [text](url) -> text
    text = re.sub(r"https?://\S+", "", text)                 # bare urls
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.M)       # headings
    text = text.replace("**", "").replace("`", "")
    text = re.sub(r"[^\u0000-\uFFFF]", "", text)             # emoji etc.
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text if len(text) <= NOTE_MAX_CHARS else text[:NOTE_MAX_CHARS].rstrip() + "..."


def release_notes(releases):
    parts = []
    for r in releases[:NOTE_VERSIONS]:
        date = (r.get("published_at") or "")[:10]
        body = clean_md(r.get("body") or "") or "No release notes."
        parts.append(f"{r.get('tag_name', '?')} ({date})\n{body}")
    return "\n\n----------\n\n".join(parts)


def build_entry(repo):
    info = api(f"/repos/{repo}")
    releases = pick_releases(repo)

    rel, entry = None, {}
    for r in releases:               # newest release that actually has .cia/.3dsx
        entry = scripts_for(r)
        if entry:
            rel = r
            break
    if not rel:
        print(f"skip {repo}: no .3dsx/.cia assets in recent releases")
        return None

    pub = rel.get("published_at") or ""
    entry["info"] = {
        "title": info["name"],
        "author": info["owner"]["login"],
        "description": info.get("description") or "",
        "category": ["homebrew"],
        "console": ["3DS"],
        "version": rel.get("tag_name", ""),
        "license": (info.get("license") or {}).get("spdx_id") or "Unknown",
        "last_updated": f"{pub[:10]} at {pub[11:16]} (UTC)" if pub else "",
        "releasenotes": release_notes(releases),
        "wiki": info["html_url"],    # drives the "open in browser / show QR" menu
    }
    return entry


def main():
    with open("repos.txt") as f:
        repos = [l.strip() for l in f if l.strip() and not l.startswith("#")]

    content = []
    for r in repos:
        try:
            e = build_entry(r)
            if e:
                content.append(e)
        except Exception as ex:
            print(f"error on {r}: {ex}")
            raise  # fail loudly so a flaky API call can't wipe apps from the store

    old_rev, old_content = 0, None
    if os.path.exists(STORE_FILE):
        with open(STORE_FILE) as f:
            old = json.load(f)
        old_rev = old["storeInfo"].get("revision", 0)
        old_content = old.get("storeContent")

    if content == old_content:
        print("no changes")
        return

    store = {
        "storeInfo": {
            "title": "Unistoreski", "author": "Ann0ying",
            "description": "My personal UniStore",
            "file": STORE_FILE, "url": STORE_URL,
            "version": 3, "revision": old_rev + 1,
        },
        "storeContent": content,
    }
    with open(STORE_FILE, "w") as f:
        json.dump(store, f, indent=2, ensure_ascii=False)
    print(f"wrote revision {old_rev + 1} with {len(content)} apps")


main()
