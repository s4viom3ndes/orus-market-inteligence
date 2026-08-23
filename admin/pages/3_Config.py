from pathlib import Path
import yaml
import streamlit as st

st.set_page_config(page_title="Config", page_icon="⚙️", layout="wide")
st.title("⚙️ Configuracao ativa")
st.caption("Somente leitura. Pra alterar, edite os arquivos no repo e faca push.")

REPO_ROOT = Path(__file__).parent.parent.parent
CONFIG_PY = REPO_ROOT / "etl" / "src" / "config.py"
MOCK_YAML = REPO_ROOT / "etl" / "config" / "mock_client.yaml"

st.subheader("etl/src/config.py")
if CONFIG_PY.exists():
    st.code(CONFIG_PY.read_text(encoding="utf-8"), language="python")
else:
    st.warning("config.py nao encontrado (rodando fora do repo?)")

st.divider()

st.subheader("etl/config/mock_client.yaml (cliente + SKUs mock)")
if MOCK_YAML.exists():
    cfg = yaml.safe_load(MOCK_YAML.read_text(encoding="utf-8"))
    st.write("**Vendedor mock**")
    st.json(cfg.get("seller", {}))

    st.write("**SKUs monitorados**")
    st.dataframe(cfg.get("skus", []), use_container_width=True, hide_index=True)

    with st.expander("YAML raw"):
        st.code(MOCK_YAML.read_text(encoding="utf-8"), language="yaml")
else:
    st.warning("mock_client.yaml nao encontrado")
