import datetime
import streamlit as st
import polars as pl
from lib.r2 import list_objects, get_json

st.set_page_config(page_title="Notificacoes", page_icon="📧", layout="wide")
st.title("📧 Historico de Notificacoes")
st.caption("Todas as tentativas de envio de email (sucesso ou falha) sao logadas em R2.")

objs = list_objects("notification_log/")
if not objs:
    st.info("Nenhuma notificacao enviada ainda. Rode `python -m jobs.test_email --to seu@email.com` pra testar.")
    st.stop()

rows = []
for o in sorted(objs, key=lambda x: x["last_modified"], reverse=True)[:200]:
    try:
        d = get_json(o["key"])
    except Exception:
        continue
    rows.append({
        "when": datetime.datetime.fromtimestamp(d["at"]).strftime("%Y-%m-%d %H:%M:%S"),
        "to": d["to"],
        "subject": d["subject"],
        "sent": "✅" if d["sent"] else "❌",
        "error": d.get("error") or "",
    })

df = pl.DataFrame(rows)
st.dataframe(df, use_container_width=True, hide_index=True)

st.divider()
st.subheader("Estatisticas")
c1, c2, c3 = st.columns(3)
c1.metric("Total tentativas", df.height)
c2.metric("Sucesso", df.filter(pl.col("sent") == "✅").height)
c3.metric("Falha", df.filter(pl.col("sent") == "❌").height)
