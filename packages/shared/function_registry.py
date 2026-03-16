from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from packages.shared.extensions import load_extension_modules

VALID_FUNCTION_KINDS = ("column_mapping_value",)


@dataclass(frozen=True)
class RegisteredFunction:
    function_key: str
    kind: str
    description: str
    module: str
    source: str
    input_type: str = "string"
    output_type: str = "string"
    deterministic: bool = True
    side_effects: bool = False
    handler: Callable[..., object] | None = field(
        default=None,
        repr=False,
        compare=False,
    )


class FunctionRegistry:
    def __init__(self) -> None:
        self._functions: dict[str, RegisteredFunction] = {}

    def register(self, function: RegisteredFunction) -> None:
        _validate_registered_function(function)
        existing = self._functions.get(function.function_key)
        if existing is not None:
            raise ValueError(
                "Duplicate function registration for key "
                f"{function.function_key!r}: {existing.module} and {function.module}"
            )
        self._functions[function.function_key] = function

    def get(self, function_key: str) -> RegisteredFunction:
        try:
            return self._functions[function_key]
        except KeyError as exc:
            raise KeyError(f"Unknown function key: {function_key}") from exc

    def list(self, *, kind: str | None = None) -> list[RegisteredFunction]:
        functions = sorted(
            self._functions.values(),
            key=lambda function: (function.kind, function.function_key),
        )
        if kind is None:
            return functions
        return [function for function in functions if function.kind == kind]

    def execute(self, function_key: str, **kwargs: Any) -> object:
        function = self.get(function_key)
        if function.handler is None:
            raise ValueError(f"Function {function_key!r} is not executable.")
        return function.handler(**kwargs)


def load_function_registry(
    *,
    extension_paths: tuple[Path, ...] = (),
    function_modules: tuple[str, ...] = (),
) -> FunctionRegistry:
    registry = FunctionRegistry()
    if not function_modules:
        return registry
    loaded_modules = load_extension_modules(
        extension_paths=extension_paths,
        extension_modules=function_modules,
    )
    for module_name, module in zip(function_modules, loaded_modules, strict=True):
        register_functions = getattr(module, "register_functions", None)
        if not callable(register_functions):
            raise ValueError(
                f"Function module {module_name!r} must define register_functions(registry)"
            )
        register_functions(registry)
    return registry


def serialize_registered_function(function: RegisteredFunction) -> dict[str, object]:
    return {
        "function_key": function.function_key,
        "kind": function.kind,
        "description": function.description,
        "module": function.module,
        "source": function.source,
        "input_type": function.input_type,
        "output_type": function.output_type,
        "deterministic": function.deterministic,
        "side_effects": function.side_effects,
        "executable": "true" if function.handler is not None else "false",
    }


def serialize_function_registry(
    registry: FunctionRegistry,
) -> dict[str, list[dict[str, object]]]:
    return {
        kind: [serialize_registered_function(function) for function in registry.list(kind=kind)]
        for kind in VALID_FUNCTION_KINDS
    }


def allowed_function_keys(
    *,
    function_registry: FunctionRegistry | None = None,
    kind: str | None = None,
) -> set[str]:
    registry = function_registry or FunctionRegistry()
    return {
        function.function_key
        for function in registry.list(kind=kind)
    }


def validate_function_key(
    function_key: str,
    *,
    function_registry: FunctionRegistry | None = None,
    kind: str | None = None,
) -> None:
    registry = function_registry or FunctionRegistry()
    try:
        function = registry.get(function_key)
    except KeyError as exc:
        raise ValueError(str(exc)) from exc
    if kind is not None and function.kind != kind:
        raise ValueError(
            "Function key is registered with an unsupported kind for this binding: "
            f"{function_key!r} is {function.kind!r}, expected {kind!r}"
        )


def _validate_registered_function(function: RegisteredFunction) -> None:
    if function.kind not in VALID_FUNCTION_KINDS:
        raise ValueError(
            "Unsupported function kind: "
            f"{function.kind!r}. Expected one of {', '.join(VALID_FUNCTION_KINDS)}."
        )
    if function.handler is None or not callable(function.handler):
        raise ValueError(f"Function {function.function_key!r} must define a callable handler.")
    if not function.function_key.strip():
        raise ValueError("Function key must not be empty.")
