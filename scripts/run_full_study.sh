#!/usr/bin/env bash
# runs both prompt levels over all four arms: 5 repeats for the floored models, 20 for deepseek.
# tmux new-session -d -s study && tmux send-keys -t study "bash scripts/run_full_study.sh" Enter
set -euo pipefail
cd /teamspace/studios/this_studio/llm-test

DATA=data/processed/questions.jsonl
KEY=data/processed/session_notes.txt
STAMP=260809

run_cell () {
  local level=$1 tag=$2 reps=$3 flag=$4
  shift 4
  local out="results/raw/${STAMP}_study_${level}_${tag}"
  uv run -m scripts.run_study \
    --dataset_path "$DATA" --key_source "$KEY" --output_dir "$out" \
    --tool_scratchpad "$flag" --n_repeats "$reps" --max_concurrent 6 --seed 42 \
    --models "$@"
  uv run -m scripts.score_study \
    --dataset_path "$out/outputs.jsonl" --key_path data/processed/answer_key.jsonl \
    --output_dir "$out" --seed 42
}

for level in plain instructed; do
  flag=false
  [ "$level" = instructed ] && flag=true
  run_cell "$level" core 5 "$flag" anthropic/claude-haiku-4.5 google/gemini-2.5-flash
  run_cell "$level" deepseek 20 "$flag" deepseek/deepseek-v3.2
done

echo "FULL STUDY COMPLETE"
