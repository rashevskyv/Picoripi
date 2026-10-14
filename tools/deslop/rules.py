"""Slop rules for Python, reimplemented on the ``ast`` module.

The rule ideas come from maharshi365/deslop (MIT) and its generic rules from dmmulroy/anti-slop
(MIT, Dillon Mulroy). No JavaScript is copied: each rule below is written for Python code.

A checker takes one parsed module and yields ``(line, message)``. A project rule also has a
``collect`` step per module and a ``report`` step after all modules were read.
"""

from __future__ import annotations

import ast
import keyword
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Dict, Hashable, Iterable, Iterator, List, Optional, Tuple

Finding = Tuple[int, str]
FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)

DEFAULT_OPTIONS: Dict[str, Any] = {
    "poor_substring_max_length": 3,
    "poor_substring_words": ["error", "fail", "failed", "ok", "true", "false", "none", "data", "result", "value", "name"],
    "duplicate_const_min_length": 4,
}

MOCK_ASSERT_METHODS = frozenset(
    {
        "assert_called", "assert_called_once", "assert_called_with", "assert_called_once_with",
        "assert_any_call", "assert_has_calls", "assert_not_called",
        "assert_awaited", "assert_awaited_once", "assert_awaited_with", "assert_awaited_once_with",
        "assert_any_await", "assert_has_awaits", "assert_not_awaited",
    }
)
MOCK_ATTRIBUTES = frozenset(
    {
        "called", "call_count", "call_args", "call_args_list", "await_count", "await_args",
        "await_args_list", "method_calls", "mock_calls",
    }
)
# Context managers and Qt waits that check behaviour: a test with one of these has a real check.
REAL_CHECK_CALLS = frozenset({"raises", "warns", "waitSignal", "waitSignals", "waitUntil", "waitCallback", "assertNotEmitted"})
# Assertion helpers by prefix (self.assertEqual, check_rows, verify_output, expect_...).
CHECK_PREFIXES = ("assert", "check", "verify", "expect")
SHAPE_SUFFIXES = ("_dict", "_list", "_str", "_int", "_float", "_bool", "_tuple", "_set", "_bytes")
CONSTANT_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
# hasattr is not here on purpose: a probe has no plain-access form (the access raises when the attribute is missing).
LITERAL_ATTRIBUTE_ARITY = {"getattr": 2, "setattr": 3}
LITERAL_ATTRIBUTE_MESSAGES = {
    "getattr": "getattr with the constant name {attr!r}; read the attribute directly",
    "setattr": "setattr with the constant name {attr!r}; assign the attribute directly",
}


@dataclass
class Module:
    """One parsed file: ``path`` is repo-relative and posix; ``options`` are the resolved thresholds."""

    path: str
    tree: ast.Module
    options: Dict[str, Any]
    _nodes: Optional[List[ast.AST]] = None

    def walk(self) -> List[ast.AST]:
        """Every node of the module, walked once and shared by the rules."""
        if self._nodes is None:
            self._nodes = list(ast.walk(self.tree))
        return self._nodes

    @property
    def is_test(self) -> bool:
        return is_test_path(self.path)


