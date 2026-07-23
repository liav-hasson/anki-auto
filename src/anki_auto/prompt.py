"""Modular prompt construction for language-neutral card generation."""

from __future__ import annotations

from .config import PromptConfig


_LEVEL_TO_SENTENCE_LENGTH: dict[str, str] = {
    "A1": "5–9",
    "A2": "5–9",
    "B1": "6–12",
    "B2": "6–12",
    "C1": "7–15",
    "C2": "7–15",
}

_LEVEL_TO_TIER: dict[str, int] = {
    "A1": 1,
    "A2": 1,
    "B1": 2,
    "B2": 2,
    "C1": 3,
    "C2": 3,
}

_CEFR_SENTENCE_GUIDANCE: dict[int, str] = {
    1: (
        "- Use simple, high-frequency, beginner-level vocabulary and basic "
        "grammar.\n"
        "- Keep subjects, tenses, and moods basic across the sentences — simple "
        "but flexible.\n"
        "- Use simple negation, question forms, and connectors where they read "
        "naturally."
    ),
    2: (
        "- Use natural, idiomatic everyday vocabulary and varied grammar.\n"
        "- Vary subjects, tenses, and moods across the sentences so the card shows "
        "the core concept flexing grammatically.\n"
        "- Give each sentence a different tone / scenario that fits the core "
        "concept's register (e.g. news report, making an order or appointment, an "
        "argument, daily conversation, a command).\n"
        "- Use a mix of prepositions, interjections, and connectors naturally "
        "within the sentences."
    ),
    3: (
        "- Use advanced, nuanced, idiomatic vocabulary and sophisticated grammar.\n"
        "- Vary subjects, tenses, and moods across the sentences so the card shows "
        "the core concept flexing grammatically.\n"
        "- Give each sentence a different tone / scenario that fits the core "
        "concept's register (e.g. news report, making an order or appointment, an "
        "argument, daily conversation, a command).\n"
        "- Use a mix of advanced prepositions, interjections, and connectors "
        "naturally within the sentences."
    ),
}


def _native_clause(cfg: PromptConfig) -> str:
    origin = cfg.origin_language
    notes = cfg.notes_language
    if origin.strip().casefold() == notes.strip().casefold():
        return f"whose native language is {origin}."
    return f"whose native languages are {origin} and {notes}."


def build_intro(cfg: PromptConfig) -> str:
    """Build the role-setting intro paragraphs."""

    return (
        f"You create high-quality {cfg.target_language} Anki flashcards for a learner "
        f"{_native_clause(cfg)} You turn one input line into natural, high-value "
        "study material and return a single structured card object that matches the "
        "provided schema.\n\n"
        "The app applies all visual styling from the card's structure, so return "
        "plain text only — no quotes, markdown, HTML, or other formatting."
    )


def build_glossary(cfg: PromptConfig) -> str:
    """Build the shared-terminology glossary."""

    return (
        "Terms used below:\n"
        "- core concept: the first word or chunk of the input line; the root of the "
        "card.\n"
        "- optional vocab: any words after the core concept; candidates for enriching "
        "the sentences.\n"
        f"- note item: a {cfg.target_language} word or chunk featured in the notes.\n"
        f"- example sentence: a {cfg.target_language} sentence of a note item, placed "
        "in the line below it.\n"
        "- blacklisted vocab: words to avoid as supporting vocabulary.\n"
        "- user instructions: extra guidelines that may adjust the defaults below."
    )


def _core_concept_section(cfg: PromptConfig) -> str:
    return (
        "1. Core concept cleanup\n"
        f"Distill the input line into one clean, reusable {cfg.target_language} core "
        "concept, ignoring the optional vocab when choosing it. Normalize it to "
        "dictionary form, for example: infinitive for verbs, singular for nouns and "
        "adjectives, gender articles, reflexive/pronominal markers, etc."
    )


def _core_sentences_section(cfg: PromptConfig) -> str:
    sentence_length = _LEVEL_TO_SENTENCE_LENGTH[cfg.level]
    tier_guidance = _CEFR_SENTENCE_GUIDANCE[_LEVEL_TO_TIER[cfg.level]]
    return (
        "2. Core sentences creation\n"
        "Analyze the core concept's meanings, usage, and formality register. "
        "Understand exactly how it is naturally used, and in what situations you "
        "would encounter it. After that analysis, write 2–3 natural, dynamic "
        "sentences that show the core concept in real, useful contexts:\n"
        "- The core concept must appear in every sentence.\n"
        "- Weave in optional vocab only where a sentence stays completely natural; "
        "freely drop any that do not fit, and never force them.\n"
        f"{tier_guidance}\n"
        f"- Match {cfg.level} difficulty — roughly {sentence_length} words each, "
        "natural and idiomatic.\n"
        f"- Give each {cfg.target_language} sentence a faithful, direct, natural "
        f"{cfg.origin_language} translation."
    )


