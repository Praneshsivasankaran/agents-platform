"""Shared base for load-bearing platform contract models (DESIGN §3, §7).

``CoreContractModel`` makes contract models **immutable, strict, and copy-safe**:

- ``frozen=True`` blocks attribute reassignment after construction;
- ``extra="forbid"`` rejects unknown/misspelled fields (never silently dropped);
- ``model_copy(update=...)`` is overridden to **revalidate** the update (Pydantic's default bypasses
  validation and could create invalid state); ``validated_copy(**changes)`` is the explicit helper.

**Deep immutability is NOT automatic.** ``frozen=True`` is *shallow* — a frozen model holding a
plain ``list``/``dict``/``set`` can still have that container mutated. So contract models must use
**immutable nested field types** (``tuple[...]``, nested ``CoreContractModel``) or convert/reject
mutable values explicitly. Two helpers below enforce this for the free-form surfaces:

- ``ToolArgs`` — a JSON-only, deeply-immutable, pickle/checkpoint-safe representation for tool args.
- ``assert_deeply_immutable`` — rejects mutable nested containers inside structured LLM payloads.

Cloud-neutral by construction — imports only Pydantic + the standard library; never a cloud SDK.
"""

from __future__ import annotations

import enum
import math
import sys
import typing
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, PlainSerializer


# --- JSON-only, deeply-immutable, checkpoint-safe representation for free-form tool args -----

class FrozenJsonDict(dict):
    """Immutable, picklable, JSON-serializable mapping used for tool-call args.

    A ``dict`` subclass (so it serializes / pickles / deep-copies like a dict) whose mutating
    methods raise. Reconstructed via ``__reduce__`` so pickle/deepcopy repopulate through the
    constructor, never the blocked ``__setitem__``.

    **Accepted limitation (trusted first-party code).** A deliberate low-level bypass via
    ``dict.__setitem__(args, ...)`` / ``dict.update(args, ...)`` can still mutate the contents. We
    accept this: provider and agent code is first-party and never does that, and all *normal*
    mutation (``args[k] = v``, ``.update(...)``, ``|=``, ``del``, ``.pop()``) is blocked. An
    Increment-2 conformance test documents this boundary. If ever warranted, this can be swapped for a
    non-``dict`` immutable representation to remove even the low-level bypass.
    """

    __slots__ = ()

    def __reduce__(self):
        return (FrozenJsonDict, (dict(self),))

    def _readonly(self, *args: Any, **kwargs: Any):
        raise TypeError("tool args mapping is immutable")

    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = _readonly

    def __ior__(self, other: Any):  # |=
        raise TypeError("tool args mapping is immutable")


def _to_frozen_json(value: Any) -> Any:
    """Validate that ``value`` is JSON-compatible and return a deeply-immutable form.

    Allowed: ``str`` / ``int`` / ``bool`` / ``None``, **finite** ``float``, sequences (-> ``tuple``),
    and string-keyed mappings (-> ``FrozenJsonDict``). Rejected with a clear error: ``set``, Pydantic
    models, arbitrary objects, non-string keys, and non-finite floats (``nan`` / ``inf`` / ``-inf``).
    """
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("tool args reject non-finite floats (nan/inf/-inf)")
        return value
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise ValueError("tool args object keys must be strings (JSON-compatible)")
            out[k] = _to_frozen_json(v)
        return FrozenJsonDict(out)
    if isinstance(value, (list, tuple)):
        return tuple(_to_frozen_json(v) for v in value)
    raise ValueError(
        "tool args must be JSON-compatible (str/int/float/bool/None/list/object); "
        f"rejected value of type {type(value).__name__}"
    )


