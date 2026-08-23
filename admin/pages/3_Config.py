from pathlib import Path
import yaml
import streamlit as st
from lib.r2 import get_client, R2_BUCKET

st.set_page_config(page_title="Config", page_icon="⚙️", layout="wide")
st.title("⚙️ Configuracao ativa")
st.caption("Somente leitura. Pra alterar, edite os arquivos no repo e faca push.")

REPO_ROOT = Path(__file__).parent.parent.parent
CONFIG_PY = REPO_ROOT / "etl" / "src" / "config.py"


def load_mock_yaml() -> str | None:
    try:
        obj = get_client().get_object(Bucket=R2_BUCKET, Key="state/mock_client.yaml")
        return obj["Body"].read().decode("utf-8")
    except Exception:
        local = REPO_ROOT / "etl" / "config" / "mock_client.yaml"
        if local.exists():
            return local.read_text(encoding="utf-8")
        return None


st.subheader("etl/src/config.py")
if CONFIG_PY.exists():
    st.code(CONFIG_PY.read_text(encoding="utf-8"), language="python")
else:
    st.warning("config.py nao encontrado (rodando fora do repo?)")

st.divider()

st.subheader("mock_client.yaml (cliente + SKUs mock)")
raw = load_mock_yaml()
if raw:
    cfg = yaml.safe_load(raw)
    st.write("**Vendedor mock**")
    st.json(cfg.get("seller", {}))

    st.write("**SKUs monitorados**")
    st.dataframe(cfg.get("skus", []), use_container_width=True, hide_index=True)

    with st.expander("YAML raw"):
        st.code(raw, language="yaml")
else:
    st.warning("mock_client.yaml nao encontrado nem no R2 nem local")
