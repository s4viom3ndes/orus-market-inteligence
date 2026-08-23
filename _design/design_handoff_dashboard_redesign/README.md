# Handoff: Orus Dashboard Redesign (Streamlit)

## Overview
Redesign of the existing Orus Streamlit dashboard (`dashboard/app.py` + `dashboard/pages/*.py`) in the Modernist visual language: flat, architectural, Archivo type, a single red accent, zero border-radius, strong 2px rules. Goal: make the same data (market snapshots, Buy Box comparison, trends) easier to read for managerial decisions.

## About the Design Files
The bundled file `Orus Dashboard Redesign.dc.html` is a **design reference built in HTML/CSS** — a clickable prototype (sidebar nav switches between the 4 screens) showing exact layout, spacing, colors and typography. It is **not** code to copy into the app. The task is to **recreate this look inside the existing Streamlit codebase** using Streamlit's theming + custom CSS injection (see "Streamlit implementation notes" below), keeping all current data logic in `dashboard/lib/r2_reader.py` and the page files untouched.

## Fidelity
**High-fidelity.** Colors, type, spacing and component patterns below are final — implement them pixel-close using the CSS provided, not as loose inspiration.

## Design tokens
- Background `#f3f2f2`, surface (cards/sidebar hover) `#eae9e9`, text `#201e1d`, accent `#ec3013`.
- Accent tint for callouts/badges: `#fff2ef` (bg) / `#7c1405` (text on tint) — used for the "VIP" SKU zone and the "Como reverter" callout.
- Divider: `#201e1d` at 40% opacity, always 2px for major rules, 1px for table row rules.
- Font: **Archivo** for everything (headings weight 800, body 400). Google Fonts: `family=Archivo:wght@400;600;800`.
- Radius: **0 everywhere** — no rounded corners on any element, ever.
- Status tags: neutral bg `#f8f4f4`/text `#444141` (GANHANDO), accent-tint bg `#fff2ef`/text `#7c1405` (PODE RECUPERAR), accent outline 1px + accent text (TRAVADO).

## Screens / Views
All 4 screens share a persistent left sidebar (264px, 2px right border, brand mark + "ORUS" + "MARKET INTELLIGENCE" caption, nav list, active item = accent text + 3px accent left border + surface background, footer showing connected seller "VariedadesSB · seller_id 183920441").

