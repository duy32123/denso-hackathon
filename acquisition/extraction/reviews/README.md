# Source review (D1-C)

`source_checked` means **the claim says what the source says, no more and no less**.
It is not a statement that the procedure is technically correct; that is
`expert_validated`, which D1-C cannot give (Schema 1.0.0 section 5).

The reviewer must not be the person who wrote the draft.

## Steps

```bash
# 1. make the sheet (one row per claim)
python -m acquisition.extraction.review sheet acquisition/extraction/drafts/REAL_WF_0001.r1.draft.json

# 2. open reviews/REAL_WF_0001.r1.sheet.csv in Excel or Google Sheets
#    fill "decision": source_checked | rejected | (empty = not reviewed yet)
#    a rejection needs a "note" saying what the source does not support

# 3. record it (your GitHub username as reviewer id)
python -m acquisition.extraction.review apply acquisition/extraction/drafts/REAL_WF_0001.r1.draft.json \
    acquisition/extraction/reviews/REAL_WF_0001.r1.sheet.csv \
    --reviewer-id <github-user> --reviewer-role "D1-C annotation/QA"

# 4. check progress, then promote when everything is checked
python -m acquisition.extraction.review status  acquisition/extraction/drafts/REAL_WF_0001.r1.draft.json
python -m acquisition.extraction.review promote acquisition/extraction/drafts/REAL_WF_0001.r1.draft.json
```

Commit `*.review.json` (the record). The `*.sheet.csv` file is a scratch file and is gitignored.

## What to check on every row

Open the `watch` link (it jumps to the cue) and compare with the `claim` column.

| Check | Reject if |
|---|---|
| Faithful | The claim adds anything not heard or seen: a reason, a number, a part name, a machine model |
| Hedging kept | The source says "can", "if", "usually", or a negation, and the claim drops it |
| Attribution | The claim presents what the presenter *says* as something *shown*, or calls the presenter an engineer |
| Right field | An action is filed as a rationale, an outcome as an acceptance criterion, and so on (see the `field` column) |
| Evidence fits | The quoted cue does not contain what the claim says, or the time window is wrong |
| Visual claims | For `observed` rows, the thing described is actually visible in the frame, not just named in the narration |
| Caption errors | The claim reads a caption error in a way the audio does not support. Listen: the audio decides, not a guide or your own knowledge |

If a claim is fine but a gap you notice has no question yet, write it in the note; the
draft author adds the question. Do not approve a claim because it is technically true.
Approve it only if the source supports it.

## What happens after

- A rejected claim goes back to the draft author. Changing the claim or its evidence
  makes its old decision **stale**; `status` lists it and it must be checked again.
- `promote` refuses while anything is pending, rejected or stale, then writes
  `data/workflows/dev/` for the exporter. Once exported, the revision is frozen:
  later fixes become revision 2.
