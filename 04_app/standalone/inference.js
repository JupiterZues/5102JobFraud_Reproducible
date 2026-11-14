(function (global) {
  "use strict";

  function normalizeText(text) {
    return String(text ?? "")
      .normalize("NFKD")
      .replace(/\p{M}/gu, "")
      .toLowerCase();
  }

  function tokenize(text) {
    const normalized = normalizeText(text);
    return (normalized.match(/[\p{L}\p{N}_]+/gu) || [])
      .filter((token) => token.length >= 2);
  }

  function createDetector(model) {
    const featureIndex = new Map();
    model.features.forEach((feature, index) => featureIndex.set(feature, index));

    function scoreText(text) {
      const tokens = tokenize(text);
      if (!tokens.length) return null;

      const counts = Object.create(null);
      tokens.forEach((token) => {
        counts[token] = (counts[token] || 0) + 1;
      });
      for (let index = 0; index < tokens.length - 1; index += 1) {
        const bigram = `${tokens[index]} ${tokens[index + 1]}`;
        counts[bigram] = (counts[bigram] || 0) + 1;
      }

      const weighted = [];
      let normSquared = 0;
      Object.entries(counts).forEach(([term, count]) => {
        const index = featureIndex.get(term);
        if (index === undefined) return;
        const value = (1 + Math.log(count)) * model.idf[index];
        weighted.push([index, value]);
        normSquared += value * value;
      });

      const norm = Math.sqrt(normSquared);
      let score = model.intercept;
      if (norm > 0) {
        weighted.forEach(([index, value]) => {
          score += model.coef[index] * (value / norm);
        });
      }
      return score;
    }

    function priority(score) {
      if (score >= model.thresholds.top_5pct) return "high";
      if (score >= model.thresholds.top_10pct) return "medium";
      if (score >= model.thresholds.top_20pct) return "low";
      return "routine";
    }

    function combineFields(record) {
      return [
        record.title,
        record.company_profile,
        record.description,
        record.requirements,
        record.benefits,
      ]
        .map((value) => String(value ?? "").trim())
        .filter(Boolean)
        .join(" ");
    }

    function scoreRecord(record) {
      const text = combineFields(record);
      if (!text) throw new Error("EMPTY_TEXT");
      const score = scoreText(text);
      return { score, priority: priority(score) };
    }

    function scoreRows(headers, rows) {
      return rows.map((row) => {
        const record = Object.fromEntries(headers.map((header, index) => [header, row[index] ?? ""]));
        const score = scoreText(combineFields(record));
        if (score === null) throw new Error("EMPTY_TEXT");
        return { ...record, risk_score: score, priority_code: priority(score) };
      }).sort((left, right) => right.risk_score - left.risk_score)
        .map((row, index) => ({ review_rank: index + 1, ...row }));
    }

    return { scoreText, scoreRecord, scoreRows, priority, tokenize };
  }

  const api = { createDetector, normalizeText, tokenize };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  global.JobGuardInference = api;
})(typeof window !== "undefined" ? window : globalThis);
