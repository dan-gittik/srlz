import base64
import dataclasses
import datetime as dt
import functools
from typing import Any, Callable, cast, overload

from .utils import concat

type SimpleType = None | bool | int | float | str | list[SimpleType] | dict[str, SimpleType]
type Predicate = Callable[[Any], bool] | Callable[[Any], str | None]
type Serializer = Callable[[Any], SimpleType]
type Deserializer = Callable[[SimpleType], Any]
type ClassSerializer[T] = Callable[[T], dict[str, SimpleType]]
type ClassDeserializer[T] = Callable[[type[T], dict[str, SimpleType]], T]
type Decorator[C: Callable] = Callable[[C], C]

CLASS = "class"
STATE = "state"
ARGS = "args"
SUBCLASSES: dict[type, dict[str, type]] = {}

# Dataclasses don't have a common base class that can be crawled for subclasses, so we patch the dataclass decorator so
# as to register its results. This means this module has to be imported before any dataclasses are defined, otherwise it
# won't be able to find them.
DATACLASSES: dict[str, type] = {}


dataclass_original = dataclasses.dataclass


@overload
def dataclass_hook(cls: type, /) -> type: ...


@overload
def dataclass_hook(cls: None, /, **kwargs: Any) -> Callable[[type], type]: ...


@functools.wraps(dataclasses.dataclass)
def dataclass_hook(cls: type | None = None, /, **kwargs: Any) -> Callable[[type], type] | type:
    if cls is None:
        return lambda cls: dataclass_hook(cls, **kwargs)
    dataclass: type = dataclass_original(**kwargs)(cls)
    DATACLASSES[dataclass.__name__] = dataclass
    return dataclass


dataclasses.dataclass = dataclass_hook  # type: ignore


