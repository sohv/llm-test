#!/usr/bin/env bash
# runs both levels of the prompt factor over all four arms and all three models.
# tmux new-session -d -s study && tmux send-keys -t study "bash scripts/run_full_study.sh" Enter
set -euo pipefail
cd /teamspace/studios/this_studio/llm-test

for level in plain instructed; do
  flag=false
  [ "$level" = instructed ] && flag=true
  uv run -m scripts.run_study \
    --dataset_path data/processed/questions.jsonl \
    --key_source data/processed/session_notes.txt \
    --output_dir "results/raw/260808_study_${level}_v1" \
    --tool_scratchpad "$flag" \
    --n_repeats 5 --seed 42
  uv run -m scripts.score_study \
    --dataset_path "results/raw/260808_study_${level}_v1/outputs.jsonl" \
    --key_path data/processed/answer_key.jsonl \
    --output_dir "results/raw/260808_study_${level}_v1" \
    --seed 42
done
echo "FULL STUDY COMPLETE"
