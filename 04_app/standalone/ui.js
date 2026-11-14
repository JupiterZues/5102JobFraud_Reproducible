(function () {
  "use strict";

  const model = window.JOBGUARD_MODEL;
  const detector = window.JobGuardInference.createDetector(model);

  const translations = {
    zh: {
      hero_eyebrow: "HUMAN-IN-THE-LOOP SCREENING",
      hero_title: "把有限的人工审核时间，用在最可疑的招聘广告上。",
      hero_text: "基于招聘文本的机器学习排序工具。它不是自动判决系统，而是帮助审核团队建立风险队列。",
      metric_test_ap: "测试集 PR-AUC",
      metric_recall: "前 5% 审核召回率",
      metric_records: "冻结训练数据",
      tab_single: "单条评估",
      tab_batch: "批量审核",
      tab_method: "方法与边界",
      form_eyebrow: "JOB POSTING INPUT",
      form_title: "粘贴招聘广告内容",
      required_hint: "至少填写一个文本字段",
      field_title: "职位标题",
      field_company: "公司介绍",
      field_description: "职位描述",
      field_requirements: "职位要求",
      field_benefits: "福利信息",
      title_placeholder: "例如：Data Entry Clerk",
      company_placeholder: "招聘公司或机构介绍",
      description_placeholder: "粘贴主要工作内容……",
      requirements_placeholder: "粘贴学历、经验和技能要求……",
      benefits_placeholder: "粘贴薪酬和福利信息……",
      assess_button: "评估审核优先级",
      clear_button: "清空",
      result_empty_title: "等待评估",
      result_empty_text: "结果将显示风险排序分数和人工审核队列建议。",
      result_eyebrow: "REVIEW PRIORITY",
      result_score_label: "风险排序分数",
      risk_routine: "常规",
      risk_low: "低",
      risk_medium: "中",
      risk_high: "高",
      result_note: "分数用于相对排序，不是概率，也不能单独作为诈骗结论。",
      assess_again: "评估另一条广告",
      boundary_title: "人工决策边界",
      boundary_text: "模型只负责排序。最终判断应结合公司资质、域名、联系方式和历史投诉。",
      batch_eyebrow: "BATCH TRIAGE",
      batch_title: "批量生成审核队列",
      batch_copy: "上传 CSV，模型会按风险分数排序并生成可下载结果。",
      sample_download: "下载示例 CSV",
      upload_title: "拖入文件或点击选择",
      upload_text: "支持 job_id、title、company_profile、description、requirements、benefits 列。",
      choose_file: "选择 CSV",
      batch_result_eyebrow: "RANKED RESULTS",
      download_results: "下载结果 CSV",
      method_1_title: "文本转为特征",
      method_1_text: "标题、公司介绍、职位描述、要求和福利被合并，并转换为 TF-IDF 一元词与二元词特征。",
      method_2_title: "线性模型排序",
      method_2_text: "Linear SVM 输出风险排序分数。模型根据验证集表现选择，而不是根据测试集反复调参。",
      method_3_title: "固定审核预算",
      method_3_text: "按 top 5%、10%、20% 建立审核队列，衡量有限人工时间能发现多少欺诈广告。",
      method_4_title: "不是概率，也不是判决",
      method_4_text: "SVM 分数没有经过概率校准。模型基于历史英文数据，不能替代人工调查或法律判断。",
      threshold_eyebrow: "VALIDATION CUTOFFS",
      threshold_title: "审核优先级阈值",
      footer_text: "仅供课程演示与人工审核辅助",
      priority_high: "高优先级 · 前 5%",
      priority_medium: "中优先级 · 前 10%",
      priority_low: "低优先级 · 前 20%",
      priority_routine: "常规审核",
      batch_processing: "正在处理文件……",
      batch_loaded: "已加载文件，正在生成排名……",
      batch_error: "无法处理该文件：",
      empty_input: "请至少填写一个文本字段。",
      batch_summary: "已处理 {count} 条广告",
    },
    en: {
      hero_eyebrow: "HUMAN-IN-THE-LOOP SCREENING",
      hero_title: "Spend limited review time on the postings that deserve it most.",
      hero_text: "A text-ranking tool for recruitment-fraud triage. It builds a review queue; it does not make the final decision.",
      metric_test_ap: "Test PR-AUC",
      metric_recall: "Recall at top 5%",
      metric_records: "Frozen training records",
      tab_single: "Single assessment",
      tab_batch: "Batch review",
      tab_method: "Method & boundaries",
      form_eyebrow: "JOB POSTING INPUT",
      form_title: "Paste the job-posting content",
      required_hint: "At least one text field is required",
      field_title: "Job title",
      field_company: "Company profile",
      field_description: "Job description",
      field_requirements: "Requirements",
      field_benefits: "Benefits",
      title_placeholder: "e.g. Data Entry Clerk",
      company_placeholder: "Company or recruiting organisation",
      description_placeholder: "Paste the main job description…",
      requirements_placeholder: "Paste education, experience, and skills…",
      benefits_placeholder: "Paste compensation and benefits…",
      assess_button: "Assess review priority",
      clear_button: "Clear",
      result_empty_title: "Ready for assessment",
      result_empty_text: "The result will show a ranking score and suggested review queue.",
      result_eyebrow: "REVIEW PRIORITY",
      result_score_label: "Risk ranking score",
      risk_routine: "Routine",
      risk_low: "Low",
      risk_medium: "Medium",
      risk_high: "High",
      result_note: "The score is for relative ranking, not a probability or a standalone fraud verdict.",
      assess_again: "Assess another posting",
      boundary_title: "Human decision boundary",
      boundary_text: "The model only prioritises. Reviewers must verify company identity, domain, contacts, and prior complaints.",
      batch_eyebrow: "BATCH TRIAGE",
      batch_title: "Build a ranked review queue",
      batch_copy: "Upload a CSV to rank postings by risk and download the results.",
      sample_download: "Download sample CSV",
      upload_title: "Drop a file or choose one",
      upload_text: "Accepted columns: job_id, title, company_profile, description, requirements, benefits.",
      choose_file: "Choose CSV",
      batch_result_eyebrow: "RANKED RESULTS",
      download_results: "Download ranked CSV",
      method_1_title: "Text to features",
      method_1_text: "Title, company profile, description, requirements, and benefits are combined and converted to TF-IDF unigram and bigram features.",
      method_2_title: "Linear ranking model",
      method_2_text: "A Linear SVM produces the ranking score. It was selected on validation performance, not repeated test tuning.",
      method_3_title: "Fixed review budget",
      method_3_text: "Top 5%, 10%, and 20% queues show how much fraud can be found with limited manual review capacity.",
      method_4_title: "Not a probability or verdict",
      method_4_text: "The SVM score is not calibrated. The model uses historical English data and cannot replace human investigation or legal judgment.",
      threshold_eyebrow: "VALIDATION CUTOFFS",
      threshold_title: "Review-priority thresholds",
      footer_text: "Course demo and human-review support only",
      priority_high: "High priority · top 5%",
      priority_medium: "Medium priority · top 10%",
      priority_low: "Low priority · top 20%",
      priority_routine: "Routine review",
      batch_processing: "Processing file…",
      batch_loaded: "File loaded. Building ranking…",
      batch_error: "Could not process this file: ",
      empty_input: "Please complete at least one text field.",
      batch_summary: "Processed {count} postings",
    },
  };

  function readPreference(key) {
    try {
      return localStorage.getItem(key);
    } catch (_) {
      return null;
    }
  }

  function savePreference(key, value) {
    try {
      localStorage.setItem(key, value);
    } catch (_) {
      // Some browsers restrict localStorage for local file URLs.
    }
  }

  let currentLanguage = readPreference("jobguard-language") || "zh";
  let batchRows = [];
  let batchColumns = [];

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const t = (key) => translations[currentLanguage][key] || key;

  function applyLanguage(language) {
    currentLanguage = language;
    savePreference("jobguard-language", language);
    document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
    $$(".lang-btn").forEach((button) => {
      button.classList.toggle("active", button.dataset.lang === language);
    });
    $$("[data-i18n]").forEach((node) => {
      node.textContent = t(node.dataset.i18n);
    });
    $$("[data-placeholder]").forEach((node) => {
      node.placeholder = t(node.dataset.placeholder);
    });
    renderThresholds();
    if (!$("#result-content").classList.contains("hidden")) {
      const code = $("#priority-pill").dataset.code;
      if (code) renderPriority(code);
    }
    if (batchRows.length) {
      renderBatchTable();
      $("#batch-summary").textContent = t("batch_summary").replace("{count}", batchRows.length);
    }
  }

  function renderPriority(code) {
    const pill = $("#priority-pill");
    pill.dataset.code = code;
    pill.className = `priority-pill ${code}`;
    pill.textContent = t(`priority_${code}`);
  }

  function renderThresholds() {
    const items = [
      ["top_5pct", "TOP 5%"],
      ["top_10pct", "TOP 10%"],
      ["top_20pct", "TOP 20%"],
    ];
    $("#threshold-cards").innerHTML = items.map(([key, label]) => `
      <div class="threshold-item">
        <span>${label}</span>
        <strong>${Number(model.thresholds[key]).toFixed(3)}</strong>
      </div>
    `).join("");
  }

  function setActiveTab(name) {
    $$(".tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.tab === name));
    $$(".panel").forEach((panel) => panel.classList.toggle("active", panel.id === `panel-${name}`));
  }

  $$(".tab").forEach((tab) => {
    tab.addEventListener("click", () => setActiveTab(tab.dataset.tab));
  });
  $$(".lang-btn").forEach((button) => {
    button.addEventListener("click", () => applyLanguage(button.dataset.lang));
  });

  function resetResult() {
    $("#assess-form").reset();
    $("#result-empty").classList.remove("hidden");
    $("#result-content").classList.add("hidden");
  }

  $("#clear-form").addEventListener("click", resetResult);
  $("#assess-again").addEventListener("click", () => {
    resetResult();
    $("#title").focus();
  });

  $("#assess-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const payload = Object.fromEntries(new FormData(event.currentTarget).entries());
    if (!Object.values(payload).some((value) => String(value).trim())) {
      alert(t("empty_input"));
      return;
    }
    try {
      const result = detector.scoreRecord(payload);
      $("#result-empty").classList.add("hidden");
      $("#result-content").classList.remove("hidden");
      renderPriority(result.priority);
      $("#score-value").textContent = Number(result.score).toFixed(3);
      const { min, max } = model.score_range;
      const position = Math.min(1, Math.max(0, (result.score - min) / (max - min)));
      $("#risk-marker").style.left = `calc(${position * 100}% - 2px)`;
    } catch (error) {
      alert(t("empty_input"));
    }
  });

  function parseCSV(text) {
    const rows = [];
    let row = [];
    let value = "";
    let quoted = false;
    const clean = text.replace(/^\ufeff/, "");

    for (let index = 0; index < clean.length; index += 1) {
      const character = clean[index];
      if (quoted) {
        if (character === '"' && clean[index + 1] === '"') {
          value += '"';
          index += 1;
        } else if (character === '"') {
          quoted = false;
        } else {
          value += character;
        }
      } else if (character === '"') {
        quoted = true;
      } else if (character === ",") {
        row.push(value);
        value = "";
      } else if (character === "\n") {
        row.push(value.replace(/\r$/, ""));
        if (row.some((cell) => cell.trim())) rows.push(row);
        row = [];
        value = "";
      } else {
        value += character;
      }
    }
    row.push(value.replace(/\r$/, ""));
    if (row.some((cell) => cell.trim())) rows.push(row);
    return rows;
  }

  const fileInput = $("#csv-file");
  const uploadZone = $("#upload-zone");

  $("#choose-file").addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", () => {
    if (fileInput.files[0]) uploadBatch(fileInput.files[0]);
  });

  ["dragenter", "dragover"].forEach((eventName) => {
    uploadZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      uploadZone.classList.add("dragover");
    });
  });
  ["dragleave", "drop"].forEach((eventName) => {
    uploadZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      uploadZone.classList.remove("dragover");
    });
  });
  uploadZone.addEventListener("drop", (event) => {
    const file = event.dataTransfer.files[0];
    if (file) uploadBatch(file);
  });

  async function uploadBatch(file) {
    const status = $("#batch-status");
    status.className = "batch-status";
    status.classList.remove("hidden");
    status.textContent = t("batch_loaded");
    $("#batch-results").classList.add("hidden");

    try {
      const parsed = parseCSV(await file.text());
      if (parsed.length < 2) throw new Error("EMPTY_CSV");
      if (parsed.length - 1 > 5000) throw new Error("MAX_ROWS");
      const headers = parsed[0].map((header) => header.trim());
      batchRows = detector.scoreRows(headers, parsed.slice(1));
      batchColumns = ["review_rank", ...headers, "risk_score", "priority_code"];
      renderBatchTable();
      $("#batch-summary").textContent = t("batch_summary").replace("{count}", batchRows.length);
      status.classList.add("hidden");
      $("#batch-results").classList.remove("hidden");
    } catch (error) {
      status.className = "batch-status error";
      status.textContent = `${t("batch_error")}${error.message}`;
    }
  }

  function displayColumns(columns) {
    const preferred = [
      "review_rank", "job_id", "title", "risk_score", "priority",
      "description", "company_profile", "requirements", "benefits",
    ];
    const ordered = preferred.filter((column) => columns.includes(column));
    const extra = columns.filter(
      (column) => !ordered.includes(column) && column !== "priority_code"
    );
    return [...ordered, ...extra];
  }

  function renderBatchTable() {
    const columns = displayColumns(batchColumns);
    $("#results-table thead").innerHTML = `<tr>${columns.map((column) => `<th>${column}</th>`).join("")}</tr>`;
    $("#results-table tbody").innerHTML = batchRows.map((row) => `
      <tr>${columns.map((column) => {
        let value = row[column] ?? "";
        if (column === "risk_score") value = Number(value).toFixed(3);
        if (column === "priority") value = t(`priority_${row.priority_code}`);
        return `<td>${String(value).replaceAll("<", "&lt;").slice(0, 220)}</td>`;
      }).join("")}</tr>
    `).join("");
  }

  function downloadCSV() {
    const columns = displayColumns(batchColumns);
    const lines = [columns.join(",")];
    batchRows.forEach((row) => {
      lines.push(columns.map((column) => {
        const value = String(row[column] ?? "").replaceAll('"', '""');
        return `"${value}"`;
      }).join(","));
    });
    const blob = new Blob(["\ufeff" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
    const anchor = document.createElement("a");
    anchor.href = URL.createObjectURL(blob);
    anchor.download = "job_fraud_ranked_results.csv";
    anchor.click();
    URL.revokeObjectURL(anchor.href);
  }

  $("#download-results").addEventListener("click", downloadCSV);
  $("#sample-download").addEventListener("click", (event) => {
    event.preventDefault();
    const blob = new Blob([model.sample_csv], { type: "text/csv;charset=utf-8" });
    const anchor = document.createElement("a");
    anchor.href = URL.createObjectURL(blob);
    anchor.download = "sample_jobs.csv";
    anchor.click();
    URL.revokeObjectURL(anchor.href);
  });

  applyLanguage(currentLanguage);
})();
