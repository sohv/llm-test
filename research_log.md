# Research log

One entry per run, appended immediately after the run finishes — not later. Pull the metrics from
the structured output file the script wrote, not from stdout. Newest entries at the top.

Read this before starting a new experiment. The most common waste is re-running something from
three weeks ago with slightly different wording.

## YYMMDD — short description

**What:** one sentence on what was tested
**Result:** one sentence on what was found
**Command:**
uv run -m scripts.run_generation --dataset_path data/processed/prompts.jsonl --output_dir results/raw/YYMMDD_description_v1 --model_id claude-sonnet-4-6 --seed 42
**Output:** results/raw/YYMMDD_description_v1/outputs.jsonl
