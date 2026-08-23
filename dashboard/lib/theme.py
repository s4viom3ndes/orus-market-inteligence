import streamlit as st

BG = "#f3f2f2"
SURFACE = "#eae9e9"
TEXT = "#201e1d"
ACCENT = "#ec3013"
ACCENT_TINT_BG = "#fff2ef"
ACCENT_TINT_TEXT = "#7c1405"
DIVIDER = "rgba(32,30,29,.4)"
NEUTRAL_200 = "#dedcdc"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@400;600;800&display=swap');

html, body,
[data-testid="stAppViewContainer"], [data-testid="stHeader"],
[data-testid="stMain"] {{
  font-family: 'Archivo', sans-serif !important;
  background: {BG} !important;
  color: {TEXT} !important;
}}

h1, h2, h3, h4, h5 {{
  font-family: 'Archivo', sans-serif !important;
  font-weight: 800 !important;
  letter-spacing: -0.015em !important;
  color: {TEXT} !important;
}}

[data-testid="stSidebar"] {{
  background: {BG} !important;
  border-right: 2px solid {DIVIDER} !important;
}}
[data-testid="stSidebar"] * {{ font-family: 'Archivo', sans-serif !important; color: {TEXT}; }}
[data-testid="stSidebarNav"] a,
[data-testid="stPageLink-NavLink"],
[data-testid="stSidebar"] a[data-testid*="stPageLink"] {{
  font-weight: 400 !important;
  color: {TEXT} !important;
  border-left: 3px solid transparent !important;
  padding: 8px 12px !important;
  text-decoration: none !important;
  display: block !important;
}}
[data-testid="stSidebarNav"] a[aria-current="page"],
[data-testid="stPageLink-NavLink"][aria-current="page"],
[data-testid="stSidebar"] a[data-testid*="stPageLink"][aria-current="page"] {{
  color: {ACCENT} !important;
  font-weight: 800 !important;
  border-left: 3px solid {ACCENT} !important;
  background: {SURFACE} !important;
}}
[data-testid="stSidebarNav"] a:hover,
[data-testid="stPageLink-NavLink"]:hover,
[data-testid="stSidebar"] a[data-testid*="stPageLink"]:hover {{
  background: {SURFACE} !important;
}}
[data-testid="stSidebar"] [data-testid="stPageLink"] p {{
  font-weight: inherit !important;
  color: inherit !important;
  margin: 0 !important;
}}

[data-testid="stMetricValue"] {{
  font-family: 'Archivo', sans-serif !important;
  font-weight: 800 !important;
  font-size: 32px !important;
  color: {TEXT} !important;
}}
[data-testid="stMetricLabel"] {{
  text-transform: uppercase !important;
  letter-spacing: .06em !important;
  font-size: 11px !important;
  opacity: .55 !important;
  color: {TEXT} !important;
}}
[data-testid="stMetricDelta"] {{ font-family: 'Archivo', sans-serif !important; }}

hr {{ border: none !important; border-top: 2px solid {DIVIDER} !important; margin: 24px 0 !important; }}

div[data-testid="stDataFrame"] * {{ border-radius: 0 !important; font-family: 'Archivo', sans-serif !important; }}
div[data-testid="stDataFrame"] table thead th {{
  text-transform: uppercase !important;
  font-size: 11px !important;
  letter-spacing: .08em !important;
  border-bottom: 2px solid {DIVIDER} !important;
  background: {BG} !important;
}}
div[data-testid="stDataFrame"] table td {{ border-bottom: 1px solid {DIVIDER} !important; }}

button, [data-baseweb="select"], [data-baseweb="input"], [data-baseweb="popover"] > div {{
  border-radius: 0 !important;
}}
button[kind="primary"], button[data-testid="baseButton-primary"] {{
  background: {ACCENT} !important;
  border-color: {ACCENT} !important;
  color: white !important;
  font-weight: 800 !important;
}}
[data-baseweb="select"] > div {{ border-radius: 0 !important; border: 1px solid {DIVIDER} !important; }}

/* slider accent */
[data-baseweb="slider"] div[role="slider"] {{ background: {ACCENT} !important; }}
[data-baseweb="slider"] > div > div > div {{ background: {ACCENT} !important; }}

/* expanders zero-radius */
[data-testid="stExpander"] {{ border-radius: 0 !important; border: 1px solid {DIVIDER} !important; }}
[data-testid="stExpander"] summary {{ font-family: 'Archivo', sans-serif !important; font-weight: 600 !important; }}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


BRAND_MARK_HTML = f"""
<div style="display:flex;align-items:center;gap:12px;padding:4px 4px 20px 4px">
  <div style="position:relative;width:26px;height:26px;flex:none">
    <div style="position:absolute;top:0;left:0;width:8px;height:8px;border-top:2px solid {ACCENT};border-left:2px solid {ACCENT}"></div>
    <div style="position:absolute;top:0;right:0;width:8px;height:8px;border-top:2px solid {ACCENT};border-right:2px solid {ACCENT}"></div>
    <div style="position:absolute;bottom:0;left:0;width:8px;height:8px;border-bottom:2px solid {ACCENT};border-left:2px solid {ACCENT}"></div>
    <div style="position:absolute;bottom:0;right:0;width:8px;height:8px;border-bottom:2px solid {ACCENT};border-right:2px solid {ACCENT}"></div>
    <div style="position:absolute;top:50%;left:50%;width:5px;height:5px;background:{ACCENT};transform:translate(-50%,-50%)"></div>
  </div>
  <div>
    <div style="font-family:'Archivo',sans-serif;font-weight:800;font-size:17px;letter-spacing:0.02em">ORUS</div>
    <div style="font-size:10px;letter-spacing:0.06em;text-transform:uppercase;opacity:0.5">Market Intelligence</div>
  </div>
</div>
"""


NAV_PAGES = [
    ("app.py", "Visão Geral"),
    ("pages/1_Mercado.py", "Mercado"),
    ("pages/2_Buy_Box.py", "Buy Box"),
    ("pages/3_Repricer.py", "Repricer"),
    ("pages/4_Trends.py", "Trends"),
]


def sidebar_header():
    st.sidebar.markdown(BRAND_MARK_HTML, unsafe_allow_html=True)
    st.sidebar.markdown(f'<hr style="border-top:2px solid {DIVIDER};margin:0 0 12px">',
                        unsafe_allow_html=True)


def sidebar_nav():
    for path, label in NAV_PAGES:
        st.sidebar.page_link(path, label=label)


def sidebar_footer(seller_name: str, seller_id: int | str):
    st.sidebar.markdown(
        f'<hr style="border-top:2px solid {DIVIDER};margin:16px 0 12px">'
        f'<div style="padding:0 4px;font-size:10px;letter-spacing:0.06em;text-transform:uppercase;opacity:0.5;margin-bottom:4px">Conta conectada</div>'
        f'<div style="padding:0 4px;font-size:14px;font-weight:800">{seller_name}</div>'
        f'<div style="padding:0 4px;font-size:11px;opacity:0.5;font-family:ui-monospace,monospace">seller_id {seller_id}</div>',
        unsafe_allow_html=True,
    )


def setup(page_title: str, seller_name: str = "VariedadesSB (mock)", seller_id: int | str = 2692951735):
    st.set_page_config(page_title=f"Orus - {page_title}", page_icon="◾", layout="wide")
    inject_css()
    sidebar_header()
    sidebar_nav()
    sidebar_footer(seller_name, seller_id)
