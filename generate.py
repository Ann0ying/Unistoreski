#!/usr/bin/env python3
import json, os, urllib.request, urllib.error

STORE_FILE = "Unistoreski.unistore"
STORE_URL = "https://raw.githubusercontent.com/Ann0ying/Unistoreski/main/" + STORE_FILE
TOKEN = os.environ.get("GITHUB_TOKEN")


def api(path):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "unistore-gen"}
    if TOKEN:
        headers["Authorization"] = "Bearer " + TOKEN
    req = urllib.request.Request("https://api.github.com" + path, headers=headers)
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def latest_release(repo):
    try:
        return api(f"/repos/{repo}/releases/latest")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    rels = api(f"/repos/{repo}/releases?per_page=1")  # fallback: prereleases only
    return rels[0] if rels else None


def build_entry(repo):
    info = api(f"/repos/{repo}")
    rel = latest_release(repo)
    if not rel:
        print(f"skip {repo}: no releases")
        return None

    entry = {}
    for a in rel["assets"]:
        name, url = a["name"], a["browser_download_url"]
        low = name.lower()
        if low.endswith(".3dsx"):
            entry[name] = [{
                "type": "downloadFile", "file": url,
                "output": "%3DSX%/" + name,
                "message": f"Downloading {name}..."}]
        elif low.endswith(".cia"):
            entry[name] = [
                {"type": "downloadFile", "file": url,
                 "output": "sdmc:/" + name,
                 "message": f"Downloading {name}..."},
                {"type": "installCia", "file": "/" + name},
                {"type": "deleteFile", "file": "sdmc:/" + name}]

    if not entry:
        print(f"skip {repo}: no .3dsx/.cia assets in latest release")
        return None

    published = (rel.get("published_at") or "")
    last = published[:10] + " at " + published[11:16] + " (UTC)" if published else ""
    entry["info"] = {
        "title": info["name"],
        "author": info["owner"]["login"],
        "description": info.get("description") or "",
        "category": ["homebrew"],
        "console": ["3DS"],
        "version": rel.get("tag_name", ""),
        "license": (info.get("license") or {}).get("spdx_id") or "Unknown",
        "last_updated": last,
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
            "title": "Unistoreski",
            "author": "Ann0ying",
            "description": "My personal UniStore",
            "file": STORE_FILE,
            "url": STORE_URL,
            "version": 3,
            "revision": old_rev + 1,
        },
        "storeContent": content,
    }
    with open(STORE_FILE, "w") as f:
        json.dump(store, f, indent=2)
    print(f"wrote revision {old_rev + 1} with {len(content)} apps")


main()
