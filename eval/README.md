# The labelled case set

`bidscout eval` measures the extractor against the files in `eval/cases/`.
Each file holds two things:

- `section3_raw` — the portal's Section 3 exactly as it arrived. Never edit
  it and never trim it (ground rule 3). A parser change is re-measured by
  replaying these.
- `labels` — what **a person** reads in that payload. Written by hand. The
  extractor never writes a label; a harness that labels its own input
  measures nothing.

## Adding a case

```bash
bidscout capture 1096282              # from a Section 3 already in the database
bidscout capture 1096282 --live       # fetch it from the portal first
```

That writes `eval/cases/cn1096282.json` with `labelled: false`. Open it, read
the buyer's own sentence, and fill the labels in:

```json
"labels": {
  "turnover":   {"amount": "2700000.00", "currency": "RON"},
  "experience": {"amount": null,         "currency": null}
}
```

- **Quote every amount as a string.** An unquoted `2700000.10` is read by
  `json` as a binary float and is not the number you typed. The loader
  refuses it rather than round it.
- **`"amount": null` is a real answer**, not a blank. It means the buyer
  states the requirement and names no figure a machine can read. The right
  behaviour is a requirement with no number, which the engine turns into
  CHECK. A number there is an *invention* and gets its own column.
- **Delete the kinds the buyer does not state.** A kind left in the file is
  read as "the buyer asks for this", so an unwanted entry turns a correct
  silence into a miss.
- Set `labelled: true` when you are done. Until then the case is listed and
  left out of every figure, so an unfinished file cannot lift the score.

## Reading the table

| column | meaning |
|---|---|
| `stated` | the buyer asks for this, per the label |
| `figure` | of those, the cases where a person could read a number |
| `cover` | of `figure`, how often the extractor found a number at all |
| `prec` | of the numbers it found, how often it was right |
| `missed` | the buyer asks for it and the extractor reported nothing |
| `invent` | a number the buyer never wrote — the one that can cost a bid |
| `spur` | a requirement reported that the buyer does not state |

A `-` is not a zero. It means there was nothing of that kind to measure.

## Honest limits, 30 September 2026

Three cases: two transcribed from the 20 September spike and one written by
hand to hold the "three financial years" trap and a euro guarantee. That is
a smoke test. Thirty captured notices would make `cover` a number worth
quoting; until then the 60% in `README.md` stays a guess.
