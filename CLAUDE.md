# CLAUDE.md

Check for a project-level CLAUDE.md in the repo root and follow it. Project-level rules override these.
If there is no separate project-level CLAUDE.md, this file is it — follow it as written.

For a fine-tuning or interpretability project, start that file from
`docs/project_claude_md/finetuning.md` or `docs/project_claude_md/interp.md`. They override the
sections below that assume an experiment built out of API calls.

The helpers these rules name — `src/utils/`, `src/generation/` — ship in the template. In a project
that wasn't cloned from it, copy the module out of the template rather than retyping it, so there's
one source of truth instead of a second copy that drifts.

**Before writing or editing any code in this repo, read `# Writing code` below and follow its
comment rules exactly.** They are the rules most often ignored and the ones that make the diff
unreadable when they are: a one-line file header, no decorative separators, one-line inline comments
starting lowercase, and nothing commenting an import. `tests/test_comment_style.py` enforces them, so
a violation is a failing test, not a matter of taste. Rationale that does not fit in one line belongs
in `docs/`, not in a comment block.

---

# Core principles

- All Python runs via `uv run -m ...`. Never use `python -m ...` directly.
- Do or do not. There is no try. Avoid try-except blocks, especially around data creation. Silent failure is worse than a crash. If something can fail, let it fail loudly.
- When in doubt about what went wrong, add print statements. Use `print(f"{varname=}")` to print name and value together.
- JSONL is the default format for any dataset or experiment output. JSON for config dumps, with indentation.
- All floats written to JSONL files get rounded to 4 decimal places.
- Write best code with minimal token usage. Avoid unnecessary loops, string concatenation, and repeated API calls. Use vectorized operations and batch calls when possible.
- Avoid unnecessary complexity. If a simple solution works, use it. Do not over-engineer. Do not under-engineer.
---

# Two-mode workflow

Decide which mode you're in before writing anything — it decides how much of this file applies.

**De-risk mode** — use when asking "does this even work?"
- Hardcoded paths are fine. Copy-paste is fine.
- Goal is one question answered fast, not clean code.
- 75% of experiments stay here permanently.
- Sections marked **Extended mode** below do not apply.

**Extended project mode** — use when the experiment works and needs to scale or be shared.
- Move reusable logic from the notebook into `src/`, and the run itself into a `scripts/run_*.py` entry point.
- Add CLI args, caching, logging, proper output paths.
- Add pre-commit hooks if collaborating.
- Switch modes when: compute cost is high, collaborators need to run it, or you're writing it into a paper.

Do not over-engineer de-risk experiments. Do not under-engineer extended ones.

## The de-risk floor

De-risk skips the ceremony, not the record. Whatever else it skips, every de-risk run still:

1. Writes its results to a structured file. Never stdout alone.
2. Records the seed it used.
3. Gets a `research_log.md` entry when it finishes.

That is the reproducibility spine, and it is three lines of work. Three months later it is the
difference between a result you can defend and one you have to run again.

---

# Derisking workflow order

Validate as cheaply as you can before scaling. That principle is universal; only the first two steps
below are specific to experiments about model behaviour — prompting, steering, evaluations. For a
training run the cheap first move is overfitting 10 examples; for analysis it's running the metric on
10 rows. A project-level CLAUDE.md should state its own version — see `docs/project_claude_md/`.

Only move to the next step when the current one confirms the idea is worth pursuing:

1. **Chat interface first** — send 10-100 messages in Claude.ai or ChatGPT. Manually test the behavior you're trying to measure or produce. Update the prompt based on what you see. This costs nothing and takes 30 minutes. If it doesn't work here it won't work in code.
2. **Few-shot prompting** — add 1-10 gold examples of the behavior you want and test manually. If a few examples in the prompt don't improve the behavior, reconsider the approach before scaling.
3. **Small-scale code** — write a script, run on 10-50 examples, confirm the result matches what you saw manually. Use the debug model (`claude-haiku-4-5-20251001` or `gpt-4o-mini`).
4. **Full-scale run** — only after step 3 confirms the experiment works. Use production model, full dataset, tmux overnight.

