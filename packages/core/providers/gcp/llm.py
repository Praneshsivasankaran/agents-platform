"""LiteLLM-backed LLMProvider for GCP/Vertex AI.

All GCP SDK and LiteLLM imports are confined to this module.
Agent logic (agents/*/agent/) never imports from here directly.

litellm is imported lazily (inside respond()) so that this module can be imported
and the constructor called without litellm installed — the import error surfaces only
when respond() is actually called. Tests mock at litellm.completion so they must patch
the module-level name; we import litellm in respond() and then call it directly.
"""
from __future__ import annotations
import json
import math
from typing import Any

from core.interfaces.base import CoreContractModel, validate_structured_schema
from core.interfaces.errors import BillableProviderError
from core.interfaces.llm import LLMProvider, LLMResponse, Tier
from core.interfaces.usage import Usage

# litellm.completion_cost() always returns cost in USD regardless of provider_currency.
# Do not relabel this value with any other currency.
_LITELLM_COST_CURRENCY = "USD"


def _validate_nonempty_str(label: str, value: object) -> str:
    """Return stripped value; raise ValueError if non-string, None, empty, or whitespace-only.

    None is treated as "empty" (SecretStore not-found sentinel) rather than a type error,
    because it is the most common return value when a secret is absent.
    """
    if value is None:
        raise ValueError(
            f"LiteLLMProvider: {label} is empty or whitespace-only (SecretStore returned None)"
        )
    if not isinstance(value, str):
        raise ValueError(
            f"LiteLLMProvider: {label}={value!r} must be a string "
            f"(type={type(value).__name__!r})"
        )
    stripped = value.strip()
    if not stripped:
        raise ValueError(
            f"LiteLLMProvider: {label} is empty or whitespace-only"
        )
    return stripped


# Internal params recognised and stripped before forwarding to litellm.
# Any other _-prefixed key in params raises ValueError (unknown internal param).
_SUPPORTED_INTERNAL_PARAMS: frozenset[str] = frozenset({"_authorized_prompt_tokens"})



# v1 message contract: only these two keys are permitted.
# Any extra field (e.g. "name", "tool_call_id") is unknown byte-weight that
# estimate_prompt_tokens does NOT account for, which can silently defeat the
# ₹50 cost ceiling.  Reject early rather than under-count.
_ALLOWED_MESSAGE_KEYS: frozenset[str] = frozenset({"role", "content"})


def _validate_messages(messages: object) -> None:
    """Validate message list structure before conservative usage estimation or provider calls.

    Must be called before ``_conservative_usage()`` or ``litellm.completion()``.
    Enforces the v1 message contract:
    - Non-empty list of dicts.
    - Each dict has exactly the keys ``role`` and ``content`` (no extras).
    - ``role`` is a non-empty string.
    - ``content`` is a non-empty, non-whitespace-only string.

    Unknown extra keys are rejected because their serialized byte-weight is not
    included in ``estimate_prompt_tokens``, which would silently under-count
    prompt tokens and could allow the ₹50 ceiling to be breached.

    Raises ``ValueError`` — non-billable because the provider has not been called.
    """
    if not isinstance(messages, list):
        raise ValueError(
            f"LiteLLMProvider: messages must be a list, "
            f"got {type(messages).__name__!r}"
        )
    if not messages:
        raise ValueError("LiteLLMProvider: messages must be non-empty")
    for i, msg in enumerate(messages):
        if not isinstance(msg, dict):
            raise ValueError(
                f"LiteLLMProvider: messages[{i}] must be a dict, "
                f"got {type(msg).__name__!r}"
            )
        unknown_keys = set(msg.keys()) - _ALLOWED_MESSAGE_KEYS
        if unknown_keys:
            raise ValueError(
                f"LiteLLMProvider: messages[{i}] contains unknown keys "
                f"{sorted(unknown_keys)!r}; only {sorted(_ALLOWED_MESSAGE_KEYS)!r} "
                f"are permitted in v1 (extra fields are not accounted for in "
                f"token estimation and can defeat the cost ceiling)"
            )
        role = msg.get("role")
        if not isinstance(role, str) or not role.strip():
            raise ValueError(
                f"LiteLLMProvider: messages[{i}].role must be a non-empty string, "
                f"got {role!r} (type={type(role).__name__!r})"
            )
        if "content" not in msg:
            raise ValueError(
                f"LiteLLMProvider: messages[{i}] is missing required key 'content'"
            )
        content = msg["content"]
        if not isinstance(content, str):
            raise ValueError(
                f"LiteLLMProvider: messages[{i}].content must be a string, "
                f"got {type(content).__name__!r} — non-string content cannot be "
                f"safely token-estimated (fail closed)"
            )
        if not content.strip():
            raise ValueError(
                f"LiteLLMProvider: messages[{i}].content is empty or "
                f"whitespace-only — blank prompts cannot be priced safely"
            )


