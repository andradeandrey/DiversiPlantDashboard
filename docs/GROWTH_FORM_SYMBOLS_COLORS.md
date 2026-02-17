# Growth Form — Symbols & Colors (Figma)

Reference for the 11 growth form categories used across the DiversiPlant dashboard.
Updated 2026-02-17 to match Figma design (node 3257-8735).

## Color Map

| Growth Form | PT Label | EN Label | Hex Color | Swatch |
|---|---|---|---|---|
| tree | Árvore | Tree | `#2a43d1` | ![#2a43d1](https://placehold.co/20x20/2a43d1/2a43d1) |
| shrub | Arbusto | Shrub | `#0095c6` | ![#0095c6](https://placehold.co/20x20/0095c6/0095c6) |
| subshrub | Sub-arbusto | Subshrub | `#612e14` | ![#612e14](https://placehold.co/20x20/612e14/612e14) |
| forb | Herbácea | Forb | `#d77d28` | ![#d77d28](https://placehold.co/20x20/d77d28/d77d28) |
| graminoid | Gramíneas e afins | Graminoid | `#633096` | ![#633096](https://placehold.co/20x20/633096/633096) |
| palm | Palmeira | Palm | `#63a355` | ![#63a355](https://placehold.co/20x20/63a355/63a355) |
| liana | Trepadeira lenhosa | Liana | `#be2843` | ![#be2843](https://placehold.co/20x20/be2843/be2843) |
| vine | Trepadeira herbácea | Vine | `#cc4fb9` | ![#cc4fb9](https://placehold.co/20x20/cc4fb9/cc4fb9) |
| scrambler | Rasteira | Scrambler | `#017201` | ![#017201](https://placehold.co/20x20/017201/017201) |
| bamboo | Bambu | Bamboo | `#fd2f6d` | ![#fd2f6d](https://placehold.co/20x20/fd2f6d/fd2f6d) |
| other | Outro | Other | `#171717` | ![#171717](https://placehold.co/20x20/171717/171717) |

## SVG Symbols (white stroke on colored badge)

Each icon is an inline SVG rendered inside a colored badge (`background-color` = hex above, `color: white`).

| Growth Form | Icon | Description |
|---|---|---|
| tree | ⏐○ | Circle (crown) + vertical line (trunk) |
| shrub | ⬠ | Pentagon outline |
| subshrub | ▫ | Square outline |
| forb | △ | Triangle outline |
| graminoid | \| | Vertical bar (thin rectangle) |
| palm | ψ | Trunk with two spreading fronds |
| bamboo | ∨ | Inverted chevron (V shape) |
| liana | ∿ | S-curve (sinuous line) |
| vine | ⌇ | Curve with dot at tip |
| scrambler | ∿∿ | Zigzag horizontal line |
| other | ⊘ | Circle with diagonal slash |

## SVG Source Code

```html
<!-- tree: circle + trunk -->
<svg width="10" height="18" viewBox="0 0 10 20">
  <circle cx="5" cy="5" r="4" fill="none" stroke="white" stroke-width="1.8"/>
  <line x1="5" y1="9" x2="5" y2="20" stroke="white" stroke-width="1.8"/>
</svg>

<!-- shrub: pentagon -->
<svg width="16" height="16" viewBox="0 0 16 16">
  <polygon points="8,1.5 14.9,5.5 12.3,13.5 3.7,13.5 1.1,5.5"
           fill="none" stroke="white" stroke-width="1.8"/>
</svg>

<!-- subshrub: square -->
<svg width="16" height="16" viewBox="0 0 16 16">
  <rect x="2" y="2" width="12" height="12"
        fill="none" stroke="white" stroke-width="2" rx="0.8"/>
</svg>

<!-- forb: triangle -->
<svg width="16" height="16" viewBox="0 0 20 18">
  <polygon points="10,1 19,17 1,17"
           fill="none" stroke="white" stroke-width="2"/>
</svg>

<!-- graminoid: vertical bar -->
<svg width="4" height="16" viewBox="0 0 4 16">
  <rect x="1" y="0" width="2" height="16" fill="white" rx="1"/>
</svg>

<!-- palm: trunk + fronds -->
<svg width="14" height="18" viewBox="0 0 14 20">
  <line x1="7" y1="20" x2="7" y2="7" stroke="white" stroke-width="1.8"/>
  <path d="M7,7 L2,1" stroke="white" stroke-width="1.8"
        fill="none" stroke-linecap="round"/>
  <path d="M7,7 L12,1" stroke="white" stroke-width="1.8"
        fill="none" stroke-linecap="round"/>
</svg>

<!-- bamboo: inverted chevron -->
<svg width="14" height="16" viewBox="0 0 14 16">
  <path d="M1,2 L7,14 L13,2" fill="none" stroke="white"
        stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>

<!-- liana: S-curve -->
<svg width="6" height="18" viewBox="0 0 6 20">
  <path d="M3,0 C0,5 6,10 3,15 C1.5,17.5 3,20 3,20"
        fill="none" stroke="white" stroke-width="2" stroke-linecap="round"/>
</svg>

<!-- vine: curve + dot -->
<svg width="10" height="18" viewBox="0 0 10 20">
  <path d="M2,20 C2,10 8,10 8,2" fill="none" stroke="white"
        stroke-width="2" stroke-linecap="round"/>
  <circle cx="8" cy="2" r="2" fill="white"/>
</svg>

<!-- scrambler: zigzag -->
<svg width="22" height="8" viewBox="0 0 22 8">
  <path d="M1,4 L5,1 L9,7 L13,1 L17,7 L21,4" fill="none" stroke="white"
        stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>

<!-- other: circle + slash -->
<svg width="16" height="16" viewBox="0 0 16 16">
  <circle cx="8" cy="8" r="6" fill="none" stroke="white" stroke-width="2"/>
  <line x1="4" y1="12" x2="12" y2="4" stroke="white" stroke-width="2"/>
</svg>
```

## Where colors are defined

| File | Variable | Purpose |
|---|---|---|
| `custom_ui/tab_03_species.py` | `_SYMBOLS`, `_GF_SVGS` | Symbols modal badges |
| `custom_server/server_app.py` | `COLOR` (line ~49) | Legacy growth form color dict |
| `custom_server/server_app.py` | `colors` (line ~152) | Legacy `color_mapping` array |
| `custom_server/server_app.py` | `ECHARTS_EMOJIS` (line ~156) | Chart legend Unicode chars |
| `custom_server/server_app.py` | `gf_colors` (line ~904) | ECharts scatter plot colors |
| `custom_server/server_app.py` | `gf_display_pt` (line ~1226) | Chart PT display names |
| `data/ui.css` | `.tree`, `.shrub`, etc. | CSS text color classes |
