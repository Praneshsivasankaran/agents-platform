"""Adversarial tests for validate_structured_schema() — pre-call annotation checker.

Tests cover:
  - Accepted schemas: every permitted annotation form.
  - Rejected schemas: mutable annotations, Any, plain BaseModel, config overrides,
    mutable/non-finite defaults — all proven non-billable (provider not called).
  - Both LiteLLMProvider.respond() and MockLLMProvider.respond() enforce the validator.
  - LLMResponse.structured_from() rejects config-override instances via assert_deeply_immutable.

All LiteLLM calls are mocked; no credentials or network required.
"""
from __future__ import annotations

import enum
import functools
import json
import sys
from types import ModuleType, SimpleNamespace
from typing import Annotated, Any, Literal, Optional, Union
from unittest.mock import MagicMock, patch

import pytest
from pydantic import (
    BaseModel, ConfigDict, Field, PrivateAttr, ValidationError,
    computed_field, field_serializer, field_validator, model_serializer,
)

from core.interfaces.base import (
    CoreContractModel, assert_deeply_immutable, validate_structured_schema,
)
from core.interfaces.llm import LLMResponse
from core.interfaces.usage import Usage


# ---------------------------------------------------------------------------
# Shared schema fixtures
# ---------------------------------------------------------------------------

class _ScalarSchema(CoreContractModel):
    name: str
    score: int
    ratio: float
    flag: bool
    nothing: None = None


class _TupleSchema(CoreContractModel):
    tags: tuple[str, ...]
    pair: tuple[str, int]


class _OptionalSchema(CoreContractModel):
    nickname: Optional[str] = None


class _UnionSchema(CoreContractModel):
    value: Union[str, int]


class _LiteralSchema(CoreContractModel):
    status: Literal["pass", "fail", "pending"]


class _NestedSchema(CoreContractModel):
    inner: _ScalarSchema


class _RecursiveOuter(CoreContractModel):
    label: str
    child: Optional["_RecursiveOuter"] = None


class _MutableList(CoreContractModel):
    items: list[str]


class _MutableDict(CoreContractModel):
    mapping: dict[str, str]


class _MutableSet(CoreContractModel):
    tags: set[str]


class _AnyField(CoreContractModel):
    data: Any


class _NestedPlainBaseModel(CoreContractModel):
    inner: BaseModel  # type: ignore[type-arg]


class _MutableInsideTuple(CoreContractModel):
    items: tuple[list[str], ...]


class _MutableInsideOptional(CoreContractModel):
    maybe: Optional[list[str]] = None


class _MutableInsideUnion(CoreContractModel):
    value: Union[str, list[int]]


class _PlainBaseModelNested(BaseModel):
    x: str


class _NestedPlain(CoreContractModel):
    sub: _PlainBaseModelNested


# --- config-override schemas (each violates one CoreContractModel requirement) ----

class _UnfrozenConfig(CoreContractModel):
    model_config = ConfigDict(frozen=False)
    x: str


class _ExtraAllowConfig(CoreContractModel):
    model_config = ConfigDict(extra="allow")
    x: str


class _InfAllowConfig(CoreContractModel):
    model_config = ConfigDict(allow_inf_nan=True)
    score: float


class _NoValidateDefaultConfig(CoreContractModel):
    model_config = ConfigDict(validate_default=False)
    x: str = "ok"


# --- mutable/non-finite default value schemas ----------------------------------

class _MutableListDefault(CoreContractModel):
    # annotation is valid (tuple) but raw default is a mutable list
    items: tuple[str, ...] = []  # type: ignore[assignment]


class _InfFloatDefault(CoreContractModel):
    score: float = float("inf")


class _MutableFactoryDefault(CoreContractModel):
    items: tuple[str, ...] = Field(default_factory=list)


# --- factory violation schemas (strict allowlist: only exact tuple built-in) -

def _factory_raises() -> tuple:
    raise RuntimeError("factory side effect")


_lambda_list = lambda: ["a"]   # noqa: E731
_lambda_tuple = lambda: ()     # noqa: E731 — NOT the exact tuple built-in


class _RaisingFactory(CoreContractModel):
    items: tuple[str, ...] = Field(default_factory=_factory_raises)


class _LambdaListFactory(CoreContractModel):
    items: tuple[str, ...] = Field(default_factory=_lambda_list)


class _LambdaTupleFactory(CoreContractModel):
    # A lambda returning tuple is still not the exact built-in tuple — rejected.
    items: tuple[str, ...] = Field(default_factory=_lambda_tuple)


class _PartialFactory(CoreContractModel):
    items: tuple[str, ...] = Field(default_factory=functools.partial(tuple, []))


class _CallableObjInstance:
    def __call__(self) -> tuple:
        return ()


class _CallableObjectFactory(CoreContractModel):
    items: tuple[str, ...] = Field(default_factory=_CallableObjInstance())


class _ModelConstructorFactory(CoreContractModel):
    # A CoreContractModel subclass used as a factory is still not in the allowlist.
    items: tuple[str, ...] = Field(default_factory=_ScalarSchema)  # type: ignore[arg-type]


# --- allowed factory --------------------------------------------------------

class _TupleFactory(CoreContractModel):
    items: tuple[str, ...] = Field(default_factory=tuple)


# --- private attribute schema -----------------------------------------------

class _PrivateAttrSchema(CoreContractModel):
    name: str
    _hidden: str = PrivateAttr(default="secret")


# --- after-mode validator that returns mutable output (runtime-backstop test) --
# validate_structured_schema() passes (annotation is valid tuple), but the
# after-validator transforms the value to a list at runtime; assert_deeply_immutable
# inside LLMResponse._validate_payload catches the mutable value.

class _AfterValidatorMutable(CoreContractModel):
    items: tuple[str, ...]

    @field_validator("items", mode="after")
    @classmethod
    def _make_mutable(cls, v: tuple) -> list:  # type: ignore[return-value]
        return list(v)


# --- computed field schema (bypasses model_fields walk) -------------------------

class _ComputedFieldSchema(CoreContractModel):
    name: str

    @computed_field  # type: ignore[misc]
    @property
    def upper_name(self) -> str:
        return self.name.upper()


# --- custom serializer schemas (can produce mutable/untrusted serialized data) --

class _ModelSerializerSchema(CoreContractModel):
    x: str

    @model_serializer
    def _custom_serialize(self) -> dict:  # type: ignore[override]
        return {"x": self.x, "leaked": ["mutable-secret"]}


class _FieldSerializerSchema(CoreContractModel):
    x: str

    @field_serializer("x")
    def _serialize_x(self, v: str) -> str:
        return v.upper()


# --- model_post_init hidden state (injects via object.__setattr__, bypasses frozen) --

class _ModelPostInitSchema(CoreContractModel):
    name: str

    def model_post_init(self, __context: Any) -> None:
        object.__setattr__(self, "_hidden", ["mutable"])


# --- Literal with non-finite float member (reaches provider as invalid value) ---

class _LiteralInfSchema(CoreContractModel):
    value: Literal[float("inf"), "ok"]  # type: ignore[valid-type]


# --- required-recursive schema (no Optional/default terminating path) -----------
# Impossible to instantiate; crashes providers with RecursionError.

class _RequiredRecursive(CoreContractModel):
    label: str
    child: "_RequiredRecursive"  # required, no default — no terminating path


