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
        "- Use a mix of simple prepositions, interjections, connectors when natural "
        "within the sentence."
    ),
    2: (
        "Write one original sentence for each core meaning of the word "
        "(typically 2, 3 if the word has versatile meanings).\n\n"
        "- Keep sentences between 6–12 words.\n"
        "- Match {level} vocabulary and grammar — natural, idiomatic, avoid "
        "beginner-level vocabulary.\n"
        "- Vary subjects, tenses, and moods across sentences so the card shows the "
        "word flexing grammatically.\n"
        "- Each sentence must have a different creative tone / scenario, according with the core word's register "
        "(e.g. news report, making an order / appointment, having an argument, daily conversation, giving a command).\n"
        "- Use a mix of prepositions, interjections, connectors naturally within the "
        "sentence."
    ),
    3: (
        "Write one original sentence for each core meaning of the word "
        "(typically 2, 3 if the word has versatile meanings).\n\n"
        "- Keep sentences between 7–15 words.\n"
        "- Match {level} vocabulary and grammar — natural, idiomatic, avoid "
        "beginner-level vocabulary.\n"
        "- Vary subjects, tenses, and moods across sentences so the card shows the "
        "word flexing grammatically.\n"
        "- Each sentence must have a different creative tone / scenario, according with the core word's register "
        "(e.g. news report, making an order / appointment, having an argument, daily conversation, giving a command).\n"
        "- Use a mix of advanced prepositions, interjections, connectors naturally "
        "within the sentence."
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
        "- Formality register."
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
        "uses not already covered by the main examples."
    )


def assemble_system_prompt(cfg: PromptConfig, *, minimal_cards: bool) -> str:
    """Join the prompt pieces in fixed order, omitting notes when minimal."""

    pieces = [
        build_system_prompt(cfg),
        build_core_concept_prompt(cfg),
        build_cefr_prompt(cfg),
        build_flashcard_prompt(cfg),
    ]
    if not minimal_cards:
        pieces.append(build_notes_prompt(cfg))
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
