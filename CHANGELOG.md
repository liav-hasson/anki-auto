# Changelog

## [0.4.0] - 2026-07-23

### Added

- Optional free-form card customization through `customization.txt`.
- Optional best-effort target-vocabulary exclusions through `blacklist.txt`.
- Bounded custom note sections that preserve structured output and safe HTML rendering.
- Optional `ANKI_REASONING_EFFORT` to raise reasoning effort on reasoning-capable models
  (e.g. `gpt-5.5`); omitted when unset so the default `gpt-4.1-mini` is unaffected.
- Example templates under `examples/` (`customization.example.txt`, `blacklist.example.txt`,
  `.env.example`) plus README steps to copy them into the project root.

### Changed

- Preflight now reports auxiliary prompt-file status and warns before confirmation when
  customization or blacklist content is unavailable.
- Minimal-card generation now clears note content returned by the model before packaging.
- Pre-run summary shows an explicit audio on/off state and aligns every row to one column.
- `ANKI_MINIMAL_CARDS` now ignores `customization.txt` entirely (it no longer affects the
  core concept or examples); a warning is shown when a customization file is skipped.
- Live `customization.txt` / `blacklist.txt` are now git-ignored; tracked templates live in
  `examples/`.

## [0.3.0] - 2026-07-13

### Added

- Preflight output now shows the actual `.apkg` file that will be written, including any
  auto-added suffix when overwrite mode is off.
- Preflight output now shows whether output overwrite mode is enabled.
- Language tags now support non-Latin language names instead of collapsing to empty tags.

### Changed

- The default Anki note type is now language-neutral (`Anki Auto Notes v2`) instead of
  French/Spanish-specific.
- Audio generation now uses the supported OpenAI text-to-speech response flow, making the
  audio path more future-proof with current OpenAI SDK versions.
- Runtime dependency ranges are pinned to tested major versions for more predictable installs.
- Generated Anki cards now use centered Arial text at 20px by default.
- A1-A2 sentence prompts now ask for simple negation, question forms, and connectors when natural.
- B1-C2 sentence prompts now emphasize natural, idiomatic target-language phrasing.
- Package/version metadata now uses one source of truth and matches the current project version.
- Internal CLI flow was simplified so the main command remains easier to maintain as the workflow grows.

### Fixed

- `.apkg` files are now written atomically, so a failed package write will not replace an
  existing deck file with a partial or corrupt file.
- Generated `.apkg` packages now have stronger test coverage for archive contents and media files.
- Stable Anki deck/model IDs now use a larger ID space to reduce collision risk.
- Stale French-only source wording was updated to match the language-neutral behavior.

### Removed

- Removed key collocations and register/usage notes from generated card output to keep notes focused.
- Removed the misleading dry-run mode, because it still called the AI and only skipped package creation.
- Removed an unused backwards-compatible rendering helper that had no in-project callers.

## [0.2.1] - 2026-07-04

### Changed

- Specified notes prompt to not repeat the same items in different sections.
- B1-C2 Prompts - forced sentences prompt to change registers / tones in each sentence

## [0.2.0] - 2026-07-04

### Added

- Language-neutral generation: configurable origin (front), target (back), and notes languages —
  no longer hardcoded to French/Spanish.
- Fully `.env`-driven configuration via a typed settings layer, with a committed `.env.example`.
- CEFR difficulty tiers (A1–C2) that adjust sentence length, grammar, and vocabulary.
- Concurrent card and audio generation for faster batches (`ANKI_CONCURRENCY`).
- Confirmation prompt before generation, with `ANKI_ASSUME_YES` bypass for automation.
- Minimal-card mode (`ANKI_MINIMAL_CARDS`) for sentences-only cards.
- Output-collision handling (`ANKI_OVERWRITE_OUTPUT`) writing `<name>_1.apkg` instead of overwriting.
- Deterministic per-card tags (`lang::…`, `level::…`) built from settings.
- Level-tagged logging (`[INFO]`/`[WARNING]`/`[ERROR]`) and friendly error messages with guidance
  links for OpenAI/config failures.

### Changed

- Migrated structured output to the OpenAI SDK `parse()` helper with a Pydantic-derived schema.
- Modular, composable prompt built from settings (system, core concept, CEFR, flashcard, notes).
- Deck/model/note fields renamed to neutral, language-agnostic names.

### Removed

- AI-generated tags and the `usage_forms` note section (replaced by deterministic tagging).

## [0.1.0] - 2026-07-01

- Add the first functional CLI for generating French Anki decks from loose input items.
- Generate Spanish-front/French-back cards with structured notes, examples, usage forms, and audio.
- Package directly importable `.apkg` files with stable note GUIDs and media filenames.
- Add OpenAI card generation, OpenAI text-to-speech audio generation, and local validation tests.
