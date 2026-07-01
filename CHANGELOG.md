# Changelog

## [Unreleased]

- Nothing yet.

## [0.1.0] - 2026-07-01

- Add the first functional CLI for generating French Anki decks from loose input items.
- Generate Spanish-front/French-back cards with structured notes, examples, usage forms, and audio.
- Package directly importable `.apkg` files with stable note GUIDs and media filenames.
- Add OpenAI card generation, OpenAI text-to-speech audio generation, and local validation tests.

## [Planned]

- Language nuetral (source and target), passed as env variables.
- Refactor hardcoded defaults to an env var for easy configurations (modeles, filenames, voices, deck names, etc..).
- Workspace cleanup (input, output files).
- Add an .env example file to be pushed.
- Provide Readme with image example of generated cards and a usage guide.
- Run in Docker option.
- Support for different CEFR student levels using variables, that modify prompts for adequate sentence generations (by length, vocabulary level, connectors, conjugations, idioms).
- CLI Progress bar for batch and long generations + track time.
- Print Token metadata and usage for cost estimation.
