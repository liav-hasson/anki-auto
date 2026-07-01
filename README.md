# anki-auto

Generate fresh French Anki `.apkg` decks from loose input items using OpenAI.

One input line becomes one complete French learning card for an A1-A2 learner who is fluent in
Spanish and English. Cards are generated fresh from loose input; the tool does not edit a live Anki
collection and does not preserve scheduling. Re-running the same input recreates a directly
importable package with stable deck/model ids, note GUIDs, and media filenames.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Create a `.env` file or export the variable in your shell:

```bash
OPENAI_API_KEY=sk-...
```

## Example input

Create `items.txt` with one loose input item per line:

```text
dog
to remember
at the train station
I would like a coffee
```

Blank lines and lines starting with `#` are ignored.

## Usage

Create a fresh package with card audio:

```bash
anki-auto items.txt french.apkg
```

Create cards without audio:

```bash
anki-auto items.txt french.apkg --no-audio
```

Preview generated structured card JSON without writing an `.apkg`:

```bash
anki-auto items.txt french.apkg --dry-run
```

## Card shape

The OpenAI response is validated as this structure:

```json
{
  "source": "telling time",
  "front_core_es": "Decir la hora",
  "back_core_fr": "Dire l'heure",
  "examples": [
    {"fr": "Il est huit heures au cafe.", "es": "Son las ocho en el cafe."},
    {"fr": "On part a midi, d'accord ?", "es": "Salimos al mediodia, vale?"}
  ],
  "word_family": [
    {"fr": "une heure", "en": "an hour / one o'clock", "note": null}
  ],
  "related_vocab": [
    {"fr": "midi", "en": "noon", "nuance": "fixed time in the middle of the day"},
    {"fr": "une horloge", "en": "a clock", "nuance": "object that shows time"}
  ],
  "key_collocations": [
    {"fr": "avoir l'heure", "en": "to know the time", "note": null}
  ],
  "register_notes": [
    "Use heure for clock time; heures is plural after numbers above one."
  ],
  "usage_forms": [
    {"fr": "une heure", "en": "one o'clock / one hour", "note": "singular form"},
    {"fr": "deux heures", "en": "two o'clock / two hours", "note": "plural form"}
  ],
  "note_examples": [
    "Le train arrive a neuf heures.",
    "Tu as l'heure ?"
  ],
  "tags": ["french", "phrase"]
}
```

The Anki note model uses exactly these fields:

- `FrontText`: rendered front-side HTML.
- `BackText`: rendered back-side HTML, including notes.
- `BackAudio`: one `[sound:...]` tag for each main French example sentence.

Front side:

- Bold Spanish core concept only.
- Spanish translations of the main example sentences below it, separated with explicit HTML breaks.
- No notes.

Back side:

- Bold French core concept at the top.
- Two or three plain French example sentences, separated with explicit HTML breaks.
- One audio clip for each main French example sentence in `BackAudio`.
- Bold `--- NOTES ---` followed by only relevant non-empty sections.
- Supported note headers are `Word family`, `Related vocab`, `Key collocations`,
  `Register and usage notes`, `Usage forms`, and `Examples`.
- Structured note entries render as `French term: English details`, with the French term before the
  first colon underlined. `register_notes` are plain English prose unless a line includes a colon.
- Only note examples are quoted, neon green, and italic. Main examples are plain and not green.
- Extra note examples are French only and do not require audio.

Useful options:

```bash
anki-auto items.txt french.apkg \
  --deck-name "French Rebuild" \
  --card-model gpt-4.1-mini \
  --audio-model gpt-4o-mini-tts \
  --voice alloy
```

## Output behavior

- The default output is a fresh `.apkg` that can be imported directly into Anki.
- Audio, when enabled, is generated once for each main French example sentence and attached with
  multiple `[sound:...]` tags on the back.
- Formatting uses field HTML with direct `<b>`, `<u>`, and explicit `<br>` breaks so imports do not
  depend on Anki applying custom CSS classes. Only note examples use bright green italic styling.
- Formatting and display casing are handled by the renderer; model output should be plain structured
  JSON.
- Stable note GUIDs are derived from the input item, Spanish front core, French back core, and the
  current three-field note format. Stable media filenames are derived from the input item, French
  back core, example index, and French example sentence.
- The default note model is `Anki Auto French Spanish Notes v2`; keep `--note-model-name` stable once
  you start importing this card format. The v2 name avoids Anki reusing the original imported model
  template while this field-rendered format settles.
- The OpenAI prompt asks for varied vocabulary and non-repetitive examples, but there is no global
  vocabulary ledger yet.

## OpenAI assumptions

Card generation uses Chat Completions with `response_format={"type": "json_schema"}` and validates
the returned JSON with Pydantic. If an installed OpenAI SDK does not accept `response_format`, the
client retries without it and still validates that the response is a JSON object matching the schema.

Audio generation uses `client.audio.speech.create(...).stream_to_file(...)` to create MP3 media files.

## Cost warning

Every non-dry-run card requires one text generation request, and audio adds two or three
text-to-speech requests per card. Test with a small input file first before recreating a large deck.

## Development

```bash
python -m pip install -e '.[dev]'
python -m compileall src tests
pytest
ruff check src tests
pylint src/anki_auto tests
```
