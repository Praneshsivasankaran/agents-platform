"""Transcribe voice/video audio through the provider-neutral STT interface."""

from __future__ import annotations

from typing import Any

from core.cost import CostCeilingExceeded, can_afford_stage, usage_cost_inr
from core.interfaces import BillableProviderError, Telemetry
from core.interfaces.llm import LLMProvider
from core.interfaces.transcription import TranscriptionProvider
from core.media import delete_extracted_audio, extract_audio

from ..schemas import BillableNodeError, StageCost
from ..state import BlogState


def make_transcribe_node(
    cfg: dict,
    llm: LLMProvider,
    tel: Telemetry,
    transcription: TranscriptionProvider,
):
    _ = llm
    cost_cfg = cfg.get("cost", {})
    transcription_cfg = cfg.get("transcription", {})
    fx_rates: dict[str, float] = cost_cfg.get("fx_rates", {"USD": 83.0})
    ceiling_inr = float(cost_cfg.get("ceiling_inr", 50.0))
    estimated_costs = {
        k: float(v) for k, v in cost_cfg.get("estimated_stage_cost_inr", {}).items()
    }
    language = str(transcription_cfg.get("language", "en"))
    timestamps = bool(transcription_cfg.get("timestamps", True))
    diarization = bool(transcription_cfg.get("diarization", False))
    normalize_voice = bool(transcription_cfg.get("normalize_voice", False))
    max_duration_s = float(transcription_cfg.get("max_duration_s", 7200.0))

    def transcribe_node(state: BlogState) -> dict[str, Any]:
        input_type: str = state.get("input_type", "voice") or "voice"  # type: ignore[assignment]
        if input_type == "video":
            audio_ref: str = state.get("audio_ref", "")  # type: ignore[assignment]
            missing_kind = "missing_audio_ref"
            missing_message = "audio_ref not set for video input; extract_audio must run first"
        else:
            audio_ref = state.get("raw_input", "")  # type: ignore[assignment]
            missing_kind = "missing_raw_input"
            missing_message = "raw_input is required for voice transcription"
        if not audio_ref:
            return {
                "error_state": {
                    "node": "transcribe",
                    "kind": missing_kind,
                    "message": missing_message,
                }
            }

        # Video audio was created by extract_audio and must be removed even when span
        # entry/exit, budget checks, provider calls, or telemetry fail.
        cleanup_ref = audio_ref if input_type == "video" else ""
        stage_cost: StageCost | None = None
        try:
            with tel.span("transcribe") as span_id:
                current_costs = list(state.get("cost_usage", []))  # type: ignore[arg-type]
                if not can_afford_stage(
                    current_costs, "transcribe", estimated_costs, ceiling_inr
                ):
                    raise CostCeilingExceeded(
                        "transcribe: estimated transcription cost exceeds remaining ceiling"
                    )

                if input_type == "voice" and normalize_voice:
                    try:
                        audio_ref = extract_audio(
                            audio_ref,
                            out_format="wav",
                            max_duration_s=max_duration_s,
                        )
                        cleanup_ref = audio_ref
                    except Exception as exc:
                        tel.log("transcribe.error", span_id=span_id, kind=type(exc).__name__)
                        return {
                            "error_state": {
                                "node": "transcribe",
                                "kind": "media_validation_failed",
                                "message": "voice media validation or normalization failed",
                            }
                        }

                try:
                    transcript_result = transcription.transcribe(
                        audio_ref,
                        language=language,
                        timestamps=timestamps,
                        diarization=diarization,
                    )
                except BillableProviderError as bpe:
                    billed_cost = StageCost(
                        stage="transcribe",
                        cost_inr=usage_cost_inr(bpe.usage, fx_rates=fx_rates),
                        tier="stt",
                    )
                    stage_cost = billed_cost
                    raise BillableNodeError(
                        billed_cost,
                        RuntimeError(f"billable-provider-failure:{bpe.category}"),
                    ) from None
                except Exception as exc:
                    tel.log("transcribe.error", span_id=span_id, kind=type(exc).__name__)
                    return {
                        "error_state": {
                            "node": "transcribe",
                            "kind": type(exc).__name__,
                            "message": f"{type(exc).__name__} in transcribe",
                        }
                    }

                cost_inr = usage_cost_inr(transcript_result.usage, fx_rates=fx_rates)
                stage_cost = StageCost(stage="transcribe", cost_inr=cost_inr, tier="stt")
                transcript_meta: dict[str, Any] = {
                    "provider": transcript_result.provider,
                    "language": transcript_result.language,
                    "confidence": transcript_result.confidence,
                    "segments": transcript_result.segments,
                    "speakers": transcript_result.speakers,
                    "duration_s": transcript_result.duration_s,
                    "cost_inr": cost_inr,
                    "latency_ms": transcript_result.latency_ms,
                }
                tel.record_usage(
                    transcript_result.usage,
                    node="transcribe",
                    tier="stt",
                    span_id=span_id,
                )
                tel.metric("stage.cost_inr", cost_inr, node="transcribe")
                tel.metric("transcribe.duration_s", transcript_result.duration_s, node="transcribe")
                tel.metric("transcribe.cost_inr", cost_inr, node="transcribe")
                tel.log(
                    "transcribe.complete",
                    span_id=span_id,
                    provider=transcript_result.provider,
                )
                return {
                    "transcript": transcript_result.text,
                    "transcript_meta": transcript_meta,
                    "cost_usage": [stage_cost],
                }
        except BillableNodeError:
            raise
        except Exception as exc:
            if stage_cost is not None:
                raise BillableNodeError(stage_cost, exc) from exc
            raise
        finally:
            if cleanup_ref:
                delete_extracted_audio(cleanup_ref)

    return transcribe_node
