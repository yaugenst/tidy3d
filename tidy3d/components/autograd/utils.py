# utilities for working with autograd

from collections.abc import Mapping, Sequence
from typing import Any

from autograd.extend import Box
from autograd.tracer import getval


def get_static(x: Any) -> Any:
    """Get the 'static' (untraced) version of some value."""
    return getval(x)


def split_list(x: list[Any], index: int) -> (list[Any], list[Any]):
    """Split a list at a given index."""
    x = list(x)
    return x[:index], x[index:]


def is_tidy_box(x: Any) -> bool:
    """Check if a value is a tidy box."""
    return getattr(x, "_tidy", False)


def contains_box(obj: Any) -> bool:
    """True if any element inside obj is an autograd Box."""
    if isinstance(obj, Box):
        return True
    if isinstance(obj, Mapping):
        return any(contains_box(v) for v in obj.values())
    if isinstance(obj, Sequence) and not isinstance(obj, (str, bytes)):
        return any(contains_box(i) for i in obj)
    return False


__all__ = [
    "get_static",
    "split_list",
    "is_tidy_box",
]
