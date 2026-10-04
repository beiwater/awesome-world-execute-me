#!/usr/bin/env python3
"""Collect GitHub fan works of Mili - world.execute(me); into site/data/works.json.

Stdlib only. Uses GITHUB_TOKEN / GH_TOKEN when present (search + README fetches).
Manual curation lives in data/overrides.json and always wins over heuristics.
"""
import base64
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OVERRIDES = os.path.join(ROOT, "data", "overrides.json")
OUT = os.path.join(ROOT, "site", "data", "works.json")
README = os.path.join(ROOT, "README.md")
README_START, README_END = "<!-- works:start -->", "<!-- works:end -->"
FORM_TITLES = [
    ("web", "🌐 网页 Web"),
    ("terminal", "🖥️ 终端 / ASCII Terminal"),
    ("video", "🎬 代码渲染视频 PV Video"),
    ("code", "☕ 代码实现 Code"),
]

QUERIES = [
    "world.execute in:name",
    "world-execute in:name",
    "world_execute in:name",
    "worldexecute in:name",
    "goddrinksjava in:name",
    "\"world.execute(me)\" in:description",
    "\"world.execute(me)\" in:readme",
    "\"world.execute (me)\" in:readme",
    "world execute me mili",
]

RELEVANT = re.compile(r"world[\s._\-]*execute|goddrinksjava|god\s*drinks\s*java", re.I)
SONG_IN_README = re.compile(r"world[\s._\-]*execute\s*\(?\s*me|goddrinksjava", re.I)

TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def request(url, accept="application/vnd.github+json"):
    headers = {"User-Agent": "awesome-world-execute-me", "Accept": accept}
    if TOKEN and "api.github.com" in url:
        headers["Authorization"] = "Bearer " + TOKEN
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code in (403, 429) and attempt < 3:
                reset = e.headers.get("x-ratelimit-reset")
                wait = max(5, int(reset) - int(time.time()) + 1) if reset else 20
                print("rate limited, sleeping %ss" % min(wait, 90), file=sys.stderr)
                time.sleep(min(wait, 90))
                continue
            raise
        except urllib.error.URLError:
            if attempt < 3:
                time.sleep(3)
                continue
            raise
    return None


def api(path, **params):
    url = "https://api.github.com" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    body = request(url)
    return json.loads(body) if body else None


def search(query):
    items, page = [], 1
    while page <= 3:
        res = api("/search/repositories", q=query, sort="stars", per_page=100, page=page)
        if not res:
            break
        items += res["items"]
        if len(res["items"]) < 100:
            break
        page += 1
        time.sleep(2)
    return items


def readme(full_name):
    res = api("/repos/%s/readme" % full_name)
    if not res or res.get("encoding") != "base64":
        return "", None
    text = base64.b64decode(res["content"]).decode("utf-8", "replace")
    return text, res.get("path")


# --- heuristics -------------------------------------------------------------

def _num(s):
    return s.replace("-", ".").replace("_", ".").rstrip(".") if s else ""


def _cap(s):
    return " " + s.capitalize() if s else ""


# (?<![a-z0-9]) instead of \b: CJK characters count as \w, so "基于Qwen" has no \b.
_B = r"(?<![a-z0-9])"
_V = r"(\d+(?:[.\-_]\d+)?)"
_S = r"[\s\-_]*"

