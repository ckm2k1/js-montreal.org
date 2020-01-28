import os
import re
import json
import uuid
import importlib.util
from datetime import datetime, timedelta, timezone
from collections import ChainMap, UserDict
from typing import Any, Union, Callable, Generator, Tuple, List, Iterator
from types import ModuleType

SENTINEL = object()


def taketimes(iterable: List, times: int) -> Generator[Tuple[int, Any], None, None]:
    for i, v in enumerate(iterable):
        if not times:
            break
        yield i, v
        times -= 1


# https://docs.python.org/3.7/library/collections.html#collections.ChainMap
class DeepChainMap(ChainMap):
    """Variant of ChainMap that allows direct updates to inner scopes"""

    def __setitem__(self, key, value):
        for mapping in self.maps:
            if key in mapping:
                mapping[key] = value
                return
        self.maps[0][key] = value

    def __delitem__(self, key):
        for mapping in self.maps:
            if key in mapping:
                del mapping[key]
                return
        raise KeyError(key)

    def pop(self, key, default=SENTINEL):
        for mapping in self.maps:
            if key in mapping:
                return mapping.pop(key)
        if default is not SENTINEL:
            return default
        raise KeyError(key)


def _identity(x: Any) -> Any:
    """Standard identity function, useful as default
    predicate for functional iterators"""
    return x


class Env:
    """Wrapper class for os.getenv that allows easy conversion
    of string values coming from env variables into python native
    types.
    """

    def _get_envvar(self, key: str, default: Any, parser: Callable,
                    hardfail: bool) -> Union[None, str]:
        if key not in os.environ:
            return default if default is not SENTINEL else None
        try:
            return parser(os.getenv(key))
        except Exception:
            if hardfail:
                raise
            return None

    def get_bool(self, key: str, default: Any = SENTINEL, hardfail=True) -> bool:
        return self._get_envvar(key, default, parse_bool, hardfail)

    def get_float(self, key: str, default: Any = SENTINEL, hardfail=True) -> float:
        return self._get_envvar(key, default, float, hardfail)

    def get_int(self, key: str, default: Any = SENTINEL, hardfail=True) -> int:
        return self._get_envvar(key, default, int, hardfail)

    def get(self, key: str, default: Any = SENTINEL, hardfail=True) -> str:
        return self._get_envvar(key, default, _identity, hardfail)


def parse_bool(val: str) -> bool:
    """Parse booleans out of strings. Commonly useful for
    extracting values out of environment variables.
    """
    return bool(re.match(r'^(true|1|yes|on)$', val, re.IGNORECASE))


def now() -> datetime:
    """Returns current datetime in UTC."""
    return datetime.utcnow()


def fmt_datetime(dt: datetime) -> str:
    """Returns a formatted datetime with truncated millis."""
    return dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] if dt else ''


class ObjDict(UserDict):
    """Subclass of dictionary that supports all regular
    dict operations get/set/exists/del using attribute
    access.

    Note the conversion of KeyError to AttributeError,
    this allows hasattr() calls to work as if they were
    `key in objdict` expressions.
    """

    def __getattr__(self, key):
        # Make sure builtin attributes
        # are returned correctly.
        try:
            return object.__getattribute__(self, key)
        except AttributeError:
            pass

        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, val):
        # Prevent setting new instance attributes
        # except the 'data' attr which we need for
        # the UserDict class to work correctly.
        if key == 'data' or (key.startswith('__') and key.endswith('__')):
            object.__setattr__(self, key, val)
        else:
            self[key] = val

    def __delattr__(self, key):
        try:
            object.__delattr__(self, key)
        except AttributeError:
            pass

        try:
            del self[key]
        except KeyError:
            raise AttributeError(key)


def td_format(td_object: timedelta) -> str:
    """Returns the timedelta object formatted as human readable string
    Ex: 1 day, 15 hours, 18 minutes"""
    seconds = int(td_object.total_seconds())
    periods = [
        ('year', 60 * 60 * 24 * 365),
        ('month', 60 * 60 * 24 * 30),
        ('day', 60 * 60 * 24),
        ('hour', 60 * 60),
        ('minute', 60),
        ('second', 1),
    ]  # noqa

    strings = []
    for period_name, period_seconds in periods:
        if seconds > period_seconds:
            period_value, seconds = divmod(seconds, period_seconds)
            has_s = 's' if period_value > 1 else ''
            strings.append("%s %s%s" % (period_value, period_name, has_s))

    return ", ".join(strings)


