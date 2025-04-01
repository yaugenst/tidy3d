# type information for autograd

import copy
from typing import Annotated, Literal, Optional, TypeAlias, Union

import autograd.numpy as anp
from autograd.builtins import dict as dict_ag
from autograd.extend import Box, defvjp, primitive
from autograd.tracer import getval
from pydantic import BeforeValidator, PlainSerializer, PositiveFloat, TypeAdapter

from tidy3d.components.type_util import _add_schema

from ..types import (
    ArrayFloat2D,
    Complex,
    Coordinate,
    PolesAndResidues,
    Size,
    Size1D,
    _auto_serializer,
)
from .utils import contains_box

# add schema to the Box
_add_schema(Box, title="AutogradBox", field_type_str="autograd.tracer.Box")

# make sure Boxes in tidy3d properly define VJPs for copy operations, for computational graph
_copy = primitive(copy.copy)
_deepcopy = primitive(copy.deepcopy)

defvjp(_copy, lambda ans, x: lambda g: _copy(g))
defvjp(_deepcopy, lambda ans, x, memo: lambda g: _deepcopy(g, memo))

Box.__copy__ = lambda v: _copy(v)
Box.__deepcopy__ = lambda v, memo: _deepcopy(v, memo)
Box.__str__ = lambda self: f"{self._value} <{type(self).__name__}>"
Box.__repr__ = Box.__str__


def traced_alias(base_alias, *, name: Optional[str] = None) -> TypeAlias:
    base_adapter = TypeAdapter(base_alias, config=dict(arbitrary_types_allowed=True))

    def _validate_box_or_container(v):
        # case 1: v itself is a tracer
        # in this case we just validate but leave the tracer untouched
        if isinstance(v, Box):
            base_adapter.validate_python(getval(v))
            return v

        # case 2: v is a plain container that contains at least one tracer
        # in this case we try to coerce into ArrayBox for efficiency
        if contains_box(v):
            dense = anp.array(v)
            base_adapter.validate_python(getval(dense))
            return dense

        raise ValueError("expected autograd tracer")

    return Annotated[
        Union[
            base_alias,
            Annotated[
                Box,
                BeforeValidator(_validate_box_or_container),
                PlainSerializer(lambda a, _: _auto_serializer(getval(a), _), when_used="json"),
            ],
            Annotated[object, BeforeValidator(_validate_box_or_container)],
        ],
        {} if name is None else {"title": name},
    ]


# Types for floats, or collections of floats that can also be autograd tracers
TracedFloat = traced_alias(float)
TracedPositiveFloat = traced_alias(PositiveFloat)
TracedSize1D = traced_alias(Size1D)
TracedSize = traced_alias(Size)
TracedCoordinate = traced_alias(Coordinate)
TracedArrayFloat2D = traced_alias(ArrayFloat2D)

# poles
TracedComplex = traced_alias(Complex)
TracedPolesAndResidues = traced_alias(PolesAndResidues)

# The data type that we pass in and out of the web.run() @autograd.primitive
PathType = tuple[Union[int, str], ...]
AutogradFieldMap = dict_ag[PathType, Box]

InterpolationType = Literal["nearest", "linear"]

__all__ = [
    "TracedFloat",
    "TracedSize1D",
    "TracedSize",
    "TracedCoordinate",
    "TracedArrayFloat2D",
    "AutogradFieldMap",
]