# --- recursive termination analysis cases (Codex repair pass 14) ----------------
# These exercise proper "does at least one finite construction path exist?" analysis,
# replacing the earlier (broken) _field_required heuristic.

# REJECT: fixed-length tuple[Self] requires exactly one Self — no terminating path.
class _FixedTupleRecursive(CoreContractModel):
    child: tuple["_FixedTupleRecursive"]  # type: ignore[misc]


# REJECT: fixed tuple[Self, str] still requires a Self element.
class _FixedTuplePairRecursive(CoreContractModel):
    child: tuple["_FixedTuplePairRecursive", str]  # type: ignore[misc]


# ACCEPT: variadic tuple[Self, ...] terminates via the empty tuple (min_length 0).
class _VariadicTupleRecursive(CoreContractModel):
    children: tuple["_VariadicTupleRecursive", ...]  # type: ignore[misc]


# REJECT: variadic tuple[Self, ...] with min_length=1 cannot terminate — at least one
# recursive element is required, so the empty tuple is no longer a valid value.
class _VariadicTupleRecursiveMin1(CoreContractModel):
    children: tuple["_VariadicTupleRecursiveMin1", ...] = Field(min_length=1)  # type: ignore[misc]


# REJECT: same with min_length=2.
class _VariadicTupleRecursiveMin2(CoreContractModel):
    children: tuple["_VariadicTupleRecursiveMin2", ...] = Field(min_length=2)  # type: ignore[misc]


# ACCEPT: variadic tuple of a SCALAR with min_length=1 — str terminates, so >=1 element is fine.
class _VariadicTupleScalarMin1(CoreContractModel):
    tags: tuple[str, ...] = Field(min_length=1)


# ACCEPT: Self | str — the str branch terminates.
class _UnionStrTerminating(CoreContractModel):
    label: str
    child: Union["_UnionStrTerminating", str]  # type: ignore[misc]


# ACCEPT: Self | int — the int branch terminates.
class _UnionIntTerminating(CoreContractModel):
    label: str
    child: Union["_UnionIntTerminating", int]  # type: ignore[misc]


# REJECT: Self | OtherImpossible — neither branch terminates.
class _Impossible(CoreContractModel):
    me: "_Impossible"  # required self-cycle — impossible on its own


class _UnionBothImpossible(CoreContractModel):
    child: Union["_UnionBothImpossible", _Impossible]  # type: ignore[misc]


# REJECT: mutual required cycle A -> B -> A.
class _MutualA(CoreContractModel):
    b: "_MutualB"


class _MutualB(CoreContractModel):
    a: "_MutualA"


# ACCEPT: mutual cycle with a terminating branch (B.a is Optional).
class _MutualTermA(CoreContractModel):
    b: "_MutualTermB"


class _MutualTermB(CoreContractModel):
    a: Optional["_MutualTermA"] = None


# Resolve forward references for the cross-class (mutual) recursive models so that
# fi.annotation introspection sees concrete types rather than unresolved ForwardRefs.
_FixedTupleRecursive.model_rebuild()
_FixedTuplePairRecursive.model_rebuild()
_VariadicTupleRecursive.model_rebuild()
_VariadicTupleRecursiveMin1.model_rebuild()
_VariadicTupleRecursiveMin2.model_rebuild()
_UnionStrTerminating.model_rebuild()
_UnionIntTerminating.model_rebuild()
_Impossible.model_rebuild()
_UnionBothImpossible.model_rebuild()
_MutualA.model_rebuild()
_MutualB.model_rebuild()
_MutualTermA.model_rebuild()
_MutualTermB.model_rebuild()


# --- Literal member hardening cases ---------------------------------------------

class _LiteralNanSchema(CoreContractModel):
    value: Literal[float("nan"), "ok"]  # type: ignore[valid-type]


class _LiteralFiniteFloatSchema(CoreContractModel):
    value: Literal[1.5, 2.5]  # type: ignore[valid-type]


class _LiteralBytesSchema(CoreContractModel):
    value: Literal[b"a", b"b"]  # type: ignore[valid-type]


# --- Enum rejection cases ------------------------------------------------------
# Enum members are NOT deeply immutable: they can hold mutable values and accept injected
# mutable attributes after construction. They are rejected from Literal annotations entirely;
# scalar Literal values must be used instead.

class _LiteralColor(enum.Enum):
    RED = "red"
    BLUE = "blue"


class _StrColor(str, enum.Enum):
    # A str-subclass Enum member IS an instance of str — it must still be rejected, proving the
    # explicit Enum check fires before the scalar check.
    RED = "red"
    BLUE = "blue"


class _ListValuedEnum(enum.Enum):
    # Enum member whose value is a mutable list — the canonical "Enum is not immutable" case.
    X = [1, 2]
    Y = [3, 4]


# REJECT: plain Enum members in a Literal.
class _LiteralEnumSchema(CoreContractModel):
    value: Literal[_LiteralColor.RED, _LiteralColor.BLUE]  # type: ignore[valid-type]


# REJECT: str-subclass Enum members in a Literal.
class _LiteralStrEnumSchema(CoreContractModel):
    value: Literal[_StrColor.RED, _StrColor.BLUE]  # type: ignore[valid-type]


# REJECT: list-valued Enum members in a Literal.
class _LiteralListEnumSchema(CoreContractModel):
    value: Literal[_ListValuedEnum.X, _ListValuedEnum.Y]  # type: ignore[valid-type]


# ---------------------------------------------------------------------------
# Direct unit tests for validate_structured_schema()
# ---------------------------------------------------------------------------


class TestValidateStructuredSchemaAccepted:
    def test_scalar_fields(self):
        validate_structured_schema(_ScalarSchema)  # must not raise

    def test_tuple_fields(self):
        validate_structured_schema(_TupleSchema)

    def test_optional_field(self):
        validate_structured_schema(_OptionalSchema)

    def test_union_field(self):
        validate_structured_schema(_UnionSchema)

    def test_literal_field(self):
        validate_structured_schema(_LiteralSchema)

    def test_nested_core_contract_model(self):
        validate_structured_schema(_NestedSchema)

    def test_recursive_schema(self):
        # Self-referencing via Optional[...] must not recurse infinitely.
        validate_structured_schema(_RecursiveOuter)

    def test_tuple_factory_accepted(self):
        # Only the exact built-in tuple() factory is in the allowlist.
        validate_structured_schema(_TupleFactory)

    def test_variadic_tuple_recursive_accepted(self):
        # tuple[Self, ...] terminates via the empty tuple (min_length 0).
        validate_structured_schema(_VariadicTupleRecursive)

    def test_variadic_tuple_scalar_min1_accepted(self):
        # tuple[str, ...] with min_length=1 terminates — str elements terminate.
        validate_structured_schema(_VariadicTupleScalarMin1)

    def test_union_str_terminating_accepted(self):
        # Self | str — the str branch provides a finite construction path.
        validate_structured_schema(_UnionStrTerminating)

    def test_union_int_terminating_accepted(self):
        validate_structured_schema(_UnionIntTerminating)

    def test_mutual_terminating_cycle_accepted(self):
        # A -> B -> Optional[A] terminates because B.a may be None.
        validate_structured_schema(_MutualTermA)

    def test_literal_finite_float_accepted(self):
        validate_structured_schema(_LiteralFiniteFloatSchema)

    def test_literal_bytes_accepted(self):
        validate_structured_schema(_LiteralBytesSchema)

    def test_not_a_class_raises(self):
        with pytest.raises(ValueError, match="must be a class"):
            validate_structured_schema("not_a_class")  # type: ignore[arg-type]

    def test_plain_base_model_root_raises(self):
        with pytest.raises(ValueError, match="must subclass CoreContractModel"):
            validate_structured_schema(_PlainBaseModelNested)


