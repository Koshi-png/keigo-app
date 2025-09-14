# -*- coding: utf-8 -*-
import re
import io
import pandas as pd
import streamlit as st

st.set_page_config(page_title="敬語抽出アプリ", page_icon="🗣️", layout="centered")

# ===== 敬語パターン（必要に応じて拡張してください） =====
RESPECT_WORDS = [
    r"なさる", r"いらっしゃる", r"おいでになる", r"おっしゃる",
    r"ご覧になる", r"召し上がる", r"お越しになる", r"お帰りになる",
    r"ご存じ(?:だ|です)", r"くださる", r"お休みになる",
]
HUMBLE_WORDS = [
    r"いたす", r"存じ(?:ます|上げる|上げております)",
    r"申し(?:ます|上げる|上げております)", r"拝見(?:します|いたします)",
    r"伺(?:います|いました|わせて)", r"差し上げ(?:ます|ました)",
    r"承知(?:しました|いたしました|しております)",
    r"頂(?:きます|けます)", r"いただ(?:きます|けます|いております)",
    r"参(?:り|ります)",
]
# 伸ばしや「笑」「w」を挟んだ語尾、空白、各種記号をゆるく許可するテール
TAIL = r"[ー〜~ｗ笑]*[\s　]*[。．.!！?？、,：:；;…‥」』）\)\]】〉》]*"

POLITE_PATTERNS = [
    # です/ます 系 + （か/ね/よ）任意 + TAIL（文中/文末どちらでも可）
    rf"(?:です|ます|でした|でしょう|ません|でございます|ござい(?:ます|ません))(?:か|ね|よ)?{TAIL}",
    # 「ください」単体も丁寧表現として拾いたい場合（任意）
    rf"ください{TAIL}",
]

BEAUTIFIER_PATTERNS = [
    r"(?:お|ご)[一-龥ぁ-んァ-ン]{1,6}(?:いたします|します|ください|です)"
]

RESPECT_RE    = [re.compile(p) for p in RESPECT_WORDS]
HUMBLE_RE     = [re.compile(p) for p in HUMBLE_WORDS]
POLITE_RE     = [re.compile(p) for p in POLITE_PATTERNS]
BEAUTIFIER_RE = [re.compile(p) for p in BEAUTIFIER_PATTERNS]

CANDIDATE_TEXT_COLS = ["セリフ", "台詞", "text", "発話", "発言", "utterance", "line"]

def _hits(patterns, s: str):
    hits = []
    for pat in patterns:
        found = pat.findall(s)
        if found:
            hits.extend([f if isinstance(f, str) else "".join(f) for f in found])
    return hits

def classify_keigo(text: str):
    if not isinstance(text, str) or not text.strip():
        return {
            "is_keigo": False,
            "respect_cnt": 0, "humble_cnt": 0, "polite_cnt": 0, "beautifier_cnt": 0,
            "respect_hits": "", "humble_hits": "", "polite_hits": "", "beautifier_hits": ""
        }
    r_hits = _hits(RESPECT_RE, text)
    h_hits = _hits(HUMBLE_RE,  text)
    p_hits = _hits(POLITE_RE,  text)
    b_hits = _hits(BEAUTIFIER_RE, text)
    return {
        "is_keigo": any([r_hits, h_hits, p_hits, b_hits]),
        "respect_cnt": len(r_hits), "humble_cnt": len(h_hits),
        "polite_cnt": len(p_hits), "beautifier_cnt": len(b_hits),
        "respect_hits": "、".join(r_hits), "humble_hits": "、".join(h_hits),
        "polite_hits": "、".join(p_hits), "beautifier_hits": "、".join(b_hits),
    }

def build_output_excel(df_all: pd.DataFrame, df_keigo: pd.DataFrame) -> bytes:
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df_all.to_excel(writer, sheet_name="classified_all", index=False)
        df_keigo.to_excel(writer, sheet_name="keigo_only", index=False)
    return bio.getvalue()

# ===== UI =====
st.title("🗣️ 敬語抽出アプリ")
st.caption("Excelを読み込み、敬語らしい発話を抽出して新しいExcelとして出力します。")