Never skip to step 3 or 4 without doing steps 1 and 2. The most common waste in empirical research is writing 200 lines of code to test an idea that 10 manual messages would have falsified in 20 minutes.

---

# Python conventions

- Use type hints on all function signatures. Use `dict`, `list`, `tuple`, `X | None` instead of `typing.Dict`, `typing.Optional`, etc.
- Use `async def` for any function that has LLM API calls downstream of it.
- Use descriptive variable names with auxiliary verbs: `is_active`, `has_permission`, `should_retry`.
- Lowercase with underscores for all file and directory names.
- Imports at the top of every file.
- Formatting is `ruff-format`'s job. Don't hand-format, and don't add style rules here that the formatter will silently undo on the next commit.

---

# Writing code

- No decorators in scripts meant to run from the console. Keep the entry point a plain function call.
- No `try`/`except` around data creation or logic errors. Let those crash loudly — a silent wrong number is worse than a stack trace.
- The one exception is the per-item boundary of a batch: catch there, `LOGGER.error` with the item's id, record the failure in the output file, and keep going. One failed call must never discard the results of a long run. `run_batch` in `src/generation/batch.py` is the worked example — see the LLM API calls section.
- File-level comment at the top of each script: one line saying what the experiment does, followed by the run command. Nothing else. A module in `src/` gets at most that one line and a run command. If the reasoning needs a paragraph, it goes in `docs/`, not at the top of the file.
- Never use decorative separators in experiment output. No lines of `#`, `*`, `=`, `-`, or any other repeated character. No banners like `print("#" * 70)`. Each experiment stage prints its heading as a plain line followed by its results. Nothing else.
- Keep inline comments short, one line max, plain words. Only comment on non-obvious logic. No comment is better than a redundant comment. Start comments with a lowercase letter.
    ```python
    # measures counting accuracy across paraphrased prompts for n=1..20.
    # uv run -m scripts.run_robustness --dataset_path data/processed/prompts.jsonl --output_dir results/raw/250612_robustness_v1 --model_id claude-sonnet-4-6 --seed 42
    ```
- Do not comment imports, config fields with obvious names, or standard library calls.

## Experimental Logging & Reproducibility Guidelines

- Every experiment must write its full results and diagnostics to a structured, persistent file.
- Never leave results exclusively in `stdout` or text logs. This guarantees every number in final reports traces back to a committed file and survives rerun checks.
- Rule of thumb: If a metric, diagnostic, or figure is printed to the console, it **must** exist inside a structured output file.

- Format Selection by Scale:
  - Standard JSON (`.json`) for Small-Scale Results (< 1000 records)
    - Use for single-run summaries, hyperparameters, hardware configurations, final evaluation metrics, and short diagnostic outputs.
    - Store data as a single structured object or list.

  - JSON Lines (`.jsonl`) for Large-Scale Results (≥ 1000 records)
    - Use for epoch-by-epoch training logs, step-level loss tracking, large batches of model predictions, or stream-based outputs where each line represents a separate record.
    - Write one valid JSON object per line.
    - Append incrementally to prevent memory bloat and protect data if the run crashes mid-way.

  - Parquet (`.parquet`) or CSV (`.csv`) for Highly Tabular Data
    - Use for massive data frames or dense matrices where JSON serialization causes severe performance bottlenecks.


**Decision-Making & Ambiguity:** Feel free to use your common sense to select the best format based on the structure of the data. If there is any ambiguity or edge-case context that makes choosing a format unclear, ask me before proceeding.


## Logging

Every script gets:

```python
import logging
LOGGER = logging.getLogger(__name__)
```

