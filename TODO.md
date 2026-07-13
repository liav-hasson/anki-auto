# TODO

## [Planned]

- **AI features**
  - Randomize AI voice setting.
  - Allow other AI providers using litellm
  - Return token / cost metadata
- **Prompt features**
  - Seperate notes per level (A1-2 should show conjugation, explain readings - while B1+ explain deeper concepts)
- **Visual**
  - Progress bar + tracking time.
- **Avoid repetition**
  - Option 1: Each card returns a list of vocabulary used (nouns, adjectives, verbs, adverbs, connectors, etc..). batch generation sends this vocabulary list in each following card so we force new vocabulary. this list may also be persisted and the user may add his own words to avoid.
  - Option 2: Group generation from single input to avoid repearing vocab.
  - Option 3: Hold a set of specific "sentence styles" (100+) grouped via CEFR level. then randomly select 4-5 and attach to prompt.
