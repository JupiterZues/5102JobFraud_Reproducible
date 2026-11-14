# Offline Single-File App

Generate the standalone HTML:

```bash
python 04_app/standalone/build_standalone.py
```

The output is the repository-root file:

```text
JobGuard.html
```

Download it and double-click to open it in a browser. The trained TF-IDF
vocabulary, IDF values, Linear SVM coefficients, thresholds, translations, and
sample CSV are embedded directly in the HTML. It does not need Python, a server,
or an internet connection.

The standalone file keeps the same limitations as the trained project model:

- The score is a ranking value, not a probability.
- It uses historical English-language data.
- It only evaluates the pasted text; it does not verify company registration,
  domains, links, or external facts.
- Human review is required before any enforcement decision.
