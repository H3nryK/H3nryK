#!/usr/bin/env python3
"""Generate assets/stats.svg for the profile README.

Uses only the standard library. Set GITHUB_TOKEN (the Actions default token is
enough) to raise API limits and to include the contribution count; without it
the script still works, but shows "n/a" for contributions.
"""

import json
import os
import sys
import urllib.request
from collections import Counter
from html import escape

USER = os.environ.get("GH_USER", "H3nryK")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = os.environ.get("OUT", "assets/stats.svg")

# Tokyo Night palette
BG, BORDER = "#1a1b27", "#2f334d"
TEXT, MUTED = "#c0caf5", "#7982a9"
ACCENT = "#6AD3F7"
LANG_COLORS = {
    "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#3178c6",
    "Rust": "#dea584", "Java": "#b07219", "C++": "#f34b7d", "HTML": "#e34c26",
    "CSS": "#9d7cd8", "Motoko": "#bb9af7", "Shell": "#89e051", "Dart": "#00B4AB",
}
FALLBACK = ["#7aa2f7", "#bb9af7", "#9ece6a", "#e0af68", "#f7768e", "#73daca"]


def request(url, body=None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-stats"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def fetch():
    user = request(f"https://api.github.com/users/{USER}")
    repos, page = [], 1
    while True:
        chunk = request(
            f"https://api.github.com/users/{USER}/repos?per_page=100&page={page}&type=owner"
        )
        repos += chunk
        if len(chunk) < 100:
            break
        page += 1
    repos = [r for r in repos if not r["fork"]]

    langs = Counter()
    for r in repos:
        try:
            langs.update(request(r["languages_url"]))
        except Exception as exc:  # keep going if one repo fails
            print(f"warn: languages for {r['name']}: {exc}", file=sys.stderr)

    contributions = None
    if TOKEN:
        query = (
            "query($login:String!){user(login:$login){contributionsCollection"
            "{contributionCalendar{totalContributions}}}}"
        )
        try:
            res = request(
                "https://api.github.com/graphql",
                {"query": query, "variables": {"login": USER}},
            )
            contributions = res["data"]["user"]["contributionsCollection"][
                "contributionCalendar"
            ]["totalContributions"]
        except Exception as exc:
            print(f"warn: contributions: {exc}", file=sys.stderr)

    return {
        "repos": len(repos),
        "stars": sum(r["stargazers_count"] for r in repos),
        "followers": user["followers"],
        "contributions": contributions,
        "langs": langs,
    }


def render(stats):
    w, h = 495, 235
    tiles = [
        ("REPOS", str(stats["repos"])),
        ("STARS", str(stats["stars"])),
        ("FOLLOWERS", str(stats["followers"])),
        (
            "CONTRIBS / YR",
            "n/a" if stats["contributions"] is None else f"{stats['contributions']:,}",
        ),
    ]
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="GitHub stats for {escape(USER)}">',
        "<style>"
        f"text{{font-family:'Fira Code','SFMono-Regular',Consolas,monospace}}"
        f".t{{fill:{ACCENT};font-size:13px;font-weight:600}}"
        f".v{{fill:{TEXT};font-size:22px;font-weight:700}}"
        f".l{{fill:{MUTED};font-size:9px;letter-spacing:1px}}"
        f".g{{fill:{TEXT};font-size:11px}}"
        f".p{{fill:{MUTED};font-size:11px}}"
        "</style>",
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="12" fill="{BG}" stroke="{BORDER}"/>',
        '<circle cx="20" cy="20" r="5" fill="#f7768e"/><circle cx="38" cy="20" r="5" fill="#e0af68"/><circle cx="56" cy="20" r="5" fill="#9ece6a"/>',
        f'<text x="76" y="24" class="t">~/{escape(USER.lower())} $ stats</text>',
    ]

    tile_w = (w - 40 - 3 * 10) / 4
    for i, (label, value) in enumerate(tiles):
        x = 20 + i * (tile_w + 10)
        out += [
            f'<rect x="{x:.1f}" y="44" width="{tile_w:.1f}" height="62" rx="8" fill="#222436" stroke="{BORDER}"/>',
            f'<text x="{x + tile_w / 2:.1f}" y="76" text-anchor="middle" class="v">{escape(value)}</text>',
            f'<text x="{x + tile_w / 2:.1f}" y="95" text-anchor="middle" class="l">{label}</text>',
        ]

    out.append(f'<text x="20" y="130" class="p"># most used languages</text>')
    total = sum(stats["langs"].values()) or 1
    top = stats["langs"].most_common(6)
    bar_x, bar_w = 20, w - 40
    out.append(f'<clipPath id="bar"><rect x="{bar_x}" y="140" width="{bar_w}" height="10" rx="5"/></clipPath>')
    out.append('<g clip-path="url(#bar)">')
    x, fb = float(bar_x), 0
    colors = {}
    for name, size in top:
        color = LANG_COLORS.get(name) or FALLBACK[fb % len(FALLBACK)]
        if name not in LANG_COLORS:
            fb += 1
        colors[name] = color
        seg = bar_w * size / total
        out.append(f'<rect x="{x:.1f}" y="140" width="{seg:.1f}" height="10" fill="{color}"/>')
        x += seg
    other = bar_x + bar_w - x
    if other > 0.5:
        out.append(f'<rect x="{x:.1f}" y="140" width="{other:.1f}" height="10" fill="{BORDER}"/>')
    out.append("</g>")

    for i, (name, size) in enumerate(top):
        col, row = i % 2, i // 2
        lx, ly = 20 + col * 235, 175 + row * 18
        pct = 100 * size / total
        out += [
            f'<circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="{colors[name]}"/>',
            f'<text x="{lx + 16}" y="{ly}" class="g">{escape(name)} <tspan class="p">{pct:.1f}%</tspan></text>',
        ]
    out.append("</svg>")
    return "\n".join(out)


if __name__ == "__main__":
    svg = render(fetch())
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"wrote {OUT}")
