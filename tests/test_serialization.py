from __future__ import annotations

import dataclasses
import datetime as dt
import math
import pathlib
from types import EllipsisType
from typing import Any

import pytest
from pydantic import BaseModel

from srlz import Serialization, SimpleType

STRING = "Hello, world!"
BYTES = b"Hello, world!"
BASE64 = "SGVsbG8sIHdvcmxkIQ=="
NOW = dt.datetime.now(dt.UTC)
DATA = {
    "_": None,
    "b": True,
    "n": 1,
    "f": 0.5,
    "s": "text",
    "xs": [1, 2, 3],
    "d": {"x": 1, "y": 2},
    "dt": NOW,
    "bin": BYTES,
}


class A1:

    def __init__(self, x: int) -> None:
        self.x = x
        self.y = 2

    def __eq__(self, other: object) -> bool:
        return isinstance(other, A1) and self.x == other.x and self.y == other.y

    @classmethod
    def from_dict(cls, data: dict[str, int]) -> A1:
        return cls(data["x"])

    def to_dict(self) -> dict[str, int]:
        return {"x": self.x}


class A2:

    __slots__ = "x", "y"

    def __init__(self, x: int) -> None:
        self.x = x
        self.y = 2

    def __eq__(self, other: object) -> bool:
        return isinstance(other, A2) and self.x == other.x and self.y == other.y


class A3:

    __slots__ = "x", "y", "__dict__"

    def __init__(self, x: int) -> None:
        self.x = x
        self.y = 2
        self.z = [3, 4, 5]

    def __eq__(self, other: object) -> bool:
        return isinstance(other, A3) and self.x == other.x and self.y == other.y and self.z == other.z


class A4:

    def __init__(self, path: str | pathlib.Path) -> None:
        self.file = open(path)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, A4) and self.file.name == other.file.name

    def __getstate__(self) -> str:
        return self.file.name

    def __setstate__(self, state: str) -> None:
        self.file = open(state)


class A5:

    def __init__(self, path: str | pathlib.Path) -> None:
        self.file = open(path)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, A5) and self.file.name == other.file.name

    def __getnewargs__(self) -> tuple[str]:
        return (self.file.name,)


class A6:

    def __init__(self, path: str | pathlib.Path, *, mode: str) -> None:
        self.file = open(path, mode)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, A6) and self.file.name == other.file.name

    def __getnewargs_ex__(self) -> tuple[tuple[str], dict[str, str]]:
        return ((self.file.name,), {"mode": self.file.mode})


class A7:

    def __init__(self, x: int):
        self.x = x

    def __eq__(self, other: object) -> bool:
        return isinstance(other, type(self)) and self.__dict__ == other.__dict__


class A7_1(A7):

    def __init__(self, x: int, y: int) -> None:
        super().__init__(x)
        self.y = y


class A7_2(A7):

    def __init__(self, x: int, s: int, xs: list[int]) -> None:
        super().__init__(x)
        self.s = s
        self.xs = xs


@dataclasses.dataclass
class A8:
    x: int
    y: int


@dataclasses.dataclass
class A9:
    s: str
    xs: list[int]


class A10(BaseModel):
    x: int
    y: int


class A11(BaseModel):
    s: str
    xs: list[int]


@pytest.fixture
def s() -> Serialization:
    return Serialization()


@pytest.fixture
def f(tmp_path: pathlib.Path) -> pathlib.Path:
    path = tmp_path / "file.txt"
    path.write_text(STRING)
    return path


def test_none(s: Serialization) -> None:
    assert s.serialize(None) is None
    assert s.deserialize(None) is None


def test_boolean(s: Serialization) -> None:
    assert s.serialize(True) is True
    assert s.deserialize(True) is True
    assert s.serialize(False) is False
    assert s.deserialize(False) is False


