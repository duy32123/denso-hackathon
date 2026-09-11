# Workflow snapshots

Canonical store for Schema 1.0.0 workflow snapshots until the WP6 database exists.
One file per revision: `<workflow_id>.r<revision>.json`.

| Folder | Meaning | Who writes it |
|---|---|---|
| `drafts/` | Compiled from `acquisition/extraction/drafts/*.draft.json`. **Not published.** Every claim is `source_review=pending`. | `compile_workflow` only — never edit by hand |
| `dev/`, `holdout/` | Read by the exporter. Anything here ends up in the hand-off bundle and becomes immutable once exported. | Promoted from `drafts/` after human source review |

## Flow

```bash
# 1. write or edit the draft (claims point at evidence-pool candidate IDs)
python -m acquisition.extraction.evidence_pool show SRC_HAAS_0005:U0018 SRC_HAAS_0005:U0019

# 2. compile: issues every ID, builds Evidence, derives support_status, validates
python -m acquisition.extraction.compile_workflow acquisition/extraction/drafts/REAL_WF_0001.r1.draft.json

# 3. a second person (D1-C) checks every claim against the source and records ReviewEvents
#    (tooling for this step is the next D1-B issue)

# 4. promote to dev/, then export
python -m acquisition.export.exporter --split dev --check
python -m acquisition.export.exporter --split dev
```

Once a revision is in the bundle it cannot be edited or removed: changes go into
revision N+1 with `supersedes_revision` and a `change_log`.

Do not create anything under `holdout/` before the D15 pipeline lock.
