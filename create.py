#!/usr/bin/env python3
"""

Usage
  # inspect the prompt without spending anything
  python3 create_site.py --manifests manifests.jsonl --manifest-id m0000001 \
      --domain brightharbour-accounting.co.uk --theme "independent accountancy practice" --dry-run

  # build one site
  python3 create_site.py --manifests manifests.jsonl --manifest-id m0000001 \
      --domain brightharbour-accounting.co.uk --theme "independent accountancy practice"

  # build many: jobs.csv with columns domain,theme[,manifest_id]; manifests assigned in order if omitted
  python3 create_site.py --manifests manifests.jsonl --jobs jobs.csv --workers 4

Requires: pip install anthropic  (credentials from ANTHROPIC_API_KEY or `ant auth login`)
"""
import argparse
import concurrent.futures
import csv
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import manifest_gen  # noqa: E402  (same directory)

DEFAULT_MODEL = "claude-opus-5"
# $ per 1M tokens: (input, output, cache write, cache read). Used only for the cost estimate in _meta.json.
PRICING = {
    "claude-opus-5": (5.00, 25.00, 6.25, 0.50),
    "claude-sonnet-5": (2.00, 10.00, 2.50, 0.20),
    "claude-haiku-4-5": (1.00, 5.00, 1.25, 0.10),
    "claude-fable-5-1": (10.00, 50.00, 12.50, 0.25),
}

FILE_RE = re.compile(r"^===== FILE: (?P<path>[^\n]+?) =====\n(?P<body>.*?)\n===== END FILE =====", re.S | re.M)

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------
SYSTEM_RULES = """You are a senior brand designer and front-end engineer. You build complete, polished, static marketing websites from a JSON design manifest. Each manifest describes one site's visual system and structure; you supply the craft and the copy.

# Output protocol
Return ONLY files, nothing else - no introduction, no summary, no markdown fences around files.
Each file is wrapped exactly like this:

===== FILE: index.html =====
<file contents>
===== END FILE =====

Order: HTML pages first, then the CSS file, then the JS file (only if the manifest calls for external files). Paths are relative to the site root and must match the manifest (`delivery.css_file`, `delivery.js_file`, one `<slug>.html` per page, `index` -> `index.html`). Every file must be complete. Never write "rest unchanged", "..." or a placeholder comment in place of real code.

# Hard constraints
- No external resources of any kind: no CDN scripts, no external stylesheets, no web fonts, no `@import`, no `<img>`, `<picture>`, `<video>`, no `url()` pointing at files. Visuals are CSS gradients, inline SVG, CSS patterns and tinted panels. Only relative links between the site's own pages, in-page anchors, `mailto:` and `tel:`.
- Use the manifest's font stacks verbatim for `font-family`. Use the palette hex values exactly. If `use_css_custom_properties` is true, expose them as custom properties on `:root` and reference those.
- Respect `delivery`: `inline` puts a `<style>` block in the head of every page; `external` links the named file; `split` inlines reset + layout + hero CSS and puts the rest in the file. Same for JS. When `nav_toggle` is `css_checkbox` the mobile menu must work with no JavaScript.
- Semantic HTML5 (`header`, `nav`, `main`, `section`, `footer`), one `h1` per page, a skip link, visible focus styles using `components.focus_ring`, 44px minimum touch targets, `prefers-reduced-motion` disables animation. `lang` attribute set from the locale hint. `<title>` and meta description unique per page. Viewport meta present.
- Responsive at the manifest breakpoints. No horizontal overflow at 360px wide. Mobile navigation must actually open and close.
- Class names follow `delivery.css_naming`; prefix every class with `delivery.class_prefix` when it is non-empty. Add HTML comments only if `html_comments` is `sparse`, and then only a few.

# Interpreting the manifest
The glossary below defines every id used in a manifest. Read `archetype` and `archetype_description` first and let them set the overall attitude, then build each part:
- `layout.pages[*].sections` is the exact section order. `hero` is always the first section of index; `page_header` is a compact title band on inner pages.
- `typography`: derive the type scale from `base_size_px` and `scale_ratio`; `h1_max_px` caps the h1; use `clamp()` when `fluid_type` is true; apply `heading_case` and `eyebrow_style`.
- `layout` numbers (`container_max_px`, `section_padding_y_px`, `grid_gap_px`, `container_pad_px`) are the spacing rhythm. Use them consistently; do not invent a second rhythm.
- `components`: `radius_px` tokens, `shadow_css` (use it verbatim where the card style needs a shadow), `card`, `button_*`, `section_pattern`, `icon_style`. If `hero_shape_accent` is true add one decorative shape behind or beside the hero.
- `palette.mode` `light_dark_sections` means alternate a few sections onto `palette.dark_band` colours (typically stats, testimonials or the cta band). `dark` means the whole site is dark.
- `motion.features` lists the only behaviours to implement, with `transition_ms` and `easing`. Keep it restrained.

# Content
- Derive a natural brand name from the domain (e.g. `brightharbour-accounting.co.uk` -> "Bright Harbour Accounting"). The site is for the theme given, written in `copy_style` tone. Real, specific copy: concrete services, plausible process steps, believable numbers, names for testimonials and team members. No lorem ipsum, no "[Company]", no "Insert text here".
- The business is fictional. Do not name real companies, real people, or make verifiable regulatory or award claims. Use the locale hint for spelling, currency, address and phone formats.
- Match the theme's audience: a law firm and a skate shop should not read alike even with similar manifests.

# What "professional" means here
Consistent vertical rhythm, a clear hierarchy, comfortable measure (`measure_ch`), aligned grids, deliberate whitespace, hover and focus states on every interactive element, a footer that looks finished, and a hero that carries the brand without an image. Prefer fewer, better-made sections over decoration. If a manifest value would look bad in a specific spot, apply it in the most tasteful way that still honours it - do not silently drop it.
"""