def test_integer(s: Serialization) -> None:
    assert s.serialize(1) == 1
    assert s.deserialize(1) == 1
    assert s.serialize(0) == 0
    assert s.deserialize(0) == 0
    assert s.serialize(-1) == -1
    assert s.deserialize(-1) == -1


def test_float(s: Serialization) -> None:
    assert s.serialize(0.5) == 0.5
    assert s.deserialize(0.5) == 0.5
    assert s.serialize(1e10) == 1e10
    assert s.deserialize(1e10) == 1e10
    assert s.serialize(1e-10) == 1e-10
    assert s.deserialize(1e-10) == 1e-10
    for symbol in ["inf", "-inf"]:
        assert s.serialize(float(symbol)) == float(symbol)
        assert s.deserialize(float(symbol)) == float(symbol)
    assert math.isnan(s.serialize(float("nan")))
    assert math.isnan(s.deserialize(float("nan")))


def test_string(s: Serialization) -> None:
    assert s.serialize("") == ""
    assert s.deserialize("") == ""
    assert s.serialize(STRING) == STRING
    assert s.deserialize(STRING) == STRING


def test_list(s: Serialization) -> None:
    assert s.serialize([]) == []
    assert s.deserialize([]) == []
    assert s.serialize([1, 2, 3]) == [1, 2, 3]
    assert s.deserialize([1, 2, 3]) == [1, 2, 3]


def test_tuple(s: Serialization) -> None:
    assert s.serialize(()) == []
    assert s.serialize((1, 2, 3)) == [1, 2, 3]


def test_set(s: Serialization) -> None:
    assert s.serialize(set()) == []
    assert s.serialize({1, 2, 3}) == [1, 2, 3]


def test_dict(s: Serialization) -> None:
    assert s.serialize({}) == {}
    assert s.deserialize({}) == {}
    assert s.serialize({"x": 1, "y": 2}) == {"x": 1, "y": 2}
    assert s.deserialize({"x": 1, "y": 2}) == {"x": 1, "y": 2}


def test_datetime_utc(s: Serialization) -> None:
    now = dt.datetime.now(dt.UTC)
    assert s.serialize(now) == {"datetime": now.isoformat()}


def test_datetime_local(s: Serialization) -> None:
    now = dt.datetime.now().astimezone()
    assert s.serialize(now) == {"datetime": now.isoformat()}
    assert s.deserialize({"datetime": now.isoformat()}) == now


def test_datetime_naive(s: Serialization) -> None:
    now = dt.datetime.now()
    assert s.serialize(now) == {"datetime": now.astimezone().isoformat()}
    assert s.deserialize({"datetime": now.astimezone().isoformat()}) == now.astimezone()


def test_datetime_value(s: Serialization) -> None:
    now = dt.datetime.now(dt.UTC)
    assert s.serialize_value(now) == ("datetime", now.isoformat())
    assert s.deserialize_value("datetime", now.isoformat()) == now


def test_bytes(s: Serialization) -> None:
    assert s.serialize(b"") == {"bytes": ""}
    assert s.deserialize({"bytes": ""}) == b""
    assert s.serialize(BYTES) == {"bytes": BASE64}
    assert s.deserialize({"bytes": BASE64}) == BYTES


def test_bytes_value(s: Serialization) -> None:
    assert s.serialize_value(BYTES) == ("bytes", BASE64)
    assert s.deserialize_value("bytes", BASE64) == BYTES


def test_nested(s: Serialization) -> None:
    data = s.serialize(DATA)
    assert data == {
        **DATA,
        "dt": {"datetime": NOW.isoformat()},
        "bin": {"bytes": BASE64},
    }
    assert s.deserialize(data) == DATA


def test_invalid(s: Serialization) -> None:
    error = f"""
unable to serialize data \\({...!r}\\): only none, booleans, integers, floats, strings and serializable values are \
allowed, as well as lists, tuples, sets or dictionaries thereof \\(available serializers are .*\\) \
""".strip()
    with pytest.raises(ValueError, match=error):
        s.serialize(...)


