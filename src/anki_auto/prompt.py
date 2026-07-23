"""Modular prompt construction for language-neutral card generation."""

from __future__ import annotations

from .config import PromptConfig


_LEVEL_TO_TIER: dict[str, int] = {
    "A1": 1,
    "A2": 1,
    "B1": 2,
    "B2": 2,
    "C1": 3,
    "C2": 3,
}

_CEFR_TIERS: dict[int, str] = {
    1: (
        "Write one original sentence for each core meaning of the word "
        "(typically 2, 3 if the word has versatile meanings).\n\n"
        "- Keep sentences between 5–9 words.\n"
        "- Match {level} vocabulary and grammar — natural, simple, beginner-level "
        "vocabulary.\n"
        "- Keep subjects, tenses, and moods basic across sentences so the cards are "
        "simple, but flexible.\n"
        "- Use a mix of simple negation, question forms, connectors when natural "
        "within the sentence.\n"
        "- If the user included extra words in the input item, try to use them in "
        "the sentences, whenever possible, but do not force them."
    ),
    2: (
        "Write one original sentence for each core meaning of the word "
        "(typically 2, 3 if the word has versatile meanings).\n\n"
        "- Keep sentences between 6–12 words.\n"
        "- Match {level} vocabulary and grammar — natural and idiomatic in the target "
        "language.\n"
        "- Vary subjects, tenses, and moods across sentences so the card shows the "
        "word flexing grammatically.\n"
        "- Each sentence must have a different creative tone / scenario, "
        "according with the core word's register (e.g. news report, making "
        "an order / appointment, having an argument, daily conversation, "
        "giving a command).\n"
        "- Use a mix of prepositions, interjections, connectors naturally within the "
        "sentence.\n"
        "- If the user included extra words in the input item, try to use them in "
        "the sentences, whenever possible, but do not force them."
    ),
    3: (
        "Write one original sentence for each core meaning of the word "
        "(typically 2, 3 if the word has versatile meanings).\n\n"
        "- Keep sentences between 7–15 words.\n"
        "- Match {level} vocabulary and grammar — natural and idiomatic in the target "
        "language.\n"
        "- Vary subjects, tenses, and moods across sentences so the card shows the "
        "word flexing grammatically.\n"
        "- Each sentence must have a different creative tone / scenario, "
        "according with the core word's register (e.g. news report, making "
        "an order / appointment, having an argument, daily conversation, "
        "giving a command).\n"
        "- Use a mix of advanced prepositions, interjections, connectors naturally "
        "within the sentence.\n"
        "- If the user included extra words in the input item, try to use them in "
        "the sentences, whenever possible, but do not force them."
    ),
}


def build_system_prompt(cfg: PromptConfig) -> str:
    """Build the role-setting system piece."""

    if cfg.origin_language.strip().casefold() == cfg.notes_language.strip().casefold():
        native_clause = f"whose native language is {cfg.origin_language}."
    else:
        native_clause = (
            "whose native languages are "
            f"{cfg.origin_language} and {cfg.notes_language}."
        )
    return (
        f"You create high-quality {cfg.target_language} Anki flashcards for a learner "
        f"{native_clause}\n\n"
        "Each card is built from one loose input item. Your task is to distill that "
        f"input into the single cleanest, most reusable {cfg.target_language} concept, "
        "then build a flashcard based on the rules explained ahead.\n\n"
        "Return exactly one structured card object matching the provided schema."
    )


def build_cefr_prompt(cfg: PromptConfig) -> str:
    """Build the CEFR difficulty piece for the tier of ``cfg.level``."""

    tier = _LEVEL_TO_TIER[cfg.level]
    return _CEFR_TIERS[tier].format(level=cfg.level)


def build_core_concept_prompt(cfg: PromptConfig) -> str:
    """Build the distillation and lemma-normalization piece."""

    return (
        "If needed, distill the input item into one clean, reusable "
        f"{cfg.target_language} learning concept by removing context clutter, "
        'examples, "etc.", and tentative lists. Capture the single reusable idea, not '
        "a verbatim copy of a long input.\n\n"
        f"Normalize the core concept to its natural {cfg.target_language} dictionary "
        "form:\n"
        "- Infinitive for verbs, singular for nouns, base form for adjectives.\n\n"
        f"If {cfg.target_language} has these, also include:\n"
        "- Gender article for nouns.\n"
        "- Reflexive/pronominal marker for verbs.\n"
        "- Masculine and feminine forms for adjectives.\n"
        "- Formality register.\n"
        "- If the user included extra words in the input item, ignore them for the core "
        "concept."
    )