def _json_thaw(value: Any) -> Any:
    """Inverse of ``_to_frozen_json`` for serialization (back to plain ``dict`` / ``list``)."""
    if isinstance(value, Mapping):
        return {k: _json_thaw(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_json_thaw(v) for v in value]
    return value


def _validate_tool_args(value: Any) -> FrozenJsonDict:
    if not isinstance(value, Mapping):
        raise ValueError("tool args must be a JSON object (mapping with string keys)")
    return _to_frozen_json(value)  # FrozenJsonDict


# Typed as ``Any`` so Pydantic does not re-coerce the immutable result back into a plain dict; the
# validator enforces JSON-only + freezes deeply, the serializer thaws to plain JSON for checkpoints.
ToolArgs = Annotated[
    Any,
    AfterValidator(_validate_tool_args),
    PlainSerializer(_json_thaw, when_used="always"),
]


# --- deep-immutability assertion for structured LLM payloads --------------------------------

_IMMUTABLE_SCALARS = (str, bytes, bool, int, float, type(None))


def assert_deeply_immutable(value: Any, path: str = "structured") -> None:
    """Reject mutable nested containers inside a structured payload.

    A frozen model is only *shallowly* immutable; this walks the value and requires every nested
    container to be immutable — nested models must subclass ``CoreContractModel`` (frozen), and
    collections must be ``tuple`` (not ``list`` / ``dict`` / ``set``). Verifies all four required
    config settings with exact comparisons (``is True`` / ``is False``), that no private attributes
    are declared, and that no Pydantic extra fields are present. Non-finite float values are rejected
    directly. Raises ``ValueError``.
    """
    if isinstance(value, CoreContractModel):
        cfg = type(value).model_config
        if cfg.get("frozen") is not True:
            raise ValueError(
                f"{path}: model {type(value).__name__!r} has frozen!=True — "
                f"post-construction mutation is possible"
            )
        if cfg.get("extra") != "forbid":
            raise ValueError(
                f"{path}: model {type(value).__name__!r} has extra!='forbid' — "
                f"unknown fields may be mutable"
            )
        if cfg.get("allow_inf_nan") is not False:
            raise ValueError(
                f"{path}: model {type(value).__name__!r} has allow_inf_nan!=False — "
                f"non-finite floats are not permitted in structured payloads"
            )
        if cfg.get("validate_default") is not True:
            raise ValueError(
                f"{path}: model {type(value).__name__!r} has validate_default!=True — "
                f"unvalidated defaults bypass contract checks"
            )
        private_attrs = getattr(type(value), "__private_attributes__", {})
        if private_attrs:
            raise ValueError(
                f"{path}: model {type(value).__name__!r} declares private attributes "
                f"{set(private_attrs)!r} — private attributes are not permitted in response schemas"
            )
        computed = getattr(type(value), "model_computed_fields", {})
        if computed:
            raise ValueError(
                f"{path}: model {type(value).__name__!r} declares computed fields "
                f"{set(computed)!r} — computed fields are not permitted in structured payloads"
            )
        if _has_custom_serializers(type(value)):
            raise ValueError(
                f"{path}: model {type(value).__name__!r} declares custom serializers — "
                f"custom serializers are not permitted in structured payloads"
            )
        if _has_model_post_init(type(value)):
            raise ValueError(
                f"{path}: model {type(value).__name__!r} overrides model_post_init — "
                f"model_post_init overrides are not permitted in structured payloads"
            )
        extra = getattr(value, "__pydantic_extra__", None) or {}
        if extra:
            raise ValueError(
                f"{path}: model {type(value).__name__!r} has unexpected extra fields "
                f"{set(extra)!r} — only extra='forbid' models are permitted in structured payloads"
            )
        # Reject undeclared instance keys (e.g., injected via model_post_init + object.__setattr__)
        hidden = {
            k for k in value.__dict__
            if k not in type(value).model_fields and not k.startswith("__pydantic_")
        }
        if hidden:
            raise ValueError(
                f"{path}: model {type(value).__name__!r} has undeclared instance keys "
                f"{hidden!r} — only declared model_fields are permitted; "
                f"model_post_init must not inject hidden state via object.__setattr__"
            )
        pydantic_private = getattr(value, "__pydantic_private__", None)
        if pydantic_private:
            raise ValueError(
                f"{path}: model {type(value).__name__!r} has non-empty __pydantic_private__ "
                f"{set(pydantic_private)!r} — private instance state is not permitted "
                f"in structured payloads"
            )
        for fname in type(value).model_fields:
            assert_deeply_immutable(getattr(value, fname), f"{path}.{fname}")
        return
    # Reject Enum members BEFORE the scalar check: a str/int-subclass Enum would otherwise pass
    # as an immutable scalar, but Enum members can carry mutable values and accept injected
    # mutable attributes after construction — they are not safely deeply-immutable.
    if isinstance(value, enum.Enum):
        raise ValueError(
            f"{path}: Enum member {value!r} is not permitted in structured payloads — "
            f"Enum members can hold mutable values/attributes; use scalar Literal values instead"
        )
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(
                f"{path}: non-finite float {value!r} is not permitted in structured payloads"
            )
        return
    if isinstance(value, _IMMUTABLE_SCALARS):
        return
    if isinstance(value, tuple):
        for i, item in enumerate(value):
            assert_deeply_immutable(item, f"{path}[{i}]")
        return
    if isinstance(value, BaseModel):
        raise ValueError(
            f"{path}: nested models in a structured payload must subclass CoreContractModel (frozen)"
        )
    raise ValueError(
        f"{path}: mutable/forbidden value of type {type(value).__name__}; use tuple[...] or a "
        "nested CoreContractModel (no list/dict/set in structured payloads)"
    )


class CoreContractModel(BaseModel):
    """Immutable, strict, copy-safe base for load-bearing provider/response contract models.

    See module docstring: ``frozen=True`` (no mutation) + ``extra="forbid"`` (no unknown fields) +
    revalidating copy. Deep immutability requires immutable nested field types in subclasses.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False, validate_default=True)

    def model_copy(self, *, update: Mapping[str, Any] | None = None, deep: bool = False):
        """Copy-with-revalidation. A plain ``model_copy(update=...)`` would bypass validation; this
        override revalidates the merged data through ``model_validate`` so invariants always hold.
        Without ``update`` it delegates to the default copy (deepcopy-safe)."""
        if update:
            return type(self).model_validate({**dict(self), **dict(update)})
        return super().model_copy(deep=deep)

    def validated_copy(self, **changes: Any):
        """Return a revalidated copy with ``changes`` applied (the explicit safe-copy helper)."""
        return type(self).model_validate({**dict(self), **changes})


# --- pre-call schema annotation validation ---------------------------------------------------
# Inspects TYPE ANNOTATIONS before a provider is called (non-billable), in contrast to
# assert_deeply_immutable() which walks VALUES after construction.

_SCHEMA_IMMUTABLE_SCALARS: frozenset = frozenset({
    str, bytes, bool, int, float, type(None),
})

_MUTABLE_ORIGINS: frozenset = frozenset({list, dict, set})

# typing.Union covers Optional / Union on Python <3.10; types.UnionType covers X|Y on 3.10+.
_UNION_ORIGINS: frozenset = frozenset({typing.Union}) | (
    frozenset({__import__("types").UnionType})
    if sys.version_info >= (3, 10)
    else frozenset()
)


@dataclass(frozen=True)
class FieldConstraints:
    """Normalized Pydantic field constraints shared by validation and offline mocks."""

    min_length: int | None = None
    max_length: int | None = None
    lower: int | float | None = None
    lower_exclusive: bool = False
    upper: int | float | None = None
    upper_exclusive: bool = False


def _flatten_constraint_metadata(metadata: typing.Iterable[Any]) -> typing.Iterator[Any]:
    """Yield individual constraint objects, unwrapping Pydantic ``FieldInfo`` items.

    Constraints written as ``Annotated[T, Field(...)]`` nest inside a single ``FieldInfo`` whose
    own ``.metadata`` list holds the real annotated-types constraint objects (``Ge``, ``MinLen``,
    ``MultipleOf``, ``_PydanticGeneralMetadata(pattern=...)``, ...). Flattening lets the same
    attribute-based introspection work whether the user wrote ``Field(...)`` or bare
    annotated-types objects, and whether the ``Annotated`` is at field level or nested inside a
    container (where Pydantic does not pre-flatten it into ``FieldInfo.metadata``).
    """
    for item in metadata or ():
        nested = getattr(item, "metadata", None)
        if isinstance(nested, (list, tuple)):
            # A FieldInfo (or similar wrapper) — its constraints live in the nested list.
            yield from _flatten_constraint_metadata(nested)
        else:
            yield item


def _constraint_number(value: Any, *, name: str, path: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(
            f"structured-schema violation at {path!r}: {name} must be a finite int or float"
        )
    if not math.isfinite(value):
        raise ValueError(
            f"structured-schema violation at {path!r}: {name} must be finite"
        )
    return value


def _constraint_length(value: Any, *, name: str, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(
            f"structured-schema violation at {path!r}: {name} must be a non-negative integer"
        )
    return value


def normalize_field_constraints(
    metadata: typing.Iterable[Any],
    *,
    path: str = "field",
) -> FieldConstraints:
    """Normalize supported Pydantic constraints and reject contradictory bounds.

    Multiple lower/upper constraints are reduced to their strongest effective bound. Equal
    bounds prefer the exclusive form because it is stricter. This function is intentionally
    shared by pre-call schema validation and MockLLMProvider so they cannot disagree.
    """
    min_length: int | None = None
    max_length: int | None = None
    lower: int | float | None = None
    lower_exclusive = False
    upper: int | float | None = None
    upper_exclusive = False

    for item in _flatten_constraint_metadata(metadata):
        pattern = getattr(item, "pattern", None)
        multiple_of = getattr(item, "multiple_of", None)
        allow_inf_nan = getattr(item, "allow_inf_nan", None)
        if pattern is not None or multiple_of is not None or allow_inf_nan is True:
            names = [
                name
                for name, value in (
                    ("pattern", pattern),
                    ("multiple_of", multiple_of),
                    ("allow_inf_nan=True", allow_inf_nan is True),
                )
                if value is not None and value is not False
            ]
            raise ValueError(
                f"structured-schema violation at {path!r}: unsupported constraint(s) "
                f"{', '.join(names)}; structured-output mocks fail closed on constraints "
                f"they cannot generate and verify deterministically"
            )
        raw_min = getattr(item, "min_length", None)
        if raw_min is not None:
            value = _constraint_length(raw_min, name="min_length", path=path)
            min_length = value if min_length is None else max(min_length, value)

        raw_max = getattr(item, "max_length", None)
        if raw_max is not None:
            value = _constraint_length(raw_max, name="max_length", path=path)
            max_length = value if max_length is None else min(max_length, value)

        for attr, exclusive in (("ge", False), ("gt", True)):
            raw = getattr(item, attr, None)
            if raw is None:
                continue
            value = _constraint_number(raw, name=attr, path=path)
            if lower is None or value > lower or (value == lower and exclusive):
                lower, lower_exclusive = value, exclusive

        for attr, exclusive in (("le", False), ("lt", True)):
            raw = getattr(item, attr, None)
            if raw is None:
                continue
            value = _constraint_number(raw, name=attr, path=path)
            if upper is None or value < upper or (value == upper and exclusive):
                upper, upper_exclusive = value, exclusive

    constraints = FieldConstraints(
        min_length=min_length,
        max_length=max_length,
        lower=lower,
        lower_exclusive=lower_exclusive,
        upper=upper,
        upper_exclusive=upper_exclusive,
    )
    _validate_constraint_bounds(constraints, path)
    return constraints


def _validate_constraint_bounds(constraints: FieldConstraints, path: str) -> None:
    if (
        constraints.min_length is not None
        and constraints.max_length is not None
        and constraints.min_length > constraints.max_length
    ):
        raise ValueError(
            f"structured-schema violation at {path!r}: contradictory length constraints "
            f"(min_length={constraints.min_length} > max_length={constraints.max_length})"
        )
    if constraints.lower is not None and constraints.upper is not None:
        if constraints.lower > constraints.upper or (
            constraints.lower == constraints.upper
            and (constraints.lower_exclusive or constraints.upper_exclusive)
        ):
            raise ValueError(
                f"structured-schema violation at {path!r}: contradictory numeric constraints"
            )


def merge_field_constraints(
    first: FieldConstraints,
    second: FieldConstraints,
    *,
    path: str = "field",
) -> FieldConstraints:
    """Merge two normalized constraint sets, keeping the strongest effective bounds."""
    min_lengths = [v for v in (first.min_length, second.min_length) if v is not None]
    max_lengths = [v for v in (first.max_length, second.max_length) if v is not None]

    lower: int | float | None = first.lower
    lower_exclusive = first.lower_exclusive
    if second.lower is not None and (
        lower is None
        or second.lower > lower
        or (second.lower == lower and second.lower_exclusive)
    ):
        lower, lower_exclusive = second.lower, second.lower_exclusive

    upper: int | float | None = first.upper
    upper_exclusive = first.upper_exclusive
    if second.upper is not None and (
        upper is None
        or second.upper < upper
        or (second.upper == upper and second.upper_exclusive)
    ):
        upper, upper_exclusive = second.upper, second.upper_exclusive

    merged = FieldConstraints(
        min_length=max(min_lengths) if min_lengths else None,
        max_length=min(max_lengths) if max_lengths else None,
        lower=lower,
        lower_exclusive=lower_exclusive,
        upper=upper,
        upper_exclusive=upper_exclusive,
    )
    _validate_constraint_bounds(merged, path)
    return merged


def constraints_allow_value(value: Any, constraints: FieldConstraints) -> bool:
    """Return whether a generated value satisfies the normalized supported constraints."""
    if value is None:
        return True
    if constraints.min_length is not None or constraints.max_length is not None:
        try:
            length = len(value)
        except TypeError:
            return False
        if constraints.min_length is not None and length < constraints.min_length:
            return False
        if constraints.max_length is not None and length > constraints.max_length:
            return False
    if constraints.lower is not None or constraints.upper is not None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
        if isinstance(value, float) and not math.isfinite(value):
            return False
        if constraints.lower is not None:
            if value < constraints.lower or (
                constraints.lower_exclusive and value == constraints.lower
            ):
                return False
        if constraints.upper is not None:
            if value > constraints.upper or (
                constraints.upper_exclusive and value == constraints.upper
            ):
                return False
    return True


def _constraints_allow_numeric_domain(domain: str, constraints: FieldConstraints) -> bool:
    if constraints.lower is None and constraints.upper is None:
        return True
    if domain == "float":
        candidates = [0.0]
        if constraints.lower is not None:
            candidates.append(
                math.nextafter(float(constraints.lower), math.inf)
                if constraints.lower_exclusive
                else float(constraints.lower)
            )
        if constraints.upper is not None:
            candidates.append(
                math.nextafter(float(constraints.upper), -math.inf)
                if constraints.upper_exclusive
                else float(constraints.upper)
            )
        return any(constraints_allow_value(candidate, constraints) for candidate in candidates)

    lower = -math.inf
    upper = math.inf
    if constraints.lower is not None:
        lower = (
            math.floor(constraints.lower) + 1
            if constraints.lower_exclusive
            else math.ceil(constraints.lower)
        )
    if constraints.upper is not None:
        upper = (
            math.ceil(constraints.upper) - 1
            if constraints.upper_exclusive
            else math.floor(constraints.upper)
        )
    return lower <= upper


def _annotation_satisfies_constraints(
    annotation: object,
    constraints: FieldConstraints,
    path: str,
) -> bool:
    """True when at least one value of ``annotation`` can satisfy supported field constraints."""
    has_length = constraints.min_length is not None or constraints.max_length is not None
    has_numeric = constraints.lower is not None or constraints.upper is not None
    if getattr(annotation, "__metadata__", None) is not None:
        annotated_constraints = normalize_field_constraints(annotation.__metadata__, path=path)
        merged = merge_field_constraints(constraints, annotated_constraints, path=path)
        return _annotation_satisfies_constraints(typing.get_args(annotation)[0], merged, path)
    if not has_length and not has_numeric:
        return True
    if annotation is type(None) or annotation is None:
        return True
    if annotation in (str, bytes):
        return not has_numeric
    if annotation is int:
        return not has_length and _constraints_allow_numeric_domain("int", constraints)
    if annotation is float:
        return not has_length and _constraints_allow_numeric_domain("float", constraints)

    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)
    if origin is typing.Literal:
        return any(constraints_allow_value(member, constraints) for member in args)
    if origin in _UNION_ORIGINS:
        return any(_annotation_satisfies_constraints(branch, constraints, path) for branch in args)
    if origin is tuple:
        if has_numeric:
            return False
        if len(args) == 2 and args[1] is Ellipsis:
            return True
        return constraints_allow_value(tuple(None for _ in args), constraints)
    return False


def _check_constraint_consistency(annotation: object, constraints: FieldConstraints, path: str) -> None:
    """Reject constraints for which the annotation has no valid value."""
    if not _annotation_satisfies_constraints(annotation, constraints, path):
        raise ValueError(
            f"structured-schema violation at {path!r}: constraints are incompatible with "
            f"annotation {annotation!r} and leave no valid value"
        )


def _has_custom_serializers(schema: type) -> bool:
    """True if any class in schema's MRO (up to CoreContractModel/BaseModel) declares serializers."""
    for cls in schema.__mro__:
        if cls is BaseModel or cls is object:
            break
        decorators = getattr(cls, "__pydantic_decorators__", None)
        if decorators is None:
            continue
        if getattr(decorators, "field_serializers", {}) or getattr(decorators, "model_serializers", {}):
            return True
    return False


def _has_model_post_init(schema: type) -> bool:
    """True if any class in schema's MRO (up to CoreContractModel/BaseModel) overrides model_post_init."""
    for cls in schema.__mro__:
        if cls is BaseModel or cls is object:
            break
        if "model_post_init" in cls.__dict__:
            return True
    return False


def _check_literal_member(member: object, path: str) -> None:
    """Assert a single ``Literal[...]`` member is a supported immutable, JSON-schema-compatible scalar.

    Allowed: ``str`` / ``bytes`` / ``bool`` / ``int`` / finite ``float`` / ``None``.
    Rejected: ``Enum`` members (can hold mutable values/attributes), non-finite floats, and
    arbitrary objects. Enums are rejected BEFORE the scalar check because a str/int-subclass Enum
    member would otherwise pass as a scalar.
    """
    if member is None:
        return
    if isinstance(member, enum.Enum):
        raise ValueError(
            f"structured-schema violation at {path!r}: Literal member {member!r} is an Enum "
            f"member — Enum members can hold mutable values/attributes; use scalar Literal "
            f"values (str/bytes/bool/int/finite float/None) instead"
        )
    if isinstance(member, bool):
        return
    if isinstance(member, (str, bytes, int)):
        return
    if isinstance(member, float):
        if not math.isfinite(member):
            raise ValueError(
                f"structured-schema violation at {path!r}: Literal member {member!r} is a "
                f"non-finite float — only finite floats are permitted in Literal annotations"
            )
        return
    raise ValueError(
        f"structured-schema violation at {path!r}: Literal member {member!r} of type "
        f"{type(member).__name__!r} is not a supported value — only str, bytes, bool, int, "
        f"finite float, and None are permitted in Literal annotations"
    )


def _check_annotation(ann: object, path: str, visiting: frozenset) -> None:
    """Recursively assert that annotation ``ann`` resolves to an immutable type.

    Pure immutability check. ``visiting`` is the set of CoreContractModel classes already being
    walked — re-encountering one simply returns (recursion guard for this walker). Recursive-cycle
    *termination* (does the schema have a finite construction path?) is a separate analysis in
    ``_assert_constructible`` so the two concerns do not interfere.
    """
    if ann is type(None) or ann is None:
        return
    if ann in _SCHEMA_IMMUTABLE_SCALARS:
        return
    if ann is typing.Any:
        raise ValueError(
            f"structured-schema violation at {path!r}: `Any` is not permitted "
            f"(immutability cannot be verified)"
        )
    # Annotated[T, ...] — __metadata__ is always present regardless of Python version.
    # get_origin() returned the base type on 3.9–3.10 and Annotated on 3.11+, so we
    # use __metadata__ as the portable discriminator.
    if getattr(ann, "__metadata__", None) is not None:
        inner = typing.get_args(ann)[0]
        constraints = normalize_field_constraints(ann.__metadata__, path=path)
        _check_constraint_consistency(inner, constraints, path)
        _check_annotation(inner, path, visiting)
        return
    origin = typing.get_origin(ann)
    args = typing.get_args(ann)
    if origin is typing.Literal:
        for member in args:
            _check_literal_member(member, path)
        return
    if origin in _UNION_ORIGINS:
        for i, a in enumerate(args):
            _check_annotation(a, f"{path}[union.{i}]", visiting)
        return
    if origin is tuple:
        for i, a in enumerate(args):
            if a is ...:
                continue
            _check_annotation(a, f"{path}[{i}]", visiting)
        return
    if origin in _MUTABLE_ORIGINS or ann in _MUTABLE_ORIGINS:
        raise ValueError(
            f"structured-schema violation at {path!r}: mutable container "
            f"{ann!r} is not permitted — use tuple[...] or nested CoreContractModel"
        )
    if isinstance(ann, type):
        if issubclass(ann, CoreContractModel):
            if ann not in visiting:
                _check_schema_fields(ann, visiting | {ann}, path)
            return
        if issubclass(ann, BaseModel):
            raise ValueError(
                f"structured-schema violation at {path!r}: nested model "
                f"{ann.__name__!r} must subclass CoreContractModel"
            )
        raise ValueError(
            f"structured-schema violation at {path!r}: unsupported type "
            f"{ann.__name__!r} — only immutable scalars, tuple, Literal, "
            f"Optional/Union, or nested CoreContractModel are permitted"
        )
    raise ValueError(
        f"structured-schema violation at {path!r}: unsupported annotation "
        f"{ann!r} — fail closed"
    )


# --- recursive-schema termination analysis ---------------------------------------------------
# Determines whether a schema has at least one FINITE construction path. A schema with a required
# field that forms a recursive cycle (directly, through a fixed-length tuple, or through a union
# where no branch terminates) is impossible to instantiate and would crash a provider with
# RecursionError. This is intentionally separate from the immutability walk above.


def _min_length_from_metadata(metadata: typing.Iterable[Any]) -> int:
    """Extract the largest ``min_length`` constraint from a Pydantic/annotated-types metadata list."""
    ml = 0
    for m in _flatten_constraint_metadata(metadata):
        v = getattr(m, "min_length", None)
        if isinstance(v, int) and not isinstance(v, bool) and v > ml:
            ml = v
    return ml


def _annotation_terminates(ann: object, stack: frozenset, min_length: int = 0) -> bool:
    """True if a value of annotation ``ann`` can be constructed in finite depth.

    ``stack`` is the set of CoreContractModel classes currently on the construction path; a model
    in ``stack`` cannot terminate via that path (it would require constructing itself).

    ``min_length`` is the minimum number of elements required if ``ann`` is a variadic
    ``tuple[X, ...]``. It comes from a ``Field(min_length=...)`` constraint on the owning field (or
    from ``Annotated`` metadata). A variadic recursive tuple terminates ONLY when zero elements are
    permitted (``min_length == 0``); ``min_length >= 1`` forces at least one element to be
    constructed, so termination then depends on the element type.
    """
    if ann is None or ann is type(None):
        return True
    if ann in _SCHEMA_IMMUTABLE_SCALARS:
        return True
    if ann is typing.Any:
        return True  # rejected by the immutability walk; not a termination concern
    if getattr(ann, "__metadata__", None) is not None:
        inner_ml = max(min_length, _min_length_from_metadata(ann.__metadata__))
        return _annotation_terminates(typing.get_args(ann)[0], stack, inner_ml)
    origin = typing.get_origin(ann)
    args = typing.get_args(ann)
    if origin is typing.Literal:
        return True
    if origin in _UNION_ORIGINS:
        # A union terminates if ANY branch terminates (e.g. Self | str, Self | None). The owning
        # field's min_length DOES propagate into each branch: a str branch interprets it as a
        # string-length constraint (still terminating), while a variadic-tuple branch interprets
        # it as an element-count constraint (so tuple[Self, ...] with min_length>=1 does NOT
        # terminate, but a sibling str branch still can).
        return any(_annotation_terminates(a, stack, min_length) for a in args)
    if origin is tuple:
        if any(a is ... for a in args):
            # Variadic tuple[X, ...]: the empty tuple terminates ONLY if min_length == 0.
            # Otherwise at least min_length elements of type args[0] must be constructed.
            if min_length <= 0:
                return True
            return _annotation_terminates(args[0], stack)
        # Fixed-length tuple terminates iff every element terminates (tuple[Self] does NOT).
        return all(_annotation_terminates(a, stack) for a in args)
    if origin in _MUTABLE_ORIGINS or ann in _MUTABLE_ORIGINS:
        return True  # rejected by the immutability walk
    if isinstance(ann, type) and issubclass(ann, CoreContractModel):
        return _model_terminates(ann, stack)
    return True  # unknown annotation — rejected by the immutability walk; don't gate on it


def annotation_can_terminate(ann: object, stack: frozenset = frozenset(), min_length: int = 0) -> bool:
    """Public wrapper around the recursive termination analysis.

    Returns True if a value of annotation ``ann`` can be constructed in finite depth, given the
    set of CoreContractModel classes already on the construction path (``stack``) and the minimum
    element count if ``ann`` is a variadic tuple (``min_length``). Used by ``MockLLMProvider`` to
    pick a terminating union branch without depending on private helpers.
    """
    return _annotation_terminates(ann, stack, min_length)


def _model_terminates(model: type, stack: frozenset) -> bool:
    """True if ``model`` has at least one finite construction path.

    A model is constructible iff every REQUIRED field is constructible (fields with a default or
    default_factory are always satisfiable). A model already on ``stack`` is a cycle → not
    constructible via this path. The field's ``min_length`` constraint is threaded into the
    top-level annotation so a required ``tuple[Self, ...] = Field(min_length>=1)`` is recognized as
    non-terminating.
    """
    if model in stack:
        return False
    new_stack = stack | {model}
    for fi in model.model_fields.values():
        if fi.is_required():
            ml = _min_length_from_metadata(getattr(fi, "metadata", ()))
            if not _annotation_terminates(fi.annotation, new_stack, ml):
                return False
    return True


def _assert_constructible(schema: type) -> None:
    """Raise if ``schema`` has no finite construction path (impossible required recursive cycle)."""
    if not _model_terminates(schema, frozenset()):
        raise ValueError(
            f"structured-schema violation: {schema.__name__!r} has no finite construction path — "
            f"a required field forms a required recursive cycle with no terminating branch. "
            f"Make a cycle field Optional/defaulted, use a variadic tuple[..., ...] (empty "
            f"terminates), or add a terminating union branch (e.g. str / int / None)."
        )


def _check_schema_config(schema: type, name: str) -> None:
    """Assert that the effective Pydantic config of ``schema`` matches CoreContractModel requirements.

    Checks the MERGED config (parent + subclass overrides) so subclasses that partially override
    the base config are still caught. Uses exact comparisons (``is True``, ``is False``) so implicit
    defaults are never silently accepted. Raises ``ValueError`` — non-billable.
    """
    cfg = schema.model_config
    if cfg.get("frozen") is not True:
        raise ValueError(
            f"structured-schema violation: {name!r} must have model_config frozen=True "
            f"(CoreContractModel requirement — frozen!=True allows post-construction mutation)"
        )
    if cfg.get("extra") != "forbid":
        raise ValueError(
            f"structured-schema violation: {name!r} must have model_config extra='forbid' "
            f"(current: extra={cfg.get('extra')!r} — unknown fields bypass token estimation "
            f"and assert_deeply_immutable)"
        )
    if cfg.get("allow_inf_nan") is not False:
        raise ValueError(
            f"structured-schema violation: {name!r} must have model_config allow_inf_nan=False "
            f"(current: allow_inf_nan={cfg.get('allow_inf_nan')!r} — non-finite floats are not "
            f"permitted in contract models)"
        )
    if cfg.get("validate_default") is not True:
        raise ValueError(
            f"structured-schema violation: {name!r} must have model_config validate_default=True "
            f"(CoreContractModel requirement — unvalidated defaults can bypass annotation checks)"
        )
    private_attrs = getattr(schema, "__private_attributes__", {})
    if private_attrs:
        raise ValueError(
            f"structured-schema violation: {name!r} declares private attributes "
            f"{set(private_attrs)!r} — private attributes are not permitted in response schemas"
        )
    computed = getattr(schema, "model_computed_fields", {})
    if computed:
        raise ValueError(
            f"structured-schema violation: {name!r} declares computed fields "
            f"{set(computed)!r} — @computed_field is not permitted in response schemas "
            f"(computed fields can produce mutable data bypassing immutability checks)"
        )
    if _has_custom_serializers(schema):
        raise ValueError(
            f"structured-schema violation: {name!r} declares custom field/model serializers — "
            f"@field_serializer and @model_serializer are not permitted in response schemas "
            f"(custom serializers can leak mutable or untrusted data)"
        )
    if _has_model_post_init(schema):
        raise ValueError(
            f"structured-schema violation: {name!r} overrides model_post_init — "
            f"model_post_init overrides are not permitted in response schemas "
            f"(they can inject undeclared mutable instance state via object.__setattr__)"
        )


def _check_field_default(default: Any, path: str) -> None:
    """Assert that a concrete field default is deeply immutable and finite.

    Permits immutable scalars, finite floats, tuples (recursively), and valid nested
    CoreContractModel instances. Rejects mutable containers, non-finite floats, plain BaseModel
    instances, and arbitrary objects. Pydantic undefined/required sentinels are handled by the
    caller (fi.is_required() guards the call site) and are never passed here.
    """
    if default is None:
        return
    # Reject Enum members BEFORE bool/scalar checks (a str/int-subclass Enum would pass otherwise).
    if isinstance(default, enum.Enum):
        raise ValueError(
            f"structured-schema violation at {path!r}: default value {default!r} is an Enum "
            f"member — Enum members can hold mutable values/attributes; use scalar values instead"
        )
    if isinstance(default, bool):
        return
    if isinstance(default, (str, bytes, int)):
        return
    if isinstance(default, float):
        if not math.isfinite(default):
            raise ValueError(
                f"structured-schema violation at {path!r}: default value "
                f"{default!r} is non-finite — only finite floats are permitted"
            )
        return
    if isinstance(default, tuple):
        for i, item in enumerate(default):
            _check_field_default(item, f"{path}[{i}]")
        return
    if isinstance(default, CoreContractModel):
        _check_schema_config(type(default), f"{path}.<default-model>")
        for fname in type(default).model_fields:
            _check_field_default(getattr(default, fname), f"{path}.{fname}")
        return
    if isinstance(default, (list, dict, set)):
        raise ValueError(
            f"structured-schema violation at {path!r}: default value "
            f"{default!r} is a mutable container — use a tuple literal or remove the default"
        )
    if isinstance(default, BaseModel):
        raise ValueError(
            f"structured-schema violation at {path!r}: default value is a plain "
            f"BaseModel instance — nested defaults must subclass CoreContractModel"
        )
    raise ValueError(
        f"structured-schema violation at {path!r}: default value {default!r} of type "
        f"{type(default).__name__!r} is not a permitted immutable type — "
        f"use immutable scalars, finite floats, tuples, or CoreContractModel instances"
    )


_ALLOWED_DEFAULT_FACTORIES: frozenset = frozenset({tuple})


def _check_schema_fields(schema: type, visiting: frozenset, parent: str) -> None:
    """Walk every Pydantic field annotation and default of ``schema`` and assert immutability."""
    _check_schema_config(schema, parent or schema.__name__)
    for name, fi in schema.model_fields.items():
        path = f"{schema.__name__}.{name}" if not parent else f"{parent}.{name}"
        constraints = normalize_field_constraints(getattr(fi, "metadata", ()), path=path)
        _check_constraint_consistency(fi.annotation, constraints, path)
        _check_annotation(fi.annotation, path, visiting)
        # Validate defaults; fi.is_required() is False when a default or default_factory exists.
        if not fi.is_required():
            if fi.default_factory is not None:
                if fi.default_factory not in _ALLOWED_DEFAULT_FACTORIES:
                    raise ValueError(
                        f"structured-schema violation at {path!r}: default_factory="
                        f"{fi.default_factory!r} is not permitted — only the built-in tuple() "
                        f"factory is allowed; use concrete immutable defaults instead"
                    )
            else:
                _check_field_default(fi.default, path)


def validate_structured_schema(schema: type) -> None:
    """Pre-call validation: schema must be a deeply-immutable CoreContractModel subclass.

    Checks:
    1. Schema is a class and a CoreContractModel subclass.
    2. Effective Pydantic config: frozen=True, extra='forbid', allow_inf_nan=False,
       validate_default=True — applied recursively to nested CoreContractModel schemas.
       Uses exact comparisons (is True / is False). Schemas declaring Pydantic private
       attributes are rejected.
    3. Every field annotation uses only immutable types (rejects Any, list/dict/set, plain
       BaseModel subclasses, and unknown annotations — fail-closed).
    4. Every field with a concrete default is validated by a full deep-immutability walk:
       permits immutable scalars, finite floats, tuples, and valid nested CoreContractModel.
       Rejects lists, dicts, sets, non-finite floats, plain BaseModel instances, and
       arbitrary objects. default_factory is permitted ONLY for the exact built-in tuple();
       all other factories (lambdas, functools.partial, callable objects, model constructors)
       are rejected pre-call.
    5. The schema has at least one finite construction path: a required field that forms a
       recursive cycle (directly, via a fixed-length tuple such as tuple[Self], or via a union
       where no branch terminates) makes the schema impossible to instantiate and is rejected
       before any provider call. Optional/defaulted cycle fields, variadic tuple[Self, ...]
       (empty terminates), and unions with a terminating branch (Self | str, Self | None) pass.
    6. Supported length and numeric constraints are finite, normalized to their strongest
       effective bounds, and mutually satisfiable. Impossible ranges are rejected before any
       provider call, including integer-only gaps such as ``gt=5, lt=6``.

    Raises ValueError — non-billable; the provider has not been called yet.
    Handles recursive/self-referencing schemas via a visited-schema set.
    """
    if not isinstance(schema, type):
        raise ValueError(
            f"validate_structured_schema: schema must be a class, "
            f"got {type(schema).__name__!r}"
        )
    if not issubclass(schema, CoreContractModel):
        raise ValueError(
            f"validate_structured_schema: {schema.__name__!r} must subclass CoreContractModel"
        )
    _check_schema_fields(schema, frozenset({schema}), parent="")
    _assert_constructible(schema)