MODEL_PATTERNS = [
    ("claude", re.compile(_B + r"(?:claude" + _S + r")?(opus|sonnet|haiku)" + _S + _V, re.I),
     lambda m: "Claude %s %s" % (m.group(1).capitalize(), _num(m.group(2)))),
    ("claude", re.compile(_B + r"claude(?![\s\-_]*code)", re.I), lambda m: "Claude"),
    ("gpt", re.compile(_B + r"gpt" + _S + _V + r"(?:" + _S + r"(astra|sol|codex|mini|pro|ultra))?", re.I),
     lambda m: "GPT-" + _num(m.group(1)) + _cap(m.group(2))),
    ("gpt", re.compile(_B + r"gpt(?!" + _S + r"\d)(?![a-z])", re.I), lambda m: "GPT"),
    # "DeepSeek Harness" (chat UI) and the DeepSeek whale mascot are themes, not the model used.
    ("deepseek", re.compile(_B + r"deepseek(?![\s\-_]*(?:harness|chan|娘|whale|鲸))" + _S + r"(?:v" + _S + r")?" + _V
                            + r"?(?:" + _S + r"(flash|pro|vision))?(?:" + _S + r"v?" + _V + r")?", re.I),
     lambda m: "DeepSeek" + (" V" + _num(m.group(1) or m.group(3)) if (m.group(1) or m.group(3)) else "") + _cap(m.group(2))),
    ("gemini", re.compile(_B + r"gemini" + _S + _V + r"?(?:" + _S + r"(pro|flash|ultra))?", re.I),
     lambda m: "Gemini" + (" " + _num(m.group(1)) if m.group(1) else "") + _cap(m.group(2))),
    ("kimi", re.compile(_B + r"kimi" + _S + r"(?:k" + _V + r")?", re.I),
     lambda m: "Kimi" + (" K" + _num(m.group(1)) if m.group(1) else "")),
    ("qwen", re.compile(_B + r"qwen" + _S + _V + r"?(?:" + _S + r"(flash|max|plus|coder|turbo))?", re.I),
     lambda m: "Qwen" + (_num(m.group(1)) if m.group(1) else "") + ("-" + m.group(2).capitalize() if m.group(2) else "")),
    ("glm", re.compile(_B + r"glm" + _S + _V + r"?", re.I), lambda m: "GLM" + ("-" + _num(m.group(1)) if m.group(1) else "")),
    ("grok", re.compile(_B + r"grok" + _S + _V + r"?", re.I), lambda m: "Grok" + (" " + _num(m.group(1)) if m.group(1) else "")),
    ("minimax", re.compile(_B + r"minimax" + _S + r"(m\d+(?:\.\d+)?|h\d+)?", re.I),
     lambda m: "MiniMax" + (" " + m.group(1).upper() if m.group(1) else "")),
    ("mimo", re.compile(r"(?:(?<![a-z0-9])|(?<=by))mimo(?![a-z])", re.I), lambda m: "Xiaomi MiMo"),
    ("doubao", re.compile(r"doubao|豆包", re.I), lambda m: "豆包"),
    ("codex", re.compile(_B + r"codex(?![a-z])", re.I), lambda m: "Codex"),
]

AI_HINT = re.compile(_B + r"ai(?![a-z])|人工智能|claude[\s\-_]*code|cursor|vibe[\s\-]*cod|提示词|一句话生成|\bllm|大模型", re.I)
# README lines that state who/what built the work (vs. credits, inspiration or the work's theme).
MADE_BY = re.compile(r"由.{0,12}(?:制作|生成|完成|编写|写)|(?:制作|生成|编写)[:：]|模型\**\s*[:：]|model\**\s*[:：]|写代码|辅助(?:编写|编程|下编写)"
                     r"|made (?:with|by)|built (?:with|by)|generated (?:with|by)|written (?:with|by)|powered by", re.I)

FAMILIES = [
    ("Claude", re.compile(r"^claude", re.I)),
    ("GPT / Codex", re.compile(r"^(gpt|codex)", re.I)),
    ("DeepSeek", re.compile(r"^deepseek", re.I)),
    ("Gemini", re.compile(r"^gemini", re.I)),
    ("Qwen", re.compile(r"^qwen", re.I)),
    ("GLM", re.compile(r"^glm", re.I)),
    ("Kimi", re.compile(r"^kimi", re.I)),
    ("Grok", re.compile(r"^grok", re.I)),
    ("MiniMax", re.compile(r"^minimax", re.I)),
    ("MiMo", re.compile(r"mimo", re.I)),
    ("豆包", re.compile(r"豆包|doubao", re.I)),
]


def families(models):
    out = []
    for label in models:
        fam = next((name for name, pat in FAMILIES if pat.search(label)), label)
        if fam not in out:
            out.append(fam)
    return out


BV = re.compile(r"\b(BV1[0-9A-Za-z]{9})\b")
YOUTUBE = re.compile(r"(?:youtube\.com/watch\?v=|youtu\.be/)([\w\-]{11})")
MD_IMG = re.compile(r"!\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
HTML_IMG = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"']", re.I)
BADGE = re.compile(r"shields\.io|badge|visitor|komarev|hits\.|count|star-history|contrib\.rocks|\.svg(\?|$)", re.I)

WEB_LANGS = {"HTML", "JavaScript", "TypeScript", "CSS", "Vue", "Svelte"}
TERMINAL = re.compile(r"ascii|terminal|console|tui|cli\b|终端|控制台|命令行|字符画", re.I)
VIDEO = re.compile(r"ffmpeg|\.mp4|渲染|render(?:ed|ing)?\b.*(?:video|frame)|逐帧|成片|\bPV\b", re.I)
WEB_WORDS = re.compile(r"网页|html|canvas|webgl|browser|浏览器|github\.io", re.I)


