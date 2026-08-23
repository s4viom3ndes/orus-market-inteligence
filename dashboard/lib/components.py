"""Componentes HTML custom seguindo o design Modernist do Orus."""
from html import escape
import streamlit as st
from lib.theme import ACCENT, ACCENT_TINT_BG, ACCENT_TINT_TEXT, DIVIDER, NEUTRAL_200, TEXT

TAG_STYLES = {
    "neutral": f"background:#f8f4f4;color:#444141;",
    "accent": f"background:{ACCENT_TINT_BG};color:{ACCENT_TINT_TEXT};",
    "outline": f"background:transparent;color:{ACCENT};border:1px solid {ACCENT};",
}


def tag(label: str, style: str = "neutral", size_px: int = 10) -> str:
    css = TAG_STYLES.get(style, TAG_STYLES["neutral"])
    return (
        f'<span style="{css}padding:3px 8px;font-size:{size_px}.5px;'
        f'text-transform:uppercase;letter-spacing:.06em;font-weight:800;font-family:Archivo,sans-serif">'
        f'{escape(label)}</span>'
    )


def bar_list_header(label: str, bar_col_label: str, right_label: str,
                    bar_width: int = 220, right_width: int = 230):
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:12px;padding-bottom:8px;'
        f'font-size:11px;text-transform:uppercase;letter-spacing:0.06em;opacity:0.55">'
        f'<div style="flex:1;min-width:0">{escape(label)}</div>'
        f'<div style="width:{bar_width}px;flex:none">{escape(bar_col_label)}</div>'
        f'<div style="width:{right_width}px;flex:none;text-align:right">{escape(right_label)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def bar_list_row(label: str, value: float, max_value: float, meta_right: str,
                 sublabel: str | None = None, bar_width: int = 220, right_width: int = 230,
                 tag_html: str | None = None):
    pct = min(100, (value / max_value * 100)) if max_value > 0 else 0
    label_block = f'<div style="font-size:14px;font-weight:800">{escape(label)}</div>'
    if sublabel:
        label_block += f'<div style="font-size:11px;opacity:0.55">{escape(sublabel)}</div>'
    tag_part = f'<div style="width:76px;flex:none">{tag_html}</div>' if tag_html else ""

    value_fmt = f"{value:,.0f}".replace(",", ".") if value >= 100 else f"{value:,.2f}"

    st.markdown(
        f'<div style="display:flex;align-items:center;gap:12px;padding:11px 0;border-bottom:1px solid {DIVIDER}">'
        f'<div style="flex:1;min-width:0">{label_block}</div>'
        f'{tag_part}'
        f'<div style="width:{bar_width}px;flex:none;display:flex;align-items:center;gap:10px">'
        f'  <div style="flex:1;height:22px;background:{NEUTRAL_200};min-width:60px">'
        f'    <div style="width:{pct:.1f}%;height:100%;background:{ACCENT}"></div>'
        f'  </div>'
        f'  <div style="width:60px;flex:none;font-family:Archivo,sans-serif;font-weight:800;font-size:15px">{value_fmt}</div>'
        f'</div>'
        f'<div style="width:{right_width}px;flex:none;text-align:right;font-size:12px;opacity:0.65">{escape(meta_right)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def horizontal_percent_bar(label: str, pct: float):
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">'
        f'<div style="width:130px;font-size:12px">{escape(label)}</div>'
        f'<div style="flex:1;height:16px;background:{NEUTRAL_200}">'
        f'  <div style="width:{pct:.1f}%;height:100%;background:{ACCENT}"></div>'
        f'</div>'
        f'<div style="width:40px;font-size:12px;text-align:right">{pct:.0f}%</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def vip_zone_open(title: str = "Seus SKUs monitorados",
                  subtitle: str = "acompanhamento exclusivo do cliente"):
    st.markdown(
        f'<div style="background:{ACCENT_TINT_BG};padding:28px 28px 8px;margin-bottom:8px">'
        f'<div style="display:flex;align-items:baseline;gap:10px;margin-bottom:18px">'
        f'  <div style="font-family:Archivo,sans-serif;font-weight:800;font-size:11px;letter-spacing:0.08em;'
        f'       text-transform:uppercase;color:{ACCENT_TINT_TEXT}">{escape(title)}</div>'
        f'  <div style="font-size:11px;opacity:0.55">— {escape(subtitle)}</div>'
        f'</div>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;padding-bottom:20px">',
        unsafe_allow_html=True,
    )


def vip_zone_close():
    st.markdown('</div></div>', unsafe_allow_html=True)