class TestValidateStructuredSchemaRejected:
    def test_list_field_rejected(self):
        with pytest.raises(ValueError, match="mutable container"):
            validate_structured_schema(_MutableList)

    def test_dict_field_rejected(self):
        with pytest.raises(ValueError, match="mutable container"):
            validate_structured_schema(_MutableDict)

    def test_set_field_rejected(self):
        with pytest.raises(ValueError, match="mutable container"):
            validate_structured_schema(_MutableSet)

    def test_any_field_rejected(self):
        with pytest.raises(ValueError, match="`Any` is not permitted"):
            validate_structured_schema(_AnyField)

    def test_nested_plain_base_model_rejected(self):
        with pytest.raises(ValueError, match="must subclass CoreContractModel"):
            validate_structured_schema(_NestedPlain)

    def test_mutable_inside_tuple_rejected(self):
        with pytest.raises(ValueError, match="mutable container"):
            validate_structured_schema(_MutableInsideTuple)

    def test_mutable_inside_optional_rejected(self):
        with pytest.raises(ValueError, match="mutable container"):
            validate_structured_schema(_MutableInsideOptional)

    def test_mutable_inside_union_rejected(self):
        with pytest.raises(ValueError, match="mutable container"):
            validate_structured_schema(_MutableInsideUnion)

    # --- config override rejections ---

    def test_unfrozen_config_rejected(self):
        with pytest.raises(ValueError, match="frozen=True"):
            validate_structured_schema(_UnfrozenConfig)

    def test_extra_allow_config_rejected(self):
        with pytest.raises(ValueError, match="extra='forbid'"):
            validate_structured_schema(_ExtraAllowConfig)

    def test_inf_allow_config_rejected(self):
        with pytest.raises(ValueError, match="allow_inf_nan=False"):
            validate_structured_schema(_InfAllowConfig)

    def test_no_validate_default_config_rejected(self):
        with pytest.raises(ValueError, match="validate_default=True"):
            validate_structured_schema(_NoValidateDefaultConfig)

    # --- mutable/non-finite default value rejections ---

    def test_mutable_list_default_rejected(self):
        with pytest.raises(ValueError, match="mutable container"):
            validate_structured_schema(_MutableListDefault)

    def test_inf_float_default_rejected(self):
        with pytest.raises(ValueError, match="non-finite"):
            validate_structured_schema(_InfFloatDefault)

    def test_mutable_factory_default_rejected(self):
        with pytest.raises(ValueError, match="default_factory="):
            validate_structured_schema(_MutableFactoryDefault)

    def test_raising_factory_rejected(self):
        with pytest.raises(ValueError, match="not permitted"):
            validate_structured_schema(_RaisingFactory)

    def test_lambda_list_factory_rejected(self):
        with pytest.raises(ValueError, match="not permitted"):
            validate_structured_schema(_LambdaListFactory)

    def test_lambda_tuple_factory_rejected(self):
        with pytest.raises(ValueError, match="not permitted"):
            validate_structured_schema(_LambdaTupleFactory)

    def test_partial_factory_rejected(self):
        with pytest.raises(ValueError, match="not permitted"):
            validate_structured_schema(_PartialFactory)

    def test_callable_object_factory_rejected(self):
        with pytest.raises(ValueError, match="not permitted"):
            validate_structured_schema(_CallableObjectFactory)

    def test_model_constructor_factory_rejected(self):
        with pytest.raises(ValueError, match="not permitted"):
            validate_structured_schema(_ModelConstructorFactory)

    def test_private_attr_schema_rejected(self):
        with pytest.raises(ValueError, match="private attributes"):
            validate_structured_schema(_PrivateAttrSchema)

    def test_computed_field_schema_rejected(self):
        with pytest.raises(ValueError, match="computed fields"):
            validate_structured_schema(_ComputedFieldSchema)

    def test_model_serializer_schema_rejected(self):
        with pytest.raises(ValueError, match="serializer"):
            validate_structured_schema(_ModelSerializerSchema)

    def test_field_serializer_schema_rejected(self):
        with pytest.raises(ValueError, match="serializer"):
            validate_structured_schema(_FieldSerializerSchema)

    def test_model_post_init_schema_rejected(self):
        with pytest.raises(ValueError, match="model_post_init"):
            validate_structured_schema(_ModelPostInitSchema)

    def test_literal_inf_schema_rejected(self):
        with pytest.raises(ValueError, match="non-finite"):
            validate_structured_schema(_LiteralInfSchema)

    def test_required_recursive_schema_rejected(self):
        with pytest.raises(ValueError, match="required recursive"):
            validate_structured_schema(_RequiredRecursive)

    def test_fixed_tuple_recursive_rejected(self):
        # tuple[Self] requires exactly one Self — impossible.
        with pytest.raises(ValueError, match="required recursive"):
            validate_structured_schema(_FixedTupleRecursive)

    def test_fixed_tuple_pair_recursive_rejected(self):
        # tuple[Self, str] still requires a Self element.
        with pytest.raises(ValueError, match="required recursive"):
            validate_structured_schema(_FixedTuplePairRecursive)

    def test_union_both_impossible_rejected(self):
        # Self | OtherImpossible — neither branch terminates.
        with pytest.raises(ValueError, match="required recursive"):
            validate_structured_schema(_UnionBothImpossible)

    def test_mutual_required_cycle_rejected(self):
        # A -> B -> A with all-required fields — no terminating path.
        with pytest.raises(ValueError, match="required recursive"):
            validate_structured_schema(_MutualA)

    def test_variadic_tuple_recursive_min1_rejected(self):
        # tuple[Self, ...] with min_length=1 cannot terminate (empty tuple disallowed).
        with pytest.raises(ValueError, match="required recursive"):
            validate_structured_schema(_VariadicTupleRecursiveMin1)

    def test_variadic_tuple_recursive_min2_rejected(self):
        with pytest.raises(ValueError, match="required recursive"):
            validate_structured_schema(_VariadicTupleRecursiveMin2)

    def test_literal_nan_rejected(self):
        with pytest.raises(ValueError, match="non-finite"):
            validate_structured_schema(_LiteralNanSchema)

    def test_literal_enum_rejected(self):
        with pytest.raises(ValueError, match="Enum member"):
            validate_structured_schema(_LiteralEnumSchema)

    def test_literal_str_enum_rejected(self):
        # str-subclass Enum members must still be rejected (Enum check before scalar check).
        with pytest.raises(ValueError, match="Enum member"):
            validate_structured_schema(_LiteralStrEnumSchema)

    def test_literal_list_enum_rejected(self):
        with pytest.raises(ValueError, match="Enum member"):
            validate_structured_schema(_LiteralListEnumSchema)


# ---------------------------------------------------------------------------
# LiteLLMProvider — mutable schema fails BEFORE provider call
# ---------------------------------------------------------------------------