def detect_models(text):
    """Model labels mentioned in text; a versioned label suppresses the bare family name."""
    hits = []  # (position, family, label)
    for family, pat, fmt in MODEL_PATTERNS:
        for m in pat.finditer(text or ""):
            hits.append((m.start(), family, fmt(m).strip()))
    hits.sort()
    versioned = {f for _, f, label in hits if any(c.isdigit() for c in label)}
    found = []
    for _, family, label in hits:
        if family in versioned and not any(c.isdigit() for c in label):
            continue
        if label not in found:
            found.append(label)
    return found


def first_image(text, full_name, branch, readme_path):
    base_dir = os.path.dirname(readme_path or "")
    for pat in (MD_IMG, HTML_IMG):
        for m in pat.finditer(text):
            src = m.group(1).strip()
            if BADGE.search(src):
                continue
            if src.startswith("//"):
                return "https:" + src
            if src.startswith("http"):
                return src.replace("github.com/%s/blob/" % full_name, "raw.githubusercontent.com/%s/" % full_name)
            path = os.path.normpath(os.path.join(base_dir, src.lstrip("./"))) if not src.startswith("/") else src.lstrip("/")
            return "https://raw.githubusercontent.com/%s/%s/%s" % (full_name, branch, urllib.parse.quote(path))
    return None


def pages_url(repo):
    owner = repo["owner"]["login"].lower()
    name = repo["name"]
    if name.lower() == owner + ".github.io":
        return "https://%s.github.io/" % owner
    return "https://%s.github.io/%s/" % (owner, name)


def classify(repo, demo, text, bvids):
    blob = " ".join([repo["name"], repo.get("description") or "", text[:4000]])
    if demo or (repo.get("language") in WEB_LANGS and WEB_WORDS.search(blob)):
        if TERMINAL.search(repo["name"] + " " + (repo.get("description") or "")) and not demo:
            return "terminal"
        return "web"
    if TERMINAL.search(blob):
        return "terminal"
    if bvids and VIDEO.search(blob):
        return "video"
    if repo.get("language") in WEB_LANGS:
        return "web"
    return "code"


def build(repo, overrides):
    full = repo["full_name"]
    text, readme_path = readme(full)
    ov = overrides.get("works", {}).get(full, {})

    desc = repo.get("description") or ""
    if not (RELEVANT.search(repo["name"] + " " + desc) or SONG_IN_README.search(text)):
        return None

    homepage = (repo.get("homepage") or "").strip()
    demo = None
    if repo.get("has_pages"):
        demo = pages_url(repo)
    elif homepage and re.search(r"github\.io|vercel\.app|netlify\.app|pages\.dev", homepage):
        demo = homepage

    bvids = []
    for m in BV.finditer(" ".join([homepage, desc, text])):
        if m.group(1) not in bvids:
            bvids.append(m.group(1))

    head = repo["name"] + " " + desc
    made_by = "\n".join(line for line in text.splitlines() if MADE_BY.search(line))
    models = detect_models(head) or detect_models(made_by)
    created = repo["created_at"][:10]
    if models or AI_HINT.search(head) or AI_HINT.search(made_by):
        maker = "ai"
    elif created < "2023-01-01":
        maker = "human"
    else:
        maker = "unknown"

    work = {
        "repo": full,
        "name": repo["name"],
        "owner": repo["owner"]["login"],
        "avatar": repo["owner"]["avatar_url"],
        "url": repo["html_url"],
        "description": desc,
        "stars": repo["stargazers_count"],
        "forks": repo["forks_count"],
        "language": repo.get("language"),
        "license": (repo.get("license") or {}).get("spdx_id"),
        "created": created,
        "pushed": repo["pushed_at"][:10],
        "demo": demo,
        "homepage": homepage or None,
        "bilibili": bvids[:3],
        "youtube": list(dict.fromkeys(YOUTUBE.findall(" ".join([homepage, text]))))[:2],
        "models": models[:4],
        "maker": maker,
        "form": classify(repo, demo, text, bvids),
        "preview": first_image(text, full, repo["default_branch"], readme_path),
        "og": "https://opengraph.githubassets.com/1/" + full,
    }
    work.update(ov)
    work["families"] = families(work["models"])
    return work


