#!/usr/bin/env bash
# restarts the study until it completes, because long runs keep getting reaped in this environment.
# setsid nohup bash scripts/supervise_study.sh >> results/raw/260809_study_run.log 2>&1 < /dev/null &
cd /teamspace/studios/this_studio/llm-test
for attempt in $(seq 1 40); do
  echo "SUPERVISOR: attempt $attempt"
  if bash scripts/run_full_study.sh; then
    echo "SUPERVISOR: finished cleanly"
    exit 0
  fi
  echo "SUPERVISOR: run exited non-zero, resuming from cache in 15s"
  sleep 15
done
echo "SUPERVISOR: giving up after 40 attempts"
exit 1