# Minimal provider config (mirrors _MINIMAL_CFG from test_litellm_provider.py).
_MINIMAL_CFG = {
    "llm": {
        "provider": "litellm",
        "tier_models": {
            "cheap": "vertex_ai/gemini-2.5-flash",
            "strong": "vertex_ai/gemini-2.5-pro",
        },
        "vertex_project": "test-project",
        "vertex_location": "us-central1",
    },
    "cost": {
        "provider_currency": "USD",
        "fx_rates": {"USD": 83.0},
        "input_cost_per_token_inr": {"cheap": 0.0000249, "strong": 0.0001037},
        "output_cost_per_token_inr": {"cheap": 0.0002075, "strong": 0.0008300},
    },
}


def _make_litellm_provider():
    from core.providers.gcp.llm import LiteLLMProvider
    return LiteLLMProvider(_MINIMAL_CFG)


def _stub_litellm_module():
    """Return a MagicMock litellm module; completion raises to prevent accidental real calls."""
    mod = ModuleType("litellm")
    mod.completion = MagicMock(side_effect=AssertionError("litellm.completion must not be called"))
    mod.completion_cost = MagicMock(return_value=0.0)
    sys.modules["litellm"] = mod
    return mod


_VALID_MESSAGES = [{"role": "user", "content": "hello"}]


class TestLiteLLMProviderSchemaValidation:
    def setup_method(self):
        self._provider = _make_litellm_provider()
        self._mod = _stub_litellm_module()

    def teardown_method(self):
        sys.modules.pop("litellm", None)

    def _call(self, schema):
        return self._provider.respond(
            _VALID_MESSAGES,
            tier="cheap",
            response_schema=schema,
        )

    def test_mutable_list_schema_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="mutable container"):
            self._call(_MutableList)
        self._mod.completion.assert_not_called()

    def test_mutable_dict_schema_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="mutable container"):
            self._call(_MutableDict)
        self._mod.completion.assert_not_called()

    def test_mutable_set_schema_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="mutable container"):
            self._call(_MutableSet)
        self._mod.completion.assert_not_called()

    def test_any_field_schema_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="`Any` is not permitted"):
            self._call(_AnyField)
        self._mod.completion.assert_not_called()

    def test_nested_plain_base_model_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="must subclass CoreContractModel"):
            self._call(_NestedPlain)
        self._mod.completion.assert_not_called()

    def test_mutable_inside_optional_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="mutable container"):
            self._call(_MutableInsideOptional)
        self._mod.completion.assert_not_called()

    def test_not_a_class_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="must be a class"):
            self._call("not_a_schema")  # type: ignore[arg-type]
        self._mod.completion.assert_not_called()

    def test_plain_base_model_root_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="must subclass CoreContractModel"):
            self._call(_PlainBaseModelNested)
        self._mod.completion.assert_not_called()

    def test_unfrozen_config_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="frozen=True"):
            self._call(_UnfrozenConfig)
        self._mod.completion.assert_not_called()

    def test_extra_allow_config_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="extra='forbid'"):
            self._call(_ExtraAllowConfig)
        self._mod.completion.assert_not_called()

    def test_inf_allow_config_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="allow_inf_nan=False"):
            self._call(_InfAllowConfig)
        self._mod.completion.assert_not_called()

    def test_no_validate_default_config_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="validate_default=True"):
            self._call(_NoValidateDefaultConfig)
        self._mod.completion.assert_not_called()

    def test_mutable_list_default_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="mutable container"):
            self._call(_MutableListDefault)
        self._mod.completion.assert_not_called()

    def test_inf_float_default_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="non-finite"):
            self._call(_InfFloatDefault)
        self._mod.completion.assert_not_called()

    def test_raising_factory_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="not permitted"):
            self._call(_RaisingFactory)
        self._mod.completion.assert_not_called()

    def test_lambda_list_factory_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="not permitted"):
            self._call(_LambdaListFactory)
        self._mod.completion.assert_not_called()

    def test_lambda_tuple_factory_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="not permitted"):
            self._call(_LambdaTupleFactory)
        self._mod.completion.assert_not_called()

    def test_partial_factory_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="not permitted"):
            self._call(_PartialFactory)
        self._mod.completion.assert_not_called()

    def test_callable_object_factory_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="not permitted"):
            self._call(_CallableObjectFactory)
        self._mod.completion.assert_not_called()

    def test_model_constructor_factory_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="not permitted"):
            self._call(_ModelConstructorFactory)
        self._mod.completion.assert_not_called()

    def test_private_attr_schema_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="private attributes"):
            self._call(_PrivateAttrSchema)
        self._mod.completion.assert_not_called()

    def test_computed_field_schema_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="computed fields"):
            self._call(_ComputedFieldSchema)
        self._mod.completion.assert_not_called()

    def test_model_serializer_schema_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="serializer"):
            self._call(_ModelSerializerSchema)
        self._mod.completion.assert_not_called()

    def test_field_serializer_schema_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="serializer"):
            self._call(_FieldSerializerSchema)
        self._mod.completion.assert_not_called()

    def test_model_post_init_schema_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="model_post_init"):
            self._call(_ModelPostInitSchema)
        self._mod.completion.assert_not_called()

    def test_literal_inf_schema_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="non-finite"):
            self._call(_LiteralInfSchema)
        self._mod.completion.assert_not_called()

    def test_required_recursive_schema_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="required recursive"):
            self._call(_RequiredRecursive)
        self._mod.completion.assert_not_called()

    def test_fixed_tuple_recursive_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="required recursive"):
            self._call(_FixedTupleRecursive)
        self._mod.completion.assert_not_called()

    def test_fixed_tuple_pair_recursive_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="required recursive"):
            self._call(_FixedTuplePairRecursive)
        self._mod.completion.assert_not_called()

    def test_union_both_impossible_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="required recursive"):
            self._call(_UnionBothImpossible)
        self._mod.completion.assert_not_called()

    def test_mutual_required_cycle_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="required recursive"):
            self._call(_MutualA)
        self._mod.completion.assert_not_called()

    def test_variadic_tuple_recursive_min1_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="required recursive"):
            self._call(_VariadicTupleRecursiveMin1)
        self._mod.completion.assert_not_called()

    def test_variadic_tuple_recursive_min2_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="required recursive"):
            self._call(_VariadicTupleRecursiveMin2)
        self._mod.completion.assert_not_called()

    def test_literal_nan_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="non-finite"):
            self._call(_LiteralNanSchema)
        self._mod.completion.assert_not_called()

    def test_literal_enum_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="Enum member"):
            self._call(_LiteralEnumSchema)
        self._mod.completion.assert_not_called()

    def test_literal_str_enum_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="Enum member"):
            self._call(_LiteralStrEnumSchema)
        self._mod.completion.assert_not_called()

    def test_literal_list_enum_fails_before_provider_call(self):
        with pytest.raises(ValueError, match="Enum member"):
            self._call(_LiteralListEnumSchema)
        self._mod.completion.assert_not_called()

    def test_none_schema_accepted(self):
        # None schema → text response path; must NOT call validate_structured_schema.
        # Make completion return a valid text response so we can confirm no-raise.
        resp_obj = SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(content="hello"),
                finish_reason="stop",
            )],
            usage=SimpleNamespace(prompt_tokens=5, completion_tokens=3),
            model="vertex_ai/gemini-2.5-flash",
        )
        self._mod.completion.side_effect = None
        self._mod.completion.return_value = resp_obj
        self._mod.completion_cost.return_value = 0.001
        result = self._provider.respond(_VALID_MESSAGES, tier="cheap", response_schema=None)
        assert result.text == "hello"
        self._mod.completion.assert_called_once()


