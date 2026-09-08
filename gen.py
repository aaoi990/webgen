#!/usr/bin/env python3
"""
manifest_gen.py - generate website design manifests, one JSON object per line.

A manifest is the full visual/structural spec for ONE site (layout, typography,
colour palette, components, motion, asset delivery). No HTML is produced here;
you feed a manifest + domain + theme to an LLM later, and that is your only
token cost.

Design goals
  * every site looks different, but every combination is "coherent": a design
    archetype is picked first and it constrains every other choice so you never
    get a luxury serif brand with neon pill buttons and wavy dividers.
  * no images, no external fonts, no CDNs - system font stacks and CSS/SVG-only
    visuals.
  * palettes are generated in HSL and pushed until they pass WCAG AA contrast.
  * CSS/JS delivery (inline vs external files, file names, class prefixes,
    naming scheme) is randomised so sites are not copy-paste clones.
  * fully reproducible: --seed reproduces a whole run, and every manifest
    carries its own `seed` so one site can be regenerated with --from-seed.

Usage
  python3 manifest_gen.py 100
  python3 manifest_gen.py --count 100000 --out manifests.jsonl --seed 7
  python3 manifest_gen.py 3 --sample                  # pretty-print first one
  python3 manifest_gen.py --glossary glossary.md      # id glossary for your system prompt
  python3 manifest_gen.py --from-seed 123456789       # regenerate one manifest

Stdlib only. Python 3.8+.
"""
import argparse
import colorsys
import hashlib
import json
import random
import sys
import time

MANIFEST_VERSION = "1.0"

# ---------------------------------------------------------------------------
# Typography: system font stacks only (nothing fetched from the network)
# ---------------------------------------------------------------------------
FONT_STACKS = {
    "humanist_sans": 'system-ui, -apple-system, "Segoe UI", Roboto, Ubuntu, Cantarell, "Noto Sans", sans-serif',
    "grotesk_sans": '"Helvetica Neue", Helvetica, Arial, "Liberation Sans", "Nimbus Sans", sans-serif',
    "geometric_sans": '"Trebuchet MS", "Segoe UI", Ubuntu, "DejaVu Sans", Verdana, sans-serif',
    "rounded_sans": 'ui-rounded, "Segoe UI", "Trebuchet MS", Ubuntu, "DejaVu Sans", sans-serif',
    "condensed_sans": '"Arial Narrow", "Roboto Condensed", "Liberation Sans Narrow", "Helvetica Neue", sans-serif',
    "transitional_serif": 'Georgia, "Times New Roman", "Liberation Serif", "DejaVu Serif", serif',
    "old_style_serif": 'Garamond, "EB Garamond", "Palatino Linotype", Palatino, "URW Palladio L", "Book Antiqua", serif',
    "modern_serif": '"Palatino Linotype", Palatino, "Book Antiqua", "URW Palladio L", Georgia, serif',
    "didone_serif": '"Bodoni MT", Didot, "Hoefler Text", "Baskerville Old Face", Baskerville, Georgia, serif',
    "mono": 'ui-monospace, "SF Mono", Menlo, Consolas, "DejaVu Sans Mono", "Liberation Mono", monospace',
}

# heading / body pairings that are known to sit well together
PAIRINGS = {
    "grotesk_grotesk": ("grotesk_sans", "grotesk_sans"),
    "humanist_humanist": ("humanist_sans", "humanist_sans"),
    "geometric_humanist": ("geometric_sans", "humanist_sans"),
    "condensed_humanist": ("condensed_sans", "humanist_sans"),
    "condensed_grotesk": ("condensed_sans", "grotesk_sans"),
    "rounded_rounded": ("rounded_sans", "rounded_sans"),
    "rounded_humanist": ("rounded_sans", "humanist_sans"),
    "serif_humanist": ("transitional_serif", "humanist_sans"),
    "serif_grotesk": ("transitional_serif", "grotesk_sans"),
    "modern_serif_grotesk": ("modern_serif", "grotesk_sans"),
    "old_style_old_style": ("old_style_serif", "old_style_serif"),
    "old_style_humanist": ("old_style_serif", "humanist_sans"),
    "didone_humanist": ("didone_serif", "humanist_sans"),
    "didone_grotesk": ("didone_serif", "grotesk_sans"),
    "humanist_serif": ("humanist_sans", "transitional_serif"),
    "grotesk_serif": ("grotesk_sans", "transitional_serif"),
    "mono_humanist": ("mono", "humanist_sans"),
    "mono_grotesk": ("mono", "grotesk_sans"),
}