def main():
    overrides = {"exclude": [], "include": [], "works": {}}
    if os.path.exists(OVERRIDES):
        with open(OVERRIDES, encoding="utf-8") as f:
            overrides.update(json.load(f))
    exclude = {x.lower() for x in overrides["exclude"]}

    repos = {}
    for q in QUERIES:
        for item in search(q):
            repos[item["full_name"]] = item
        time.sleep(2)
    for full in overrides["include"]:
        if full not in repos:
            item = api("/repos/" + full)
            if item:
                repos[full] = item
    print("candidates: %d" % len(repos), file=sys.stderr)

    works = []
    for full, repo in sorted(repos.items()):
        if full.lower() in exclude or repo.get("fork") or repo.get("archived") and repo["stargazers_count"] == 0:
            continue
        w = build(repo, overrides)
        if w:
            works.append(w)
    works.sort(key=lambda w: (-w["stars"], w["created"]))
    write_readme(works)

    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            if json.load(f).get("works") == works:
                print("works: %d, unchanged" % len(works), file=sys.stderr)
                return
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({
            "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "count": len(works),
            "works": works,
        }, f, ensure_ascii=False, indent=1)
    print("works: %d -> %s" % (len(works), os.path.relpath(OUT, ROOT)), file=sys.stderr)


def readme_text(value, capitalize=False):
    """Keep untrusted GitHub text on one line, with literal Markdown characters."""
    text = re.sub(r"\s+", " ", value or "").strip()
    # GitHub descriptions may contain unfinished quotes or CJK brackets.
    pairs = dict(zip("“‘『（《「【", "”’』）》」】"))
    closing = {right: left for left, right in pairs.items()}
    stack, unmatched = [], set()
    for index, char in enumerate(text):
        if char == "’" and index and text[index - 1].isalnum():
            continue  # Apostrophe, not a closing quotation mark.
        if char == '"':
            if stack and stack[-1][0] == char:
                stack.pop()
            else:
                stack.append((char, index))
        elif char in pairs:
            stack.append((char, index))
        elif char in closing:
            match = next((i for i in range(len(stack) - 1, -1, -1)
                          if stack[i][0] == closing[char]), None)
            if match is None:
                unmatched.add(index)
            else:
                stack.pop(match)
    unmatched.update(index for _, index in stack)
    text = "".join(char for index, char in enumerate(text) if index not in unmatched)
    text = re.sub(r"([！!~～,，·?？])\1+", r"\1", text).strip()
    # Capitalize only an initial Latin letter; Chinese descriptions need no casing.
    if capitalize:
        text = re.sub(r"^([^A-Za-z\u3400-\u9fff]*)([a-z])",
                      lambda match: match[1] + match[2].upper(), text)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"([\\`*_\[\]|])", r"\\\1", text)


def readme_url(url):
    """Quote delimiters that would otherwise end a Markdown link destination."""
    return urllib.parse.quote(url, safe=":/?#@!$&'*+,;=%~-._")


def write_readme(works):
    """Regenerate the list between the README markers (README stays hand-written elsewhere)."""
    if not os.path.exists(README):
        return
    with open(README, encoding="utf-8") as f:
        text = f.read()
    if README_START not in text or README_END not in text:
        return
    out = []
    for form, _ in FORM_TITLES:
        group = [w for w in works if w["form"] == form]
        # Stable headings keep the hand-written Contents links valid after updates.
        heading = {"web": "网页 Web", "terminal": "终端 ASCII Terminal",
                   "video": "代码渲染视频 PV Video", "code": "代码实现 Code"}[form]
        out += ["", "### %s" % heading, ""]
        for w in sorted(group, key=lambda work: -work["stars"]):
            desc = readme_text(w.get("description"), capitalize=True)
            if not desc:
                desc = "%s形式的二创作品" % heading.split(" ")[0]
            if desc.lower().startswith(w["repo"].lower()):
                desc = "作品简介：" + desc
            desc = desc.rstrip(".。") + "."
            details = ["★ %d" % w["stars"]]
            model = ", ".join(w["models"])
            if model:
                details.append("AI 模型：" + readme_text(model))
            elif w["maker"] == "ai":
                details.append("AI 模型：未注明")
            elif w["maker"] == "human":
                details.append("制作：手写")
            if w.get("demo"):
                details.append("[在线 demo](%s)" % readme_url(w["demo"]))
            details += ["[B站](https://www.bilibili.com/video/%s)" % readme_url(bv)
                        for bv in w.get("bilibili", [])[:1]]
            details += ["[YouTube](https://www.youtube.com/watch?v=%s)" % readme_url(video)
                        for video in w.get("youtube", [])[:1]]
            out.append("- [%s](%s) - %s %s." %
                       (readme_text(w["repo"]), readme_url(w["url"]), desc, "；".join(details)))
    head, rest = text.split(README_START, 1)
    tail = rest.split(README_END, 1)[1]
    new = head + README_START + "\n" + "\n".join(out).strip("\n") + "\n" + README_END + tail
    if new != text:
        with open(README, "w", encoding="utf-8") as f:
            f.write(new)


if __name__ == "__main__":
    main()
