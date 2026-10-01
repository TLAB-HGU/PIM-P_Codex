# Changes

## 0.1.1 — 2026-10-02

- Pin the transitive image-size dependency to patched 2.0.3 with an npm override and refreshed lockfile.
- Verify that manifest notes match actual PPTX notes and every declared source citation is embedded in those notes.
- Add regressions for mismatched manifests, unembedded citations and malformed ICNS parser termination.
- Add npm vulnerability auditing and Python 3.10/3.12 coverage to CI.
- Revalidate a fresh copied skill installation and both real-paper sample decks before lab publication.

## 0.1.0 — 2026-10-01

- Adapt the upstream paper analysis/design workflow for Codex local skills.
- Preserve normal/easy modes, source-linked briefs, and Korean speaker notes.
- Add deck.json generation and slide-level evidence manifests.
- Support per-page scan detection, optional OCR, column-aware extraction, validated crops, and exact-source equation fallback.
- Fix Korean preview rendering with isolated fontconfig and OS fonts.
- Add PPTX package/notes/provenance QA and actual text checks after rendering.
- Implement native bar point highlighting, installation backups, dependency diagnosis, and regression tests.
- Preserve upstream MIT license and attribution in independently installed skills.

This is the first development release. Paper interpretation and visual quality still require source and image review.