def test_no_deserializer(s: Serialization) -> None:
    assert s.deserialize({"x": {"custom": "..."}}) == {"x": {"custom": "..."}}


def test_custom_by_type(s: Serialization) -> None:
    add_custom_serialization(s, by_type=True)
    data = {"custom": "..."}
    assert s.serialize(...) == data
    assert s.deserialize(data) is ...


def test_custom_by_callable(s: Serialization) -> None:
    add_custom_serialization(s, by_type=False)
    data = {"custom": "..."}
    assert s.serialize(...) == data
    assert s.deserialize(data) is ...


def test_custom_value(s: Serialization) -> None:
    assert s.serialize_value(...) == (None, None)
    with pytest.raises(ValueError, match=r"no custom deserializer \(available deserializers are .*\)"):
        s.deserialize_value("custom", "...")
    add_custom_serialization(s)
    assert s.serialize_value(...) == ("custom", "...")
    assert s.deserialize_value("custom", "...") is ...


def test_class(s: Serialization) -> None:
    s.add_class(A1)
    a = A1(1)
    data = {"A1": {"x": 1, "y": 2}}
    assert s.serialize(a) == data
    assert s.deserialize(data) == a


def test_class_serializers(s: Serialization) -> None:
    def serialize_A1(data: A1) -> dict[str, int]:
        return data.to_dict()

    def deserialize_A1(cls: type[A1], data: dict[str, int]) -> A1:
        return A1.from_dict(data)

    s.add_class(A1, serialize_A1, deserialize_A1)
    a = A1(1)
    data = {"A1": {"x": 1}}
    assert s.serialize(a) == data
    assert s.deserialize(data) == a


def test_class_value(s: Serialization) -> None:
    a = A1(1)
    assert s.serialize_value(a) == (None, None)
    with pytest.raises(ValueError, match=r"no A1 deserializer \(available deserializers are .*\)"):
        s.deserialize_value("A1", {"x": 1, "y": 2})
    s.add_class(A1)
    assert s.serialize_value(a) == ("A1", {"x": 1, "y": 2})
    assert s.deserialize_value("A1", {"x": 1, "y": 2}) == a


def test_slots(s: Serialization) -> None:
    s.add_class(A2)
    a = A2(1)
    data = {"A2": {"x": 1, "y": 2}}
    assert s.serialize(a) == data
    assert s.deserialize(data) == a


def test_slots_and_dict(s: Serialization) -> None:
    s.add_class(A3)
    a = A3(1)
    data = {"A3": {"x": 1, "y": 2, "z": [3, 4, 5]}}
    assert s.serialize(a) == data
    assert s.deserialize(data) == a


def test_state(s: Serialization, f: pathlib.Path) -> None:
    s.add_class(A4)
    a = A4(f)
    assert a.file.read() == STRING
    data = {"A4": {"state": str(f)}}
    assert s.serialize(a) == data
    b = s.deserialize(data)
    assert a == b
    assert b.file.read() == STRING


def test_args(s: Serialization, f: pathlib.Path) -> None:
    s.add_class(A5)
    a = A5(f)
    assert a.file.read() == STRING
    data = {"A5": {"args": [str(f)]}}
    assert s.serialize(a) == data
    b: A5 = s.deserialize(data)
    assert a == b
    assert b.file.read() == STRING


def test_args_kwargs(s: Serialization, f: pathlib.Path) -> None:
    s.add_class(A6)
    a = A6(f, mode="rb")
    assert a.file.read() == BYTES
    data = {"A6": {"args": [[str(f)], {"mode": "rb"}]}}
    assert s.serialize(a) == data
    b: A6 = s.deserialize(data)
    assert a == b
    assert b.file.read() == BYTES