def build_system_prompt():
    return SYSTEM_RULES + "\n\n" + manifest_gen.glossary_markdown()


LOCALES = [
    ((".co.uk", ".uk", ".org.uk", ".me.uk", ".ltd.uk"), "en-GB", "UK: British spelling, GBP (£), UK postcodes, +44 phone numbers"),
    ((".ie",), "en-IE", "Ireland: British spelling, EUR (€), Eircodes, +353 phone numbers"),
    ((".com.au", ".au", ".net.au"), "en-AU", "Australia: British spelling, AUD ($), state + postcode addresses, +61 phone numbers"),
    ((".co.nz", ".nz"), "en-NZ", "New Zealand: British spelling, NZD ($), +64 phone numbers"),
    ((".ca",), "en-CA", "Canada: Canadian spelling, CAD ($), postal codes like M5V 2T6, +1 phone numbers"),
    ((".de",), "de-DE", "Germany: German language, EUR (€), German addresses and +49 phone numbers"),
    ((".fr",), "fr-FR", "France: French language, EUR (€), French addresses and +33 phone numbers"),
    ((".es",), "es-ES", "Spain: Spanish language, EUR (€), +34 phone numbers"),
    ((".nl",), "nl-NL", "Netherlands: Dutch language, EUR (€), +31 phone numbers"),
]


def locale_hint(domain):
    d = domain.lower()
    for suffixes, lang, hint in LOCALES:
        if any(d.endswith(s) for s in suffixes):
            return lang, hint
    return "en-US", "United States: US spelling, USD ($), US addresses and +1 phone numbers"


def build_user_message(manifest, domain, theme, notes=None):
    lang, hint = locale_hint(domain)
    m = dict(manifest)
    # the glossary in the system prompt already explains these; keep the per-site message lean
    m.pop("archetype_description", None)
    for k in ("heading_stack", "body_stack"):
        m.get("typography", {}).pop(k, None)
    parts = [
        "domain: %s" % domain,
        "theme: %s" % theme,
        "locale: %s (%s)" % (lang, hint),
    ]
    if notes:
        parts.append("notes: %s" % notes)
    files = expected_files(manifest)
    parts.append("files to return, in this order: %s" % ", ".join(files))
    parts.append("manifest:\n" + json.dumps(m, separators=(",", ":"), sort_keys=True))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Parsing, validation, writing
# ---------------------------------------------------------------------------
def expected_files(manifest):
    files = []
    for page in manifest["layout"]["pages"]:
        files.append("index.html" if page["slug"] == "index" else page["slug"] + ".html")
    d = manifest["delivery"]
    if d.get("css_file"):
        files.append(d["css_file"])
    if d.get("js_file"):
        files.append(d["js_file"])
    return files


def parse_files(text):
    out = {}
    for m in FILE_RE.finditer(text):
        path = m.group("path").strip().strip("`")
        body = m.group("body")
        # tolerate a model that fenced the file body anyway
        fence = re.match(r"^```[a-zA-Z0-9_-]*\n(.*)\n```\s*$", body, re.S)
        if fence:
            body = fence.group(1)
        out[path] = body.rstrip() + "\n"
    return out


def safe_relpath(path):
    p = Path(path)
    return not p.is_absolute() and ".." not in p.parts and not str(path).startswith(("/", "\\"))


