---
title: kf-csv-query
emoji: 🚀
colorFrom: green
colorTo: blue
sdk: streamlit
sdk_version: 1.44.1
app_file: app.py
pinned: false
---

# KF-CSVQuery

> CSVをアップロードしてSQLで自由に集計。Excelマクロはもう不要。

## The Problem

Excelマクロが崩壊して動かない、VLOOKUPが壊れた、集計が毎回手作業。SQLなら安定して動き、誰でも読めるクエリで再現性のある集計ができます。

## How It Works

1. CSVファイルをアップロード
2. DuckDBのインメモリデータベースに自動登録（テーブル名: `data`）
3. SQLエディタでクエリを書いて実行
4. 結果をCSVでダウンロード、または棒グラフ/折れ線グラフで可視化

## Libraries Used

- **DuckDB** — 高速インメモリSQL分析エンジン
- **Polars** — 高速DataFrameライブラリ（CSV読み込み・型推論）

## Development

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deployment

Hosted on [Hugging Face Spaces](https://huggingface.co/spaces/mitoi/kf-csv-query).

---

Part of the [KaleidoFuture AI-Driven Development Research](https://kaleidofuture.com) — proving that everyday problems can be solved with existing libraries, no AI model required.