# ---------------------------------------------------------------------------
# Enumerations + one-line glossary (exported with --glossary for your prompt)
# ---------------------------------------------------------------------------
GLOSSARY = {
    "nav": {
        "topbar_logo_left_links_right": "Single bar: logo left, links right, optional CTA button as last item.",
        "topbar_logo_left_links_center_cta_right": "Single bar: logo left, links centred, CTA button right.",
        "topbar_logo_center_links_split": "Logo centred, links split half left / half right of it.",
        "topbar_with_utility_row": "Slim utility row (phone, email, hours) above the main nav bar.",
        "floating_pill": "Nav is a detached rounded pill floating a little below the top edge, centred.",
        "sidebar_left_desktop": "Fixed left sidebar with logo + vertical links on desktop; becomes a top bar on mobile.",
        "minimal_logo_and_menu_button": "Only logo + a menu button on all sizes; menu opens a full-screen overlay.",
        "bordered_grid_bar": "Nav bar with visible 1px cell borders between logo, links and CTA (Swiss grid feel).",
    },
    "nav_behaviour": {
        "static": "Scrolls away with the page.",
        "sticky": "Sticks to the top; adds a subtle shadow or border once scrolled.",
        "sticky_shrink": "Sticks and reduces padding/logo size after scrolling.",
        "hide_on_scroll_down": "Hides when scrolling down, reappears on scroll up (JS).",
    },
    "mobile_nav": {
        "slide_in_drawer": "Panel slides in from the right.",
        "dropdown_panel": "Panel drops down under the bar.",
        "fullscreen_overlay": "Full-viewport overlay with large stacked links.",
    },
    "hero": {
        "split_text_left_visual_right": "Two columns: headline/intro/CTAs left, decorative visual right.",
        "split_visual_left_text_right": "Two columns: decorative visual left, text right.",
        "centered_stack": "Centred eyebrow, headline, intro, CTA row; visual (if any) below.",
        "full_bleed_band": "Full-width coloured/gradient band with centred or left text.",
        "editorial_left_headline": "Very large left-aligned headline over ~8 columns, small intro beneath, no visual.",
        "headline_plus_stat_strip": "Headline block followed by a horizontal strip of 3-4 key stats.",
        "card_on_pattern": "Content sits in a card/panel placed over a patterned or tinted background.",
        "two_tone_split": "Background split vertically into two colours; text on one side, visual on the other.",
        "minimal_headline_only": "Short headline + one line + one CTA, generous whitespace, nothing else.",
        "offset_overlap": "Text block overlaps the edge of a tinted panel/visual for depth.",
    },
    "hero_visual": {
        "abstract_gradient_panel": "Rounded panel filled with a soft multi-stop gradient.",
        "geometric_shapes_svg": "Inline SVG of circles/rects/lines in palette colours.",
        "dot_grid_pattern": "CSS radial-gradient dot grid panel, optionally with one accent shape.",
        "stat_cards": "2-4 small cards showing numbers/labels instead of an image.",
        "browser_mockup_frame": "CSS 'browser window' frame containing placeholder UI blocks (no screenshot).",
        "icon_grid": "Grid of inline SVG icons in tinted tiles.",
        "line_art_svg": "Simple stroked inline SVG illustration (abstract, few paths).",
        "ring_stack": "Concentric rings / arcs in inline SVG or CSS borders.",
        "none": "No visual; typography carries the hero.",
    },
    "section": {
        "features": "Grid of 3-6 feature blocks (icon or number, title, 1-2 lines).",
        "services": "Service cards, often with a 'learn more' link each.",
        "values": "3-4 principles/values in a row or list.",
        "how_it_works": "Numbered steps, horizontal on desktop, vertical on mobile.",
        "showcase": "Grid of CSS-only tiles (gradient/pattern) representing work or products; no images.",
        "about": "Two-column narrative + a few facts or a pull quote.",
        "stats": "Row of large numbers with labels.",
        "trusted_by_text": "Text-only 'trusted by' list of plausible client names in muted type (no logos).",
        "testimonials": "1-3 quote cards or one large quote.",
        "team": "Grid of people cards using initials in tinted circles instead of photos.",
        "pricing": "2-3 tier cards, one highlighted.",
        "comparison_table": "Simple table comparing options or plans.",
        "faq": "Accordion or two-column Q&A.",
        "cta_band": "Full-width call-to-action band with headline + button.",
        "contact": "Contact details + a static (non-submitting, mailto or disabled) form.",
    },
    "footer": {
        "multi_column_4": "Brand + 3 link columns, bottom legal row.",
        "multi_column_3_with_brand": "Brand blurb left, 2 link columns right.",
        "minimal_single_row": "One row: brand, few links, copyright.",
        "centered_stack": "Centred logo, link row, copyright.",
        "big_cta_then_links": "Large CTA statement first, then compact link row.",
        "split_brand_left_links_right": "Brand/contact left, links right, thin top border.",
    },
    "divider": {
        "none": "Sections butt together; alternate backgrounds.",
        "thin_rule": "1px full-width rule between sections.",
        "diagonal_skew": "Section edges skewed with clip-path or transform.",
        "wave_svg": "Inline SVG wave along section boundary.",
        "curve_svg": "Inline SVG gentle single curve.",
        "offset_band": "Background band starts/ends offset from the content.",
    },
    "card": {
        "flat_bordered": "1px border, no shadow.",
        "elevated_soft": "No border, soft shadow.",
        "elevated_strong": "Stronger layered shadow.",
        "glass": "Translucent surface with backdrop blur (dark or gradient backgrounds only).",
        "borderless_tinted": "No border; subtly tinted background.",
        "accent_top_border": "3-4px accent bar along the top.",
        "accent_left_border": "3-4px accent bar along the left.",
        "numbered_minimal": "No box; large number/index + text.",
    },
    "button_shape": {"pill": "border-radius 999px", "rounded_md": "8-12px radius", "rounded_sm": "3-5px radius", "square": "0 radius"},
    "button_hover": {
        "darken": "Background darkens.",
        "lift": "translateY(-2px) + stronger shadow.",
        "fill_sweep": "Background colour sweeps in from one side.",
        "outline_to_solid": "Outline button fills on hover.",
        "glow": "Soft coloured box-shadow glow (dark themes).",
        "underline_slide": "Text links: underline grows in from the left.",
    },
    "section_pattern": {
        "none": "Plain backgrounds.",
        "dots": "Faint radial-gradient dot grid on alternate sections.",
        "grid_lines": "Faint 1px CSS grid lines.",
        "diagonal_stripes": "Very faint repeating-linear-gradient stripes.",
        "corner_blob": "One large low-opacity blob (border-radius 40% 60%...) tucked in a section corner.",
    },
    "css_delivery": {
        "inline": "All CSS in a <style> block in each HTML file.",
        "external": "All CSS in the external file named in delivery.css_file.",
        "split": "Critical CSS (reset, layout, hero) inline; the rest in delivery.css_file.",
    },
    "js_delivery": {"inline": "JS in a <script> at end of body.", "external": "JS in delivery.js_file.", "none": "No JavaScript at all."},
    "css_naming": {
        "bem": "block__element--modifier classes.",
        "semantic": "Plain descriptive classes (.hero, .card, .site-header).",
        "utility_light": "Semantic components plus a small set of utility classes (.grid-3, .mt-lg, .text-muted).",
    },
    "motion_level": {"none": "No animation beyond colour transitions.", "subtle": "Short fades/transitions, one reveal effect.", "moderate": "Reveals, counters, hover lifts; still restrained."},
}

