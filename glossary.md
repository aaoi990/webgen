# Manifest glossary (manifest_version 1.0)

## Archetypes

- **corporate_clean** - Crisp, trustworthy B2B look. Structured grids, restrained colour, clear hierarchy.
- **editorial** - Magazine-like. Big serif headlines, generous whitespace, asymmetry, muted colour.
- **bold_modern** - Startup energy. Heavy geometric type, high contrast, one vivid accent, large hero.
- **soft_minimal** - Calm and airy. Off-white or pastel grounds, rounded shapes, low contrast accents, lots of space.
- **dark_tech** - Developer/tech feel. Dark grounds, mono or grotesk headings, subtle gradients and grid lines.
- **warm_organic** - Earthy and human. Warm neutrals, terracotta/olive/ochre, soft serifs or humanist sans, organic shapes.
- **swiss_grid** - International/Swiss style. Visible grid, hairline borders, flush-left type, zero radius, one accent.
- **luxury** - Premium and quiet. Cream or near-black grounds, thin serifs, tracked uppercase labels, gold/bronze/deep accents.
- **playful_pro** - Friendly but polished. Rounded everything, cheerful but controlled colour, card-heavy layouts.
- **classic_trust** - Established professional (legal, finance, medical, trades). Navy/burgundy/forest, serif headings, bordered blocks.

## nav

- `topbar_logo_left_links_right` - Single bar: logo left, links right, optional CTA button as last item.
- `topbar_logo_left_links_center_cta_right` - Single bar: logo left, links centred, CTA button right.
- `topbar_logo_center_links_split` - Logo centred, links split half left / half right of it.
- `topbar_with_utility_row` - Slim utility row (phone, email, hours) above the main nav bar.
- `floating_pill` - Nav is a detached rounded pill floating a little below the top edge, centred.
- `sidebar_left_desktop` - Fixed left sidebar with logo + vertical links on desktop; becomes a top bar on mobile.
- `minimal_logo_and_menu_button` - Only logo + a menu button on all sizes; menu opens a full-screen overlay.
- `bordered_grid_bar` - Nav bar with visible 1px cell borders between logo, links and CTA (Swiss grid feel).

## nav_behaviour

- `static` - Scrolls away with the page.
- `sticky` - Sticks to the top; adds a subtle shadow or border once scrolled.
- `sticky_shrink` - Sticks and reduces padding/logo size after scrolling.
- `hide_on_scroll_down` - Hides when scrolling down, reappears on scroll up (JS).

## mobile_nav

- `slide_in_drawer` - Panel slides in from the right.
- `dropdown_panel` - Panel drops down under the bar.
- `fullscreen_overlay` - Full-viewport overlay with large stacked links.

## hero

- `split_text_left_visual_right` - Two columns: headline/intro/CTAs left, decorative visual right.
- `split_visual_left_text_right` - Two columns: decorative visual left, text right.
- `centered_stack` - Centred eyebrow, headline, intro, CTA row; visual (if any) below.
- `full_bleed_band` - Full-width coloured/gradient band with centred or left text.
- `editorial_left_headline` - Very large left-aligned headline over ~8 columns, small intro beneath, no visual.
- `headline_plus_stat_strip` - Headline block followed by a horizontal strip of 3-4 key stats.
- `card_on_pattern` - Content sits in a card/panel placed over a patterned or tinted background.
- `two_tone_split` - Background split vertically into two colours; text on one side, visual on the other.
- `minimal_headline_only` - Short headline + one line + one CTA, generous whitespace, nothing else.
- `offset_overlap` - Text block overlaps the edge of a tinted panel/visual for depth.

## hero_visual

- `abstract_gradient_panel` - Rounded panel filled with a soft multi-stop gradient.
- `geometric_shapes_svg` - Inline SVG of circles/rects/lines in palette colours.
- `dot_grid_pattern` - CSS radial-gradient dot grid panel, optionally with one accent shape.
- `stat_cards` - 2-4 small cards showing numbers/labels instead of an image.
- `browser_mockup_frame` - CSS 'browser window' frame containing placeholder UI blocks (no screenshot).
- `icon_grid` - Grid of inline SVG icons in tinted tiles.
- `line_art_svg` - Simple stroked inline SVG illustration (abstract, few paths).
- `ring_stack` - Concentric rings / arcs in inline SVG or CSS borders.
- `none` - No visual; typography carries the hero.

## section

- `features` - Grid of 3-6 feature blocks (icon or number, title, 1-2 lines).
- `services` - Service cards, often with a 'learn more' link each.
- `values` - 3-4 principles/values in a row or list.
- `how_it_works` - Numbered steps, horizontal on desktop, vertical on mobile.
- `showcase` - Grid of CSS-only tiles (gradient/pattern) representing work or products; no images.
- `about` - Two-column narrative + a few facts or a pull quote.
- `stats` - Row of large numbers with labels.
- `trusted_by_text` - Text-only 'trusted by' list of plausible client names in muted type (no logos).
- `testimonials` - 1-3 quote cards or one large quote.
- `team` - Grid of people cards using initials in tinted circles instead of photos.
- `pricing` - 2-3 tier cards, one highlighted.
- `comparison_table` - Simple table comparing options or plans.
- `faq` - Accordion or two-column Q&A.
- `cta_band` - Full-width call-to-action band with headline + button.
- `contact` - Contact details + a static (non-submitting, mailto or disabled) form.