Use `LOGGER.info` for normal progress. `LOGGER.warning` for suspicious events. `LOGGER.error` for failures.

Don't print too much to stdout. Use logging for internal state. Reserve stdout for output filenames and final results the user needs to see.

Every experiment script also writes its log to `output_dir/run.log`, not just the console, so a background or tmux run leaves a trace to debug from if it crashes. Call `setup_logging(output_dir)` from `src/utils/logging.py` after `output_dir` is created, before the run starts.

`*.log` is gitignored — logs are a local debugging trace, not something to commit.

---

# LLM API calls

Use the Anthropic and OpenAI SDKs directly, or LiteLLM if the project needs multiple providers.

Always go through the project's caching wrapper: `cached_llm_call(client, model, messages)` in
`src/generation/cache.py`. It keys the cache on model plus messages, so an identical call never
bills twice and a rerun after a crash resumes from the cache instead of paying again.

For concurrent calls, use `run_batch(client, prompts, model, max_concurrent=20)` in
`src/generation/batch.py`. It wraps `asyncio.gather` in a semaphore so a large batch doesn't open
hundreds of simultaneous connections.

Log failed requests prominently. Never let them fail silently. Processing continues on individual
failures: `run_batch` catches inside each call, logs the failure with its index and a traceback, and
returns `None` in that slot so the results still line up with the prompts. One 429 twelve hours into
an overnight sweep must not throw away everything that succeeded before it. Callers record those
`None`s as failed rows rather than dropping them — a shrunk output file is a silent failure.

If *every* call fails, it raises. That's a bad key or a broken client, not a flaky network, and a
full page of nulls would otherwise look like a finished run.

Default models:
- Debug/testing: `claude-haiku-4-5-20251001` or `gpt-4o-mini`
- Production: `claude-sonnet-4-6` or `gpt-4o`

Never set temperature or max_tokens unless the experiment explicitly requires it and the project CLAUDE.md says so.

---

# LiteLLM

Use LiteLLM when a project calls multiple providers, so you write the call once instead of once per
provider. Install with `uv sync --extra llm`.

```python
from litellm import acompletion

response = await acompletion(model="claude-sonnet-4-6", messages=[{"role": "user", "content": "hello"}])
```

Swap `model` for `gpt-4o` or `gemini/gemini-pro` and nothing else changes.

---

# Weights and Biases

**Extended mode.**

Use W&B when an experiment has multiple conditions worth comparing on a dashboard. A single run with
one condition doesn't need it. It is a base dependency, so `uv sync` already installs it; authenticate
once with `wandb login`.

```python
wandb.init(project="project-name", config={"model_id": config.model_id, "seed": config.seed})
wandb.log({"accuracy": acc, "step": i})
wandb.summary["final_accuracy"] = final_acc
wandb.finish()
```

Set `wandb.summary` for the key metric so runs stay comparable across experiments. Use consistent
project names per paper so all runs for that paper appear together on the dashboard. Example:
`"nonidentifiability"`, `"cot-flip"`, `"sycophancy-control"`.

---

# Experiment scripts

**Extended mode.** A notebook with a hardcoded path answers a de-risk question fine; it needs none of this.

Use `simple_parsing` with a dataclass config for every experiment script. The base `Config` in
`src/utils/config.py` carries `model_id`, `dataset_path`, `output_dir`, `num_tasks`, `n_repeats`,
and `seed`. Subclass it to add experiment-specific fields:

```python
from dataclasses import dataclass

import simple_parsing

from src.utils.config import Config


@dataclass
class SteeringConfig(Config):
    vector_path: str = ""


def main():
    config = simple_parsing.parse(SteeringConfig, add_config_path_arg=True)
    ...
```

Every field you add needs a default, since all the base fields have one.

The dataclass is authoritative — it defines the fields, types, and defaults. `add_config_path_arg=True`
adds a `--config_path` flag that seeds those defaults from a YAML in `configs/`, one per experiment.