# ---------------------------------------------------------------------------
# Archetypes: the anchor that keeps every other choice coherent
# ---------------------------------------------------------------------------
ARCHETYPES = {
    "corporate_clean": dict(
        weight=14,
        desc="Crisp, trustworthy B2B look. Structured grids, restrained colour, clear hierarchy.",
        pairings=["grotesk_grotesk", "humanist_humanist", "geometric_humanist", "serif_humanist", "modern_serif_grotesk"],
        nav=["topbar_logo_left_links_right", "topbar_logo_left_links_center_cta_right", "topbar_with_utility_row"],
        hero=["split_text_left_visual_right", "centered_stack", "headline_plus_stat_strip", "full_bleed_band", "split_visual_left_text_right"],
        hero_visual=["abstract_gradient_panel", "stat_cards", "browser_mockup_frame", "geometric_shapes_svg", "icon_grid"],
        footer=["multi_column_4", "multi_column_3_with_brand", "split_brand_left_links_right"],
        divider=["none", "thin_rule", "offset_band", "curve_svg"],
        card=["flat_bordered", "elevated_soft", "accent_top_border", "borderless_tinted"],
        button_shape=["rounded_sm", "rounded_md"],
        hover=["darken", "lift", "outline_to_solid"],
        modes={"light": 78, "light_dark_sections": 17, "dark": 5},
        harmony=["monochrome", "analogous", "neutral_plus_accent", "complementary"],
        hue_ranges=[(200, 240), (165, 195), (245, 265)], sat=(0.45, 0.75),
        density=["comfortable", "compact"], shadow=["none", "soft"], radius=["sm", "md"], border=["hairline"],
        heading_weight=[600, 700], heading_case=["normal", "eyebrow_uppercase"], motion=["subtle", "none", "moderate"],
        pattern=["none", "dots", "grid_lines"], tone=["confident", "formal", "plain_spoken"],
    ),
    "editorial": dict(
        weight=9,
        desc="Magazine-like. Big serif headlines, generous whitespace, asymmetry, muted colour.",
        pairings=["serif_humanist", "serif_grotesk", "didone_grotesk", "humanist_serif", "grotesk_serif", "old_style_humanist"],
        nav=["topbar_logo_center_links_split", "topbar_logo_left_links_right", "minimal_logo_and_menu_button"],
        hero=["editorial_left_headline", "minimal_headline_only", "offset_overlap", "split_text_left_visual_right"],
        hero_visual=["none", "line_art_svg", "abstract_gradient_panel", "ring_stack"],
        footer=["minimal_single_row", "centered_stack", "split_brand_left_links_right"],
        divider=["thin_rule", "none"],
        card=["numbered_minimal", "flat_bordered", "borderless_tinted"],
        button_shape=["square", "rounded_sm"],
        hover=["underline_slide", "darken", "outline_to_solid"],
        modes={"light": 88, "light_dark_sections": 10, "dark": 2},
        harmony=["neutral_plus_accent", "monochrome", "analogous"],
        hue_ranges=[(0, 20), (20, 45), (340, 360), (190, 220), (150, 175)], sat=(0.30, 0.60),
        density=["airy", "comfortable"], shadow=["none"], radius=["none", "sm"], border=["hairline", "bold"],
        heading_weight=[400, 500, 600], heading_case=["normal", "eyebrow_uppercase"], motion=["none", "subtle"],
        pattern=["none"], tone=["considered", "understated", "confident"],
        neutral_tint=["warm", "none"],
    ),
    "bold_modern": dict(
        weight=13,
        desc="Startup energy. Heavy geometric type, high contrast, one vivid accent, large hero.",
        pairings=["grotesk_grotesk", "geometric_humanist", "condensed_humanist", "condensed_grotesk", "humanist_humanist"],
        nav=["topbar_logo_left_links_center_cta_right", "floating_pill", "topbar_logo_left_links_right"],
        hero=["centered_stack", "split_text_left_visual_right", "full_bleed_band", "two_tone_split", "headline_plus_stat_strip"],
        hero_visual=["abstract_gradient_panel", "browser_mockup_frame", "geometric_shapes_svg", "stat_cards", "ring_stack"],
        footer=["multi_column_4", "big_cta_then_links", "multi_column_3_with_brand"],
        divider=["none", "diagonal_skew", "offset_band", "curve_svg"],
        card=["elevated_soft", "borderless_tinted", "flat_bordered", "elevated_strong"],
        button_shape=["pill", "rounded_md"],
        hover=["lift", "darken", "fill_sweep"],
        modes={"light": 60, "dark": 25, "light_dark_sections": 15},
        harmony=["complementary", "analogous", "split_complementary", "monochrome"],
        hue_ranges=[(215, 265), (265, 300), (150, 180), (5, 25), (330, 350)], sat=(0.65, 0.95),
        density=["comfortable", "airy"], shadow=["soft", "medium"], radius=["md", "lg", "xl"], border=["hairline", "none"],
        heading_weight=[700, 800], heading_case=["normal", "eyebrow_uppercase"], motion=["moderate", "subtle"],
        pattern=["none", "dots", "corner_blob", "grid_lines"], tone=["energetic", "confident", "direct"],
    ),
    "soft_minimal": dict(
        weight=10,
        desc="Calm and airy. Off-white or pastel grounds, rounded shapes, low contrast accents, lots of space.",
        pairings=["rounded_rounded", "rounded_humanist", "humanist_humanist", "geometric_humanist", "serif_humanist"],
        nav=["topbar_logo_left_links_right", "floating_pill", "topbar_logo_center_links_split"],
        hero=["centered_stack", "minimal_headline_only", "split_text_left_visual_right", "card_on_pattern"],
        hero_visual=["abstract_gradient_panel", "ring_stack", "dot_grid_pattern", "none", "icon_grid"],
        footer=["centered_stack", "minimal_single_row", "multi_column_3_with_brand"],
        divider=["none", "curve_svg", "wave_svg"],
        card=["borderless_tinted", "elevated_soft", "flat_bordered"],
        button_shape=["pill", "rounded_md"],
        hover=["darken", "lift"],
        modes={"light": 100},
        harmony=["analogous", "monochrome", "neutral_plus_accent"],
        hue_ranges=[(150, 200), (200, 250), (20, 45), (300, 340)], sat=(0.30, 0.55),
        density=["airy", "comfortable"], shadow=["none", "soft"], radius=["lg", "xl"], border=["hairline", "none"],
        heading_weight=[500, 600], heading_case=["normal"], motion=["subtle", "none"],
        pattern=["none", "dots", "corner_blob"], tone=["warm", "gentle", "plain_spoken"],
        neutral_tint=["primary", "warm"],
    ),
    "dark_tech": dict(
        weight=10,
        desc="Developer/tech feel. Dark grounds, mono or grotesk headings, subtle gradients and grid lines.",
        pairings=["mono_humanist", "mono_grotesk", "grotesk_grotesk", "geometric_humanist", "condensed_grotesk"],
        nav=["topbar_logo_left_links_right", "topbar_logo_left_links_center_cta_right", "floating_pill", "bordered_grid_bar"],
        hero=["centered_stack", "split_text_left_visual_right", "headline_plus_stat_strip", "card_on_pattern", "editorial_left_headline"],
        hero_visual=["browser_mockup_frame", "dot_grid_pattern", "geometric_shapes_svg", "abstract_gradient_panel", "stat_cards"],
        footer=["multi_column_4", "split_brand_left_links_right", "minimal_single_row"],
        divider=["none", "thin_rule", "offset_band"],
        card=["glass", "flat_bordered", "borderless_tinted", "accent_top_border"],
        button_shape=["rounded_sm", "rounded_md", "square"],
        hover=["glow", "darken", "lift"],
        modes={"dark": 85, "light_dark_sections": 15},
        harmony=["analogous", "monochrome", "complementary", "neutral_plus_accent"],
        hue_ranges=[(200, 260), (260, 290), (160, 185), (40, 55)], sat=(0.55, 0.90),
        density=["comfortable", "compact"], shadow=["none", "glow"], radius=["sm", "md"], border=["hairline"],
        heading_weight=[600, 700], heading_case=["normal", "eyebrow_uppercase"], motion=["subtle", "moderate"],
        pattern=["grid_lines", "dots", "none"], tone=["technical", "direct", "confident"],
        neutral_tint=["primary", "cool"],
    ),
    "warm_organic": dict(
        weight=9,
        desc="Earthy and human. Warm neutrals, terracotta/olive/ochre, soft serifs or humanist sans, organic shapes.",
        pairings=["serif_humanist", "old_style_humanist", "modern_serif_grotesk", "humanist_humanist", "rounded_humanist", "humanist_serif"],
        nav=["topbar_logo_left_links_right", "topbar_logo_center_links_split", "topbar_with_utility_row"],
        hero=["split_text_left_visual_right", "split_visual_left_text_right", "centered_stack", "offset_overlap"],
        hero_visual=["abstract_gradient_panel", "ring_stack", "line_art_svg", "geometric_shapes_svg"],
        footer=["multi_column_3_with_brand", "centered_stack", "split_brand_left_links_right"],
        divider=["none", "curve_svg", "wave_svg", "offset_band"],
        card=["borderless_tinted", "flat_bordered", "elevated_soft", "accent_left_border"],
        button_shape=["rounded_md", "pill", "rounded_sm"],
        hover=["darken", "lift"],
        modes={"light": 90, "light_dark_sections": 10},
        harmony=["analogous", "monochrome", "neutral_plus_accent", "split_complementary"],
        hue_ranges=[(10, 40), (40, 60), (70, 110), (350, 360)], sat=(0.35, 0.65),
        density=["comfortable", "airy"], shadow=["none", "soft"], radius=["md", "lg"], border=["hairline"],
        heading_weight=[500, 600, 700], heading_case=["normal"], motion=["subtle", "none"],
        pattern=["none", "corner_blob", "dots"], tone=["warm", "friendly", "considered"],
        neutral_tint=["warm", "primary"],
    ),
    "swiss_grid": dict(
        weight=8,
        desc="International/Swiss style. Visible grid, hairline borders, flush-left type, zero radius, one accent.",
        pairings=["grotesk_grotesk", "condensed_grotesk", "mono_grotesk", "humanist_humanist", "grotesk_serif"],
        nav=["bordered_grid_bar", "topbar_logo_left_links_right", "sidebar_left_desktop"],
        hero=["editorial_left_headline", "headline_plus_stat_strip", "two_tone_split", "minimal_headline_only"],
        hero_visual=["geometric_shapes_svg", "none", "stat_cards", "dot_grid_pattern"],
        footer=["multi_column_4", "split_brand_left_links_right", "minimal_single_row"],
        divider=["thin_rule", "none"],
        card=["flat_bordered", "numbered_minimal", "accent_top_border"],
        button_shape=["square"],
        hover=["fill_sweep", "darken", "underline_slide"],
        modes={"light": 80, "dark": 12, "light_dark_sections": 8},
        harmony=["neutral_plus_accent", "monochrome", "complementary"],
        hue_ranges=[(0, 15), (210, 240), (40, 55), (150, 170)], sat=(0.60, 0.95),
        density=["compact", "comfortable"], shadow=["none"], radius=["none"], border=["hairline", "bold"],
        heading_weight=[500, 600, 700], heading_case=["normal", "eyebrow_uppercase", "h2_uppercase"], motion=["none", "subtle"],
        pattern=["grid_lines", "none"], tone=["direct", "plain_spoken", "formal"],
        neutral_tint=["none", "cool"],
    ),
    "luxury": dict(
        weight=8,
        desc="Premium and quiet. Cream or near-black grounds, thin serifs, tracked uppercase labels, gold/bronze/deep accents.",
        pairings=["didone_humanist", "didone_grotesk", "old_style_old_style", "old_style_humanist", "modern_serif_grotesk"],
        nav=["topbar_logo_center_links_split", "minimal_logo_and_menu_button", "topbar_logo_left_links_right"],
        hero=["minimal_headline_only", "centered_stack", "editorial_left_headline", "two_tone_split", "offset_overlap"],
        hero_visual=["none", "ring_stack", "line_art_svg", "abstract_gradient_panel"],
        footer=["centered_stack", "minimal_single_row", "multi_column_3_with_brand"],
        divider=["thin_rule", "none"],
        card=["flat_bordered", "numbered_minimal", "borderless_tinted"],
        button_shape=["square", "rounded_sm"],
        hover=["underline_slide", "outline_to_solid", "darken"],
        modes={"light": 55, "dark": 35, "light_dark_sections": 10},
        harmony=["neutral_plus_accent", "monochrome"],
        hue_ranges=[(35, 50), (20, 35), (340, 360), (150, 170), (220, 240)], sat=(0.30, 0.60),
        density=["airy"], shadow=["none"], radius=["none", "sm"], border=["hairline"],
        heading_weight=[300, 400, 500], heading_case=["eyebrow_uppercase", "h2_uppercase", "normal"], motion=["subtle", "none"],
        pattern=["none"], tone=["understated", "formal", "considered"],
        neutral_tint=["warm", "none"],
    ),
    "playful_pro": dict(
        weight=9,
        desc="Friendly but polished. Rounded everything, cheerful but controlled colour, card-heavy layouts.",
        pairings=["rounded_rounded", "rounded_humanist", "geometric_humanist", "humanist_humanist", "grotesk_grotesk"],
        nav=["topbar_logo_left_links_right", "floating_pill", "topbar_logo_left_links_center_cta_right"],
        hero=["split_text_left_visual_right", "centered_stack", "card_on_pattern", "split_visual_left_text_right", "two_tone_split"],
        hero_visual=["geometric_shapes_svg", "icon_grid", "abstract_gradient_panel", "stat_cards", "ring_stack"],
        footer=["multi_column_3_with_brand", "big_cta_then_links", "centered_stack"],
        divider=["wave_svg", "curve_svg", "none", "offset_band"],
        card=["elevated_soft", "borderless_tinted", "accent_top_border", "flat_bordered"],
        button_shape=["pill", "rounded_md"],
        hover=["lift", "darken", "fill_sweep"],
        modes={"light": 95, "light_dark_sections": 5},
        harmony=["analogous", "split_complementary", "complementary", "monochrome"],
        hue_ranges=[(190, 230), (15, 40), (280, 320), (140, 170), (45, 60)], sat=(0.55, 0.85),
        density=["comfortable", "airy"], shadow=["soft", "medium"], radius=["lg", "xl"], border=["none", "hairline", "bold"],
        heading_weight=[700, 800], heading_case=["normal"], motion=["moderate", "subtle"],
        pattern=["dots", "corner_blob", "none"], tone=["friendly", "energetic", "warm"],
        neutral_tint=["primary", "warm"],
    ),
    "classic_trust": dict(
        weight=10,
        desc="Established professional (legal, finance, medical, trades). Navy/burgundy/forest, serif headings, bordered blocks.",
        pairings=["serif_humanist", "serif_grotesk", "old_style_humanist", "modern_serif_grotesk", "humanist_serif", "humanist_humanist"],
        nav=["topbar_with_utility_row", "topbar_logo_left_links_right", "topbar_logo_left_links_center_cta_right"],
        hero=["split_text_left_visual_right", "full_bleed_band", "headline_plus_stat_strip", "centered_stack", "offset_overlap"],
        hero_visual=["stat_cards", "abstract_gradient_panel", "line_art_svg", "icon_grid", "none"],
        footer=["multi_column_4", "multi_column_3_with_brand", "split_brand_left_links_right"],
        divider=["thin_rule", "none", "offset_band"],
        card=["flat_bordered", "accent_left_border", "accent_top_border", "borderless_tinted"],
        button_shape=["rounded_sm", "square"],
        hover=["darken", "outline_to_solid"],
        modes={"light": 85, "light_dark_sections": 15},
        harmony=["monochrome", "neutral_plus_accent", "analogous", "complementary"],
        hue_ranges=[(205, 235), (345, 360), (0, 10), (140, 165), (25, 45)], sat=(0.40, 0.70),
        density=["comfortable", "compact"], shadow=["none", "soft"], radius=["sm", "none"], border=["hairline", "bold"],
        heading_weight=[600, 700], heading_case=["normal", "eyebrow_uppercase"], motion=["none", "subtle"],
        pattern=["none", "grid_lines"], tone=["formal", "reassuring", "plain_spoken"],
        neutral_tint=["cool", "none", "warm"],
    ),
}