def _notes_section(cfg: PromptConfig) -> str:
    return (
        "3. Notes section\n"
        "Produce two note sections that deepen understanding of the core concept "
        "only. Use judgment: include only genuinely useful, closely related items — "
        "3–6 per section, choosing the count per word based on how many genuinely "
        "related items actually exist, never padding to a fixed number. Do not note "
        "unrelated words or the optional vocab.\n"
        "- Word family: useful related forms of the core concept (noun, verb, "
        "adjective, adverb, participle), including prefixed or derived forms that are "
        'easy to overlook (e.g. for "hacer": "rehacer", "deshacer"). Do not note the '
        "core concept itself.\n"
        "- Related vocab: useful nearby words — synonyms, antonyms, close "
        "alternatives, idioms.\n"
        "Rules for constructing notes:\n"
        "- Word family and Related vocab are the only sections to produce by "
        "default; never add another section unless a user instruction explicitly "
        "requests it.\n"
        f"- Every gloss, nuance, and register note is written in {cfg.notes_language} "
        "(may differ from native language); target terms and example sentences stay "
        f"in {cfg.target_language}.\n"
        f"- For every note item, return: 1. The {cfg.target_language} term. 2. The "
        f"direct {cfg.notes_language} translation. 3. A minimal {cfg.notes_language} "
        "usage nuance (register, region, usage notes, only when relevant. soft "
        f"maximum of ~10 words). 4. One {cfg.target_language} example sentence that "
        "uses the item naturally. Never repeat an item across sections.\n"
        f"- Example sentences must match the CEFR level of the user - {cfg.level}."
    )


def build_default_behavior(cfg: PromptConfig, *, minimal_cards: bool) -> str:
    """Build the default-behavior block: core cleanup, sentences, and notes."""

    subsections = [_core_concept_section(cfg), _core_sentences_section(cfg)]
    if not minimal_cards:
        subsections.append(_notes_section(cfg))
    body = "\n\n".join(subsections)
    return f"=== DEFAULT BEHAVIOR ===\n{body}"


def build_user_instructions(cfg: PromptConfig) -> str:
    """Build the optional user-customization block."""

    lines = "\n".join(f"- {instruction}" for instruction in cfg.customization)
    return (
        "=== USER INSTRUCTIONS ===\n"
        "These are the user's own instructions, and they take precedence over the "
        "default behavior above. Apply every one of them fully, even when they "
        "extend, change, or directly contradict the defaults. The only things they "
        "cannot override are the language placement and the response schema.\n"
        f"{lines}"
    )


def build_blacklist(cfg: PromptConfig) -> str:
    """Build the optional best-effort blacklisted-vocab block."""

    lines = "\n".join(f"- {entry}" for entry in cfg.blacklist)
    return (
        "=== BLACKLISTED VOCAB ===\n"
        "Avoid these words as supporting vocabulary in the sentences and note items, "
        "on a best-effort basis:\n"
        f"{lines}"
    )


def assemble_system_prompt(cfg: PromptConfig, *, minimal_cards: bool) -> str:
    """Join the system-prompt sections with optional user overlays."""

    pieces = [
        build_intro(cfg),
        build_glossary(cfg),
        build_default_behavior(cfg, minimal_cards=minimal_cards),
    ]
    if cfg.customization and not minimal_cards:
        pieces.append(build_user_instructions(cfg))
    if cfg.blacklist:
        pieces.append(build_blacklist(cfg))
    return "\n\n".join(pieces)


def build_card_messages(
    item: str,
    cfg: PromptConfig,
    *,
    minimal_cards: bool,
) -> list[dict[str, str]]:
    """Build chat messages for one loose input line."""

    return [
        {
            "role": "system",
            "content": assemble_system_prompt(cfg, minimal_cards=minimal_cards),
        },
        {"role": "user", "content": f"Input line: {item.strip()}"},
    ]