def test_baseclass(s: Serialization) -> None:
    s.add_baseclass(A7)
    a = A7_1(1, 2)
    data = {"A7": {"class": "A7_1", "x": 1, "y": 2}}
    assert s.serialize(a) == data
    assert s.deserialize(data) == a
    b = A7_2(1, 2, [3, 4, 5])
    data = {"A7": {"class": "A7_2", "x": 1, "s": 2, "xs": [3, 4, 5]}}
    assert s.serialize(b) == data
    assert s.deserialize(data) == b


def test_dynamic_subclass(s: Serialization) -> None:
    s.add_baseclass(A7)

    class A7_3(A7):

        def __init__(self, x: int, b: bool, d: dict[str, int]) -> None:
            super().__init__(x)
            self.b = b
            self.d = d

    a = A7_3(1, True, {"x": 1, "y": 2})
    data = {"A7": {"class": "A7_3", "x": 1, "b": True, "d": {"x": 1, "y": 2}}}
    assert s.serialize(a) == data
    assert s.deserialize(data) == a


def test_invalid_subclass(s: Serialization) -> None:
    s.add_baseclass(A7)
    with pytest.raises(ValueError, match=r"A7 has no subclass A7_4"):
        s.deserialize({"A7": {"class": "A7_4", "x": 1}})


def test_dataclass(s: Serialization) -> None:
    a = A8(1, 2)
    data = {"dataclass": {"class": "A8", "x": 1, "y": 2}}
    assert s.serialize(a) == data
    assert s.deserialize(data) == a
    b = A9(STRING, [1, 2, 3])
    data = {"dataclass": {"class": "A9", "s": STRING, "xs": [1, 2, 3]}}
    assert s.serialize(b) == data
    assert s.deserialize(data) == b


def test_invalid_dataclass(s: Serialization) -> None:
    with pytest.raises(ValueError, match=r"no B data class \(available data classes are .*\)"):
        s.deserialize({"dataclass": {"class": "B", "x": 1, "y": 2}})


def test_pydantic(s: Serialization) -> None:
    def serialize_pydantic(data: BaseModel) -> SimpleType:
        return data.model_dump()

    def deserialize_pydantic(cls: type[BaseModel], data: SimpleType) -> BaseModel:
        return cls(**data)

    s.add_baseclass(BaseModel, serialize_pydantic, deserialize_pydantic)
    a = A10(x=1, y=2)
    data = {"BaseModel": {"class": "A10", "x": 1, "y": 2}}
    assert s.serialize(a) == data
    assert s.deserialize(data) == a
    b = A11(s=STRING, xs=[1, 2, 3])
    data = {"BaseModel": {"class": "A11", "s": STRING, "xs": [1, 2, 3]}}
    assert s.serialize(b) == data
    assert s.deserialize(data) == b


def test_add_remove(s: Serialization) -> None:
    s.add("custom", EllipsisType, serialize_custom, deserialize_custom)
    assert s.serialize(...) == {"custom": "..."}
    assert s.deserialize({"custom": "..."}) is ...
    s.remove("custom")
    with pytest.raises(ValueError):
        s.serialize(...)
    with pytest.raises(ValueError, match=r"no custom serialization \(available serializations are .*\)"):
        s.remove("custom")


def test_imbalance(s: Serialization) -> None:
    s.serializer("custom", EllipsisType)(serialize_custom)
    with pytest.raises(RuntimeError, match=r"no deserializers for custom"):
        s.deserialize(1)
    s.remove("custom")
    s.deserializer("custom")(deserialize_custom)
    with pytest.raises(RuntimeError, match=r"no serializers for custom"):
        s.serialize(1)


def add_custom_serialization(s: Serialization, by_type: bool = False) -> None:
    if by_type:
        predicate = EllipsisType
    else:
        predicate = is_ellipsis
    s.serializer("custom", predicate)(serialize_custom)
    s.deserializer("custom")(deserialize_custom)


def is_ellipsis(data: Any) -> bool:
    return str(data) == "Ellipsis"


def serialize_custom(data: EllipsisType) -> SimpleType:
    return "..."


def deserialize_custom(data: SimpleType) -> EllipsisType:
    return ...