# per-archetype hard rules ("never do X with Y")
GLASS_OK_MODES = {"dark"}
GLOW_OK_MODES = {"dark"}

RADIUS_TOKENS = {
    "none": {"sm": 0, "md": 0, "lg": 0},
    "sm": {"sm": 2, "md": 4, "lg": 8},
    "md": {"sm": 4, "md": 8, "lg": 16},
    "lg": {"sm": 6, "md": 12, "lg": 24},
    "xl": {"sm": 10, "md": 18, "lg": 32},
}
BUTTON_RADIUS = {"pill": 999, "rounded_md": (8, 12), "rounded_sm": (3, 5), "square": 0}
DENSITY = {
    "compact": {"section_py": (52, 68), "grid_gap": (16, 22), "container_px": (18, 22)},
    "comfortable": {"section_py": (76, 96), "grid_gap": (24, 32), "container_px": (22, 28)},
    "airy": {"section_py": (104, 136), "grid_gap": (32, 44), "container_px": (24, 32)},
}
CONTAINER_WIDTHS = [1080, 1120, 1160, 1200, 1240, 1280, 1320]
SCALE_RATIOS = [1.2, 1.25, 1.333, 1.414]

MOTION_FEATURES = {
    "subtle": ["scroll_reveal_fade", "sticky_header_shadow", "smooth_scroll_anchors", "faq_accordion", "back_to_top"],
    "moderate": ["scroll_reveal_fade_up", "stat_counter_animation", "sticky_header_shadow", "smooth_scroll_anchors",
                 "faq_accordion", "tabs", "back_to_top", "hover_lift_cards", "hero_gradient_drift"],
}

