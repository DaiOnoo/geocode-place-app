
import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import os

st.title("📍 Google Maps API XY座標取得アプリ（履歴＋住所比較付き）")

api_key = st.text_input("🔑 Google Maps APIキー", type="password")
mode = st.radio("使用するAPIを選択", ["Geocoding API（住所）", "Places API（施設名＋住所）"])
DEFAULT_BUDGET = 200.0
budget = st.number_input("💰 月間の上限予算（USD）", min_value=0.0, value=DEFAULT_BUDGET, step=10.0)

uploaded_file = st.file_uploader("📄 CSVアップロード（列名：施設名, 住所）", type="csv")

# 単価設定
COST_PER_REQUEST = {
    "Geocoding API（住所）": 0.005,
    "Places API（施設名＋住所）": 0.017
}
LOG_FILE = "usage_log.csv"

# 履歴読み込みと予算残
usage_df = pd.DataFrame(columns=["日時", "API", "件数", "金額"])
if os.path.exists(LOG_FILE):
    usage_df = pd.read_csv(LOG_FILE)
    used_total = usage_df["金額"].sum()
else:
    used_total = 0.0
remaining_budget = budget - used_total
st.info(f"📊 使用済み金額: ${used_total:.2f} / 残り予算: ${remaining_budget:.2f}")

if st.button("📜 利用履歴を表示"):
    if usage_df.empty:
        st.write("履歴はまだありません。")
    else:
        st.dataframe(usage_df)

if uploaded_file and api_key:
    df = pd.read_csv(uploaded_file)
    required_cols = ["住所"] if mode == "Geocoding API（住所）" else ["施設名", "住所"]
    if not all(col in df.columns for col in required_cols):
        st.error(f"必要な列が不足しています: {required_cols}")
    else:
        cost_per = COST_PER_REQUEST[mode]
        total_rows = len(df)
        estimated_cost = total_rows * cost_per
        st.success(f"📦 対象件数: {total_rows:,} 件 → 想定費用: ${estimated_cost:.2f}")
        if estimated_cost > remaining_budget:
            st.error("❌ 残り予算を超えるため、処理を中止しました。")
        else:
            if st.button("🚀 実行開始"):
                df["検索キーワード"] = ""
                df["取得結果_住所"] = ""
                df["取得結果_緯度"] = None
                df["取得結果_経度"] = None
                request_count = 0

                for i, row in df.iterrows():
                    if mode == "Geocoding API（住所）":
                        keyword = row["住所"]
                        url = "https://maps.googleapis.com/maps/api/geocode/json"
                        params = {"address": keyword, "key": api_key, "language": "ja"}
                    else:
                        keyword = f"{row['施設名']} {row['住所']}"
                        url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
                        params = {
                            "input": keyword,
                            "inputtype": "textquery",
                            "fields": "geometry,formatted_address",
                            "key": api_key,
                            "language": "ja"
                        }

                    df.at[i, "検索キーワード"] = keyword
                    res = requests.get(url, params=params).json()
                    request_count += 1

                    result = None
                    if mode == "Geocoding API（住所）":
                        if res.get("status") == "OK":
                            result = res["results"][0]
                    else:
                        if res.get("candidates"):
                            result = res["candidates"][0]

                    if result:
                        loc = result["geometry"]["location"]
                        formatted = result.get("formatted_address", "")
                        df.at[i, "取得結果_緯度"] = loc["lat"]
                        df.at[i, "取得結果_経度"] = loc["lng"]
                        df.at[i, "取得結果_住所"] = formatted

                spent = request_count * cost_per
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                new_log = pd.DataFrame([{
                    "日時": now,
                    "API": mode,
                    "件数": request_count,
                    "金額": spent
                }])
                new_log.to_csv(LOG_FILE, mode="a", header=not os.path.exists(LOG_FILE), index=False)
                st.success(f"✅ 完了: {request_count} 件 → 課金見込: ${spent:.2f}")
                st.dataframe(df)
                csv = df.to_csv(index=False, encoding="utf-8-sig")
                st.download_button("📥 結果CSVをダウンロード", csv, "result_comparison.csv", "text/csv")