class LiteLLMProvider(LLMProvider):
    name = "litellm"

    def __init__(self, cfg: dict, secret_store=None) -> None:
        llm_cfg = cfg.get("llm", {})
        tier_models = llm_cfg.get("tier_models", {})
        if not tier_models:
            raise ValueError(
                "LiteLLMProvider: cfg.llm.tier_models is empty — "
                "must map 'cheap' and 'strong' to model identifiers"
            )

        # Issue 6: Validate each required tier individually, with type and blank checks.
        for required_tier in ("cheap", "strong"):
            model_id = tier_models.get(required_tier)
            if model_id is None:
                raise ValueError(
                    f"LiteLLMProvider: llm.tier_models.{required_tier} is missing or blank"
                )
            if not isinstance(model_id, str):
                raise ValueError(
                    f"LiteLLMProvider: llm.tier_models.{required_tier}={model_id!r} must be a string"
                )
            if not model_id.strip():
                raise ValueError(
                    f"LiteLLMProvider: llm.tier_models.{required_tier} is blank/whitespace-only"
                )

        self._tier_models: dict[str, str] = {str(k): str(v) for k, v in tier_models.items()}

        cost_cfg = cfg.get("cost", {})

        # LiteLLM always reports costs in USD. Validate USD FX rate is present.
        fx_rates = cost_cfg.get("fx_rates", {})
        if "USD" not in fx_rates:
            raise ValueError(
                "LiteLLMProvider: cfg.cost.fx_rates must contain 'USD' entry "
                "(LiteLLM reports all costs in USD)"
            )
        self._fx_rate: float = float(fx_rates["USD"])

        # Issue 2 Fix D: Reject zero / non-finite FX rate at construction.
        if not math.isfinite(self._fx_rate) or self._fx_rate <= 0:
            raise ValueError(
                f"LiteLLMProvider: fx_rates.USD={self._fx_rate!r} must be finite and > 0"
            )

        # Per-token fallback pricing (stored in INR/token).
        # Stored as raw (un-coerced) values first so type checks below can fire correctly.
        self._output_cpt_inr: dict[str, float] = {}
        self._input_cpt_inr: dict[str, float] = {}
        for k, v in cost_cfg.get("output_cost_per_token_inr", {}).items():
            self._output_cpt_inr[str(k)] = v  # keep raw for validation; coerced below
        for k, v in cost_cfg.get("input_cost_per_token_inr", {}).items():
            self._input_cpt_inr[str(k)] = v

        # Issue 2: Validate individual price values strictly before coercion.
        # bool is a subclass of int in Python — must check bool BEFORE numeric check.
        for label, price_map in [
            ("input_cost_per_token_inr", self._input_cpt_inr),
            ("output_cost_per_token_inr", self._output_cpt_inr),
        ]:
            for tier_key, val in price_map.items():
                if isinstance(val, bool):
                    raise ValueError(
                        f"LiteLLMProvider: cost.{label}.{tier_key}={val!r} is bool, not numeric"
                    )
                if not isinstance(val, (int, float)):
                    raise ValueError(
                        f"LiteLLMProvider: cost.{label}.{tier_key}={val!r} is not numeric "
                        f"(type={type(val).__name__!r})"
                    )
                if not math.isfinite(val):
                    raise ValueError(
                        f"LiteLLMProvider: cost.{label}.{tier_key}={val!r} is not finite"
                    )
                if val <= 0:
                    raise ValueError(
                        f"LiteLLMProvider: cost.{label}.{tier_key}={val!r} must be > 0 "
                        f"(zero price means cost is never accounted)"
                    )

        # Now safe to coerce to float.
        self._output_cpt_inr = {k: float(v) for k, v in self._output_cpt_inr.items()}
        self._input_cpt_inr = {k: float(v) for k, v in self._input_cpt_inr.items()}

        # Vertex project and location
        self._secret_store = secret_store

        # Issue 3: Validate vertex_location strictly — must be a non-empty, non-whitespace string.
        raw_location = llm_cfg.get("vertex_location", "us-central1")
        self._vertex_location: str = _validate_nonempty_str("vertex_location", raw_location)

        vertex_project_direct = llm_cfg.get("vertex_project")
        vertex_project_secret_key = llm_cfg.get("vertex_project_secret", "")

        if vertex_project_direct is not None:
            # Direct project — validate strictly (catches "", "   ", 123, etc.)
            self._vertex_project: str = _validate_nonempty_str(
                "vertex_project", vertex_project_direct
            )
        elif vertex_project_secret_key:
            # Require SecretStore — no os.environ fallback.
            if self._secret_store is None:
                raise ValueError(
                    f"LiteLLMProvider: vertex_project_secret={vertex_project_secret_key!r} "
                    f"requires a SecretStore but none was provided. "
                    f"Inject via factory or pass secret_store= explicitly."
                )
            val = self._secret_store.get(vertex_project_secret_key)
            # Issue 3: Validate resolved secret value strictly.
            self._vertex_project = _validate_nonempty_str("vertex_project", val)
        else:
            # No project configured — only fail at call time if model is vertex_ai/
            self._vertex_project = ""

        # Issue 2: Require complete fallback pricing for every configured tier — unconditionally.
        # An empty pricing map is also an error (no conditional guard on map being non-empty).
        for tier_key in self._tier_models:
            if tier_key not in self._input_cpt_inr:
                raise ValueError(
                    f"LiteLLMProvider: cost.input_cost_per_token_inr is missing "
                    f"entry for tier={tier_key!r} — required for cost fallback"
                )
            if tier_key not in self._output_cpt_inr:
                raise ValueError(
                    f"LiteLLMProvider: cost.output_cost_per_token_inr is missing "
                    f"entry for tier={tier_key!r} — required for cost fallback"
                )

    def _build_litellm_params(
        self,
        messages: list[dict],
        tier: str,
        params: dict | None,
        response_schema: type | None,
    ) -> tuple[list[dict], dict]:
        """Build the final (messages, call_kwargs) that will be sent to litellm.

        Used by BOTH budget estimators and the actual respond() call so that
        token counting is consistent with what is actually sent.

        Issue 3 fix: schema is passed via native response_format (the Pydantic model
        itself), NOT injected as text into messages. This ensures agent token-budget
        authorization covers the exact payload sent — no hidden overhead added after
        authorization.
        """
        # Validate reserved internal params before stripping.
        auth_tokens = params.get("_authorized_prompt_tokens") if params else None
        if auth_tokens is not None:
            if isinstance(auth_tokens, bool) or not isinstance(auth_tokens, int) or auth_tokens <= 0:
                raise ValueError(
                    f"_authorized_prompt_tokens must be a positive non-boolean integer, "
                    f"got {auth_tokens!r} (type={type(auth_tokens).__name__!r})"
                )

        # Reject unknown internal (_-prefixed) parameters — unknown keys may hide bugs
        # or indicate callers relying on undocumented silent-stripping behaviour.
        for _k in (params or {}):
            if _k.startswith("_") and _k not in _SUPPORTED_INTERNAL_PARAMS:
                raise ValueError(
                    f"LiteLLMProvider: unknown internal parameter {_k!r}; "
                    f"supported internal params: {sorted(_SUPPORTED_INTERNAL_PARAMS)}"
                )

        # Validate max_tokens when present: must be a positive, non-boolean integer.
        _max_tokens_val = (params or {}).get("max_tokens")
        if _max_tokens_val is not None:
            if isinstance(_max_tokens_val, bool):
                raise ValueError(
                    f"LiteLLMProvider: max_tokens must not be a bool, "
                    f"got {_max_tokens_val!r}"
                )
            if not isinstance(_max_tokens_val, int) or _max_tokens_val <= 0:
                raise ValueError(
                    f"LiteLLMProvider: max_tokens must be a positive integer, "
                    f"got {_max_tokens_val!r} (type={type(_max_tokens_val).__name__!r})"
                )

        final_messages = list(messages)
        # Strip supported internal keys (prefixed with "_") before forwarding to litellm.
        # "_authorized_prompt_tokens" is a platform-internal key; it must never reach the API.
        call_kwargs: dict = {
            k: v for k, v in (params or {}).items() if not k.startswith("_")
        }
        model = self._tier_models[tier]
        call_kwargs["model"] = model

        if response_schema is not None:
            # LiteLLM documented structured output: pass the Pydantic model directly as
            # response_format. LiteLLM translates it to the provider-specific (Vertex/
            # Gemini) format internally. See https://docs.litellm.ai/docs/completion/json_mode
            # ("response_format=<Pydantic Model>"). Messages are NOT modified — the schema
            # travels via response_format only, so token-budget authorization covers the
            # exact payload sent.
            call_kwargs["response_format"] = response_schema
            # Do NOT add schema instructions to messages — messages are returned unchanged.

        # Forward Vertex project/location if model uses vertex_ai/
        if self._vertex_project and model.startswith("vertex_ai/"):
            call_kwargs.setdefault("vertex_project", self._vertex_project)
            call_kwargs.setdefault("vertex_location", self._vertex_location)

        return final_messages, call_kwargs

    def _extract_tokens(self, raw_usage: object) -> tuple[int, int]:
        """Extract prompt and completion tokens from LiteLLM usage.

        Fails closed on any missing, invalid, bool, float, negative, or zero-prompt token value.
        Issue 2: strict extraction rules for real provider calls.
        """
        _MISSING = object()

        def _require_token_field(name: str) -> int:
            val = getattr(raw_usage, name, _MISSING)
            if val is _MISSING or val is None:
                raise ValueError(
                    f"LiteLLMProvider: response.usage.{name} is missing or None — "
                    f"cannot account for cost (fail closed)"
                )
            if isinstance(val, bool):
                raise ValueError(
                    f"LiteLLMProvider: response.usage.{name}={val!r} is a bool, not int"
                )
            if not isinstance(val, int):
                raise ValueError(
                    f"LiteLLMProvider: response.usage.{name}={val!r} is not an integer "
                    f"(type={type(val).__name__!r})"
                )
            if val < 0:
                raise ValueError(
                    f"LiteLLMProvider: response.usage.{name}={val!r} is negative"
                )
            return val

        prompt_tokens = _require_token_field("prompt_tokens")
        completion_tokens = _require_token_field("completion_tokens")

        if prompt_tokens == 0:
            raise ValueError(
                f"LiteLLMProvider: response.usage.prompt_tokens=0 on a real call — "
                f"every request sends a prompt; zero means the usage object is broken"
            )

        return prompt_tokens, completion_tokens

    def _compute_cost_native(
        self,
        response: object,
        prompt_tokens: int,
        completion_tokens: int,
        tier: str,
    ) -> float:
        """Compute cost in USD. Fails closed if no pricing data available.

        LiteLLM is primary; configured per-token pricing is fallback;
        raises ValueError if neither is available.

        Issue 2: litellm cost must be finite AND > 0 to be accepted as primary.
        NaN, inf, 0, and negative all fall through to fallback.
        Fallback-computed cost must also be finite AND > 0.
        """
        import litellm as _litellm  # type: ignore[import-untyped]

        # Try litellm's cost lookup first — only accept finite AND > 0
        try:
            cost = _litellm.completion_cost(completion_response=response)
            if math.isfinite(cost) and cost > 0:
                return float(cost)
            # else fall through to configured fallback (0, NaN, inf, negative all rejected)
        except Exception:
            pass

        # Fallback — require both tiers have pricing; missing tier is an error.
        out_cpt_inr = self._output_cpt_inr.get(tier)
        in_cpt_inr = self._input_cpt_inr.get(tier)

        if out_cpt_inr is not None and in_cpt_inr is not None:
            cost_inr = (prompt_tokens * in_cpt_inr) + (completion_tokens * out_cpt_inr)
            if not math.isfinite(cost_inr) or cost_inr <= 0:
                raise ValueError(
                    f"LiteLLMProvider: fallback pricing for tier={tier!r} produced "
                    f"cost_inr={cost_inr!r} which is not finite+positive — "
                    f"check output_cost_per_token_inr values"
                )
            return cost_inr / self._fx_rate  # convert INR back to USD for cost_native

        # Neither litellm pricing nor configured fallback available
        raise ValueError(
            f"LiteLLMProvider: cannot compute cost for tier={tier!r} — "
            f"litellm.completion_cost() returned non-positive/non-finite or failed, and "
            f"no output_cost_per_token_inr configured for this tier. "
            f"Set cost.output_cost_per_token_inr.{tier} in config to enable fallback pricing."
        )

    def _conservative_usage(
        self,
        tier: str,
        call_kwargs: dict,
        params: dict | None,
        response_schema: type | None = None,
    ) -> "Usage":
        """
        Conservative worst-case Usage when real usage cannot be extracted.
        Uses the authorized prompt estimate passed by the caller (never word-count guesses).

        When falling back (no ``_authorized_prompt_tokens``), the schema overhead is
        accounted for by passing ``response_schema`` to ``estimate_prompt_tokens`` — so a
        structured call's conservative estimate matches what a node would authorize for the
        identical request. Never returns cost_native=0.
        """
        from core.cost import estimate_prompt_tokens as _estimate_prompt_tokens

        # Prefer the caller-provided authorized estimate (the same number used for budget gating).
        authorized = (params or {}).get("_authorized_prompt_tokens")
        if authorized and isinstance(authorized, int) and not isinstance(authorized, bool) and authorized > 0:
            estimated_prompt_tokens = authorized
        else:
            # Fallback: use the same conservative estimator as authorization, including
            # the response-schema JSON overhead so structured calls are not under-counted.
            sent_messages = call_kwargs.get("messages", [])
            try:
                estimated_prompt_tokens = _estimate_prompt_tokens(
                    sent_messages, response_schema=response_schema
                )
            except Exception:
                # Fail closed: cannot estimate the prompt safely → raise rather than
                # silently using a tiny number that would under-account the incurred cost.
                raise ValueError(
                    "conservative usage estimation failed; cannot account for prompt safely"
                ) from None

        # Output: use configured max_tokens or a safe upper bound
        max_output = int((params or {}).get("max_tokens") or call_kwargs.get("max_tokens") or 2048)

        in_cpt = self._input_cpt_inr.get(tier, 0)
        out_cpt = self._output_cpt_inr.get(tier, 0)

        # We always have valid pricing at this point (validated at construction)
        cost_inr = (estimated_prompt_tokens * in_cpt) + (max_output * out_cpt)
        cost_native = cost_inr / self._fx_rate  # convert back to USD

        if not math.isfinite(cost_native) or cost_native <= 0:
            # Absolute fallback: use 1 full standard cost unit to avoid zero
            cost_native = max(in_cpt + out_cpt, 0.0001) / self._fx_rate

        return Usage(
            prompt_tokens=estimated_prompt_tokens,
            completion_tokens=max_output,
            cost_native=cost_native,
            currency=_LITELLM_COST_CURRENCY,
            synthetic=True,  # conservative estimate, not real measurement
        )

    def respond(
        self,
        messages: list[dict],
        *,
        tier: Tier,
        params: dict[str, Any] | None = None,
        tools: list[dict] | None = None,
        response_schema: type[CoreContractModel] | None = None,
    ) -> LLMResponse:
        # Raise NotImplementedError for non-empty tools (explicit, not silent)
        # This check is BEFORE the provider call — no cost incurred, not BillableProviderError.
        if tools:
            raise NotImplementedError(
                "LiteLLMProvider: tool/function calling is not yet implemented. "
                "Pass tools=None or tools=[] until tool support is added."
            )

        model = self._tier_models.get(tier)
        if model is None:
            raise ValueError(
                f"LiteLLMProvider: tier={tier!r} not in tier_models "
                f"(available: {list(self._tier_models)})"
            )

        # Validate vertex_project is set for vertex_ai models
        # This check is BEFORE the provider call — not BillableProviderError.
        if model.startswith("vertex_ai/") and not self._vertex_project:
            raise ValueError(
                f"LiteLLMProvider: model {model!r} requires vertex_project; "
                f"set llm.vertex_project_secret in config (or llm.vertex_project directly)"
            )

        # Validate response_schema before any cost estimation or provider interaction.
        # validate_structured_schema() recursively inspects every field annotation and
        # rejects mutable containers (list/dict/set), Any, plain BaseModel subclasses,
        # and unsupported annotations — all before any provider cost is incurred.
        if response_schema is not None:
            validate_structured_schema(response_schema)

        # Validate message structure before any cost estimation or provider interaction.
        # Non-string / non-dict / blank / extra-field content is caught here (non-billable)
        # rather than inside a post-call except handler.
        _validate_messages(messages)

        # Issue 3: Use _build_litellm_params as the single place for schema injection
        # so token counting (budget estimation) and the actual call use identical payloads.
        effective_messages, call_kwargs = self._build_litellm_params(
            messages, tier, params, response_schema
        )
        # Remove "model" from call_kwargs since litellm.completion takes it as positional/kwarg
        call_model = call_kwargs.pop("model")

        # Build the full kwargs dict we'll pass (including messages for conservative usage estimate)
        full_call_kwargs = {"messages": effective_messages, **call_kwargs}

        # Pre-call: compute conservative usage BEFORE calling litellm.
        # Messages are already validated (string content guaranteed), so estimation
        # cannot fail due to bad content. If it fails for any other reason it is a
        # programming error and we raise a non-billable ValueError — the provider has
        # not been called yet. After this point every post-call failure path uses
        # pre_conservative and never calls _conservative_usage() inside an except handler.
        try:
            pre_conservative = self._conservative_usage(
                tier, full_call_kwargs, params, response_schema
            )
        except Exception as _pre_exc:
            raise ValueError(
                f"LiteLLMProvider: pre-call prompt estimation failed "
                f"({type(_pre_exc).__name__}); cannot proceed safely"
            ) from None

        import litellm as _litellm  # type: ignore[import-untyped]

        # KEY rule for every BillableProviderError below: never `raise X from exc`, and
        # never `raise X` while still inside the `except` suite. Construct the error inside
        # `except`, store it in `_pending_error`, then raise AFTER the except block. This
        # guarantees `__cause__ is None` and `__context__ is None` on the raised error, so
        # the original (possibly content-bearing) provider exception can never reach a
        # caller. Categories are allowlisted, content-free strings.

        # --- Step 1: call litellm ---
        # Pre-call validation failures above this line are safely non-billable.
        # Once we call litellm, ambiguous failures (timeout, network drop) may have been billed.
        _pending_error: BillableProviderError | None = None
        response = None
        try:
            response = _litellm.completion(
                model=call_model,
                messages=effective_messages,
                **call_kwargs,
            )
        except Exception:
            # A network error, timeout, or partial failure may have reached Vertex and
            # incurred cost. Use pre-computed conservative usage — never call
            # _conservative_usage() here (would re-enter exception context and could
            # leak the raw provider exception via __context__ if estimation failed).
            _pending_error = BillableProviderError(pre_conservative, "provider_call_failed")
        if _pending_error is not None:
            raise _pending_error  # raised OUTSIDE except → no __context__, no __cause__

        # --- Step 2: usage extraction — billable from here on ---
        _pending_error = None
        usage = None
        try:
            raw_usage = getattr(response, "usage", None)
            if raw_usage is None:
                raise ValueError("usage None")
            prompt_tokens, completion_tokens = self._extract_tokens(raw_usage)
            cost_native = self._compute_cost_native(response, prompt_tokens, completion_tokens, tier)
            usage = Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_native=float(cost_native),
                currency=_LITELLM_COST_CURRENCY,
                synthetic=False,
            )
        except Exception:
            # Use pre-computed conservative usage (never call _conservative_usage inside except).
            _pending_error = BillableProviderError(pre_conservative, "usage_extraction_failed")
        if _pending_error is not None:
            raise _pending_error

        # --- Step 3: validate and extract response text ---
        _pending_error = None
        text = None
        try:
            _cat = "response_shape_invalid"
            if not getattr(response, "choices", None):
                raise ValueError("no choices")
            choice = response.choices[0]
            msg_obj = getattr(choice, "message", None)
            if msg_obj is None:
                raise ValueError("no message")
            content = getattr(msg_obj, "content", None)
            if content is None:
                raise ValueError("content None")
            if not isinstance(content, str):
                raise ValueError("content not str")
            if not content.strip():
                _cat = "response_empty"
                raise ValueError("content empty")
            text = content  # str, non-empty, non-whitespace
        except Exception:
            _pending_error = BillableProviderError(usage, _cat)
        if _pending_error is not None:
            raise _pending_error

        # --- Step 4: structured output parsing (if schema) ---
        if response_schema is not None:
            _pending_error = None
            parsed = None
            try:
                parsed = json.loads(text)
            except Exception:
                _pending_error = BillableProviderError(usage, "json_parse_failed")
            if _pending_error is not None:
                raise _pending_error

            _pending_error = None
            try:
                return LLMResponse.structured_from(response_schema, parsed, usage=usage)
            except Exception:
                _pending_error = BillableProviderError(usage, "schema_validation_failed")
            if _pending_error is not None:
                raise _pending_error

        return LLMResponse(text=text, usage=usage)