def sku_card(kicker: str, title: str, status_label: str, status_style: str,
             my_price: float, winner_price: float, gap: float,
             n_competitors: int, position: int):
    gap_color = ACCENT if gap > 0 else TEXT
    gap_sign = "+" if gap > 0 else ""
    st.markdown(
        f'<div style="background:#fff;padding:24px;border-top:4px solid {ACCENT};box-shadow:0 1px 2px rgba(0,0,0,.04)">'
        f'  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px">'
        f'    <div>'
        f'      <div style="font-size:10px;text-transform:uppercase;letter-spacing:.08em;opacity:0.6;font-weight:800">{escape(kicker)}</div>'
        f'      <div style="font-size:19px;font-weight:800;margin-top:4px">{escape(title)}</div>'
        f'    </div>'
        f'    {tag(status_label, status_style)}'
        f'  </div>'
        f'  <div style="display:flex;gap:28px;margin-bottom:14px">'
        f'    <div>'
        f'      <div style="font-size:10.5px;opacity:0.55;text-transform:uppercase;letter-spacing:0.05em">Meu preço</div>'
        f'      <div style="font-family:Archivo,sans-serif;font-weight:800;font-size:23px">R$ {my_price:,.2f}</div>'
        f'    </div>'
        f'    <div>'
        f'      <div style="font-size:10.5px;opacity:0.55;text-transform:uppercase;letter-spacing:0.05em">Winner</div>'
        f'      <div style="font-family:Archivo,sans-serif;font-weight:800;font-size:23px">R$ {winner_price:,.2f}</div>'
        f'    </div>'
        f'    <div>'
        f'      <div style="font-size:10.5px;opacity:0.55;text-transform:uppercase;letter-spacing:0.05em">Gap</div>'
        f'      <div style="font-family:Archivo,sans-serif;font-weight:800;font-size:23px;color:{gap_color}">{gap_sign}R$ {abs(gap):,.2f}</div>'
        f'    </div>'
        f'  </div>'
        f'  <div style="border-top:1px solid {DIVIDER};margin:0 0 10px"></div>'
        f'  <div style="display:flex;justify-content:space-between;font-size:12.5px;opacity:0.65">'
        f'    <div>{n_competitors} concorrentes</div>'
        f'    <div>Posição atual: {position}º</div>'
        f'  </div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def competitor_row(rank: int, seller: str, price: float, delta_vs_you: float, is_you: bool = False):
    bg = f"background:{ACCENT_TINT_BG};border-left:4px solid {ACCENT}" if is_you else ""
    you_tag = f' {tag("VOCÊ", "accent")}' if is_you else ""
    if is_you:
        delta_text = "sua oferta"
    elif delta_vs_you < 0:
        delta_text = f'R$ {abs(delta_vs_you):,.2f} mais barato que você'
    else:
        delta_text = f'R$ {delta_vs_you:,.2f} mais caro que você'

    st.markdown(
        f'<div style="display:flex;align-items:center;gap:16px;padding:11px 14px;border-bottom:1px solid {DIVIDER};{bg}">'
        f'  <div style="width:32px;font-family:Archivo,sans-serif;font-weight:800;font-size:16px;opacity:0.6">{rank}º</div>'
        f'  <div style="flex:1;min-width:0;font-size:14px;font-weight:600">{escape(str(seller))}{you_tag}</div>'
        f'  <div style="width:120px;font-family:Archivo,sans-serif;font-weight:800;font-size:16px;text-align:right">R$ {price:,.2f}</div>'
        f'  <div style="width:200px;font-size:12px;opacity:0.65;text-align:right">{delta_text}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def reversion_callout(margin_headroom: float, target_price: float, current_price: float):
    delta_today = current_price - target_price
    st.markdown(
        f'<div style="background:{ACCENT_TINT_BG};border-left:4px solid {ACCENT};padding:24px;margin-top:16px">'
        f'  <div style="display:flex;gap:40px;align-items:center">'
        f'    <div style="flex:1">'
        f'      <div style="font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;font-weight:800;color:{ACCENT_TINT_TEXT};margin-bottom:8px">Como reverter</div>'
        f'      <div style="font-size:13px;line-height:1.5">Você tem <b>R$ {margin_headroom:,.2f}</b> de folga acima do seu min_price. '
        f'      Baixar pra <b>R$ {target_price:,.2f}</b> te coloca em 1º e mantém margem defensável.</div>'
        f'    </div>'
        f'    <div style="text-align:right">'
        f'      <div style="font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;opacity:0.55">Preço-alvo</div>'
        f'      <div style="font-family:Archivo,sans-serif;font-weight:800;font-size:32px;color:{ACCENT_TINT_TEXT}">R$ {target_price:,.2f}</div>'
        f'      <div style="font-size:12px;opacity:0.65">−R$ {delta_today:,.2f} vs hoje</div>'
        f'    </div>'
        f'  </div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def locked_callout(min_price: float, winner_price: float):
    st.markdown(
        f'<div style="background:transparent;border:1px solid {ACCENT};padding:24px;margin-top:16px">'
        f'  <div style="font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;font-weight:800;color:{ACCENT};margin-bottom:8px">Situação travada</div>'
        f'  <div style="font-size:13px;line-height:1.5">O winner está em <b>R$ {winner_price:,.2f}</b>, abaixo do seu min_price de <b>R$ {min_price:,.2f}</b>. '
        f'  Não é possível recuperar buy box só com preço — reavalie custos/logística (ex: aderir ao Full) ou aceite 2º lugar como estratégia.</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
