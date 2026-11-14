"""Streamlit demo for fraudulent job-posting triage."""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import streamlit as st

from fraud_detector import FraudDetector, threshold_rows


st.set_page_config(
    page_title="Job Fraud Review Assistant",
    page_icon="🔎",
    layout="wide",
)

st.markdown(
    """
    <style>
    .block-container {max-width: 1120px; padding-top: 2.2rem;}
    .hero {
        padding: 1.3rem 1.5rem;
        border-radius: 16px;
        background: #f4f1e9;
        border-left: 7px solid #c55a11;
        margin-bottom: 1.2rem;
    }
    .hero h1 {margin: 0 0 .35rem 0; color: #14213d;}
    .hero p {margin: 0; color: #595f69; font-size: 1.02rem;}
    .score-box {
        padding: 1rem 1.2rem;
        border-radius: 14px;
        background: #eaf1f8;
        border: 1px solid #c8d7e7;
    }
    .score-value {font-size: 2.2rem; font-weight: 700; color: #14213d;}
    .warning {
        padding: .8rem 1rem;
        border-radius: 10px;
        background: #fff5e8;
        color: #6b3a00;
        font-size: .92rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def load_detector() -> FraudDetector:
    return FraudDetector()


detector = load_detector()

st.markdown(
    """
    <div class="hero">
      <h1>虚假招聘审核助手</h1>
      <p>按风险分数给招聘广告排序，帮助人工审核团队优先处理高风险内容。</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.subheader("审核优先级阈值")
    st.dataframe(
        pd.DataFrame(threshold_rows(detector.thresholds)),
        hide_index=True,
        use_container_width=True,
    )
    st.caption(
        "阈值来自验证集 top-k 排名。分数是排序值，不是概率；"
        "分数越高，越应该优先人工复核。"
    )
    st.divider()
    st.caption(
        "验证集：PR-AUC 0.896 | 审核前 5% 的 Recall 0.859\n\n"
        "测试集：PR-AUC 0.947 | 审核前 5% 的 Recall 0.887"
    )

single_tab, batch_tab, about_tab = st.tabs(
    ["单条评估", "批量 CSV", "模型说明"]
)

with single_tab:
    left, right = st.columns([1.45, 1])
    with left:
        title = st.text_input("职位标题", placeholder="例如：Data Entry Clerk")
        company_profile = st.text_area(
            "公司介绍",
            height=100,
            placeholder="粘贴公司背景或招聘公司描述……",
        )
        description = st.text_area(
            "职位描述",
            height=150,
            placeholder="粘贴主要工作内容……",
        )
        requirements = st.text_area(
            "职位要求",
            height=100,
            placeholder="粘贴学历、经验、技能要求……",
        )
        benefits = st.text_area(
            "福利信息",
            height=80,
            placeholder="粘贴薪酬或福利信息……",
        )
        evaluate = st.button("评估审核优先级", type="primary", use_container_width=True)

    with right:
        st.subheader("结果")
        if evaluate:
            try:
                score, priority = detector.score_record(
                    {
                        "title": title,
                        "company_profile": company_profile,
                        "description": description,
                        "requirements": requirements,
                        "benefits": benefits,
                    }
                )
                st.markdown(
                    f"""
                    <div class="score-box">
                      <div>风险排序分数</div>
                      <div class="score-value">{score:.3f}</div>
                      <div><strong>建议队列：{priority}</strong></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.progress(
                    min(1.0, max(0.0, (score + 2.3) / 3.8)),
                    text="仅用于相对排序，不代表概率",
                )
            except ValueError as error:
                st.warning(str(error))
        else:
            st.info("填写至少一个文本字段后开始评估。")
        st.markdown(
            '<div class="warning">结果仅用于辅助人工审核。'
            "不得作为自动拒绝、处罚或违法认定的唯一依据。</div>",
            unsafe_allow_html=True,
        )

with batch_tab:
    st.subheader("批量评分")
    st.write(
        "CSV 可以包含 `job_id`、`title`、`company_profile`、`description`、"
        "`requirements`、`benefits` 列。缺失文本会被视为空字符串。"
    )
    uploaded_file = st.file_uploader("上传职位 CSV", type=["csv"])
    if uploaded_file is not None:
        try:
            frame = pd.read_csv(uploaded_file)
            st.caption(f"已读取 {len(frame):,} 条记录")
            preview = frame.head(5)
            st.dataframe(preview, hide_index=True, use_container_width=True)
            if st.button("开始批量评分", type="primary"):
                result = detector.score_frame(frame)
                st.success(f"已完成 {len(result):,} 条广告评分")
                st.dataframe(result, hide_index=True, use_container_width=True)
                output = io.StringIO()
                result.to_csv(output, index=False)
                st.download_button(
                    "下载排名结果 CSV",
                    output.getvalue(),
                    file_name="job_fraud_ranked_results.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
        except Exception as error:
            st.error(f"处理失败：{error}")

with about_tab:
    st.subheader("模型如何工作")
    st.markdown(
        """
        1. 将标题、公司介绍、职位描述、要求和福利合并为文本。
        2. 使用预训练好的 TF-IDF 提取一元词和二元词特征。
        3. Linear SVM 输出一个风险排序分数。
        4. 根据验证集对应的 5%、10%、20% 排名阈值标记审核优先级。

        **为什么不是概率？**  
        Linear SVM 的 `decision_function` 输出只是到分类边界的距离，
        没有经过概率校准，不能把 0 解释成 50%。

        **适用边界**

        - 适合作为招聘审核的排序辅助工具。
        - EMSCAD 是历史英文数据，应用到新平台前必须重新验证。
        - 人工应结合公司资质、外部链接、联系方式和投诉历史作最终判断。
        """
    )