def is_test_path(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return path.startswith("tests/") or name.startswith("test_") or name.endswith("_test.py")


@dataclass(frozen=True)
class Rule:
    id: str
    default_on: bool
    scope: str  # "tests": test files only; "all": every file
    why: str
    check: Optional[Callable[[Module], Iterable[Finding]]] = None
    collect: Optional[Callable[[Module], Iterable[Tuple[int, Hashable, str]]]] = None
    report: Optional[Callable[[Dict[Hashable, List[Tuple[str, int, str]]]], Dict[str, List[Finding]]]] = None


# ---- shared helpers -------------------------------------------------------------------------

def _name_of(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _is_name(node: ast.AST, name: str) -> bool:
    return isinstance(node, ast.Name) and node.id == name


def _test_functions(tree: ast.Module) -> Iterator[ast.AST]:
    """Test functions at module level and in Test* classes or unittest TestCase subclasses."""
    for node in tree.body:
        if isinstance(node, FUNCTION_NODES) and node.name.startswith("test"):
            yield node
        elif isinstance(node, ast.ClassDef) and _is_test_class(node):
            for item in node.body:
                if isinstance(item, FUNCTION_NODES) and item.name.startswith("test"):
                    yield item


def _is_test_class(node: ast.ClassDef) -> bool:
    return node.name.startswith("Test") or any(_name_of(base).endswith("TestCase") for base in node.bases)


def _public_functions(tree: ast.Module) -> Iterator[ast.AST]:
    for node in tree.body:
        if isinstance(node, FUNCTION_NODES) and not node.name.startswith("_"):
            yield node
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            for item in node.body:
                if isinstance(item, FUNCTION_NODES) and not item.name.startswith("_"):
                    yield item


def _mentions_mock(node: ast.AST) -> bool:
    return any(
        isinstance(sub, ast.Attribute) and (sub.attr in MOCK_ATTRIBUTES or sub.attr in MOCK_ASSERT_METHODS)
        for sub in ast.walk(node)
    )


def _call_kind(call: ast.Call) -> Optional[str]:
    """'mock' for a mock-call check, 'real' for a result or state check, None for any other call."""
    name = _name_of(call.func)
    if name in REAL_CHECK_CALLS:
        return "real"
    if name in MOCK_ASSERT_METHODS:
        return "mock"
    if name.lstrip("_").startswith(CHECK_PREFIXES):
        return "mock" if _mentions_mock(call) else "real"
    return None


def _assert_kind(test: ast.expr) -> str:
    if isinstance(test, ast.BoolOp):
        return "mock" if all(_assert_kind(value) == "mock" for value in test.values) else "real"
    return "mock" if _mentions_mock(test) else "real"


def _statement_lists(node: ast.AST) -> Iterator[List[ast.stmt]]:
    for value in vars(node).values():
        if isinstance(value, list) and value and isinstance(value[0], ast.stmt):
            yield value


def _is_builtin_call(node: ast.AST, name: str, arity: int) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == name
        and len(node.args) == arity
        and not node.keywords
    )


# ---- test rules (scope "tests") -------------------------------------------------------------

def check_call_only_assertions(module: Module) -> Iterator[Finding]:
    for func in _test_functions(module.tree):
        kinds = set()
        for node in ast.walk(func):
            if isinstance(node, ast.Assert):
                kinds.add(_assert_kind(node.test))
            elif isinstance(node, ast.Call):
                kind = _call_kind(node)
                if kind is not None:
                    kinds.add(kind)
        if "mock" in kinds and "real" not in kinds:
            yield func.lineno, f"{func.name} checks only mock calls; also assert a result or a state"


def _assertion_key(stmt: ast.stmt) -> Optional[str]:
    if isinstance(stmt, ast.Assert):
        return "assert " + ast.dump(stmt.test)
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call) and _call_kind(stmt.value) is not None:
        return "call " + ast.dump(stmt.value)
    return None


def check_repeated_assert_call(module: Module) -> Iterator[Finding]:
    for func in _test_functions(module.tree):
        for node in ast.walk(func):
            for body in _statement_lists(node):
                previous = None
                for stmt in body:
                    key = _assertion_key(stmt)
                    # Only directly adjacent repeats: an assertion can call code that changes state.
                    if key is not None and key == previous:
                        yield stmt.lineno, "the same assertion repeats right after itself; keep one"
                    previous = key


def _in_literal(test: ast.expr) -> Optional[str]:
    if isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.In):
        if isinstance(test.left, ast.Constant) and isinstance(test.left.value, str):
            return test.left.value
    return None


def _too_generic(literal: str, options: Dict[str, Any]) -> bool:
    return len(literal) <= options["poor_substring_max_length"] or literal.strip().lower() in options["poor_substring_words"]


def check_poor_substring_tests(module: Module) -> Iterator[Finding]:
    for func in _test_functions(module.tree):
        for node in ast.walk(func):
            found: Optional[str] = None
            if isinstance(node, ast.Assert):
                found = _in_literal(node.test)
            elif isinstance(node, ast.Call) and node.args:
                name = _name_of(node.func)
                if name == "assertTrue":
                    found = _in_literal(node.args[0])
                elif name == "assertIn" and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    found = node.args[0].value
            if found is not None and _too_generic(found, module.options):
                yield node.lineno, f"substring {ascii(found)} is too generic to prove the output; assert the full value"


def _is_sys_modules(node: ast.AST) -> bool:
    if isinstance(node, ast.Attribute):
        return node.attr == "modules" and _is_name(node.value, "sys")
    return isinstance(node, ast.Constant) and node.value == "sys.modules"


def check_module_mocking(module: Module) -> Iterator[Finding]:
    message = "replaces modules in sys.modules; inject the dependency instead"
    for node in module.walk():
        if isinstance(node, ast.Call):
            if node.args and _is_sys_modules(node.args[0]) and isinstance(node.func, ast.Attribute) and node.func.attr in {"dict", "setitem"}:
                yield node.lineno, message
            elif isinstance(node.func, ast.Attribute) and _is_sys_modules(node.func.value) and node.func.attr in {"update", "setdefault"}:
                yield node.lineno, message
        elif isinstance(node, (ast.Assign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Subscript) and _is_sys_modules(target.value) for target in targets):
                yield node.lineno, message


# ---- code rules (scope "all") ---------------------------------------------------------------

def _is_cast(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id == "cast"
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "cast"
        and isinstance(func.value, ast.Name)
        and func.value.id in ("typing", "typing_extensions")
    )


