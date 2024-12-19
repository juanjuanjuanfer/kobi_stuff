import streamlit as st
import utils
import requests
import psycopg2

# Connection variables for the Postgres database
USER = "postgres.injfjstsivnxlkaznjje"
PASSWORD = "SerP@r@Gener@r22"
HOST = "aws-0-us-west-1.pooler.supabase.com"
PORT = "5432"
DBNAME = "postgres"

# Streamlit page configuration
st.set_page_config(
    page_title="KTBX Data Tool",
    page_icon="📊",
    layout="wide",
)

st.title("Herramienta de manejo de datos para KoboToolbox")

# Check if assets have already been retrieved in the session state
if "assets" not in st.session_state:
    with st.spinner("Cargando..."):
        # Get assets and store them in session state
        st.session_state["assets"] = utils.set_connection()

# Retrieve the assets from session state
assets = st.session_state["assets"]

# Show selectbox with the assets
selection = st.selectbox("Seleccione un formulario", list(assets.keys()))

# Show the selected asset
st.write(f"Formulario seleccionado: {selection}")

# Use session state to manage form data retrieval
if "form_data" not in st.session_state:
    st.session_state["form_data"] = None

if st.button("Obtener datos del formulario"):
    with st.spinner("Cargando..."):
        # Retrieve the form data and store it in session state
        st.session_state["form_data"] = utils.get_form_data(assets[selection])

# Display the form data if available
if st.session_state["form_data"] is not None:
    st.dataframe(st.session_state["form_data"][0], width=2000)
    st.dataframe(st.session_state["form_data"][1], width=2000)
    form_id = assets[selection]  # or any unique form identifier
    query = utils.generate_create_table_queries(st.session_state["form_data"][0], st.session_state["form_data"][1], form_id=form_id)


    st.write("**SQL para crear tablas:**")
    st.code(query, language='sql')

    secrets = utils.get_secrets()
    kobo_url = secrets['kobo']['KOBO_API_TOKEN']

    headers = {
        "Authorization": f"Token {kobo_url}"
    }
    url = f"https://eu.kobotoolbox.org/api/v2/assets/{assets[selection]}/data.json"
    resp = requests.get(url, headers=headers)
    data = resp.json()

    st.write("**Generando INSERT statements...**")
    inserts = utils.generate_insert_queries(st.session_state["form_data"][0], st.session_state["form_data"][1], data, kpi_url="eu.kobotoolbox.org", asset=assets[selection], token=kobo_url, form_id=form_id)
    st.code(inserts, language='sql')

    # Button to execute queries
    if st.button("Ejecutar queries en la base de datos"):
        with st.spinner("Ejecutando queries..."):
            try:
                # Connect to the database
                conn = psycopg2.connect(
                    user=USER,
                    password=PASSWORD,
                    host=HOST,
                    port=PORT,
                    dbname=DBNAME
                )
                conn.autocommit = True
                cur = conn.cursor()

                # Execute table creation queries
                # The creation queries are separated by double newlines in utils.generate_create_table_queries
                for create_stmt in query.split("\n\n"):
                    create_stmt = create_stmt.strip()
                    if create_stmt:
                        cur.execute(create_stmt)

                # Execute insert queries
                # Similarly, insert statements are separated by newlines
                for insert_stmt in inserts.split("\n"):
                    insert_stmt = insert_stmt.strip()
                    if insert_stmt:
                        cur.execute(insert_stmt)

                cur.close()
                conn.close()
                st.success("Se ejecutaron los queries correctamente en la base de datos!")
            except Exception as e:
                st.error(f"Error al ejecutar queries: {e}")
