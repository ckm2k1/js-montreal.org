# -*- coding: utf-8 -*-
#
# __init__.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

import uuid
import copy
from enum import Enum
from typing import List, Dict, Callable, Optional, Union, NamedTuple, Any


class CallbackOrder(Enum):
    Begin = 0
    Any = 1
    End = 2

    def __lt__(self, other):
        return self.value < other.value


class Event(object):
    """Event
    """
    def to_dict(self):
        return vars(self)

    def __repr__(self):
        return repr(vars(self))

    def __contains__(self, key):
        return key in vars(self)

    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, value):
        return setattr(self, key, value)

    def __delitem__(self, key):
        delattr(self, key)


CallbackResult = Optional[Union[Event, Dict[str, Any]]]


Callback = NamedTuple('CallBack',  [
    ('name', str),
    ('callback', Callable[[Event], CallbackResult])
])


class Observable(object):
    """Observable
    """
    def __init__(self):
        """Contrustor

        :rtype: NoReturn
        """
        self._callbacks = []
        self._counter = 0

    def get_callbacks(self) -> List[Callback]:
        """Get all callbacks

        :rtype: List[Callback]
        """
        return [copy.deepcopy(c) for _, c in self._callbacks]

    def get_callbacks_by_name(self, name: str) -> List[Callback]:
        """Get all callback filtered by name

        :rtype: List[Callback]
        """
        callbacks = [c for _, c in self._callbacks if c['name'] == name]
        return copy.deepcopy(callbacks)

    def subscribe(self, callback: Callable, name: str = None, order: CallbackOrder = CallbackOrder.Any):
        """Subscribe to the observable and return the name

        :rtype: str
        """
        if not callable(callback):
            raise TypeError('Callback to have to be callable')
        if not name:
            name = str(uuid.uuid4())

        self._callbacks.append(((order, self._counter), {'name': name, 'callback': callback}))
        self._callbacks.sort()
        self._counter += 1

        return name

    def unsubscribe(self, callback: Callable = None, name: str = None):
        """Unsubscribe to the observable

        :rtype: List[Callback]
        """
        if not name and not callback:
            raise TypeError('name or callback can''t be null')

        removed = []
        for _, c in self._callbacks:
            if name and callback:
                if name == c['name'] and callback == c['callback']:
                    removed.append(c)
            elif name and name == c['name']:
                removed.append(c)
            elif callback and callback == c['callback']:
                removed.append(c)

        self._callbacks = [c for c in self._callbacks if c[1] not in removed]

        return removed

    def dispatch(self, **attrs) -> List[CallbackResult]:
        """Dispatch an event to the subscribers

        :rtype: List[CallbackResult]
        """
        results = []
        e = Event()
        e.source = self
        for k, v in attrs.items():
            setattr(e, k, v)
        for _, fn in self._callbacks:
            results.append(fn['callback'](e))
        return results

    def dispatch_breakable(self, **attrs) -> List[CallbackResult]:
        """Dispatch an event to the subscribers
        But inject the result of the previous subscriber in the next subscriber call.
        If a subscriber return None, the next subscribers will not be called

        :rtype: List[CallbackResult]
        """
        results = []
        e = Event()
        e.source = self
        for k, v in attrs.items():
            setattr(e, k, v)
        for _, fn in self._callbacks:
            if results:
                last = results[-1]
                if last and isinstance(last, dict):
                    for k, v in last.items():
                        setattr(e, k, v)
                elif last and isinstance(last, Event):
                    for k, v in vars(last).items():
                        setattr(e, k, v)
                elif last is None:
                    return results
            results.append(fn['callback'](e))
        return results
