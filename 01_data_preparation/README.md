# Data Preparation v2

## 1. 数据来源

- **数据集**：Employment Scam Aegean Dataset（EMSCAD），Kaggle 副本名为 *Real / Fake Job Posting Prediction*。
- **下载地址**：https://www.kaggle.com/datasets/shivamb/real-or-fake-fake-jobposting-prediction
- **下载日期**：2026年11月13日。
- **使用条款**：Kaggle 数据集页面标注为 **CC0 1.0（Public Domain）**。本项目用于课程学习、分析和模型评估，并注明数据来源。
- **原始论文**：Vidros et al. (2017), *Automatic Detection of Online Recruitment Frauds: Characteristics, Methods, and a Public Dataset*. https://doi.org/10.3390/fi9010006

## 2. 数据清洗与防泄漏去重

原始数据有 **17,880 条记录、18 个字段**。将 `title`、`company_profile`、`description`、`requirements`、`benefits` 按顺序合并成 `text_all`；缺失的文本填空字符串，并合并多余空白字符。

| 处理步骤 | 删除数量 | 剩余数量 |
|---|---:|---:|
| 原始数据 | — | 17,880 |
| 删除空文本 | 0 | 17,880 |
| 第一轮：按 `text_all + fraudulent` 完全去重 | 2,001 | 15,879 |
| 第二轮：按 `text_key + fraudulent` 再次去重 | 129 | **15,750** |

第二轮先生成临时 `text_key`：将文本转小写、去掉 URL、UUID/长十六进制哈希和标点，并合并多余空白。**`text_all` 保持原样，`text_key` 只用于去重和检查，不写入最终 CSV，也不用于训练模型。**

标签：`fraudulent=0` 表示正常招聘，`fraudulent=1` 表示虚假招聘。清洗后正常招聘 **15,042 条（95.50%）**，虚假招聘 **708 条（4.50%）**。

## 3. 训练、验证、测试集划分

按 `fraudulent` **分层随机划分**，随机种子为 **42**，目标比例为 **70% / 15% / 15%**。

| 数据集 | 样本量 | 虚假招聘数 | 虚假比例 |
|---|---:|---:|---:|
| Train | 11,025 | 496 | 4.4989% |
| Validation | 2,362 | 106 | 4.4877% |
| Test | 2,363 | 106 | 4.4858% |
| **合计** | **15,750** | **708** | **4.4952%** |

已检查：`job_id` 唯一；各集合之间没有重复 `job_id`，也没有相同的规范化 `text_key`。**后续建模直接使用 `jobs_clean.csv` 的 `split` 列，不要自行重新划分。**

## 4. 基线模型与 EDA

基线使用 `DummyClassifier(strategy="prior")`，为所有样本输出训练集的虚假招聘比例，不使用文本进行预测。

| 指标 | Validation | Test |
|---|---:|---:|
| Average Precision（AP） | 0.044877 | 0.044858 |
| ROC-AUC | 0.500000 | 0.500000 |

已生成三张图：清洗后类别分布图、原始数据字段缺失率图、清洗后文本词数分布图。

## 5. 文件说明与下游使用方式

| 文件 | 用途 |
|---|---|
| `data/raw/fake_job_postings.csv` | 原始数据，供复现 |
| `data/intermediate/jobs_clean_v2.csv` | v2 清洗后数据（15,750行），含 `job_id`、`text_all`、`fraudulent`、`split` 及五个元数据字段 |
| `01_data_preparation/baseline_predictions_v2.csv` | 验证集和测试集基线风险分数（4,725行） |
| `01_data_preparation/figures/class_balance_v2.png` | 类别分布 |
| `01_data_preparation/figures/missing_values_v2.png` | 原始字段缺失率 |
| `01_data_preparation/figures/text_length_v2.png` | 文本长度分布 |
| `01_data_preparation/data_preparation_v2.ipynb` | 完整处理、划分、基线和绘图代码 |

- **Modeling stage**：进一步检查 v2 中残余的格式变体，生成 `data/processed/jobs_clean.csv`，并直接使用其中的 `split` 字段。`job_id` 仅作编号，不作为模型特征。
- **Evaluation stage**：使用冻结模型的风险分数完成固定审核容量分析。Baseline 只是参考，不能代替正式分类模型。
- **注意**：旧版 15,879 条的数据、基线预测和 EDA 图不能与本版混用。

下游冻结数据在 v2 基础上又删除了 34 条残余格式变体，最终为
15,716 条。建模和最终评价统一使用 `data/processed/jobs_clean.csv`。

## 6. 数据局限

数据中虚假招聘占比较低，部分原始字段缺失较多；数据也属于历史招聘信息。此次规范化去重可减少部分重复文本造成的泄漏，但无法识别所有语义相似或改写的招聘文本。