# section ordering groups: pick from pool, then order group by group with shuffles inside
SECTION_GROUPS = [
    (["features", "services", "values", "how_it_works", "showcase"], (1, 2)),
    (["about", "stats", "trusted_by_text", "testimonials", "team"], (1, 3)),
    (["pricing", "comparison_table", "faq"], (0, 2)),
]
ARCH_SECTION_BLOCK = {  # sections that don't suit an archetype
    "luxury": {"pricing", "comparison_table", "stats"},
    "editorial": {"pricing", "comparison_table", "trusted_by_text"},
    "soft_minimal": {"comparison_table"},
    "swiss_grid": {"testimonials"},
}

TONE = ["confident", "formal", "plain_spoken", "considered", "understated", "energetic", "direct", "warm",
        "gentle", "technical", "friendly", "reassuring"]
HEADLINE_STYLE = ["short_punchy", "descriptive_benefit", "question", "statement_with_qualifier"]
CTA_STYLE = ["imperative_verb", "benefit_led", "soft_invite"]

ASSET_DIRS = ["assets", "static", "public", "_", "site", "res"]
CSS_BASENAMES = ["site", "main", "theme", "styles", "app", "core", "base", "layout"]
JS_BASENAMES = ["site", "main", "app", "ui", "behaviour", "scripts", "core"]