### 1. Visão Geral (`app.py`)
- 4 metrics in a row (label 11px uppercase muted above, value 32px Archivo 800): Ofertas coletadas, Produtos de catálogo, Vendedores únicos, Categorias.
- 2px divider.
- "Distribuição por categoria": **horizontal bar list**, not a table — one row per category: name (bold, fixed 1fr min-width:0), a fixed-width (220px) bar (neutral-200 track, accent fill, width % of the top category's count) + count label, and a right-aligned 230px column with "produtos · vendedores · preço médio". This replaced a raw dataframe after client feedback that a table wasn't intuitive for a fast read.
- "Buy Box winners": same bar-list pattern, ranked by `visits_30d`, with a small `tag` (neutral=full, outline=cross_docking) for `shipping_logistic_type` and trailing price+reviews text. (An earlier scatter-plot attempt was rejected — bar lists are the established pattern here.)
- Two-column footer: a manual horizontal-bar breakdown of `shipping_logistic_type` share among winners, and a compact trending-keywords table.

### 2. Mercado por Categoria (`pages/1_Mercado.py`)
- A category "selector" styled as a `.input`-like trigger (bordered box, label + value + ▾) — static in the mock, must be a real `st.selectbox` in the app, just visually skinned.
- 3 metrics row (Ofertas, Produtos distintos, Vendedores).
- "Produtos mais competidos nessa categoria" — standard table (`n_sellers`, `min_price`, `max_price`, `avg_price`, `visits_30d`).
- "Ofertas nessa categoria" — full offers table per the source columns (product_name, seller_id, price, logistic_type, condition, rank, buy_box, visits_30d, reviews_count). **This screen's plain-table pattern is approved as-is — keep it in the design system unchanged.**

### 3. Buy Box Monitor (`pages/2_Buy_Box.py`)
- Title + one-line caption.
- **"Seus SKUs monitorados"**: a VIP treatment — the client's own SKUs get a dedicated tinted zone (`background:#fff2ef`, padding) containing a 2-column card grid (one `.card` per SKU), each card: 4px accent top border, kicker = SKU code, title = product name, status tag top-right, then 3 stat blocks (Meu preço / Winner / Gap — gap in accent red when losing, default color at R$0,00), divider, footer row (concorrentes count · posição atual). This is a deliberate departure from tables — client's own SKUs must read as "special", everything else stays tabular/bar-based.
- "Ofertas concorrentes por SKU": a SKU picker (same `.input`-styled trigger), then a **comparison list** (not a plain table): each competitor row shows rank, seller, price, and a right-aligned delta line ("R$ X,XX mais barato que você"); the client's own row is visually distinct (accent-tinted background, 4px accent left border, "VOCÊ" tag). Below it, a **"Como reverter" callout** (accent-tinted box, accent left border): left side explains the margin headroom vs. `min_price`, right side shows the exact target price to take rank 1 and the delta vs. today, in large Archivo 800 type. This whole block exists specifically to answer "where am I losing and how do I fix it" — keep the recommended-price computation server-side (see State/Data below).

### 4. Trends (`pages/3_Trends.py`)
- Caption with snapshot timestamp.
- Two columns: "Top 25 do site" table (rank, keyword) and "Trends por categoria" (table, or an info box when ML doesn't expose category trends for current roots).
- "Histórico de snapshots" table (when, key, size_kb).

## Interactions & Behavior
- Sidebar nav = Streamlit's native multi-page nav (`st.Page`/`pages/` folder) — style it to match (flush-left labels, accent active state), don't rebuild navigation in JS.
- Category selector, SKU selector = real `st.selectbox`, CSS-skinned to match the `.input` look.
- No animations/transitions needed; this is a data dashboard, not a marketing site.
- "Como reverter" target price: `min(current_winner_price - 0.01, my_current_price - some_step)`, clamped to be `>= min_price`; if the computed target would be `< min_price`, show the TRAVADO state instead of a callout (mirrors the existing `buy_box_monitor.py` status logic — don't invent a new rule, reuse `services/buy_box_monitor.py`'s thresholds).

## State Management
No new state beyond what the pages already compute from `load_latest_market_snapshot()` / `load_buy_box_state()`. The only new derived values are: bar-chart percentages (row value ÷ max value in the same table) and the "Como reverter" target price described above — both pure functions over existing dataframes, computed in Python before rendering, not new data sources.

## Streamlit implementation notes
Streamlit can't take arbitrary component styling out of the box; use this two-layer approach:

1. **`.streamlit/config.toml`** (theme base):
```toml
[theme]
primaryColor = "#ec3013"
backgroundColor = "#f3f2f2"
secondaryBackgroundColor = "#eae9e9"
textColor = "#201e1d"
font = "sans serif"
```

2. **`dashboard/lib/theme.py`** — one `inject_css()` function called at the top of every page (`app.py` and each `pages/*.py`, right after `st.set_page_config`), injecting Archivo + the flattening/override rules via `st.markdown(..., unsafe_allow_html=True)`:
```python
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@400;600;800&display=swap');
html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
  font-family: 'Archivo', sans-serif; background: #f3f2f2; color: #201e1d;
}
h1, h2, h3, h4 { font-family: 'Archivo', sans-serif; font-weight: 800; letter-spacing: -0.015em; }
[data-testid="stSidebar"] { background: #f3f2f2; border-right: 2px solid rgba(32,30,29,.4); }
[data-testid="stSidebarNav"] a { font-weight: 400; color: #201e1d; }
[data-testid="stSidebarNav"] a[aria-current="page"] { color: #ec3013; font-weight: 800;
  border-left: 3px solid #ec3013; }
[data-testid="stMetricValue"] { font-family: 'Archivo', sans-serif; font-weight: 800; }
[data-testid="stMetricLabel"] { text-transform: uppercase; letter-spacing: .06em; font-size: 11px; opacity: .55; }
hr { border-top: 2px solid rgba(32,30,29,.4) !important; }
div[data-testid="stDataFrame"] * { border-radius: 0 !important; }
div[data-testid="stDataFrame"] table thead th {
  text-transform: uppercase; font-size: 11px; letter-spacing: .08em;
  border-bottom: 2px solid rgba(32,30,29,.4) !important; }
div[data-testid="stDataFrame"] table td { border-bottom: 1px solid rgba(32,30,29,.4) !important; }
button, [data-baseweb="select"], [data-baseweb="input"] { border-radius: 0 !important; }
</style>
"""
def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)
```
Verify the exact `data-testid` selectors against the installed Streamlit version (they change between releases) — inspect the rendered DOM and adjust before shipping.

3. **Bar lists, VIP SKU cards, comparison rows, "Como reverter" callout**: these need real HTML, not `st.dataframe`/`st.metric` — build them as small helper functions in `dashboard/lib/components.py` that return an HTML string (f-strings over the dataframe rows, mirroring the exact markup patterns in the mock) and render via `st.markdown(html, unsafe_allow_html=True)`. Do **not** try to force this look out of `st.dataframe` — it can't render per-cell tags/bars reliably; the mock's markup is the source of truth for the HTML these helpers should emit.
4. Status tags (`tag-neutral`/`tag-accent`/`tag-outline`) → reuse the same 3 span styles (bg/text/border combinations under "Design tokens" above) inside the HTML helpers, driven by the existing status strings from `services/buy_box_monitor.py`.

## Assets
No images/icons. The "brand mark" (small square with 4 corner brackets + center dot, drawn with plain `div`s/borders) is the only graphic element — recreate it as a tiny reusable HTML snippet in the sidebar, not an image file.

## Files
- `Orus Dashboard Redesign.dc.html` — the full clickable design reference (open in any browser; click sidebar items to switch screens).