uploaded = st.file_uploader("Excelファイル（.xlsx）を選択", type=["xlsx"])

if uploaded:
    # シート名の検出
    try:
        xl = pd.ExcelFile(uploaded)
        sheet_name = st.selectbox("シートを選択", xl.sheet_names, index=0)
        df = xl.parse(sheet_name)
    except Exception as e:
        st.error(f"読み込みエラー: {e}")
        st.stop()

    st.write("プレビュー（先頭5行）")
    st.dataframe(df.head())

    # テキスト列の候補と選択
    default_text_col = None
    for cand in CANDIDATE_TEXT_COLS:
        if cand in df.columns:
            default_text_col = cand
            break
    text_col = st.selectbox(
        "セリフ（テキスト）列を選択",
        options=list(df.columns),
        index=list(df.columns).index(default_text_col) if default_text_col in df.columns else 0
    )

    # 任意：話者列によるフィルタ
    with st.expander("話者などのフィルタ（任意）"):
        filter_col = st.selectbox("フィルタ対象の列を選択（任意）", options=["（使わない）"] + list(df.columns))
        filter_val = None
        if filter_col != "（使わない）":
            uniq = ["（未選択）"] + sorted([str(v) for v in df[filter_col].dropna().astype(str).unique()])
            filter_val = st.selectbox("値を選択（任意）", options=uniq)

    # 実行
    if st.button("敬語判定を実行"):
        work_df = df.copy()

        # フィルタ適用
        if filter_col != "（使わない）" and filter_val and filter_val != "（未選択）":
            work_df = work_df[work_df[filter_col].astype(str) == filter_val].copy()

        if text_col not in work_df.columns:
            st.error(f"選択した列 '{text_col}' が見つかりません。")
            st.stop()

        # 判定
        results = work_df[text_col].apply(classify_keigo).apply(pd.Series)
        out_all = pd.concat([work_df.reset_index(drop=True), results], axis=1)
        out_keigo = out_all[out_all["is_keigo"]].copy()

        st.success(f"判定完了：全行 {len(out_all)} 件 / 敬語を含む行 {len(out_keigo)} 件")
        st.write("敬語のみプレビュー（先頭20件）")
        st.dataframe(out_keigo.head(20))

        # ダウンロード（Excel / CSV）
        xlsx_bytes = build_output_excel(out_all, out_keigo)
        st.download_button(
            label="📥 Excel をダウンロード（classified_all / keigo_only）",
            data=xlsx_bytes,
            file_name="keigo_result.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        st.download_button(
            label="📥 CSV（keigo_only だけ）をダウンロード",
            data=out_keigo.to_csv(index=False).encode("utf-8-sig"),
            file_name="keigo_only.csv",
            mime="text/csv",
        )

    with st.expander("⚙️ 高度な設定（正規表現の追加）"):
        st.write("行頭・行末のスペース削除は自動で行われます。追加の敬語パターンがあれば改行区切りで入力してください。")
        extra_respect = st.text_area("尊敬語 追加パターン（正規表現・改行区切り）", "")
        extra_humble  = st.text_area("謙譲語 追加パターン（正規表現・改行区切り）", "")
        extra_polite  = st.text_area("丁寧語 文末 追加パターン（正規表現・改行区切り）", "")
        extra_beauty  = st.text_area("美化語 追加パターン（正規表現・改行区切り）", "")

        if st.button("追加パターンを適用"):
            def _lines(s): 
                return [l.strip() for l in s.splitlines() if l.strip()]
            try:
                RESPECT_RE.extend([re.compile(p) for p in _lines(extra_respect)])
                HUMBLE_RE.extend([re.compile(p) for p in _lines(extra_humble)])
                POLITE_RE.extend([re.compile(p) for p in _lines(extra_polite)])
                BEAUTIFIER_RE.extend([re.compile(p) for p in _lines(extra_beauty)])
                st.success("追加パターンを適用しました。上の『敬語判定を実行』を再実行してください。")
            except re.error as e:
                st.error(f"正規表現エラー: {e}")

else:
    st.info("上のボタンから .xlsx ファイルを選んでください。")
