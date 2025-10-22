
from pathlib import Path
import streamlit as st



def page_header(assets_dir):
    st.set_page_config(
        page_title="Quinex",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    st.logo(
        assets_dir / "logo_ice_2_bottom_en_white.svg",
        size="large",
        link="https://www.fz-juelich.de/en/ice/ice-2",
        icon_image= assets_dir / "logo_fzj.svg",
    )

    # Use quinex logo instead of title.
    st.image(
        assets_dir / "quinex_logo.svg",
        width=400,
    )
    st.markdown("Quinex is a tool for **qu**antitative **in**formation **ex**traction from text.")