def check_chained_cast(module: Module) -> Iterator[Finding]:
    for node in module.walk():
        if isinstance(node, ast.Call) and _is_cast(node):
            if any(isinstance(sub, ast.Call) and _is_cast(sub) for arg in node.args[1:] for sub in ast.walk(arg)):
                yield node.lineno, "cast of a cast; give the value one type or narrow it once"


def check_getattr_literal(module: Module) -> Iterator[Finding]:
    for node in module.walk():
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        name = node.func.id
        arity = LITERAL_ATTRIBUTE_ARITY.get(name)
        if arity is None or node.keywords or len(node.args) != arity:
            continue
        attr = node.args[1]
        if not (isinstance(attr, ast.Constant) and isinstance(attr.value, str)):
            continue
        text = attr.value
        if not text.isidentifier() or keyword.iskeyword(text) or text.startswith("__"):
            continue
        yield node.lineno, LITERAL_ATTRIBUTE_MESSAGES[name].format(attr=text)


def _is_reduce(func: ast.expr) -> bool:
    return _is_name(func, "reduce") or (isinstance(func, ast.Attribute) and func.attr == "reduce" and _is_name(func.value, "functools"))


def _is_display(node: ast.AST) -> bool:
    return isinstance(node, (ast.List, ast.Tuple, ast.Dict, ast.Set))


def _copies_accumulator(body: ast.AST, acc: str) -> bool:
    for sub in ast.walk(body):
        if isinstance(sub, ast.BinOp) and isinstance(sub.op, (ast.Add, ast.BitOr)):
            if (_is_name(sub.left, acc) and _is_display(sub.right)) or (_is_name(sub.right, acc) and _is_display(sub.left)):
                return True
        elif isinstance(sub, ast.Dict) and any(key is None and _is_name(value, acc) for key, value in zip(sub.keys, sub.values)):
            return True
        elif isinstance(sub, (ast.List, ast.Tuple, ast.Set)) and any(
            isinstance(elt, ast.Starred) and _is_name(elt.value, acc) for elt in sub.elts
        ):
            return True
    return False


def check_reduce_accumulator_copy(module: Module) -> Iterator[Finding]:
    for node in module.walk():
        if isinstance(node, ast.Call) and _is_reduce(node.func) and node.args and isinstance(node.args[0], ast.Lambda):
            params = node.args[0].args.args
            if params and _copies_accumulator(node.args[0].body, params[0].arg):
                yield node.lineno, "the reducer copies the accumulator each step (quadratic); append to one list instead"


def _is_materialised(node: ast.expr) -> bool:
    if isinstance(node, (ast.ListComp, ast.SetComp)):
        return True
    return (
        isinstance(node, ast.Call)
        and _is_name(node.func, "list")
        and len(node.args) == 1
        and (isinstance(node.args[0], (ast.ListComp, ast.SetComp)) or _is_builtin_call(node.args[0], "map", 2) or _is_builtin_call(node.args[0], "filter", 2))
    )


def check_filter_map_chain(module: Module) -> Iterator[Finding]:
    for node in module.walk():
        if _is_builtin_call(node, "map", 2) and _is_builtin_call(node.args[1], "filter", 2):
            if not isinstance(node.args[1].args[1], ast.GeneratorExp):
                yield node.lineno, "map over filter; one comprehension states both steps"
        elif isinstance(node, ast.ListComp) and len(node.generators) == 1 and _is_materialised(node.generators[0].iter):
            yield node.lineno, "the comprehension iterates a materialised comprehension; merge them into one"


# ---- opt-in rules ----------------------------------------------------------------------------

def _mentions_any(node: ast.AST) -> bool:
    return any(
        (isinstance(sub, ast.Name) and sub.id == "Any") or (isinstance(sub, ast.Attribute) and sub.attr == "Any")
        for sub in ast.walk(node)
    )


def check_any_params_returns(module: Module) -> Iterator[Finding]:
    for func in _public_functions(module.tree):
        args = func.args
        params = [*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg]
        annotations = [param.annotation for param in params if param is not None and param.annotation is not None]
        if func.returns is not None:
            annotations.append(func.returns)
        if any(_mentions_any(annotation) for annotation in annotations):
            yield func.lineno, f"public {func.name} uses Any in its signature; name the type"


def _is_type_name(name: str) -> bool:
    """CamelCase names are types; ALL_CAPS names are constants and are not aliases of types."""
    return name[:1].isupper() and not name.isupper()


def check_pass_through_type_alias(module: Module) -> Iterator[Finding]:
    for stmt in module.tree.body:
        if not (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name)):
            continue
        target = stmt.targets[0].id
        if _is_type_name(target) and isinstance(stmt.value, (ast.Name, ast.Attribute)) and _is_type_name(_name_of(stmt.value)):
            value = _name_of(stmt.value)
            yield stmt.lineno, f"alias {target} = {value} changes nothing; use {value}"