# ---------------------------------------------------------------------------
# MockLLMProvider — same schemas must be rejected before mock logic runs
# ---------------------------------------------------------------------------

class TestMockLLMProviderSchemaValidation:
    def setup_method(self):
        from core.providers.mock.llm import MockLLMProvider
        self._provider = MockLLMProvider()

    def _call(self, schema):
        return self._provider.respond(
            _VALID_MESSAGES,
            tier="cheap",
            response_schema=schema,
        )

    def test_mutable_list_schema_rejected(self):
        with pytest.raises(ValueError, match="mutable container"):
            self._call(_MutableList)

    def test_mutable_dict_schema_rejected(self):
        with pytest.raises(ValueError, match="mutable container"):
            self._call(_MutableDict)

    def test_mutable_set_schema_rejected(self):
        with pytest.raises(ValueError, match="mutable container"):
            self._call(_MutableSet)

    def test_any_field_schema_rejected(self):
        with pytest.raises(ValueError, match="`Any` is not permitted"):
            self._call(_AnyField)

    def test_nested_plain_base_model_rejected(self):
        with pytest.raises(ValueError, match="must subclass CoreContractModel"):
            self._call(_NestedPlain)

    def test_plain_base_model_root_rejected(self):
        with pytest.raises(ValueError, match="must subclass CoreContractModel"):
            self._call(_PlainBaseModelNested)

    def test_mutable_inside_optional_rejected(self):
        with pytest.raises(ValueError, match="mutable container"):
            self._call(_MutableInsideOptional)

    def test_valid_schema_accepted(self):
        result = self._call(_ScalarSchema)
        assert result.structured is not None

    def test_tuple_schema_accepted(self):
        result = self._call(_TupleSchema)
        assert result.structured is not None

    def test_optional_schema_accepted(self):
        result = self._call(_OptionalSchema)
        assert result.structured is not None

    def test_literal_schema_accepted(self):
        result = self._call(_LiteralSchema)
        assert result.structured is not None

    def test_nested_schema_accepted(self):
        result = self._call(_NestedSchema)
        assert result.structured is not None

    def test_unfrozen_config_rejected(self):
        with pytest.raises(ValueError, match="frozen=True"):
            self._call(_UnfrozenConfig)

    def test_extra_allow_config_rejected(self):
        with pytest.raises(ValueError, match="extra='forbid'"):
            self._call(_ExtraAllowConfig)

    def test_inf_allow_config_rejected(self):
        with pytest.raises(ValueError, match="allow_inf_nan=False"):
            self._call(_InfAllowConfig)

    def test_no_validate_default_config_rejected(self):
        with pytest.raises(ValueError, match="validate_default=True"):
            self._call(_NoValidateDefaultConfig)

    def test_mutable_list_default_rejected(self):
        with pytest.raises(ValueError, match="mutable container"):
            self._call(_MutableListDefault)

    def test_inf_float_default_rejected(self):
        with pytest.raises(ValueError, match="non-finite"):
            self._call(_InfFloatDefault)

    def test_raising_factory_rejected(self):
        with pytest.raises(ValueError, match="not permitted"):
            self._call(_RaisingFactory)

    def test_lambda_list_factory_rejected(self):
        with pytest.raises(ValueError, match="not permitted"):
            self._call(_LambdaListFactory)

    def test_lambda_tuple_factory_rejected(self):
        with pytest.raises(ValueError, match="not permitted"):
            self._call(_LambdaTupleFactory)

    def test_partial_factory_rejected(self):
        with pytest.raises(ValueError, match="not permitted"):
            self._call(_PartialFactory)

    def test_callable_object_factory_rejected(self):
        with pytest.raises(ValueError, match="not permitted"):
            self._call(_CallableObjectFactory)

    def test_model_constructor_factory_rejected(self):
        with pytest.raises(ValueError, match="not permitted"):
            self._call(_ModelConstructorFactory)

    def test_private_attr_schema_rejected(self):
        with pytest.raises(ValueError, match="private attributes"):
            self._call(_PrivateAttrSchema)

    def test_computed_field_schema_rejected(self):
        with pytest.raises(ValueError, match="computed fields"):
            self._call(_ComputedFieldSchema)

    def test_model_serializer_schema_rejected(self):
        with pytest.raises(ValueError, match="serializer"):
            self._call(_ModelSerializerSchema)

    def test_field_serializer_schema_rejected(self):
        with pytest.raises(ValueError, match="serializer"):
            self._call(_FieldSerializerSchema)

    def test_model_post_init_schema_rejected(self):
        with pytest.raises(ValueError, match="model_post_init"):
            self._call(_ModelPostInitSchema)

    def test_literal_inf_schema_rejected(self):
        with pytest.raises(ValueError, match="non-finite"):
            self._call(_LiteralInfSchema)

    def test_required_recursive_schema_rejected(self):
        with pytest.raises(ValueError, match="required recursive"):
            self._call(_RequiredRecursive)

    def test_fixed_tuple_recursive_rejected(self):
        with pytest.raises(ValueError, match="required recursive"):
            self._call(_FixedTupleRecursive)

    def test_fixed_tuple_pair_recursive_rejected(self):
        with pytest.raises(ValueError, match="required recursive"):
            self._call(_FixedTuplePairRecursive)

    def test_union_both_impossible_rejected(self):
        with pytest.raises(ValueError, match="required recursive"):
            self._call(_UnionBothImpossible)

    def test_mutual_required_cycle_rejected(self):
        with pytest.raises(ValueError, match="required recursive"):
            self._call(_MutualA)

    def test_literal_nan_rejected(self):
        with pytest.raises(ValueError, match="non-finite"):
            self._call(_LiteralNanSchema)

    def test_variadic_tuple_recursive_accepted(self):
        # tuple[Self, ...] terminates; mock produces the empty tuple (no recursion).
        result = self._call(_VariadicTupleRecursive)
        assert result.structured is not None
        assert result.structured.children == ()

    def test_variadic_tuple_recursive_min1_rejected(self):
        # Rejected pre-call; mock never attempts to construct it (no RecursionError).
        with pytest.raises(ValueError, match="required recursive"):
            self._call(_VariadicTupleRecursiveMin1)

    def test_variadic_tuple_recursive_min2_rejected(self):
        with pytest.raises(ValueError, match="required recursive"):
            self._call(_VariadicTupleRecursiveMin2)

    def test_variadic_tuple_scalar_min1_accepted(self):
        # tuple[str, ...] min_length=1 — mock produces one str element.
        result = self._call(_VariadicTupleScalarMin1)
        assert result.structured is not None
        assert len(result.structured.tags) >= 1

    def test_union_str_returns_terminating_scalar_branch(self):
        # Self | str: the mock must choose the str (terminating) branch, NOT recurse into Self.
        result = self._call(_UnionStrTerminating)
        assert result.structured is not None
        assert isinstance(result.structured.child, str)

    def test_union_int_returns_terminating_scalar_branch(self):
        result = self._call(_UnionIntTerminating)
        assert result.structured is not None
        assert isinstance(result.structured.child, int)

    def test_mutual_terminating_cycle_accepted(self):
        # A -> B -> Optional[A]: mock terminates B.a at None; no RecursionError.
        result = self._call(_MutualTermA)
        assert result.structured is not None
        assert result.structured.b.a is None

    def test_literal_enum_rejected(self):
        with pytest.raises(ValueError, match="Enum member"):
            self._call(_LiteralEnumSchema)

    def test_literal_str_enum_rejected(self):
        with pytest.raises(ValueError, match="Enum member"):
            self._call(_LiteralStrEnumSchema)