## footer

- `multi_column_4` - Brand + 3 link columns, bottom legal row.
- `multi_column_3_with_brand` - Brand blurb left, 2 link columns right.
- `minimal_single_row` - One row: brand, few links, copyright.
- `centered_stack` - Centred logo, link row, copyright.
- `big_cta_then_links` - Large CTA statement first, then compact link row.
- `split_brand_left_links_right` - Brand/contact left, links right, thin top border.

## divider

- `none` - Sections butt together; alternate backgrounds.
- `thin_rule` - 1px full-width rule between sections.
- `diagonal_skew` - Section edges skewed with clip-path or transform.
- `wave_svg` - Inline SVG wave along section boundary.
- `curve_svg` - Inline SVG gentle single curve.
- `offset_band` - Background band starts/ends offset from the content.

## card

- `flat_bordered` - 1px border, no shadow.
- `elevated_soft` - No border, soft shadow.
- `elevated_strong` - Stronger layered shadow.
- `glass` - Translucent surface with backdrop blur (dark or gradient backgrounds only).
- `borderless_tinted` - No border; subtly tinted background.
- `accent_top_border` - 3-4px accent bar along the top.
- `accent_left_border` - 3-4px accent bar along the left.
- `numbered_minimal` - No box; large number/index + text.

## button_shape

- `pill` - border-radius 999px
- `rounded_md` - 8-12px radius
- `rounded_sm` - 3-5px radius
- `square` - 0 radius

## button_hover

- `darken` - Background darkens.
- `lift` - translateY(-2px) + stronger shadow.
- `fill_sweep` - Background colour sweeps in from one side.
- `outline_to_solid` - Outline button fills on hover.
- `glow` - Soft coloured box-shadow glow (dark themes).
- `underline_slide` - Text links: underline grows in from the left.

## section_pattern

- `none` - Plain backgrounds.
- `dots` - Faint radial-gradient dot grid on alternate sections.
- `grid_lines` - Faint 1px CSS grid lines.
- `diagonal_stripes` - Very faint repeating-linear-gradient stripes.
- `corner_blob` - One large low-opacity blob (border-radius 40% 60%...) tucked in a section corner.

## css_delivery

- `inline` - All CSS in a <style> block in each HTML file.
- `external` - All CSS in the external file named in delivery.css_file.
- `split` - Critical CSS (reset, layout, hero) inline; the rest in delivery.css_file.

## js_delivery

- `inline` - JS in a <script> at end of body.
- `external` - JS in delivery.js_file.
- `none` - No JavaScript at all.

## css_naming

- `bem` - block__element--modifier classes.
- `semantic` - Plain descriptive classes (.hero, .card, .site-header).
- `utility_light` - Semantic components plus a small set of utility classes (.grid-3, .mt-lg, .text-muted).

## motion_level

- `none` - No animation beyond colour transitions.
- `subtle` - Short fades/transitions, one reveal effect.
- `moderate` - Reveals, counters, hover lifts; still restrained.

## Font stacks

- `humanist_sans`: `system-ui, -apple-system, "Segoe UI", Roboto, Ubuntu, Cantarell, "Noto Sans", sans-serif`
- `grotesk_sans`: `"Helvetica Neue", Helvetica, Arial, "Liberation Sans", "Nimbus Sans", sans-serif`
- `geometric_sans`: `"Trebuchet MS", "Segoe UI", Ubuntu, "DejaVu Sans", Verdana, sans-serif`
- `rounded_sans`: `ui-rounded, "Segoe UI", "Trebuchet MS", Ubuntu, "DejaVu Sans", sans-serif`
- `condensed_sans`: `"Arial Narrow", "Roboto Condensed", "Liberation Sans Narrow", "Helvetica Neue", sans-serif`
- `transitional_serif`: `Georgia, "Times New Roman", "Liberation Serif", "DejaVu Serif", serif`
- `old_style_serif`: `Garamond, "EB Garamond", "Palatino Linotype", Palatino, "URW Palladio L", "Book Antiqua", serif`
- `modern_serif`: `"Palatino Linotype", Palatino, "Book Antiqua", "URW Palladio L", Georgia, serif`
- `didone_serif`: `"Bodoni MT", Didot, "Hoefler Text", "Baskerville Old Face", Baskerville, Georgia, serif`
- `mono`: `ui-monospace, "SF Mono", Menlo, Consolas, "DejaVu Sans Mono", "Liberation Mono", monospace`

## Palette keys

`bg`, `surface` (cards / alternate sections), `text`, `text_muted`, `border`, `primary`, `primary_hover`, `primary_soft` (tints, badges), `on_primary` (text on primary), `accent`, `on_accent`, `gradient` (2 stops). `dark_band` (only when mode is light_dark_sections) gives colours for the dark sections. `contrast` reports WCAG ratios that were verified at generation time.
