# Changelog

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
