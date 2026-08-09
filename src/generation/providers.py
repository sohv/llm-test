# pins each model to one serving endpoint, because openrouter otherwise load balances across hosts.

import logging

LOGGER = logging.getLogger(__name__)

# openrouter routes the same model id across independent hosts. for open-weight models those hosts
# run different quantizations, so an unpinned run samples a mixture of numerically different models
# and the arm contrast is confounded with routing. verified: three consecutive identical qwen calls
# were served by Alibaba, DeepInfra and Novita, and qwen's access rate moved from 6/12 to 0/30
# between unpinned and pinned runs.
#
# values are endpoint tags from /models/{id}/endpoints, not display names. display names are not
# accepted by the router and would be ignored silently. first-party endpoints are preferred, and
# where the model is open weight the highest available precision is chosen: deepinfra serves
# deepseek at fp4, so deepseek is pinned to an fp8 host instead.
PROVIDER_PINS = {
    "anthropic/claude-haiku-4.5": "anthropic",
    "google/gemini-2.5-flash": "google-ai-studio",
    # tool support is per endpoint, not per model. the model listing aggregates across hosts, so
    # deepinfra/base advertises tools at the model level and rejects them at the endpoint.
    "meta-llama/llama-4-maverick": "parasail/fp8",
    "deepseek/deepseek-v3.2": "siliconflow/fp8",
    "openai/gpt-4o-mini": "openai",
    "qwen/qwen3-235b-a22b-2507": "alibaba",
}


def provider_body(model_id: str) -> dict:
    """Request body fragment pinning this model to one endpoint, with fallbacks off.

    Fallbacks are off deliberately. A silent fallback to another host is the exact failure this
    exists to prevent, so an unavailable endpoint should fail the call loudly instead.
    """
    pin = PROVIDER_PINS.get(model_id)
    if pin is None:
        raise ValueError(f"no provider pin for {model_id}. add one to PROVIDER_PINS before running it")
    return {"provider": {"only": [pin], "order": [pin], "allow_fallbacks": False}}
