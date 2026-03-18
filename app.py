"""KF-CSVQuery — CSV to SQL query tool powered by DuckDB."""

import io
import json

import duckdb
import openpyxl
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

        # --- Auto Analysis: Summary stats for numeric columns ---
        numeric_cols_all = df_pandas.select_dtypes(include="number").columns.tolist()
        if numeric_cols_all:
            with st.expander(t("auto_analysis_title"), expanded=True):
                stats_rows = []
                for col in numeric_cols_all:
                    stats_rows.append({
                        t("auto_analysis_column"): col,
                        "COUNT": int(df_pandas[col].count()),
                        "SUM": df_pandas[col].sum(),
                        "AVG": round(df_pandas[col].mean(), 2),
                        "MIN": df_pandas[col].min(),
                        "MAX": df_pandas[col].max(),
                    })
                stats_df = pd.DataFrame(stats_rows)
                st.dataframe(stats_df, use_container_width=True)

        # Register in DuckDB
        con = duckdb.connect(":memory:")
        con.register("data", df_pandas)

        # --- Mode tabs ---
        tab_easy, tab_sql = st.tabs([t("easy_mode"), t("sql_mode")])

        # =============================================
        # Easy Mode (No-code aggregation wizard)
        # =============================================
        with tab_easy:
            st.markdown(f"### {t('easy_mode_title')}")
            st.caption(t("easy_mode_desc"))

            all_columns = df_pandas.columns.tolist()

            ecol1, ecol2, ecol3 = st.columns(3)
            with ecol1:
                group_col = st.selectbox(
                    t("easy_group_by"),
                    options=all_columns,
                    key="easy_group",
                )
            with ecol2:
                agg_col_options = numeric_cols_all if numeric_cols_all else all_columns
                agg_col = st.selectbox(
                    t("easy_agg_column"),
                    options=agg_col_options,
                    key="easy_agg_col",
                )
            with ecol3:
                agg_methods = ["SUM", "AVG", "COUNT", "MAX", "MIN"]
                agg_method = st.selectbox(
                    t("easy_agg_method"),
                    options=agg_methods,
                    key="easy_agg_method",
                )

            # Build and execute query automatically
            alias_name = f"{agg_method.lower()}_{agg_col}"
            easy_query = (
                f'SELECT "{group_col}", {agg_method}("{agg_col}") AS "{alias_name}"\n'
                f'FROM data\n'
                f'GROUP BY "{group_col}"\n'
                f'ORDER BY "{alias_name}" DESC'
            )

            with st.expander(t("easy_generated_sql")):
                st.code(easy_query, language="sql")

            try:
                easy_result = con.execute(easy_query).fetchdf()
                st.markdown(f"**{t('result_rows').format(count=len(easy_result))}**")
                st.dataframe(easy_result, use_container_width=True)

                # Store for download / chart
                st.session_state["easy_result"] = easy_result

            except Exception as e:
                st.error(f"{t('query_error')}: {e}")

            # Download buttons for easy mode result
            if "easy_result" in st.session_state and st.session_state["easy_result"] is not None:
                easy_res = st.session_state["easy_result"]
                dl1, dl2, dl3 = st.columns(3)
                with dl1:
                    csv_bytes = easy_res.to_csv(index=False).encode("utf-8-sig")
                    st.download_button(
                        label=t("download_result"),
                        data=csv_bytes,
                        file_name="easy_result.csv",
                        mime="text/csv",
                        key="easy_dl_csv",
                    )
                with dl2:
                    xlsx_buf = io.BytesIO()
                    with pd.ExcelWriter(xlsx_buf, engine="openpyxl") as writer:
                        easy_res.to_excel(writer, index=False, sheet_name="Result")
                    st.download_button(
                        label=t("download_xlsx"),
                        data=xlsx_buf.getvalue(),
                        file_name="easy_result.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="easy_dl_xlsx",
                    )

        # =============================================
        # SQL Mode (existing functionality)
        # =============================================
        with tab_sql:
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

            # --- Template save / load ---
            tmpl_col1, tmpl_col2 = st.columns(2)
            with tmpl_col1:
                if query.strip():
                    template_data = json.dumps(
                        {"name": "My Query", "sql": query.strip()},
                        ensure_ascii=False,
                        indent=2,
                    )
                    st.download_button(
                        label=t("template_save"),
                        data=template_data.encode("utf-8"),
                        file_name="query_template.json",
                        mime="application/json",
                        key="tmpl_save",
                    )
            with tmpl_col2:
                tmpl_file = st.file_uploader(
                    t("template_load"),
                    type=["json"],
                    key="tmpl_upload",
                )
                if tmpl_file is not None:
                    try:
                        tmpl = json.loads(tmpl_file.getvalue().decode("utf-8"))
                        if "sql" in tmpl:
                            st.session_state["loaded_template_sql"] = tmpl["sql"]
                            st.info(t("template_loaded").format(name=tmpl.get("name", "?")))
                        else:
                            st.warning(t("template_invalid"))
                    except Exception as e:
                        st.error(f"{t('template_invalid')}: {e}")

            # Show loaded template button
            if "loaded_template_sql" in st.session_state:
                if st.button(t("template_apply"), key="tmpl_apply"):
                    st.session_state["sql_query"] = st.session_state["loaded_template_sql"]
                    del st.session_state["loaded_template_sql"]
                    st.rerun()

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

                col_dl1, col_dl2, col_spacer = st.columns([1, 1, 2])
                with col_dl1:
                    csv_bytes = result.to_csv(index=False).encode("utf-8-sig")
                    st.download_button(
                        label=t("download_result"),
                        data=csv_bytes,
                        file_name="query_result.csv",
                        mime="text/csv",
                    )
                with col_dl2:
                    xlsx_buf = io.BytesIO()
                    with pd.ExcelWriter(xlsx_buf, engine="openpyxl") as writer:
                        result.to_excel(writer, index=False, sheet_name="Result")
                    st.download_button(
                        label=t("download_xlsx"),
                        data=xlsx_buf.getvalue(),
                        file_name="query_result.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
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
render_footer(libraries=["DuckDB — in-memory SQL engine", "pandas — CSV parsing and data manipulation", "openpyxl — Excel export"], repo_name="kf-csv-query")
