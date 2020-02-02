import asyncio
from typing import Optional, List, Callable, Any
from borgy_process_agent.enums import ActionType


class Action(asyncio.Future):

    def __init__(self, priority: int, type: ActionType, data: Any = None, **kwargs):
        super().__init__(**kwargs)

        if not isinstance(type, ActionType):
            type = ActionType(type)
        self.type: ActionType = type
        self.data: Optional[List] = data
        self.prio = priority

    def __repr__(self) -> str:
        data = len(self.data) if self.data is not None else 'None'
        return f'<{self.__class__.__name__}: ' \
            f'type={self.type.value}, ' \
            f'data={data}, ' \
            f'fut={self._repr_info()}>'

    def complete(self) -> bool:
        self.set_result(self.data)

    def on_done(self, callback: Callable):
        self.add_done_callback(callback)

    def fail(self, exc: Exception):
        self.set_exception(exc)

    def failed(self) -> bool:
        if self.done():
            return True if self.exception() else False
        return False

    def __lt__(self, other: 'Action') -> bool:
        return self.prio < other.prio