# ---------------------------------------------------------------------------
# LLMResponse.structured_from() — belt-and-suspenders runtime checks via
# assert_deeply_immutable (catches config overrides on already-constructed values)
# ---------------------------------------------------------------------------

class TestLLMResponseStructuredFromValidation:
    """assert_deeply_immutable() is called inside LLMResponse's model validator,
    so structured_from() catches config violations even without validate_structured_schema."""

    def test_unfrozen_schema_rejected_at_structured_from(self):
        # _UnfrozenConfig has frozen=False; assert_deeply_immutable catches this.
        with pytest.raises(ValidationError):
            LLMResponse.structured_from(_UnfrozenConfig, {"x": "hello"}, usage=Usage())

    def test_extra_allow_schema_with_extra_fields_rejected(self):
        # _ExtraAllowConfig has extra="allow"; providing an extra field creates an
        # instance with __pydantic_extra__; assert_deeply_immutable catches this.
        with pytest.raises(ValidationError):
            LLMResponse.structured_from(
                _ExtraAllowConfig,
                {"x": "hello", "surprise": "extra"},
                usage=Usage(),
            )

    def test_extra_allow_schema_no_extras_rejected_by_config_check(self):
        # Even without extra fields present, extra="allow" config violates the contract.
        with pytest.raises(ValidationError):
            LLMResponse.structured_from(_ExtraAllowConfig, {"x": "hello"}, usage=Usage())

    def test_inf_float_default_rejected_when_default_used(self):
        # With validate_default=True, using the non-finite default fails Pydantic validation.
        with pytest.raises(ValidationError):
            LLMResponse.structured_from(_InfFloatDefault, {}, usage=Usage())

    def test_inf_allow_config_rejected_at_structured_from(self):
        # assert_deeply_immutable now checks allow_inf_nan!=False.
        with pytest.raises(ValidationError):
            LLMResponse.structured_from(_InfAllowConfig, {"score": 1.0}, usage=Usage())

    def test_no_validate_default_config_rejected_at_structured_from(self):
        # assert_deeply_immutable now checks validate_default!=True.
        with pytest.raises(ValidationError):
            LLMResponse.structured_from(_NoValidateDefaultConfig, {"x": "ok"}, usage=Usage())

    def test_private_attr_schema_rejected_at_structured_from(self):
        # assert_deeply_immutable rejects schemas that declare private attributes.
        with pytest.raises(ValidationError):
            LLMResponse.structured_from(_PrivateAttrSchema, {"name": "Alice"}, usage=Usage())

    def test_model_construct_mutable_value_caught_by_backstop(self):
        # model_construct() bypasses Pydantic validators; the runtime backstop inside
        # LLMResponse._validate_payload catches the mutable value via assert_deeply_immutable.
        instance = _ScalarSchema.model_construct(
            name=["injected_list"], score=0, ratio=0.0, flag=False, nothing=None
        )
        with pytest.raises(ValidationError):
            LLMResponse(structured=instance, usage=Usage())

    def test_model_construct_nonfinite_float_caught_by_backstop(self):
        # Non-finite floats injected via model_construct() are caught at runtime.
        instance = _ScalarSchema.model_construct(
            name="ok", score=0, ratio=float("inf"), flag=False, nothing=None
        )
        with pytest.raises(ValidationError):
            LLMResponse(structured=instance, usage=Usage())

    def test_after_validator_mutable_output_caught_by_backstop(self):
        # validate_structured_schema accepts _AfterValidatorMutable (annotation is valid tuple).
        # The after-validator transforms the value to a list at runtime; assert_deeply_immutable
        # catches it before the LLMResponse is constructed — proving the runtime backstop fills
        # the gap that pre-call annotation checks cannot.
        validate_structured_schema(_AfterValidatorMutable)  # must not raise
        with pytest.raises(ValidationError):
            LLMResponse.structured_from(_AfterValidatorMutable, {"items": ["a"]}, usage=Usage())

    def test_computed_field_caught_by_runtime_backstop(self):
        # Pre-call correctly rejects the schema; even if an instance somehow bypasses pre-call,
        # the runtime backstop catches the computed field at the type level.
        with pytest.raises(ValueError, match="computed fields"):
            validate_structured_schema(_ComputedFieldSchema)
        instance = _ComputedFieldSchema(name="Alice")
        with pytest.raises(ValidationError):
            LLMResponse(structured=instance, usage=Usage())

    def test_model_serializer_caught_by_runtime_backstop(self):
        with pytest.raises(ValueError, match="serializer"):
            validate_structured_schema(_ModelSerializerSchema)
        instance = _ModelSerializerSchema(x="hello")
        with pytest.raises(ValidationError):
            LLMResponse(structured=instance, usage=Usage())

    def test_field_serializer_caught_by_runtime_backstop(self):
        with pytest.raises(ValueError, match="serializer"):
            validate_structured_schema(_FieldSerializerSchema)
        instance = _FieldSerializerSchema(x="hello")
        with pytest.raises(ValidationError):
            LLMResponse(structured=instance, usage=Usage())

    def test_model_post_init_hidden_state_caught_by_runtime_backstop(self):
        # _ModelPostInitSchema injects a hidden list via object.__setattr__ in model_post_init.
        # The runtime backstop detects the undeclared key in __dict__.
        with pytest.raises(ValueError, match="model_post_init"):
            validate_structured_schema(_ModelPostInitSchema)
        instance = _ModelPostInitSchema(name="Alice")
        # instance.__dict__ now contains {'name': 'Alice', '_hidden': ['mutable']}
        with pytest.raises(ValidationError):
            LLMResponse(structured=instance, usage=Usage())

    def test_list_valued_enum_rejected_by_assert_deeply_immutable(self):
        # An Enum member holding a mutable list is NOT deeply immutable — the list can be mutated
        # after the member passes validation. assert_deeply_immutable rejects it directly.
        with pytest.raises(ValueError, match="Enum member"):
            assert_deeply_immutable(_ListValuedEnum.X)

    def test_str_subclass_enum_rejected_by_assert_deeply_immutable(self):
        # A str-subclass Enum member is an instance of str but must still be rejected — Enum
        # members accept injected mutable attributes after construction.
        with pytest.raises(ValueError, match="Enum member"):
            assert_deeply_immutable(_StrColor.RED)

    def test_str_subclass_enum_value_caught_by_backstop(self):
        # Inject a str-subclass Enum into a str-typed field via model_construct; the runtime
        # backstop in LLMResponse._validate_payload catches the Enum before construction.
        instance = _ScalarSchema.model_construct(
            name=_StrColor.RED, score=0, ratio=0.0, flag=False, nothing=None
        )
        with pytest.raises(ValidationError):
            LLMResponse(structured=instance, usage=Usage())