def build_flashcard_prompt(cfg: PromptConfig) -> str:
    """Build the card-structure piece (back-first, front translation)."""

    return (
        "Build the flashcard around the core concept and level of the user, in the "
        "following structure:\n"
        f"- Back: the normalized {cfg.target_language} core concept, and the example "
        "sentences.\n"
        "- Front: direct, natural translation of the core concept and example "
        f"sentences in {cfg.origin_language}."
    )


def build_notes_prompt(cfg: PromptConfig) -> str:
    """Build the optional learning-notes piece."""

    return (
        "Always add notes to a card, extending the learning value from each card. The "
        f"notes are written in {cfg.notes_language}.\n\n"
        f"Every gloss, nuance, and register note is written in {cfg.notes_language}; "
        f"target terms and note examples stay in {cfg.target_language}.\n\n"
        "The following notes sections are optional, select depending on the added "
        "value for the card; leave the rest empty rather than padding with filler. "
        "Do not repeat the same note item on different sections.\n\n"
        "word_family: all related forms of the concept (noun, verb, adjective, "
        "adverb, participles), if exists. note only if a form uncommon.\n"
        "related_vocab: nearby or derived words worth knowing, synonyms, antonyms, "
        "idioms, each with a very short meaning / usage nuance.\n"
        f"note_examples: 1–3 extra {cfg.target_language} sentences showing meanings or "
        "uses not already covered by the main examples.\n\n"
        "custom_note_sections: use only for additional named sections explicitly "
        "requested in user customization. Otherwise leave it empty. Do not duplicate "
        "items from built-in sections."
    )


def build_instruction_contract_prompt(
    cfg: PromptConfig,
    *,
    minimal_cards: bool,
) -> str:
    """State instruction precedence and non-overridable card requirements."""

    note_requirement = (
        "Notes are disabled. Every note collection must be empty."
        if minimal_cards
        else f"Write all note explanations in {cfg.notes_language}."
    )
    blacklist_requirement = (
        "\n- Apply the supplied vocabulary blacklist to supporting vocabulary."
        if cfg.blacklist
        else ""
    )
    return (
        "Apply instructions in this priority order, from highest to lowest:\n"
        "1. Hard requirements in this system message.\n"
        "2. The current input item and its explicit request.\n"
        "3. global user customization.\n"
        "4. Built-in content and style defaults.\n\n"
        "Hard requirements:\n"
        f"- Keep target concepts and target examples in {cfg.target_language}.\n"
        f"- Keep front translations in {cfg.origin_language}.\n"
        f"- {note_requirement}\n"
        "- Return exactly one object matching the structured response schema."
        f"{blacklist_requirement}"
    )


def build_blacklist_prompt(cfg: PromptConfig) -> str:
    """Build the best-effort supporting-vocabulary exclusion block."""

    entries = "\n".join(cfg.blacklist)
    return (
        "Vocabulary blacklist (hard requirement):\n"
        f"Avoid the following {cfg.target_language} words and phrases as supporting "
        "vocabulary in main and note examples whenever possible. This is best effort: "
        "the requested learning concept may still be used when it overlaps an entry.\n"
        f"{entries}"
    )


def build_customization_prompt(cfg: PromptConfig) -> str:
    """Build the free-form user customization block without reinterpreting it."""

    instructions = "\n".join(cfg.customization)
    return (
        "User customization:\n"
        "These instructions may override built-in content and style preferences. "
        "They cannot override hard requirements or the current input item's explicit "
        "request.\n"
        f"{instructions}"
    )


def assemble_system_prompt(cfg: PromptConfig, *, minimal_cards: bool) -> str:
    """Join prompt pieces with explicit precedence and optional user overlays."""

    pieces = [
        build_system_prompt(cfg),
        build_instruction_contract_prompt(cfg, minimal_cards=minimal_cards),
    ]
    if cfg.blacklist:
        pieces.append(build_blacklist_prompt(cfg))
    pieces.extend(
        [
            build_core_concept_prompt(cfg),
            build_cefr_prompt(cfg),
            build_flashcard_prompt(cfg),
        ]
    )
    if not minimal_cards:
        pieces.append(build_notes_prompt(cfg))
    if cfg.customization and not minimal_cards:
        pieces.append(build_customization_prompt(cfg))
    return "\n\n".join(pieces)


def build_card_messages(
    item: str,
    cfg: PromptConfig,
    *,
    minimal_cards: bool,
) -> list[dict[str, str]]:
    """Build chat messages for one loose input item."""

    return [
        {
            "role": "system",
            "content": assemble_system_prompt(cfg, minimal_cards=minimal_cards),
        },
        {"role": "user", "content": f"Input item: {item.strip()}"},
    ]
