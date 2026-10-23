# Contributing

Thanks for your interest in Capzoryx Copilot. Small, focused changes are easiest to review.

1. Fork the repository and work on a branch.
2. Set up locally as described in the README (Python 3.12, Node 22).
3. Before opening a pull request run `python -m pytest api/tests -q`, `npm run build --prefix web` and `node scripts/extract_ui_strings.cjs --check`. Two backend tests fail only on Windows (file mode, line endings) and pass on Linux CI.
4. Every user-facing text goes through `t()` or `T()` in `web/src/i18n.tsx` so it can be translated.
5. Security-sensitive changes need a regression test. Report vulnerabilities privately; see SECURITY.md.

By contributing you agree that your contribution is licensed under the MIT license of this repository.