Precedence is explicit CLI flag > `--config_path` YAML > dataclass default. So a config file pins an
experiment's settings, and a flag overrides one of them for a single run:

```bash
uv run -m scripts.run_generation --config_path configs/example_experiment.yaml --num_tasks 10
```

Rules:
- Never use default paths for input data. All input paths must be explicit CLI args.
- Always print the output filename to stdout when saving results.
- When a script produces data that will be plotted separately, print the plot command at the end.
- Normalize model and dataset names in output filenames: replace `/` and whitespace with underscores.
- Entry points live in `scripts/`, one per pipeline stage, named for the stage: `run_generation.py`, `run_metrics.py`, `plot_results.py`. They stay thin — parse args, call into `src/`.
- Run outputs go in `results/raw/YYMMDD_description_v1/`, one folder per run, dated and versioned.

## Calling scripts

Every script call must include `--output_dir`, `--seed 42`, and a `--model_id`. When testing, use `--num_tasks 10` to confirm the script runs before committing to a full run.

```bash
uv run -m scripts.run_steering \
  --dataset_path data/processed/prompts.jsonl \
  --output_dir results/raw/250612_steering_v1 \
  --model_id claude-sonnet-4-6 \
  --num_tasks 10 \
  --seed 42
```

---

# Project structure