class Indexer(Iterator):
    """Class implementing an interator of a monotonically
    rising sequence of integers.
    Example:
        i = Indexer()

        # supports all calling methods below:
        i() -> 0
        next(i) -> 1
        i.next() -> 2
        i.last -> 1
        i.cur -> 2
    """

    def __init__(self, initial: int = 0):
        self._initial = initial
        self._idx: int = initial
        self._last: int = initial
        self._cap = None

    def reset(self, initial=None):
        initial = initial if initial is not None else self._initial
        self._cap = None
        self._last = initial
        self._idx = initial
        self._initial = initial

    def cap(self, num) -> 'Indexer':
        """Returns the current instance of Indexer
        capped to a number of iterations starting from the
        current index. This can be used in a for loop to
        run through the next n integers.
        Ex:
            i = Indexer()
            i() -> 0
            i() -> 1
            for n in i.cap(10):
                print(n)
            2 3 4 5 6 7 8 9 10 11
        """
        self._cap = num
        return iter(self)

    def __iter__(self) -> 'Indexer':
        return self

    def __next__(self) -> int:
        if self._cap is not None:
            if self._cap == 0:
                self._cap = None
                raise StopIteration
            else:
                self._cap -= 1
        self._last = self._idx
        self._idx += 1
        return self._last

    def __call__(self) -> int:
        return self.__next__()

    def next(self) -> int:
        return self.__next__()

    @property
    def cur(self) -> int:
        return self._idx

    @property
    def last(self) -> int:
        return self._last


def load_module_from_path(path: str) -> ModuleType:
    """Returns a live module object loaded
    from the provided path argument.
    """
    assert path, 'Invalid module path.'
    spec = importlib.util.spec_from_file_location('usercode', location=path)
    usercode = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(usercode)
    return usercode


class ComplexEncoder(json.JSONEncoder):
    """JSON encoder that supports bytes serialization. Bytes are
    coerced to a UTF-8 string, replacing any sequences that fail
    decoding."""

    def default(self, obj):
        if isinstance(obj, bytes):
            return obj.decode(encoding='utf8', errors='replace')
        if isinstance(obj, uuid.UUID):
            return str(obj)
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)


mem_size_units = {
    '': 1,
    'E': 1000 * 1000 * 1000 * 1000 * 1000 * 1000,
    'P': 1000 * 1000 * 1000 * 1000 * 1000,
    'T': 1000 * 1000 * 1000 * 1000,
    'G': 1000 * 1000 * 1000,
    'M': 1000 * 1000,
    'K': 1000,
    'Ei': 1024 * 1024 * 1024 * 1024 * 1024 * 1024,
    'Pi': 1024 * 1024 * 1024 * 1024 * 1024,
    'Ti': 1024 * 1024 * 1024 * 1024,
    'Gi': 1024 * 1024 * 1024,
    'Mi': 1024 * 1024,
    'Ki': 1024
}

cpu_size_units = {'': 1, 'm': 0.001}


def get_now():
    """Facilitates testing."""
    dt = datetime.utcnow()
    return dt.replace(tzinfo=timezone.utc)


def get_now_isoformat():
    """Facilitates testing."""
    return get_now().isoformat()


def memory_str_to_nbytes(mem_size_str):
    m = re.search(r"^(\d+)(.*)$", str(mem_size_str))
    if not m:
        raise ValueError("No match for memory allocatable")

    if not m.group(2) in mem_size_units:
        raise ValueError("Unexpected memory size unit " + m.group(2))

    mem_size_bytes = int(m.group(1)) * mem_size_units[m.group(2)]
    return mem_size_bytes


def cpu_str_to_ncpu(cpu_str):
    m = re.search(r"^([\d.]+)(.*)$", str(cpu_str))
    if not m:
        raise ValueError("No match for cpu allocatable")

    if not m.group(2) in cpu_size_units:
        raise ValueError("Unexpected cpu size unit " + m.group(2))

    cpu_size = float(m.group(1)) * cpu_size_units[m.group(2)]
    return cpu_size