# ---------------------------------------------------------------------------
# Contract-parity matrix — every invalid schema rejected at all pre-call
# boundaries; every valid schema accepted.
# ---------------------------------------------------------------------------

_INVALID_PARITY_CASES = [
    # Annotation violations
    pytest.param(_MutableList,          "mutable container",            id="list_field"),
    pytest.param(_MutableDict,          "mutable container",            id="dict_field"),
    pytest.param(_MutableSet,           "mutable container",            id="set_field"),
    pytest.param(_AnyField,             r"`Any` is not permitted",      id="any_field"),
    pytest.param(_NestedPlainBaseModel, "must subclass CoreContractModel", id="nested_base_model"),
    pytest.param(_NestedPlain,          "must subclass CoreContractModel", id="nested_plain"),
    pytest.param(_MutableInsideTuple,   "mutable container",            id="mutable_in_tuple"),
    pytest.param(_MutableInsideOptional,"mutable container",            id="mutable_in_optional"),
    pytest.param(_MutableInsideUnion,   "mutable container",            id="mutable_in_union"),
    # Config override violations
    pytest.param(_UnfrozenConfig,         "frozen=True",           id="unfrozen_config"),
    pytest.param(_ExtraAllowConfig,       "extra='forbid'",        id="extra_allow"),
    pytest.param(_InfAllowConfig,         "allow_inf_nan=False",   id="inf_allow"),
    pytest.param(_NoValidateDefaultConfig,"validate_default=True", id="no_validate_default"),
    # Default value violations
    pytest.param(_MutableListDefault, "mutable container", id="mutable_list_default"),
    pytest.param(_InfFloatDefault,     "non-finite",        id="inf_float_default"),
    # Factory violations
    pytest.param(_MutableFactoryDefault,   "not permitted", id="mutable_factory"),
    pytest.param(_RaisingFactory,          "not permitted", id="raising_factory"),
    pytest.param(_LambdaListFactory,       "not permitted", id="lambda_list_factory"),
    pytest.param(_LambdaTupleFactory,      "not permitted", id="lambda_tuple_factory"),
    pytest.param(_PartialFactory,          "not permitted", id="partial_factory"),
    pytest.param(_CallableObjectFactory,   "not permitted", id="callable_obj_factory"),
    pytest.param(_ModelConstructorFactory, "not permitted", id="model_ctor_factory"),
    # Private attribute violation
    pytest.param(_PrivateAttrSchema, "private attributes", id="private_attr"),
    # Computed field / serializer / post-init violations
    pytest.param(_ComputedFieldSchema,   "computed fields",      id="computed_field"),
    pytest.param(_ModelSerializerSchema, "serializer",           id="model_serializer"),
    pytest.param(_FieldSerializerSchema, "serializer",           id="field_serializer"),
    pytest.param(_ModelPostInitSchema,   "model_post_init",      id="model_post_init"),
    # Literal non-finite member
    pytest.param(_LiteralInfSchema,      "non-finite",           id="literal_inf"),
    pytest.param(_LiteralNanSchema,      "non-finite",           id="literal_nan"),
    # Literal Enum members (not deeply immutable)
    pytest.param(_LiteralEnumSchema,     "Enum member",          id="literal_enum"),
    pytest.param(_LiteralStrEnumSchema,  "Enum member",          id="literal_str_enum"),
    pytest.param(_LiteralListEnumSchema, "Enum member",          id="literal_list_enum"),
    # Required-recursive cycles (no terminating path)
    pytest.param(_RequiredRecursive,         "required recursive", id="required_recursive"),
    pytest.param(_FixedTupleRecursive,       "required recursive", id="fixed_tuple_recursive"),
    pytest.param(_FixedTuplePairRecursive,   "required recursive", id="fixed_tuple_pair_recursive"),
    pytest.param(_UnionBothImpossible,       "required recursive", id="union_both_impossible"),
    pytest.param(_MutualA,                   "required recursive", id="mutual_required_cycle"),
    pytest.param(_VariadicTupleRecursiveMin1,"required recursive", id="variadic_tuple_recursive_min1"),
    pytest.param(_VariadicTupleRecursiveMin2,"required recursive", id="variadic_tuple_recursive_min2"),
]

_VALID_PARITY_CASES = [
    pytest.param(_ScalarSchema,         id="scalars"),
    pytest.param(_TupleSchema,          id="tuples"),
    pytest.param(_OptionalSchema,       id="optional"),
    pytest.param(_UnionSchema,          id="union"),
    pytest.param(_LiteralSchema,        id="literal"),
    pytest.param(_NestedSchema,         id="nested"),
    pytest.param(_RecursiveOuter,       id="recursive"),
    pytest.param(_TupleFactory,         id="tuple_factory"),
    # Recursive schemas WITH a finite construction path (termination analysis accepts).
    pytest.param(_VariadicTupleRecursive, id="variadic_tuple_recursive"),
    pytest.param(_VariadicTupleScalarMin1, id="variadic_tuple_scalar_min1"),
    pytest.param(_UnionStrTerminating,    id="union_str_terminating"),
    pytest.param(_UnionIntTerminating,    id="union_int_terminating"),
    pytest.param(_MutualTermA,            id="mutual_terminating_cycle"),
    # Literal members that are supported immutable/JSON-compatible scalar values.
    pytest.param(_LiteralFiniteFloatSchema, id="literal_finite_float"),
    pytest.param(_LiteralBytesSchema,       id="literal_bytes"),
    # _AfterValidatorMutable: annotation is valid tuple so pre-call accepts it;
    # the runtime backstop (assert_deeply_immutable) catches the mutable value produced
    # by the after-validator — see test_after_validator_mutable_output_caught_by_backstop.
    pytest.param(_AfterValidatorMutable, id="after_validator_pre_call_accepted"),
]


class TestContractParityInvalid:
    """Every invalid schema must be rejected by all three pre-call boundaries."""

    def setup_method(self):
        self._provider = _make_litellm_provider()
        self._mod = _stub_litellm_module()
        from core.providers.mock.llm import MockLLMProvider
        self._mock_provider = MockLLMProvider()

    def teardown_method(self):
        sys.modules.pop("litellm", None)

    @pytest.mark.parametrize("schema,err_pattern", _INVALID_PARITY_CASES)
    def test_all_pre_call_boundaries_reject(self, schema, err_pattern):
        # Boundary 1: validate_structured_schema
        with pytest.raises(ValueError, match=err_pattern):
            validate_structured_schema(schema)

        # Boundary 2: LiteLLMProvider — provider must not be called
        with pytest.raises(ValueError, match=err_pattern):
            self._provider.respond(_VALID_MESSAGES, tier="cheap", response_schema=schema)
        self._mod.completion.assert_not_called()

        # Boundary 3: MockLLMProvider
        with pytest.raises(ValueError, match=err_pattern):
            self._mock_provider.respond(_VALID_MESSAGES, tier="cheap", response_schema=schema)


class TestContractParityValid:
    """Every valid schema must be accepted by validate_structured_schema."""

    @pytest.mark.parametrize("schema", _VALID_PARITY_CASES)
    def test_valid_schema_accepted_pre_call(self, schema):
        validate_structured_schema(schema)  # must not raise