EXTERNAL_RE = re.compile(r"""(?:src|href)\s*=\s*["']\s*(?:https?:)?//""", re.I)
CSS_EXTERNAL_RE = re.compile(r"""@import|url\(\s*["']?\s*(?:https?:)?//""", re.I)
IMG_RE = re.compile(r"<(?:img|picture|video|iframe|object|embed)\b", re.I)
LINK_RE = re.compile(r"""href\s*=\s*["']([^"'#?]+?\.html)(?:[#?][^"']*)?["']""", re.I)


def validate(files, manifest):
    issues = []
    expected = expected_files(manifest)
    for f in expected:
        if f not in files:
            issues.append("missing file: %s" % f)
    for path in files:
        if not safe_relpath(path):
            issues.append("unsafe path: %s" % path)
    html_files = {p: b for p, b in files.items() if p.endswith(".html")}
    for path, body in html_files.items():
        low = body.lower()
        if "<!doctype html" not in low:
            issues.append("%s: missing <!doctype html>" % path)
        if "<title" not in low:
            issues.append("%s: missing <title>" % path)
        if 'name="viewport"' not in low and "name='viewport'" not in low:
            issues.append("%s: missing viewport meta" % path)
        if EXTERNAL_RE.search(body):
            issues.append("%s: references an external URL (src/href to http(s)://)" % path)
        if IMG_RE.search(body):
            issues.append("%s: contains an <img>/<picture>/<video>/<iframe> element; the manifest forbids images" % path)
        if CSS_EXTERNAL_RE.search(body):
            issues.append("%s: inline CSS uses @import or an external url()" % path)
        if re.search(r"lorem ipsum|\[company\]|\[insert|placeholder text", low):
            issues.append("%s: placeholder copy present" % path)
        for target in LINK_RE.findall(body):
            t = target.split("/")[-1] if target.startswith("./") else target
            if t not in files and t.lstrip("./") not in files:
                issues.append("%s: links to %s which was not returned" % (path, target))
        d = manifest["delivery"]
        if d.get("css_file") and os.path.basename(d["css_file"]) not in body:
            issues.append("%s: does not link the stylesheet %s" % (path, d["css_file"]))
        if d.get("js_file") and os.path.basename(d["js_file"]) not in body:
            issues.append("%s: does not load the script %s" % (path, d["js_file"]))
        if d.get("css_delivery") == "inline" and "<style" not in low:
            issues.append("%s: css_delivery is inline but there is no <style> block" % path)
    for path, body in files.items():
        if path.endswith(".css"):
            if CSS_EXTERNAL_RE.search(body):
                issues.append("%s: uses @import or an external url()" % path)
            if len(body.strip()) < 500:
                issues.append("%s: stylesheet is suspiciously short (%d bytes)" % (path, len(body)))
        if path.endswith(".js") and re.search(r"https?://", body):
            issues.append("%s: contains an http(s):// URL" % path)
    return issues


def write_site(files, site_dir):
    site_dir = Path(site_dir)
    site_dir.mkdir(parents=True, exist_ok=True)
    for path, body in files.items():
        if not safe_relpath(path):
            continue
        target = site_dir / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
def make_client():
    try:
        import anthropic
    except ImportError:
        sys.exit("The anthropic package is not installed. Run: pip install anthropic")
    return anthropic, anthropic.Anthropic()


def call_model(anthropic, client, system, messages, model, max_tokens, effort, use_fallbacks):
    """Streamed request (long output). Returns the final Message."""
    kwargs = dict(
        model=model,
        max_tokens=max_tokens,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=messages,
        output_config={"effort": effort},
    )
    if use_fallbacks:
        # server-side refusal fallback: if a safety classifier declines, the API re-runs on a fallback model in the same call
        try:
            with client.beta.messages.stream(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs) as stream:
                return stream.get_final_message()
        except (TypeError, anthropic.BadRequestError) as e:
            print("  note: fallbacks unavailable (%s); retrying without" % e.__class__.__name__, file=sys.stderr)
    with client.messages.stream(**kwargs) as stream:
        return stream.get_final_message()


def message_text(msg):
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def usage_dict(msg):
    u = msg.usage
    return {
        "input_tokens": getattr(u, "input_tokens", 0) or 0,
        "output_tokens": getattr(u, "output_tokens", 0) or 0,
        "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
        "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
    }


def add_usage(a, b):
    return {k: a.get(k, 0) + b.get(k, 0) for k in set(a) | set(b)}


