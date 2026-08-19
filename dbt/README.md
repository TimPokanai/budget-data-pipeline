# dbt project — Phase 3 transformation

Full design rationale lives in
[`docs/phase-3-transformation.md`](../docs/phase-3-transformation.md); this
file is just the quickstart.

```bash
cd dbt

# Separate virtualenv recommended -- see requirements.txt for why.
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

dbt deps                                 # installs dbt_utils

cp profiles.yml.example profiles.yml     # fill in real values; gitignored
dbt debug --target local                 # sanity-check the connection

dbt build --target local                 # run + test everything, in order
dbt build --target neon                  # same models, against Neon
```

`dbt docs generate && dbt docs serve` renders the model docs and the DAG
diagram in `docs/phase-3-transformation.md` interactively.
