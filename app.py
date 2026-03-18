"""KF-CSVQuery — CSV to SQL query tool powered by DuckDB."""

import io

import duckdb
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="KF-CSVQuery",
    page_icon="🔍",
    layout="wide",
)

from components.header import render_header
from components.footer import render_footer
from components.i18n import t

# --- Header ---
render_header()
st.info("💻 " + t("desktop_recommended"))

# --- Preset Queries ---
PRESET_QUERIES = {
    "row_count": "SELECT COUNT(*) AS row_count FROM data",
    "first_10": "SELECT * FROM data LIMIT 10",
    "column_stats": "SELECT\n  COUNT(*) AS total_rows,\n  COUNT(DISTINCT *) AS distinct_rows\nFROM data",
    "group_by_example": "-- Edit column_name to match your data\nSELECT column_name, COUNT(*) AS cnt\nFROM data\nGROUP BY column_name\nORDER BY cnt DESC\nLIMIT 20",
    "sum_example": "-- Edit numeric_col / group_col to match your data\nSELECT group_col, SUM(numeric_col) AS total\nFROM data\nGROUP BY group_col\nORDER BY total DESC",
}

# --- File Upload ---
uploaded_file = st.file_uploader(t("upload_prompt"), type=["csv", "tsv"])

if uploaded_file is not None:
    # Read CSV with pandas
    try:
        raw_bytes = uploaded_file.getvalue()
        # Try comma first, then tab
        try:
            df_pandas = pd.read_csv(io.BytesIO(raw_bytes))
        except Exception:
            df_pandas = pd.read_csv(io.BytesIO(raw_bytes), sep="\t")

        st.success(t("file_loaded").format(rows=df_pandas.shape[0], cols=df_pandas.shape[1]))

        # Show preview
        with st.expander(t("data_preview"), expanded=True):
            st.dataframe(df_pandas.head(100), use_container_width=True)

        # Show column info
        with st.expander(t("column_info")):
            col_info = pd.DataFrame({
                "column": df_pandas.columns,
                "dtype": [str(d) for d in df_pandas.dtypes],
                "null_count": [df_pandas[c].isnull().sum() for c in df_pandas.columns],
            })
            st.dataframe(col_info, use_container_width=True)

        # Register in DuckDB
        con = duckdb.connect(":memory:")
        con.register("data", df_pandas)

        st.markdown(f"### {t('sql_editor')}")

        # Preset query selector
        preset_labels = {
            "row_count": t("preset_row_count"),
            "first_10": t("preset_first_10"),
            "column_stats": t("preset_column_stats"),
            "group_by_example": t("preset_group_by"),
            "sum_example": t("preset_sum"),
        }
        preset_choice = st.selectbox(
            t("preset_label"),
            options=[""] + list(preset_labels.keys()),
            format_func=lambda x: t("preset_select_placeholder")
            if x == ""
            else preset_labels.get(x, x),
        )

        default_query = (
            PRESET_QUERIES.get(preset_choice, "SELECT * FROM data LIMIT 10")
            if preset_choice
            else "SELECT * FROM data LIMIT 10"
        )

        query = st.text_area(
            t("query_input"),
            value=default_query,
            height=150,
            key="sql_query",
        )

        if st.button(t("run_query"), type="primary"):
            if query.strip():
                try:
                    with st.spinner(t("processing")):
                        result = con.execute(query).fetchdf()

                    st.markdown(f"**{t('result_rows').format(count=len(result))}**")
                    st.dataframe(result, use_container_width=True)

                    # Store result for download and charting
                    st.session_state["query_result"] = result

                except Exception as e:
                    st.error(f"{t('query_error')}: {e}")

        # Download & Chart section (show if we have results)
        if "query_result" in st.session_state and st.session_state["query_result"] is not None:
            result = st.session_state["query_result"]

            col_dl, col_spacer = st.columns([1, 3])
            with col_dl:
                csv_bytes = result.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    label=t("download_result"),
                    data=csv_bytes,
                    file_name="query_result.csv",
                    mime="text/csv",
                )

            # --- Chart Section ---
            st.markdown(f"### {t('chart_title')}")

            if len(result.columns) >= 2:
                chart_col1, chart_col2, chart_col3 = st.columns(3)
                with chart_col1:
                    chart_type = st.selectbox(
                        t("chart_type"),
                        options=["bar", "line"],
                        format_func=lambda x: t(f"chart_{x}"),
                    )
                with chart_col2:
                    x_col = st.selectbox(t("chart_x"), options=result.columns.tolist())
                with chart_col3:
                    numeric_cols = result.select_dtypes(include="number").columns.tolist()
                    if numeric_cols:
                        y_col = st.selectbox(t("chart_y"), options=numeric_cols)
                    else:
                        y_col = st.selectbox(t("chart_y"), options=result.columns.tolist())

                if st.button(t("chart_draw")):
                    try:
                        chart_data = result[[x_col, y_col]].set_index(x_col)
                        if chart_type == "bar":
                            st.bar_chart(chart_data)
                        else:
                            st.line_chart(chart_data)
                    except Exception as e:
                        st.error(f"{t('chart_error')}: {e}")
            else:
                st.info(t("chart_need_cols"))

        con.close()

    except Exception as e:
        st.error(f"{t('load_error')}: {e}")

else:
    st.info(t("no_file"))

# --- Footer ---
render_footer(libraries=["DuckDB — in-memory SQL engine", "pandas — CSV parsing and data manipulation"])
