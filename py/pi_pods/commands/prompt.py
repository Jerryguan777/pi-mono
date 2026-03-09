"""Agent prompt command for pi_pods."""

import sys

from pi_pods.config import get_active_pod, load_config


async def prompt_model(
    model_name: str,
    user_args: list[str],
    pod: str | None = None,
    api_key: str | None = None,
) -> None:
    """Chat with a deployed model via the pi-agent.

    Resolves the active (or named) pod, finds the model configuration, then
    delegates to the agent main function.

    Note: The agent integration is not yet implemented and will raise
    RuntimeError, mirroring the TypeScript source behaviour.

    Args:
        model_name: Local name of the model to chat with.
        user_args: Additional arguments passed through to the agent.
        pod: Pod name override (uses active pod if None).
        api_key: Optional API key override.
    """
    if pod:
        config = load_config()
        pod_obj = config.pods.get(pod)
        if pod_obj is None:
            print(f"Pod '{pod}' not found", file=sys.stderr)
            sys.exit(1)
        active_name = pod
        active_pod = pod_obj
    else:
        active = get_active_pod()
        if active is None:
            print("No active pod. Use 'pi pods active <name>' to set one.", file=sys.stderr)
            sys.exit(1)
        active_name, active_pod = active

    model_config = active_pod.models.get(model_name)
    if model_config is None:
        print(f"Model '{model_name}' not found on pod '{active_name}'", file=sys.stderr)
        sys.exit(1)

    # Delegate to agent -- not yet implemented
    print("Agent error: Not implemented", file=sys.stderr)
    sys.exit(1)