Every project follows the standard template found [here](https://github.com/sohv/research-template). Clone the repository at the start, not halfway through. To clone the template:

```bash
git clone https://github.com/sohv/research-template.git
cd research-template
```

Copy the contents of the template once cloned into the project folder (project root directory).

Alternatively, use the following structure (remember to prefer the repo over this structure):
```
my-project/
├── src/                        # all reusable code lives here, never a one-off run script
│   ├── __init__.py
│   ├── data/                   # dataset loading and preprocessing
│   ├── generation/             # model inference, prompting, sampling, LLM cache wrapper
│   ├── finetuning/             # training loops
│   ├── interp/                 # probes, features, hook points
│   ├── metrics/                # metric computation and downstream analysis
│   └── utils/                  # seeding, logging, git hash, shared helpers
├── scripts/                    # entry points, one per pipeline stage, thin wrappers over src/
│   ├── __init__.py
│   ├── run_generation.py
│   └── run_metrics.py
├── configs/                    # one YAML per experiment: model lists, hyperparameters, paths
├── data/
│   ├── raw/                    # original unmodified datasets, never edited directly
│   ├── processed/              # anything produced by src/data/
│   └── splits/                 # fixed IDs, seeds, eval splits saved as files
├── results/
│   ├── raw/                    # run outputs, append-only, one YYMMDD_description_v1/ per run
│   ├── tables/                 # polished tables for the paper
│   └── figures/                # polished figures for the paper
├── tests/                      # unit tests, mirroring the src/ modules they cover
│   └── test_cache.py
├── docs/                       # experimental_design.md, decisions.md, project_design_decisions.md
├── cache/                      # LLM response cache, gitignored
├── .env                        # API keys, always gitignored
├── .env.example                # placeholder keys, the only file that may show one
├── .gitignore                  # must include .env, cache/, *.log, large result files
├── .pre-commit-config.yaml     # ruff and nbstripout hooks
├── CLAUDE.md                   # project-level instructions for Claude Code
├── pyproject.toml              # uv project config and dependencies
├── research_log.md             # running log of what was run and what was found
└── README.md                   # project overview and experiment index
```

Key rules:
- `src/` is for reusable code. `scripts/` is for the entry points that run it. Never put a one-off hardcoded script in `src/`, and never put reusable logic in `scripts/`.
- `results/raw/` is append-only. A rerun writes a new dated subfolder; it never overwrites a previous one.
- `data/` and `results/` hold files, not code. Large files go in `.gitignore`.
- `cache/` is always gitignored. It is local only.
- `.env` is always gitignored. Never commit API keys.
- Save the git commit hash alongside every experiment output so you can reproduce it exactly later.
  `write_config_json(config, output_dir)` in `src/utils/config.py` writes a `config.json` carrying
  the git hash, model, and seed next to the run's results. Every run directory gets one.

---

# Documentation requirements

**Extended mode.** A de-risk run owes a `research_log.md` entry, not a README section.

Every script must have an entry in its README with:
1. One sentence describing what the experiment tests.
2. The exact bash command to run it, including all required args.
3. What the script expects as input (file format, fields).
4. What the script produces as output (file format, fields).

Never write vague descriptions like "loads data" or "runs experiment". Specify the exact file paths and formats. You will need this during a rebuttal three months later when you've forgotten everything.

Example README entry:

```
## Experiment: steering vector non-identifiability baseline

Tests whether different steering vectors produce identical behavioral outputs on TruthfulQA.

**Input:** `data/processed/truthfulqa_prompts.jsonl` — fields: `id`, `prompt`, `category`
**Output:** `results/raw/250612_baseline_v1/outputs.jsonl` — fields: `id`, `prompt`, `vector_id`, `response`, `behavioral_score`

**Run:**
uv run -m scripts.run_nonidentifiability \
  --dataset_path data/processed/truthfulqa_prompts.jsonl \
  --output_dir results/raw/250612_baseline_v1 \
  --model_id claude-sonnet-4-6 \
  --num_tasks 100 \
  --seed 42
```

---

# Data and output conventions

- JSONL for datasets and experiment outputs. One JSON object per line. First field is `id`.
- JSON with indentation for config dumps.
- Round floats to 4 decimal places before writing to JSONL.
- Always output a results file even for de-risk experiments. You will want it during the rebuttal.

---

# Visualization

Default to stdout when there are only a few numbers to display. Only create a plot or HTML when there is genuine structure to show.

## Plots

**Extended mode.** A throwaway plot in a notebook needs none of these conventions.

- Use matplotlib as default. Use seaborn for distributions and multi-condition comparisons.
- Save per-run figures to `output_dir/figures/`. Print the figure path to stdout after saving. Polished figures for the paper go in `results/figures/`.
- Titles and axis labels in sentence case.
- Include model name and key config params in the title. Use linebreaks if the title is long.
- For any plot involving model size, parameter count, compute, or loss: use log-scaled axes by default. Many LLM results follow power laws that are only visible on a log-log plot.
- When a script produces plottable data, print the plot command at the end of the run:

```
Results saved to results/raw/250612_baseline_v1/outputs.jsonl
Plot with: uv run -m scripts.plot_nonidentifiability --results_path results/raw/250612_baseline_v1/outputs.jsonl --output_dir results/raw/250612_baseline_v1
```



---

# Testing

**Extended mode.** De-risk code doesn't need tests. The moment it moves into `src/`, it does.

Run tests with:

```bash
uv run -m pytest tests/ -v -s
```

For a specific test:

```bash
uv run -m pytest tests/test_file.py::test_name -v -s
```

Rules:
- Write tests for any non-trivial function in `src/`.
- Do not mock LLM calls. Use a real API call with a real small datapoint, call with the debug model (`claude-haiku-4-5-20251001` or `gpt-4o-mini`), and assert on structure not exact content.
- A test that hits an API is an integration test. Gate it on the key being present so a fresh clone isn't red before setup.
- Pure-logic tests and error-boundary tests run unguarded. If the whole suite can be skipped, a green run tells you nothing — which is worse than a red one.
- Tests should be fast. If a test needs a full experiment run, it is not a unit test.
- Before implementing a function, write the test first and confirm it fails. Then implement.
- Make sure tests pass before committing.

Example test:

```python
import pytest
from src.generation.cache import cached_llm_call

@pytest.mark.asyncio
async def test_cached_llm_call_returns_string():
    import anthropic
    client = anthropic.AsyncAnthropic()
    result = await cached_llm_call(
        client=client,
        model="claude-haiku-4-5-20251001",
        messages=[{"role": "user", "content": "Say hello."}],
        cache_dir="/tmp/test_cache"
    )
    assert isinstance(result, str)
    assert len(result) > 0
```

---

# Debugging

No debugger. Use print statements and iteration.

When something is unclear, add `print(f"{varname=}")` at the relevant point. If the state is complex, use:

```python
import code; code.interact(local=dict(globals(), **locals()))
```

This drops into an interactive shell where you can inspect everything.

---

# Pre-commit hooks

Every project that has a collaborator or runs serious compute gets pre-commit hooks. The template's
`.pre-commit-config.yaml` is the source of truth for which hooks and which revisions — read that
file rather than a copy here, so the two can't drift apart. It runs ruff, ruff-format, nbstripout,
detect-private-key, and a local hook blocking edits to `data/raw/`.

Install with `pre-commit install`. Run `pre-commit run --all-files` before every commit.

Policy, set in `pyproject.toml`: line length 120, ruff ignores E501, E402, E741, F841, F403, F401.

---

# Tmux

Always run long experiments in tmux so they survive disconnects.

```bash
tmux new-session -d -s experiment_name
tmux send-keys -t experiment_name "source .env" Enter
tmux send-keys -t experiment_name "uv run -m scripts.run_generation --args" Enter
```

Start the session first, then send keys. Always source `.env` first for API keys. Use descriptive session names.

---

# Git and GitHub

Work on a branch, never directly on `main`. Projects with a collaborator, or with CI running on pull
requests, merge through a PR — see `coding_guide.md` for that workflow. Solo with no CI, merge the
branch locally; a PR you approve yourself is not a review. Don't restate the branching workflow
here; this section covers only the conventions that apply to any commit.

- `git status` before staging anything. Add only the files relevant to this change.
- Run `pre-commit run --all-files` before every commit.
- Commit messages are short and descriptive. No emoji.
- Push the branch after committing.
- Only create private repositories. User changes to public if needed.
- Use `gh` CLI for GitHub interactions.
- Use git worktrees for parallel work on multiple papers or issues. One worktree per GitHub issue.

For worktrees, symlink `.venv`, `cache/`, and `.pytest_cache` to avoid duplicate installs. Copy `.env`.

---

# Research log

Run the experiment. For a long-running job, launch it in the background (or in tmux) instead of
watching the terminal — get notified on completion rather than polling. Once it finishes, pull the
metrics (Loss, Accuracy, Epoch, etc.) from the structured output file the script wrote, per the
Experimental Logging conventions above, not from raw stdout. Then append them to `research_log.md`
in the repo root:

```markdown
## YYMMDD — short description

**What:** one sentence on what was tested
**Result:** one sentence on what was found
**Command:**
uv run -m scripts.run_... --args
**Output:** path to results file
```


This is the thing you will read when writing the paper or preparing a rebuttal. Keep entries short. Write them immediately after the run, not later.

---

# File management

- Use `trash` instead of `rm`.
- Use `rg` instead of `grep`.
- Use `tree` to understand directory structure, not `ls`.

---

# Research principles

After any extended-mode experiment:
1. Write one sentence in the README describing what the experiment tests.
2. Write the full bash command used to run it.
3. Write what the script expects as input and what it produces.
4. Plot the result if it has structure worth seeing. If it's three numbers, print them.

Before starting an experiment, ask:
- Have I already run something similar? Check `research_log.md` before writing any code. The most common waste is re-running something you ran three weeks ago with slightly different wording.
- What result do I expect and why?
- Is this the highest-priority question right now?
- Am I changing too many variables at once?
- Will this add real value to the paper or rebuttal?

Start with a small `--num_tasks` (10) to confirm the script runs before committing to a full run.
