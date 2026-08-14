# Voice Samples

Drop the channel creator's own writing samples here (`.txt` or `.md` files) for
**writer-profile distillation** in the Humanization Gate (Script + Publish stages).

## How it's used

The `humanize` skill extracts style hypotheses from your samples before rewriting:

1. Sentence-length pattern (variance, signature fragments)
2. Word-choice level (casual vs. academic; "stuff"/"thing" vs. "elements"/"components")
3. Paragraph openers (straight in? context first? a question?)
4. Punctuation habits (em dashes, parentheticals, ellipses, fragments)
5. Recurring phrases / verbal tics ("honestly", "basically", "look,")
6. Transition style (explicit connectors, or next thought with no bridge)

Then scripts, hooks, and publish metadata are rewritten to match that voice —
not generic human tone.

## What to add

- 2-3 paragraphs of writing in the creator's natural voice
- Paste from past captions, posts, scripts, or emails they've written
- A file per register if the voice differs (e.g., `script.md`, `linkedin.md`, `email.md`)

## Checks

`creatorforge doctor` lists these files as `Voice samples ({channel})`. The
`viral-setup --check` dependency check also scans `channels/*/voice/`.
