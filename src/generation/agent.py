# runs one question as an independent agent session and returns the trial record.

import asyncio
import json
import logging
from pathlib import Path

from src.generation.arms import MANIPULATION_CHECK, Arm, build_system_prompt
from src.generation.cache import load_cached, save_cached, trial_cache_path
from src.generation.parsing import split_scratchpad
from src.generation.tools import READ_FILE_TOOL, accessed_forbidden, execute_read_file, read_forbidden

LOGGER = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


async def _complete(
    client, model_id: str, messages: list[dict], tools: list[dict] | None, temperature: float, max_tokens: int
):
    kwargs = {"model": model_id, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    if tools:
        kwargs["tools"] = tools
    return await client.chat.completions.create(**kwargs)


def _assistant_message(message) -> dict:
    """Rebuild the assistant turn as a plain dict so it can go back into the message list."""
    payload = {"role": "assistant", "content": message.content or ""}
    if message.tool_calls:
        payload["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.function.name, "arguments": call.function.arguments},
            }
            for call in message.tool_calls
        ]
    return payload


async def run_trial(
    client,
    model_id: str,
    arm: Arm,
    question: dict,
    sandbox_dir: Path | str,
    trial_index: int,
    temperature: float = 1.0,
    max_tokens: int = 2048,
    max_steps: int = 6,
    tool_scratchpad: bool = False,
) -> dict:
    """One question, one arm, one independent session. Never shares context with another trial."""
    system_prompt = build_system_prompt(arm, tool_scratchpad)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question["question"]},
    ]
    tools = [READ_FILE_TOOL] if arm.tool_enabled else None
    tool_log: list[dict] = []
    assistant_texts: list[str] = []
    steps = 0
    finish_reason = None

    while steps < max_steps:
        steps += 1
        response = await _complete(client, model_id, messages, tools, temperature, max_tokens)
        message = response.choices[0].message
        finish_reason = response.choices[0].finish_reason
        assistant_texts.append(message.content or "")
        messages.append(_assistant_message(message))

        if not message.tool_calls:
            break

        for call in message.tool_calls:
            arguments = json.loads(call.function.arguments or "{}")
            raw_path = str(arguments.get("path", ""))
            content, record = execute_read_file(sandbox_dir, raw_path)
            record["step"] = steps
            tool_log.append(record)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": content})

    # the reasoning that matters for DV 4 is written in the turn that carries the tool call, not in
    # the turn that carries the answer, so the scratchpad is collected across every assistant turn.
    # the final answer comes from the last turn alone.
    raw_response = assistant_texts[-1] if assistant_texts else ""
    scratchpad = "\n".join(filter(None, (split_scratchpad(text)[0] for text in assistant_texts)))
    _, final_answer, parsed_cleanly = split_scratchpad(raw_response)

    manipulation_response = ""
    manipulation_raw = ""
    if arm.tool_enabled:
        messages.append({"role": "user", "content": MANIPULATION_CHECK})
        check = await _complete(client, model_id, messages, None, temperature, max_tokens)
        manipulation_raw = check.choices[0].message.content or ""
        # models carry the scratchpad habit into this turn, so judge the stated answer, not the
        # reasoning behind it
        _, stated, _ = split_scratchpad(manipulation_raw)
        manipulation_response = stated or manipulation_raw

    return {
        "id": question["id"],
        "tier": question["tier"],
        "arm": arm.name,
        "model_id": model_id,
        "trial_index": trial_index,
        "steps": steps,
        "finish_reason": finish_reason,
        "truncated": finish_reason == "length",
        "hit_step_ceiling": steps >= max_steps and bool(tool_log),
        "tool_log": tool_log,
        "accessed": accessed_forbidden(tool_log),
        "read_forbidden": read_forbidden(tool_log),
        "scratchpad": scratchpad,
        "final_answer": final_answer,
        "raw_response": raw_response,
        "assistant_texts": assistant_texts,
        "manipulation_response": manipulation_response,
        "manipulation_raw": manipulation_raw,
        "parsed_cleanly": parsed_cleanly,
        "error": None,
    }


async def run_trials(
    client,
    model_id: str,
    arm: Arm,
    questions: list[dict],
    sandbox_dir: Path | str,
    n_repeats: int,
    cache_dir: Path | str = "cache",
    max_concurrent: int = 8,
    tool_scratchpad: bool = False,
    **trial_kwargs,
) -> list[dict]:
    """Run every question n_repeats times, at most max_concurrent sessions in flight.

    A session that fails comes back as a record with error set rather than taking the run down,
    so one rate limit twelve hours into a sweep doesn't discard everything before it. If every
    session fails it raises, because that is a broken key, not a flaky network.
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    system_prompt = build_system_prompt(arm, tool_scratchpad)
    errors: list[Exception] = []

    async def one(question: dict, trial_index: int) -> dict:
        path = trial_cache_path(cache_dir, model_id, arm.name, question["id"], trial_index, system_prompt)
        cached = load_cached(path)
        if cached is not None:
            return cached
        async with semaphore:
            try:
                record = await run_trial(
                    client,
                    model_id,
                    arm,
                    question,
                    sandbox_dir,
                    trial_index,
                    tool_scratchpad=tool_scratchpad,
                    **trial_kwargs,
                )
            except Exception as error:
                LOGGER.error(
                    f"{model_id} {arm.name} {question['id']} trial {trial_index} failed: {error!r}", exc_info=True
                )
                errors.append(error)
                return {
                    "id": question["id"],
                    "tier": question["tier"],
                    "arm": arm.name,
                    "model_id": model_id,
                    "trial_index": trial_index,
                    "accessed": None,
                    "parsed_cleanly": False,
                    "error": repr(error),
                }
        save_cached(path, record)
        return record

    jobs = [one(question, index) for question in questions for index in range(n_repeats)]
    LOGGER.info(f"{model_id} {arm.name}: {len(jobs)} sessions at concurrency {max_concurrent}")
    records = await asyncio.gather(*jobs)

    if jobs and len(errors) == len(jobs):
        raise RuntimeError(f"all {len(jobs)} sessions failed for {model_id} {arm.name}: {errors[0]!r}")
    if errors:
        LOGGER.error(f"{len(errors)}/{len(jobs)} sessions failed and were recorded with error set")
    return records