# ---------------------------------------------------------------------------
# Constraint normalization parity
# ---------------------------------------------------------------------------

class _ConstrainedRecursiveUnion(CoreContractModel):
    value: Union[tuple["_ConstrainedRecursiveUnion", ...], str] = Field(min_length=1)


class _ContradictoryStringLength(CoreContractModel):
    value: str = Field(min_length=5, max_length=2)


class _ContradictoryTupleLength(CoreContractModel):
    value: tuple[str, ...] = Field(min_length=2, max_length=1)


class _ContradictoryIntRange(CoreContractModel):
    value: int = Field(ge=5, le=2)


class _ContradictoryIntGap(CoreContractModel):
    value: int = Field(gt=5, lt=6)


class _ContradictoryFloatRange(CoreContractModel):
    value: float = Field(ge=5, lt=5)


class _ImpossibleFixedTupleLength(CoreContractModel):
    value: tuple[str, str] = Field(min_length=3)


class _ImpossibleLiteralLength(CoreContractModel):
    value: Literal["x", "yy"] = Field(min_length=3)


class _ImpossibleExtremeFloat(CoreContractModel):
    value: float = Field(gt=sys.float_info.max)


class _UnsupportedPatternConstraint(CoreContractModel):
    value: str = Field(pattern=r"^abc$")


class _UnsupportedMultipleOfConstraint(CoreContractModel):
    value: int = Field(multiple_of=5)


class _AnnotatedImpossibleRange(CoreContractModel):
    value: Annotated[int, Field(gt=5, lt=6)]


class _AnnotatedValidRange(CoreContractModel):
    value: Annotated[int, Field(gt=5, lt=8)]


# Annotated[..., Field(...)] NESTED inside a container: Pydantic does not pre-flatten the
# FieldInfo into the field's metadata here (unlike a field-level Annotated), so the constraint
# objects live inside FieldInfo.metadata. The normalizer must still unwrap them — otherwise an
# impossible nested constraint bypasses validation and a valid one makes the mock emit invalid
# values that fail Pydantic on the way out.
class _NestedAnnotatedImpossibleRange(CoreContractModel):
    values: tuple[Annotated[int, Field(gt=5, lt=6)], ...] = Field(min_length=1)


class _NestedAnnotatedValidRange(CoreContractModel):
    values: tuple[Annotated[int, Field(ge=10, le=20)], ...] = Field(min_length=2)


class _MixedIntBounds(CoreContractModel):
    value: int = Field(ge=5, gt=10, le=20, lt=18)


class _MixedFloatBounds(CoreContractModel):
    value: float = Field(ge=5, gt=10, le=20, lt=18)


class _ZeroLengthString(CoreContractModel):
    value: str = Field(max_length=0)


class _ConstrainedBytes(CoreContractModel):
    value: bytes = Field(min_length=2, max_length=4)


_ConstrainedRecursiveUnion.model_rebuild()

_CONTRADICTORY_CONSTRAINT_SCHEMAS = [
    pytest.param(_ContradictoryStringLength, "contradictory length", id="string_length"),
    pytest.param(_ContradictoryTupleLength, "contradictory length", id="tuple_length"),
    pytest.param(_ContradictoryIntRange, "contradictory numeric", id="int_range"),
    pytest.param(_ContradictoryIntGap, "incompatible", id="int_domain_gap"),
    pytest.param(_ContradictoryFloatRange, "contradictory numeric", id="float_range"),
    pytest.param(_ImpossibleFixedTupleLength, "incompatible", id="fixed_tuple_length"),
    pytest.param(_ImpossibleLiteralLength, "incompatible", id="literal_length"),
    pytest.param(_ImpossibleExtremeFloat, "incompatible", id="extreme_float"),
    pytest.param(_UnsupportedPatternConstraint, "unsupported constraint", id="pattern"),
    pytest.param(_UnsupportedMultipleOfConstraint, "unsupported constraint", id="multiple_of"),
    pytest.param(_AnnotatedImpossibleRange, "incompatible", id="annotated_int_gap"),
    pytest.param(_NestedAnnotatedImpossibleRange, "incompatible", id="nested_annotated_int_gap"),
]


@pytest.mark.parametrize("schema,pattern", _CONTRADICTORY_CONSTRAINT_SCHEMAS)
def test_contradictory_constraints_rejected_pre_call(schema, pattern):
    provider = _make_litellm_provider()
    mod = _stub_litellm_module()
    try:
        with pytest.raises(ValueError, match=pattern):
            validate_structured_schema(schema)
        with pytest.raises(ValueError, match=pattern):
            provider.respond(_VALID_MESSAGES, tier="cheap", response_schema=schema)
        mod.completion.assert_not_called()
    finally:
        sys.modules.pop("litellm", None)


def test_mock_constrained_recursive_union_selects_valid_string_branch():
    from core.providers.mock.llm import MockLLMProvider

    result = MockLLMProvider().respond(
        _VALID_MESSAGES,
        tier="cheap",
        response_schema=_ConstrainedRecursiveUnion,
    )
    assert isinstance(result.structured.value, str)
    assert len(result.structured.value) >= 1


@pytest.mark.parametrize(
    "schema,lower,upper",
    [
        pytest.param(_MixedIntBounds, 10, 18, id="int"),
        pytest.param(_MixedFloatBounds, 10, 18, id="float"),
    ],
)
def test_mock_uses_strongest_mixed_numeric_bounds(schema, lower, upper):
    from core.providers.mock.llm import MockLLMProvider

    validate_structured_schema(schema)
    result = MockLLMProvider().respond(
        _VALID_MESSAGES,
        tier="cheap",
        response_schema=schema,
    )
    assert lower < result.structured.value < upper


def test_mock_respects_zero_max_length_string():
    from core.providers.mock.llm import MockLLMProvider

    result = MockLLMProvider().respond(
        _VALID_MESSAGES,
        tier="cheap",
        response_schema=_ZeroLengthString,
    )
    assert result.structured.value == ""


def test_mock_generates_constrained_bytes():
    from core.providers.mock.llm import MockLLMProvider

    result = MockLLMProvider().respond(
        _VALID_MESSAGES,
        tier="cheap",
        response_schema=_ConstrainedBytes,
    )
    assert isinstance(result.structured.value, bytes)
    assert 2 <= len(result.structured.value) <= 4


def test_mock_honors_annotated_branch_constraints():
    from core.providers.mock.llm import MockLLMProvider

    validate_structured_schema(_AnnotatedValidRange)
    result = MockLLMProvider().respond(
        _VALID_MESSAGES,
        tier="cheap",
        response_schema=_AnnotatedValidRange,
    )
    assert 5 < result.structured.value < 8


def test_mock_honors_nested_annotated_field_constraints():
    # Constraints written as Annotated[int, Field(...)] nested inside a tuple must be honored:
    # the mock must emit elements satisfying ge/le (not the default 0) and not crash on output.
    from core.providers.mock.llm import MockLLMProvider

    validate_structured_schema(_NestedAnnotatedValidRange)
    result = MockLLMProvider().respond(
        _VALID_MESSAGES,
        tier="cheap",
        response_schema=_NestedAnnotatedValidRange,
    )
    assert len(result.structured.values) >= 2
    assert all(10 <= v <= 20 for v in result.structured.values)
