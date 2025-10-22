from pathlib import Path
from datetime import datetime
import streamlit as st
from header import page_header

     
cwd = Path(__file__).parent.resolve()
assets_dir = cwd.parents[3] / "assets"
page_header(assets_dir)

pg = st.navigation(
    [
        st.Page(
            "pages/get_started.py",
            title="Get started",
            icon=":material/home:",
        ),
        st.Page(
            "pages/results.py",
            title="Results",
            icon=":material/analytics:",
        ),        
    ]
)
pg.run()
getting_started_column, docs_column = st.columns([0.4, 0.6], gap="large")

# Footer
st.markdown(
    """
    <style>
        .footer {
            position: absolute;
            bottom: -10rem;
            width: 100%;
            text-align: right;
            padding: 1rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="footer">'
    '<a href="https://www.fz-juelich.de/en/legal-notice">Imprint</a>'
    '&emsp;'
    f'<a href="https://www.fz-juelich.de/ice/ice-2">Jülich Systems Analysis</a> &copy; {datetime.now().year}'   
    '</div>',
    unsafe_allow_html=True,
)

# Set mode to light mode
st.markdown(
    """
    <style>
        .reportview-container .main .block-container {
            color: #111;
        }
    </style>
    """,
    unsafe_allow_html=True,
)