class Serialization:

    def __init__(
        self,
        serialize_datetime: bool = True,
        serialize_bytes: bool = True,
        serialize_dataclass: bool = True,
    ) -> None:
        self.serializers: dict[str, tuple[Predicate, Serializer]] = {}
        self.deserializers: dict[str, Deserializer] = {}
        if serialize_datetime:
            self.add("datetime", dt.datetime, self._serialize_datetime, self._deserialize_datetime)
        if serialize_bytes:
            self.add("bytes", bytes, self._serialize_bytes, self._deserialize_bytes)
        if serialize_dataclass:
            self.add("dataclass", self._detect_dataclass, self._serialize_dataclass, self._deserialize_dataclass)

    def serializer(self, name: str, predicate: type | Predicate) -> Decorator[Serializer]:
        if isinstance(predicate, type):
            predicate = self._predicate_for_type(predicate)

        def decorator(serializer: Serializer) -> Serializer:
            self.serializers[name] = predicate, serializer
            return serializer

        return decorator

    def deserializer(self, name: str) -> Decorator[Deserializer]:
        def decorator(deserializer: Deserializer) -> Deserializer:
            self.deserializers[name] = deserializer
            return deserializer

        return decorator

    def add(
        self,
        name: str,
        predicate: type | Predicate,
        serializer: Serializer,
        deserializer: Deserializer,
    ) -> None:
        self.serializer(name, predicate)(serializer)
        self.deserializer(name)(deserializer)

    def remove(self, name: str) -> None:
        available = {*self.serializers, *self.deserializers}
        if name not in available:
            raise ValueError(f"no {name} serialization (available serializations are {concat(available)})")
        self.serializers.pop(name, None)
        self.deserializers.pop(name, None)

    def add_class[T](
        self,
        cls: type[T],
        class_serializer: ClassSerializer[T] | None = None,
        class_deserializer: ClassDeserializer[T] | None = None,
    ) -> None:
        serializer = functools.partial(self._serialize_class, class_serializer=class_serializer)
        deserializer = functools.partial(self._deserialize_class, cls, class_deserializer=class_deserializer)
        self.add(cls.__name__, cls, serializer, deserializer)

    def add_baseclass[T](
        self,
        cls: type[T],
        class_serializer: ClassSerializer[T] | None = None,
        class_deserializer: ClassDeserializer[T] | None = None,
    ) -> None:
        self.add(
            cls.__name__,
            self._predicate_for_type(cls),
            self._subclass_serializer(class_serializer),
            self._subclass_deserializer(cls, class_deserializer),
        )

    @overload
    def serialize[T: SimpleType](self, data: T, field: str | None = None) -> T: ...

    @overload
    def serialize(self, data: Any, field: str | None = None) -> SimpleType: ...

    def serialize(self, data: Any, field: str | None = None) -> SimpleType:
        self._check_balance()
        prefix = f"{field}." if field else ""
        if data is None or isinstance(data, bool | int | float | str):
            return data
        if isinstance(data, list | tuple | set):
            return [self.serialize(item, f"{prefix}{n}") for n, item in enumerate(data)]
        if isinstance(data, dict):
            return {key: self.serialize(value, f"{prefix}{key}") for key, value in data.items()}
        name, serialized = self.serialize_value(data)
        if not name:
            name = field if field else "data"
            raise ValueError(
                f"unable to serialize {name} ({data!r}): only none, booleans, integers, floats, strings and "
                f"serializable values are allowed, as well as lists, tuples, sets or dictionaries thereof "
                f"(available serializers are {concat(self.serializers)})"
            )
        return {name: serialized}

    def deserialize(self, data: SimpleType) -> Any:
        self._check_balance()
        if isinstance(data, dict) and len(data) == 1:
            key, value = data.popitem()
            if key in self.deserializers:
                return self.deserialize_value(key, value)
            return {key: self.deserialize(value)}
        if isinstance(data, list):
            return [self.deserialize(item) for item in data]
        if isinstance(data, dict):
            return {key: self.deserialize(value) for key, value in data.items()}
        return data

    def serialize_value(self, data: Any) -> tuple[str | None, SimpleType]:
        self._check_balance()
        for name, (predicate, serializer) in self.serializers.items():
            if predicate(data):
                return name, serializer(data)
        return None, None

    def deserialize_value(self, name: str, data: SimpleType) -> Any:
        self._check_balance()
        if name not in self.deserializers:
            raise ValueError(f"no {name} deserializer (available deserializers are {concat(self.deserializers)})")
        return self.deserializers[name](data)

    def _predicate_for_type(self, data_type: type) -> Predicate:
        def predicate(data: Any) -> bool:
            return isinstance(data, data_type)

        return predicate

    def _check_balance(self) -> None:
        serializers = {*self.serializers} - {*self.deserializers}
        if serializers:
            raise RuntimeError(f"no deserializers for {concat(serializers)}")
        deserializers = {*self.deserializers} - {*self.serializers}
        if deserializers:
            raise RuntimeError(f"no serializers for {concat(deserializers)}")

    def _serialize_datetime(self, datetime: dt.datetime) -> str:
        if datetime.tzinfo is None:
            datetime = datetime.astimezone()
        return datetime.isoformat()

    def _deserialize_datetime(self, data: SimpleType) -> dt.datetime:
        data = cast(str, data)
        return dt.datetime.fromisoformat(data)

    def _serialize_bytes(self, data: bytes) -> str:
        return base64.b64encode(data).decode()

    def _deserialize_bytes(self, data: SimpleType) -> bytes:
        data = cast(str, data)
        return base64.b64decode(data)

    def _detect_dataclass(self, data: Any) -> str | None:
        if dataclasses.is_dataclass(data):
            return type(data).__name__
        return None

    def _serialize_dataclass(self, data: Any) -> SimpleType:
        return {CLASS: type(data).__name__, **self.serialize(dataclasses.asdict(data))}

    def _deserialize_dataclass(self, data: SimpleType) -> Any:
        data = cast(dict[str, SimpleType], data)
        class_name = cast(str, data.pop(CLASS))
        if class_name in DATACLASSES:
            return DATACLASSES[class_name](**data)
        raise ValueError(f"no {class_name} data class (available data classes are {concat(DATACLASSES)})")

    def _serialize_class[T](
        self,
        data: T,
        class_serializer: ClassSerializer[T] | None = None,
    ) -> dict[str, SimpleType]:
        if class_serializer is not None:
            return class_serializer(data)
        if hasattr(data, "__getnewargs_ex__"):
            return {ARGS: self.serialize(data.__getnewargs_ex__())}
        if hasattr(data, "__getnewargs__"):
            return {ARGS: self.serialize(data.__getnewargs__())}
        if hasattr(data, "__getstate__") and type(data).__getstate__ is not object.__getstate__:
            return {STATE: self.serialize(data.__getstate__())}
        if hasattr(data, "__slots__") and "__dict__" in data.__slots__:
            slots = {key: getattr(data, key) for key in data.__slots__ if key != "__dict__"}
            return self.serialize({**data.__dict__, **slots})
        if hasattr(data, "__slots__"):
            return self.serialize({key: getattr(data, key) for key in data.__slots__})
        return self.serialize(data.__dict__)

    def _deserialize_class[T](
        self,
        cls: type[T],
        data: SimpleType,
        class_deserializer: ClassDeserializer[T] | None = None,
    ) -> Any:
        data = cast(dict[str, SimpleType], data)
        if class_deserializer is not None:
            return class_deserializer(cls, data)
        if hasattr(cls, "__getnewargs_ex__"):
            args, kwargs = self.deserialize(data[ARGS])
            return cls(*args, **kwargs)
        if hasattr(cls, "__getnewargs__"):
            return cls(*self.deserialize(data[ARGS]))
        obj = object.__new__(cls)
        if hasattr(obj, "__setstate__"):
            obj.__setstate__(self.deserialize(data[STATE]))
        elif hasattr(obj, "__slots__") and "__dict__" in obj.__slots__:
            values = self.deserialize(data)
            for key in obj.__slots__:
                if key != "__dict__":
                    setattr(obj, key, values.pop(key))
            obj.__dict__.update(values)
        elif hasattr(obj, "__slots__"):
            for key, value in self.deserialize(data).items():
                setattr(obj, key, value)
        else:
            obj.__dict__.update(self.deserialize(data))
        return obj

    def _subclass_serializer[T](
        self,
        class_serializer: ClassSerializer[T] | None = None,
    ) -> Serializer:
        def serialize(data: T) -> SimpleType:
            return {CLASS: type(data).__name__, **self._serialize_class(data, class_serializer)}

        return serialize

    def _subclass_deserializer[T](
        self,
        baseclass: type[T],
        class_deserializer: ClassDeserializer[T] | None = None,
    ) -> Deserializer:
        def deserialize(data: SimpleType) -> T:
            data = cast(dict[str, SimpleType], data)
            class_name = cast(str, data.pop(CLASS))
            subclass = self._find_subclass(baseclass, class_name)
            return self._deserialize_class(subclass, data, class_deserializer)

        return deserialize

    def _find_subclass(self, cls: type, class_name: str) -> type:
        if cls not in SUBCLASSES or class_name not in SUBCLASSES[cls]:
            SUBCLASSES[cls] = {subclass.__name__: subclass for subclass in cls.__subclasses__()}
        if class_name in SUBCLASSES[cls]:
            return SUBCLASSES[cls][class_name]
        raise ValueError(f"{cls.__name__} has no subclass {class_name}")