def estimate_cost(model, usage):
    if model not in PRICING:
        return None
    i, o, cw, cr = PRICING[model]
    return round((usage["input_tokens"] * i + usage["output_tokens"] * o
                  + usage["cache_creation_input_tokens"] * cw + usage["cache_read_input_tokens"] * cr) / 1e6, 4)


# ---------------------------------------------------------------------------
# One site end to end
# ---------------------------------------------------------------------------
def build_site(job, manifest, args, system, api=None):
    domain, theme, notes = job["domain"], job["theme"], job.get("notes")
    site_dir = Path(args.out_dir) / domain
    t0 = time.time()
    user_msg = build_user_message(manifest, domain, theme, notes)

    if args.dry_run:
        print("=" * 30, "SYSTEM PROMPT (%d chars, cached)" % len(system), "=" * 30)
        print(system)
        print("=" * 30, "USER MESSAGE (%d chars)" % len(user_msg), "=" * 30)
        print(user_msg)
        return {"domain": domain, "dry_run": True}

    anthropic, client = api
    messages = [{"role": "user", "content": user_msg}]
    total_usage = {}
    try:
        msg = call_model(anthropic, client, system, messages, args.model, args.max_tokens, args.effort, not args.no_fallbacks)
    except anthropic.RateLimitError as e:
        return {"domain": domain, "error": "rate limited: %s" % e.message}
    except anthropic.APIStatusError as e:
        return {"domain": domain, "error": "API error %s: %s" % (e.status_code, e.message)}
    except anthropic.APIConnectionError as e:
        return {"domain": domain, "error": "connection error: %s" % e}
    total_usage = add_usage(total_usage, usage_dict(msg))

    if msg.stop_reason == "refusal":
        det = getattr(msg, "stop_details", None)
        return {"domain": domain, "error": "model refused (%s)" % (getattr(det, "category", None) or "no category")}
    text = message_text(msg)
    files = parse_files(text)
    if not files:
        (site_dir).mkdir(parents=True, exist_ok=True)
        (site_dir / "_raw_response.txt").write_text(text, encoding="utf-8")
        return {"domain": domain, "error": "no files parsed from response; raw saved to _raw_response.txt"}
    truncated = msg.stop_reason == "max_tokens"
    issues = validate(files, manifest)
    if truncated:
        issues.insert(0, "response was cut off at max_tokens; the last file is probably incomplete")

    repairs = 0
    while issues and repairs < args.repair_rounds:
        repairs += 1
        fix_request = (
            "Validation found these problems:\n- " + "\n- ".join(issues) +
            "\n\nReturn ONLY the files that need to change, complete, using the same FILE protocol. "
            "Keep everything else identical. Do not add any prose."
        )
        # append-only history: last model reply, then the fix request
        messages = messages + [{"role": "assistant", "content": text}, {"role": "user", "content": fix_request}]
        try:
            fix = call_model(anthropic, client, system, messages, args.model, args.max_tokens, args.effort, not args.no_fallbacks)
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as e:
            issues.append("repair call failed: %s" % e)
            break
        total_usage = add_usage(total_usage, usage_dict(fix))
        text = message_text(fix)
        fixed = parse_files(text)
        if not fixed:
            break
        files.update(fixed)
        issues = validate(files, manifest)

    write_site(files, site_dir)
    meta = {
        "domain": domain,
        "theme": theme,
        "manifest_id": manifest["id"],
        "manifest_seed": manifest.get("seed"),
        "archetype": manifest["archetype"],
        "model": args.model,
        "effort": args.effort,
        "files": sorted(files),
        "stop_reason": msg.stop_reason,
        "repair_rounds": repairs,
        "remaining_issues": issues,
        "usage": total_usage,
        "estimated_cost_usd": estimate_cost(args.model, total_usage),
        "seconds": round(time.time() - t0, 1),
    }
    (site_dir / "_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (site_dir / "_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return meta


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def load_manifests(path):
    by_id, ordered = {}, []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            m = json.loads(line)
            by_id[m["id"]] = m
            by_id[m["id"].split("-")[0]] = m  # allow the short "m0000001" form
            ordered.append(m)
    return by_id, ordered


def load_jobs(path):
    jobs = []
    with open(path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            row = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
            if not row.get("domain") or not row.get("theme"):
                continue
            jobs.append(row)
    return jobs


def main():
    ap = argparse.ArgumentParser(description="Build a website from a manifest + domain + theme via the Claude API.")
    ap.add_argument("--manifests", default="manifests.jsonl", help="JSONL from manifest_gen.py")
    ap.add_argument("--manifest-id", help="id (m0000001 or m0000001-d998fb) to use for a single site")
    ap.add_argument("--manifest-line", type=int, help="1-based line number in the JSONL to use instead of an id")
    ap.add_argument("--domain", help="domain for a single site")
    ap.add_argument("--theme", help="theme / business description for a single site")
    ap.add_argument("--notes", help="optional extra guidance for a single site")
    ap.add_argument("--jobs", help="CSV with columns domain,theme[,manifest_id,notes] for batch mode")
    ap.add_argument("--manifest-offset", type=int, default=0, help="batch mode: skip this many manifests before assigning in order")
    ap.add_argument("--out-dir", default="sites", help="sites are written to <out-dir>/<domain>/")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--max-tokens", type=int, default=64000)
    ap.add_argument("--repair-rounds", type=int, default=1, help="validation fix-up turns (0 disables)")
    ap.add_argument("--no-fallbacks", action="store_true", help="disable server-side refusal fallbacks")
    ap.add_argument("--workers", type=int, default=1, help="parallel sites in batch mode")
    ap.add_argument("--force", action="store_true", help="rebuild sites whose folder already has _meta.json")
    ap.add_argument("--dry-run", action="store_true", help="print the prompts and exit without calling the API")
    ap.add_argument("--save-prompt", action="store_true", help="also write system_prompt.txt next to the sites")
    args = ap.parse_args()

    by_id, ordered = load_manifests(args.manifests)
    system = build_system_prompt()
    if args.save_prompt:
        Path(args.out_dir).mkdir(parents=True, exist_ok=True)
        (Path(args.out_dir) / "system_prompt.txt").write_text(system, encoding="utf-8")

    # assemble (job, manifest) pairs
    pairs = []
    if args.jobs:
        jobs = load_jobs(args.jobs)
        cursor = args.manifest_offset
        for job in jobs:
            mid = job.get("manifest_id")
            if mid:
                if mid not in by_id:
                    print("skip %s: manifest %s not found" % (job["domain"], mid), file=sys.stderr)
                    continue
                m = by_id[mid]
            else:
                if cursor >= len(ordered):
                    print("skip %s: ran out of manifests" % job["domain"], file=sys.stderr)
                    continue
                m = ordered[cursor]
                cursor += 1
            pairs.append((job, m))
    else:
        if not (args.domain and args.theme):
            ap.error("--domain and --theme are required (or use --jobs)")
        if args.manifest_line:
            m = ordered[args.manifest_line - 1]
        elif args.manifest_id:
            if args.manifest_id not in by_id:
                ap.error("manifest %s not found in %s" % (args.manifest_id, args.manifests))
            m = by_id[args.manifest_id]
        else:
            m = ordered[0]
        pairs.append(({"domain": args.domain, "theme": args.theme, "notes": args.notes}, m))

    if not args.force and not args.dry_run:
        before = len(pairs)
        pairs = [(j, m) for j, m in pairs if not (Path(args.out_dir) / j["domain"] / "_meta.json").exists()]
        if len(pairs) < before:
            print("skipping %d already-built site(s); use --force to rebuild" % (before - len(pairs)), file=sys.stderr)
    if not pairs:
        print("nothing to do", file=sys.stderr)
        return

    api = None if args.dry_run else make_client()
    results = []

    def run(pair):
        job, m = pair
        print("building %s  (%s, %s)" % (job["domain"], m["id"], m["archetype"]), file=sys.stderr)
        r = build_site(job, m, args, system, api)
        if r.get("error"):
            print("  FAILED %s: %s" % (job["domain"], r["error"]), file=sys.stderr)
        elif not r.get("dry_run"):
            print("  done %s: %d files, %s issue(s), $%s, %ss" % (
                job["domain"], len(r["files"]), len(r["remaining_issues"]), r["estimated_cost_usd"], r["seconds"]), file=sys.stderr)
        return r

    if args.workers > 1 and len(pairs) > 1 and not args.dry_run:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
            results = list(ex.map(run, pairs))
    else:
        results = [run(p) for p in pairs]

    if not args.dry_run:
        ok = [r for r in results if not r.get("error")]
        cost = sum(r.get("estimated_cost_usd") or 0 for r in ok)
        summary = {"built": len(ok), "failed": len(results) - len(ok), "estimated_cost_usd": round(cost, 4),
                   "sites_with_remaining_issues": sum(1 for r in ok if r.get("remaining_issues"))}
        print(json.dumps(summary, indent=2), file=sys.stderr)
        log = Path(args.out_dir) / "build_log.jsonl"
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "a", encoding="utf-8") as fh:
            for r in results:
                fh.write(json.dumps(r) + "\n")


if __name__ == "__main__":
    main()