# ---------------------------------------------------------------------------
# Colour maths
# ---------------------------------------------------------------------------
def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def hsl_to_hex(h, s, l):
    r, g, b = colorsys.hls_to_rgb((h % 360) / 360.0, clamp(l), clamp(s))
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def luminance(hex_):
    def chan(c):
        c /= 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hex_[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def fit(hsl, bg_hex, min_ratio, direction):
    """Nudge lightness in `direction` ('darker'|'lighter') until contrast vs bg passes."""
    h, s, l = hsl
    step = -0.01 if direction == "darker" else 0.01
    for _ in range(100):
        if contrast(hsl_to_hex(h, s, l), bg_hex) >= min_ratio:
            break
        l = clamp(l + step, 0.02, 0.98)
        if l in (0.02, 0.98):
            break
    return (h, s, l)


def hue_name(h, s):
    if s < 0.12:
        return "neutral"
    h %= 360
    for limit, name in [(12, "red"), (38, "orange"), (52, "amber"), (68, "yellow"), (95, "lime"), (160, "green"),
                        (190, "teal"), (215, "sky"), (255, "blue"), (285, "violet"), (320, "purple"), (345, "magenta"), (360, "red")]:
        if h < limit:
            if s < 0.28:
                return "muted " + name
            return name
    return "red"


def pick_hue(rng, ranges):
    lo, hi = rng.choice(ranges)
    return rng.uniform(lo, hi) % 360


def build_palette(rng, arch):
    mode = weighted(rng, arch["modes"])
    harmony = rng.choice(arch["harmony"])
    h = pick_hue(rng, arch["hue_ranges"])
    s = rng.uniform(*arch["sat"])
    if harmony == "neutral_plus_accent":
        # primary is near-neutral; the accent carries the colour
        accent_h, accent_s = h, max(s, 0.5)
        h, s = (h if rng.random() < 0.5 else rng.uniform(200, 230)), rng.uniform(0.08, 0.22)
    else:
        accent_h = {
            "monochrome": h,
            "analogous": h + rng.choice([-1, 1]) * rng.uniform(25, 40),
            "complementary": h + 180 + rng.uniform(-12, 12),
            "split_complementary": h + rng.choice([150, 210]) + rng.uniform(-8, 8),
        }[harmony] % 360
        accent_s = clamp(s * (0.8 if harmony == "complementary" else 0.9), 0.25, 0.9)

    tint_kind = rng.choice(arch.get("neutral_tint", ["primary", "cool", "none"]))
    tint_h = {"primary": h if harmony != "neutral_plus_accent" else accent_h, "warm": rng.uniform(30, 48),
              "cool": rng.uniform(210, 232), "none": 0}[tint_kind]
    tint_s = 0.0 if tint_kind == "none" else rng.uniform(0.05, 0.16)
    dark = mode == "dark"

    if not dark:
        bg = (tint_h, tint_s, rng.uniform(0.975, 1.0))
        bg_hex = hsl_to_hex(*bg)
        surface = (tint_h, tint_s, bg[2] - rng.uniform(0.03, 0.055))
        text = fit((tint_h, clamp(tint_s + 0.15, 0, 0.35), rng.uniform(0.08, 0.17)), bg_hex, 10.0, "darker")
        muted = fit((tint_h, clamp(tint_s + 0.05, 0, 0.3), rng.uniform(0.36, 0.46)), hsl_to_hex(*surface), 4.6, "darker")
        border = (tint_h, tint_s, rng.uniform(0.84, 0.90))
        primary = fit((h, s, rng.uniform(0.30, 0.48)), bg_hex, 3.1, "darker")
        accent = fit((accent_h, accent_s, rng.uniform(0.34, 0.52)), bg_hex, 3.0, "darker")
        soft = (h if harmony != "neutral_plus_accent" else accent_h, clamp(s * 0.6, 0.1, 0.5), rng.uniform(0.92, 0.955))
        hover_shift, dir_ = -0.07, "darker"
    else:
        bg = (tint_h, clamp(tint_s + 0.08, 0, 0.3), rng.uniform(0.06, 0.11))
        bg_hex = hsl_to_hex(*bg)
        surface = (tint_h, clamp(tint_s + 0.06, 0, 0.3), bg[2] + rng.uniform(0.035, 0.055))
        text = fit((tint_h, tint_s, rng.uniform(0.90, 0.95)), bg_hex, 10.0, "lighter")
        muted = fit((tint_h, tint_s, rng.uniform(0.62, 0.70)), hsl_to_hex(*surface), 4.6, "lighter")
        border = (tint_h, tint_s, rng.uniform(0.18, 0.24))
        primary = fit((h, clamp(s, 0.3, 0.8), rng.uniform(0.55, 0.68)), bg_hex, 3.1, "lighter")
        accent = fit((accent_h, clamp(accent_s, 0.3, 0.8), rng.uniform(0.58, 0.70)), bg_hex, 3.0, "lighter")
        soft = (h, clamp(s * 0.5, 0.1, 0.5), rng.uniform(0.17, 0.22))
        hover_shift, dir_ = +0.07, "lighter"

    # monochrome: separate accent from primary by lightness so it is still usable
    if harmony == "monochrome":
        accent = fit((h, clamp(s * 0.7, 0.15, 0.8), clamp(primary[2] + (0.16 if not dark else -0.14))), bg_hex, 3.0, dir_)

    primary_hex = hsl_to_hex(*primary)
    on_primary = None
    for cand in ("#ffffff", bg_hex, hsl_to_hex(*text)):
        if contrast(cand, primary_hex) >= 4.5:
            on_primary = cand
            break
    if on_primary is None:  # darken primary until white text passes
        primary = fit(primary, "#ffffff", 4.5, "darker")
        primary_hex = hsl_to_hex(*primary)
        on_primary = "#ffffff"
    accent_hex = hsl_to_hex(*accent)
    on_accent = "#ffffff" if contrast("#ffffff", accent_hex) >= 4.5 else hsl_to_hex(*text)
    if contrast(on_accent, accent_hex) < 4.5:
        accent = fit(accent, "#ffffff", 4.5, "darker")
        accent_hex, on_accent = hsl_to_hex(*accent), "#ffffff"

    pal = {
        "mode": mode,
        "harmony": harmony,
        "primary_hue_name": hue_name(primary[0], primary[1]),
        "accent_hue_name": hue_name(accent[0], accent[1]),
        "bg": bg_hex,
        "surface": hsl_to_hex(*surface),
        "text": hsl_to_hex(*text),
        "text_muted": hsl_to_hex(*muted),
        "border": hsl_to_hex(*border),
        "primary": primary_hex,
        "primary_hover": hsl_to_hex(primary[0], primary[1], clamp(primary[2] + hover_shift)),
        "primary_soft": hsl_to_hex(*soft),
        "on_primary": on_primary,
        "accent": accent_hex,
        "on_accent": on_accent,
    }
    g2 = (primary[0] + rng.uniform(14, 26), primary[1], clamp(primary[2] + (0.12 if not dark else 0.08)))
    pal["gradient"] = [primary_hex, accent_hex if (harmony != "monochrome" and rng.random() < 0.55) else hsl_to_hex(*g2)]

    if mode == "light_dark_sections":
        band_bg = (tint_h, clamp(tint_s + 0.12, 0, 0.35), rng.uniform(0.09, 0.13))
        band_bg_hex = hsl_to_hex(*band_bg)
        band_primary = fit((h, clamp(s, 0.3, 0.8), 0.62), band_bg_hex, 3.0, "lighter")
        band_primary_hex = hsl_to_hex(*band_primary)
        band_on = max(("#ffffff", band_bg_hex), key=lambda c: contrast(c, band_primary_hex))
        if contrast(band_on, band_primary_hex) < 4.5:
            # lighten until the dark band colour reads on it (stays >= 3.0 vs the band bg by construction)
            band_primary = fit(band_primary, band_bg_hex, 4.5, "lighter")
            band_primary_hex, band_on = hsl_to_hex(*band_primary), band_bg_hex
        pal["dark_band"] = {
            "bg": band_bg_hex,
            "text": hsl_to_hex(tint_h, tint_s, 0.95),
            "text_muted": hsl_to_hex(*fit((tint_h, tint_s, 0.7), band_bg_hex, 4.6, "lighter")),
            "primary": band_primary_hex,
            "on_primary": band_on,
        }

    pal["contrast"] = {
        "text_on_bg": round(contrast(pal["text"], pal["bg"]), 1),
        "muted_on_surface": round(contrast(pal["text_muted"], pal["surface"]), 1),
        "primary_on_bg": round(contrast(pal["primary"], pal["bg"]), 1),
        "on_primary_on_primary": round(contrast(pal["on_primary"], pal["primary"]), 1),
    }
    return pal, primary[0]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def weighted(rng, table):
    items = list(table.items())
    total = sum(w for _, w in items)
    r = rng.uniform(0, total)
    for k, w in items:
        r -= w
        if r <= 0:
            return k
    return items[-1][0]


def rint(rng, rng_or_val):
    if isinstance(rng_or_val, tuple):
        return rng.randint(*rng_or_val)
    return rng_or_val


def slug_token(rng, n):
    return "".join(rng.choice("abcdefghjkmnpqrstuvwxyz23456789") for _ in range(n))


def dedupe_adjacent(seq):
    out = []
    for x in seq:
        if not out or out[-1] != x:
            out.append(x)
    return out


def build_sections(rng, arch_name, multi_page):
    blocked = ARCH_SECTION_BLOCK.get(arch_name, set())
    chosen = []
    for pool, (lo, hi) in SECTION_GROUPS:
        pool = [p for p in pool if p not in blocked]
        k = rng.randint(lo, min(hi, len(pool)))
        picks = rng.sample(pool, k)
        if "features" in picks and "services" in picks:
            picks.remove(rng.choice(["features", "services"]))
        chosen.append(picks)
    if not chosen[0]:
        chosen[0] = [rng.choice(["features", "services"])]
    order = chosen[0] + chosen[1] + chosen[2]
    # mid-page CTA band sometimes; always one before footer/contact
    if len(order) >= 4 and rng.random() < 0.45:
        order.insert(rng.randint(2, len(order) - 1), "cta_band")
    if rng.random() < 0.9:
        order.append("cta_band")
    if rng.random() < 0.55:
        order.append("contact")
    out = dedupe_adjacent(order)
    if multi_page:
        # home is a digest; move heavier sections to their own pages
        home = dedupe_adjacent([s_ for s_ in out if s_ not in ("pricing", "comparison_table", "faq", "team", "contact")])[:6]
        if "cta_band" not in home:
            home.append("cta_band")
        pages = [{"slug": "index", "title": "Home", "sections": ["hero"] + home}]
        about_secs = ["about"] + [s_ for s_ in ("values", "team", "stats", "testimonials") if s_ in out or rng.random() < 0.4]
        pages.append({"slug": "about", "title": rng.choice(["About", "About Us", "Our Story", "Who We Are"]),
                      "sections": ["page_header"] + list(dict.fromkeys(about_secs)) + ["cta_band"]})
        svc_title = rng.choice(["Services", "What We Do", "Solutions", "Offerings"])
        svc_secs = ["page_header", "services" if "services" in out else "features"]
        if "how_it_works" in out or rng.random() < 0.5:
            svc_secs.append("how_it_works")
        if "pricing" in out:
            svc_secs.append("pricing")
        if "comparison_table" in out:
            svc_secs.append("comparison_table")
        if "faq" in out:
            svc_secs.append("faq")
        pages.append({"slug": svc_title.lower().replace(" ", "-"), "title": svc_title, "sections": svc_secs + ["cta_band"]})
        pages.append({"slug": "contact", "title": rng.choice(["Contact", "Get in Touch", "Contact Us"]),
                      "sections": ["page_header", "contact"] + (["faq"] if "faq" in out and rng.random() < 0.4 else [])})
        return pages
    return [{"slug": "index", "title": "Home", "sections": ["hero"] + out}]


# ---------------------------------------------------------------------------
# Manifest builder
# ---------------------------------------------------------------------------
def build_manifest(seed, idx):
    rng = random.Random(seed)
    arch_name = weighted(rng, {k: v["weight"] for k, v in ARCHETYPES.items()})
    A = ARCHETYPES[arch_name]

    palette, primary_hue = build_palette(rng, A)
    mode = palette["mode"]

    # --- components, with coherence rules
    card = rng.choice(A["card"])
    if card == "glass" and mode not in GLASS_OK_MODES:
        card = "borderless_tinted"
    hover = rng.choice(A["hover"])
    if hover == "glow" and mode not in GLOW_OK_MODES:
        hover = "darken"
    shadow = rng.choice(A["shadow"])
    if mode == "dark" and shadow in ("soft", "medium"):
        shadow = rng.choice(["none", "glow"])
    if card in ("elevated_soft", "elevated_strong") and shadow == "none":
        shadow = "soft" if card == "elevated_soft" else "medium"
    divider = rng.choice(A["divider"])
    hero = rng.choice(A["hero"])
    hero_visual = rng.choice(A["hero_visual"])
    if hero in ("editorial_left_headline", "minimal_headline_only"):
        hero_visual = "none"
    elif hero_visual == "none" and hero in ("split_text_left_visual_right", "split_visual_left_text_right", "two_tone_split"):
        hero_visual = rng.choice([v for v in A["hero_visual"] if v != "none"] or ["abstract_gradient_panel"])
    pattern = rng.choice(A["pattern"])
    if hero in ("full_bleed_band", "card_on_pattern", "two_tone_split") and pattern != "none" and rng.random() < 0.6:
        pattern = "none"  # only one loud background idea per site
    nav = rng.choice(A["nav"])
    nav_behaviour = rng.choice(["static", "sticky", "sticky", "sticky_shrink"])
    motion = rng.choice(A["motion"])
    if nav == "floating_pill":
        nav_behaviour = "sticky"
    if motion == "moderate" and rng.random() < 0.25:
        nav_behaviour = "hide_on_scroll_down"
    if motion == "none" and nav_behaviour in ("sticky_shrink", "hide_on_scroll_down"):
        nav_behaviour = "sticky"
    mobile_nav = "fullscreen_overlay" if nav == "minimal_logo_and_menu_button" else rng.choice(["slide_in_drawer", "dropdown_panel", "fullscreen_overlay"])

    button_shape = rng.choice(A["button_shape"])
    radius_key = rng.choice(A["radius"])
    if button_shape == "square" and radius_key not in ("none", "sm"):
        radius_key = "sm"
    if button_shape == "pill" and radius_key in ("none", "sm"):
        radius_key = "md"
    br = BUTTON_RADIUS[button_shape]
    button_radius = rint(rng, br)

    # --- typography
    pairing = rng.choice(A["pairings"])
    head_font, body_font = PAIRINGS[pairing]
    heading_case = rng.choice(A["heading_case"])
    heading_weight = rng.choice(A["heading_weight"])
    if head_font in ("didone_serif", "old_style_serif", "modern_serif") and heading_weight > 700:
        heading_weight = 700
    tracking = {"normal": rng.choice(["-0.02em", "-0.015em", "-0.01em", "0"]),
                "eyebrow_uppercase": rng.choice(["-0.01em", "0"]),
                "h2_uppercase": rng.choice(["0.04em", "0.06em"])}[heading_case]
    if head_font == "condensed_sans":
        tracking = "0"
    typography = {
        "pairing": pairing,
        "heading_font": head_font,
        "heading_stack": FONT_STACKS[head_font],
        "body_font": body_font,
        "body_stack": FONT_STACKS[body_font],
        "base_size_px": rng.choice([16, 16, 17, 18]),
        "scale_ratio": rng.choice(SCALE_RATIOS),
        "fluid_type": rng.random() < 0.6,
        "heading_weight": heading_weight,
        "heading_letter_spacing": tracking,
        "heading_line_height": rng.choice([1.05, 1.1, 1.15, 1.2]),
        "body_line_height": rng.choice([1.55, 1.6, 1.65, 1.7]),
        "heading_case": heading_case,
        "eyebrow_style": rng.choice(["uppercase_tracked_small", "accent_colour_small", "numbered", "none"]),
        "measure_ch": rng.choice([60, 65, 68, 72]),
        "h1_max_px": rng.choice([44, 48, 52, 56, 60, 64, 72]) if hero not in ("editorial_left_headline",) else rng.choice([64, 72, 80, 88]),
    }

    # --- layout numbers
    density = rng.choice(A["density"])
    D = DENSITY[density]
    container = rng.choice(CONTAINER_WIDTHS)
    layout = {
        "structure": "multi_page" if (multi := rng.random() < 0.35) else "single_page",
        "container_max_px": container,
        "container_pad_px": rng.randint(*D["container_px"]),
        "section_padding_y_px": rng.randint(*D["section_py"]),
        "grid_gap_px": rng.randint(*D["grid_gap"]),
        "density": density,
        "card_columns_desktop": rng.choice([3, 3, 4, 2]),
        "breakpoints_px": {"mobile": rng.choice([600, 640, 720]), "tablet": rng.choice([900, 960, 1024])},
        "nav": nav,
        "nav_behaviour": nav_behaviour,
        "mobile_nav": mobile_nav,
        "nav_cta_button": rng.random() < 0.7,
        "hero": hero,
        "hero_visual": hero_visual,
        "hero_height": rng.choice(["auto", "min_70vh", "min_85vh"]) if hero not in ("minimal_headline_only",) else "auto",
        "section_divider": divider,
        "alternate_section_backgrounds": rng.random() < 0.7,
        "footer": rng.choice(A["footer"]),
        "pages": build_sections(rng, arch_name, multi),
    }

    # --- components / tokens
    radius = dict(RADIUS_TOKENS[radius_key])
    if card == "glass":
        radius["lg"] = max(radius["lg"], 12)
    text_rgb = tuple(int(palette["text"][i:i + 2], 16) for i in (1, 3, 5))
    shadow_css = {
        "none": "none",
        "soft": "0 1px 2px rgba(%d,%d,%d,.06), 0 6px 16px rgba(%d,%d,%d,.07)" % (text_rgb * 2),
        "medium": "0 2px 4px rgba(%d,%d,%d,.08), 0 12px 28px rgba(%d,%d,%d,.12)" % (text_rgb * 2),
        "glow": "0 0 0 1px %s33, 0 8px 32px %s2e" % (palette["primary"], palette["primary"]),
    }[shadow]
    border_w = {"hairline": 1, "bold": 2, "none": 0}[rng.choice(A["border"])]
    components = {
        "radius_px": radius,
        "border_width_px": border_w,
        "shadow": shadow,
        "shadow_css": shadow_css,
        "card": card,
        "button_shape": button_shape,
        "button_radius_px": button_radius,
        "button_primary_style": rng.choice(["solid_primary", "solid_primary", "solid_accent", "solid_text_colour"]),
        "button_secondary_style": rng.choice(["outline", "ghost_text_link", "soft_tint"]),
        "button_hover": hover,
        "link_hover": rng.choice(["underline_slide", "colour_shift", "underline_always_thicker"]),
        "icon_style": rng.choice(["inline_svg_outline", "inline_svg_filled", "numbered_circles", "none"]),
        "section_pattern": pattern,
        "hero_shape_accent": rng.random() < 0.4,
        "focus_ring": "2px solid %s" % palette["accent"],
        "image_policy": "none: use CSS gradients, inline SVG, patterns and tinted panels for all visuals",
    }

    # --- motion
    feats = []
    if motion != "none":
        pool = MOTION_FEATURES[motion]
        feats = rng.sample(pool, rng.randint(2, min(4 if motion == "subtle" else 6, len(pool))))
    if any("faq" in p["sections"] for p in layout["pages"]) and "faq_accordion" not in feats:
        feats.append("faq_accordion" if motion != "none" else "faq_details_element")
    motion_spec = {
        "level": motion,
        "features": sorted(set(feats)),
        "transition_ms": rng.choice([150, 180, 200, 240]),
        "easing": rng.choice(["ease", "ease-out", "cubic-bezier(.2,.8,.2,1)", "cubic-bezier(.4,0,.2,1)"]),
        "respect_prefers_reduced_motion": True,
    }

    # --- delivery / anti-clone
    css_delivery = rng.choice(["inline", "external", "external", "split"])
    needs_js = motion != "none" or nav_behaviour in ("sticky_shrink", "hide_on_scroll_down") or "faq_accordion" in feats
    nav_toggle = "js" if (needs_js and rng.random() < 0.75) else "css_checkbox"
    if nav_toggle == "js":
        needs_js = True
    js_delivery = "none" if not needs_js else rng.choice(["inline", "external", "external"])
    asset_dir = rng.choice(ASSET_DIRS)
    tok = slug_token(rng, rng.choice([0, 0, 4, 5]))
    css_name = rng.choice(CSS_BASENAMES) + ("-" + tok if tok else "")
    js_name = rng.choice(JS_BASENAMES) + ("-" + tok if tok else "")
    prefix = rng.choice(["", "", "", slug_token(rng, 2), slug_token(rng, 3)])
    delivery = {
        "css_delivery": css_delivery,
        "css_file": None if css_delivery == "inline" else "%s/%s.css" % (asset_dir, css_name),
        "js_delivery": js_delivery,
        "js_file": "%s/%s.js" % (asset_dir, js_name) if js_delivery == "external" else None,
        "nav_toggle": nav_toggle,
        "css_naming": rng.choice(["bem", "semantic", "semantic", "utility_light"]),
        "class_prefix": prefix,
        "use_css_custom_properties": rng.random() < 0.75,
        "minify_external_assets": css_delivery != "inline" and rng.random() < 0.4,
        "html_comments": rng.choice(["none", "none", "sparse"]),
        "external_resources": "forbidden",
    }

    copy = {
        "tone": rng.choice(A["tone"]),
        "headline_style": rng.choice(HEADLINE_STYLE),
        "cta_style": rng.choice(CTA_STYLE),
        "paragraph_length": rng.choice(["short", "short", "medium"]),
        "use_eyebrow_labels": typography["eyebrow_style"] != "none",
        "emphasise_numbers": any("stats" in p["sections"] or hero == "headline_plus_stat_strip" for p in layout["pages"]),
    }

    fp_src = "|".join([arch_name, nav, hero, hero_visual, pairing, str(int(primary_hue // 15)), mode, card, button_shape, layout["footer"], divider])
    core_fp = hashlib.sha1(fp_src.encode()).hexdigest()[:12]

    return {
        "manifest_version": MANIFEST_VERSION,
        "id": "m%07d-%s" % (idx, core_fp[:6]),
        "seed": seed,
        "archetype": arch_name,
        "archetype_description": A["desc"],
        "palette": palette,
        "typography": typography,
        "layout": layout,
        "components": components,
        "motion": motion_spec,
        "delivery": delivery,
        "copy_style": copy,
        "_core_fingerprint": core_fp,
    }


# ---------------------------------------------------------------------------
# Generation loop with uniqueness
# ---------------------------------------------------------------------------
COMPACT_DROP = [("archetype_description",), ("typography", "heading_stack"), ("typography", "body_stack"),
                ("components", "image_policy"), ("delivery", "external_resources"), ("palette", "contrast")]


def compact(m):
    """Drop fields the glossary already explains (saves ~20% tokens per site)."""
    for path in COMPACT_DROP:
        d = m
        for k in path[:-1]:
            d = d.get(k, {})
        d.pop(path[-1], None)
    return m


def generate(count, run_seed, start_id, out_fh, quiet=False, compact_out=False):
    master = random.Random(run_seed)
    seen_core, seen_full = set(), set()
    produced, attempts, relaxed = 0, 0, False
    consecutive_core_hits = 0
    arch_counts = {}
    t0 = time.time()
    while produced < count:
        attempts += 1
        seed = master.getrandbits(52)
        m = build_manifest(seed, start_id + produced)
        core = m.pop("_core_fingerprint")
        if not relaxed and core in seen_core:
            consecutive_core_hits += 1
            if consecutive_core_hits > 500:
                relaxed = True
                if not quiet:
                    print("note: core-fingerprint space is getting crowded; falling back to full-manifest uniqueness", file=sys.stderr)
            continue
        consecutive_core_hits = 0
        full = hashlib.sha1(json.dumps(m, sort_keys=True).encode()).hexdigest()
        if full in seen_full:
            continue
        seen_core.add(core)
        seen_full.add(full)
        if compact_out:
            compact(m)
        out_fh.write(json.dumps(m, separators=(",", ":")) + "\n")
        produced += 1
        arch_counts[m["archetype"]] = arch_counts.get(m["archetype"], 0) + 1
        if not quiet and produced % 10000 == 0:
            print("  %d / %d  (%.1fs)" % (produced, count, time.time() - t0), file=sys.stderr)
    return {"produced": produced, "attempts": attempts, "seconds": round(time.time() - t0, 2),
            "unique_core_fingerprints": len(seen_core), "archetypes": dict(sorted(arch_counts.items()))}


def glossary_markdown():
    """The id glossary as markdown. Identical for every site, so it belongs in a cached system prompt."""
    lines = ["# Manifest glossary (manifest_version %s)" % MANIFEST_VERSION, "", "## Archetypes", ""]
    for k, v in ARCHETYPES.items():
        lines.append("- **%s** - %s" % (k, v["desc"]))
    for group, table in GLOSSARY.items():
        lines += ["", "## %s" % group, ""]
        for k, v in table.items():
            lines.append("- `%s` - %s" % (k, v))
    lines += ["", "## Font stacks", ""]
    for k, v in FONT_STACKS.items():
        lines.append("- `%s`: `%s`" % (k, v))
    lines += ["", "## Palette keys", "",
              "`bg`, `surface` (cards / alternate sections), `text`, `text_muted`, `border`, `primary`, `primary_hover`, "
              "`primary_soft` (tints, badges), `on_primary` (text on primary), `accent`, `on_accent`, `gradient` (2 stops). "
              "`dark_band` (only when mode is light_dark_sections) gives colours for the dark sections. "
              "`contrast` reports WCAG ratios that were verified at generation time.", ""]
    return "\n".join(lines)


def write_glossary(path):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(glossary_markdown())


def main():
    ap = argparse.ArgumentParser(description="Generate website design manifests as JSONL.")
    ap.add_argument("count", nargs="?", type=int, help="number of manifests to generate")
    ap.add_argument("--count", dest="count_opt", type=int, help="number of manifests to generate")
    ap.add_argument("--out", default="manifests.jsonl", help="output .jsonl path (default manifests.jsonl)")
    ap.add_argument("--seed", type=int, default=None, help="run seed for reproducible output (default: random)")
    ap.add_argument("--start-id", type=int, default=1, help="first numeric id (default 1)")
    ap.add_argument("--append", action="store_true", help="append to --out instead of overwriting")
    ap.add_argument("--sample", action="store_true", help="pretty-print the first manifest to stderr")
    ap.add_argument("--glossary", metavar="PATH", help="write the id glossary markdown to PATH and exit (unless count given)")
    ap.add_argument("--from-seed", type=int, metavar="SEED", help="regenerate one manifest from its seed and print it")
    ap.add_argument("--compact", action="store_true", help="omit fields the glossary already explains (smaller prompts)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if args.from_seed is not None:
        m = build_manifest(args.from_seed, 0)
        m.pop("_core_fingerprint", None)
        print(json.dumps(m, indent=2))
        return
    if args.glossary:
        write_glossary(args.glossary)
        if not args.quiet:
            print("wrote glossary to %s" % args.glossary, file=sys.stderr)
    count = args.count_opt if args.count_opt is not None else args.count
    if count is None:
        if args.glossary:
            return
        ap.error("count is required (positional or --count)")
    if count <= 0:
        ap.error("count must be > 0")

    run_seed = args.seed if args.seed is not None else random.SystemRandom().getrandbits(32)
    mode = "a" if args.append else "w"
    with open(args.out, mode, encoding="utf-8") as fh:
        stats = generate(count, run_seed, args.start_id, fh, quiet=args.quiet, compact_out=args.compact)
    stats["run_seed"] = run_seed
    stats["out"] = args.out
    if args.sample:
        with open(args.out, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    print(json.dumps(json.loads(line), indent=2), file=sys.stderr)
                    break
    if not args.quiet:
        print(json.dumps(stats, indent=2), file=sys.stderr)


if __name__ == "__main__":
    main()