def _defines_all(tree: ast.Module) -> bool:
    return any(
        isinstance(stmt, ast.Assign) and any(_is_name(target, "__all__") for target in stmt.targets)
        for stmt in tree.body
    )


def _module_binding_counts(tree: ast.Module) -> Counter:
    counts: Counter = Counter()
    for stmt in tree.body:
        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            for alias in stmt.names:
                counts[alias.asname or alias.name.split(".")[0]] += 1
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            counts[stmt.name] += 1
        elif isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                for sub in ast.walk(target):
                    if isinstance(sub, ast.Name):
                        counts[sub.id] += 1
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            counts[stmt.target.id] += 1
    return counts


def check_renamed_imports(module: Module) -> Iterator[Finding]:
    # Package __init__ files and modules with __all__ re-export names on purpose.
    if module.path.rsplit("/", 1)[-1] == "__init__.py" or _defines_all(module.tree):
        return
    bound = _module_binding_counts(module.tree)
    for node in module.walk():
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for alias in node.names:
            if alias.asname is None or alias.name == "*":
                continue
            if alias.asname == alias.name:
                yield node.lineno, f"{alias.name} is imported as itself; drop the alias"
            elif isinstance(node, ast.ImportFrom) and not alias.asname.startswith("_") and bound[alias.name] == 0:
                yield node.lineno, f"alias {alias.asname} for {alias.name} avoids no conflict; import {alias.name} directly"


def check_shape_in_names(module: Module) -> Iterator[Finding]:
    for node in module.walk():
        name = None
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            name = node.id
        elif isinstance(node, ast.arg):
            name = node.arg
        if name and name.endswith(SHAPE_SUFFIXES) and not name.startswith("__"):
            yield node.lineno, f"{name} encodes its type in the name; name the role instead"


def collect_duplicate_consts(module: Module) -> Iterator[Tuple[int, Hashable, str]]:
    minimum = module.options["duplicate_const_min_length"]
    for stmt in module.tree.body:
        if not (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name)):
            continue
        name = stmt.targets[0].id
        if not CONSTANT_NAME.match(name) or not isinstance(stmt.value, ast.Constant):
            continue
        literal = stmt.value.value
        if isinstance(literal, bool) or literal is None:
            continue
        if isinstance(literal, str) and len(literal) >= minimum:
            yield stmt.lineno, ("str", literal), name
        elif isinstance(literal, (int, float)) and abs(literal) > 10:
            yield stmt.lineno, ("num", literal), name


def report_duplicate_consts(entries: Dict[Hashable, List[Tuple[str, int, str]]]) -> Dict[str, List[Finding]]:
    found: Dict[str, List[Finding]] = defaultdict(list)
    for key, places in entries.items():
        paths = sorted({path for path, _, _ in places})
        if len(paths) < 2:
            continue
        for path, line, name in places:
            others = [other for other in paths if other != path]
            listed = ", ".join(others[:3]) + (" and more" if len(others) > 3 else "")
            found[path].append((line, f"{name} repeats the value {ascii(key[1])} of a constant in {listed}"))
    return found


RULES: Dict[str, Rule] = {
    rule.id: rule
    for rule in (
        Rule("call-only-assertions", True, "tests", "a test that only checks mock calls does not check the result", check_call_only_assertions),
        Rule("module-mocking", True, "tests", "replacing whole modules hides the real dependency", check_module_mocking),
        Rule("poor-substring-tests", True, "tests", "a short or generic substring passes for many wrong outputs", check_poor_substring_tests),
        Rule("repeated-assert-call", True, "tests", "the same assertion twice in a row adds no check", check_repeated_assert_call),
        Rule("chained-cast", True, "all", "a cast of a cast invents type evidence twice", check_chained_cast),
        Rule("getattr-literal", True, "all", "a constant attribute name hides a plain attribute access", check_getattr_literal),
        Rule("reduce-accumulator-copy", True, "all", "a reducer that copies its accumulator is quadratic", check_reduce_accumulator_copy),
        Rule("filter-map-chain", True, "all", "map over filter reads better as one comprehension", check_filter_map_chain),
        Rule("any-params-returns", False, "all", "Any in a public signature passes unchecked types on", check_any_params_returns),
        Rule("pass-through-type-alias", False, "all", "an alias that renames a type with no change adds a name only", check_pass_through_type_alias),
        Rule("renamed-imports", False, "all", "an import alias that avoids no conflict adds a name only", check_renamed_imports),
        Rule("shape-in-names", False, "all", "a type suffix in a name repeats what the type says", check_shape_in_names),
        Rule("duplicate-consts", False, "all", "the same constant in several modules drifts apart", collect=collect_duplicate_consts, report=report_duplicate_consts),
    )
}
