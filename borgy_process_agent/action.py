import asyncio
from typing import Optional, List, Callable
from borgy_process_agent.enums import ActionType


class Action:

    def __init__(self,
                 priority: int,
                 type: ActionType,
                 future: asyncio.Future = None,
                 data: Optional[List] = None):
        if not isinstance(type, ActionType):
            type = ActionType(type)
        self.type: ActionType = type
        self.future: asyncio.Future = future if isinstance(
            future, asyncio.Future) else asyncio.get_event_loop().create_future()
        self.data: Optional[List] = data
        self.prio = priority

    def __repr__(self) -> str:
        data = len(self.data) if self.data is not None else 'None'
        return f"<Action: type={self.type.value}, data={data}>"

    def done(self):
        if self.failed():
            raise self.future.exception()
        self.future.set_result(self.data)

    def on_done(self, callback: Callable):
        self.future.add_done_callback(callback)

    def fail(self, exc: Exception = None):
        self.future.set_exception(exc)

    def failed(self) -> bool:
        if self.future.done():
            return True if self.future.exception() else False
        return False

    def cancel(self, exc: Exception = None) -> bool:
        if exc is not None:
            self.fail(exc)
        return self.future.cancel()

    def __lt__(self, other: 'Action') -> bool:
        return self.prio < other.prio

    def __await__(self) -> asyncio.Future:
        # Makes the Action class usable with native
        # 'await' keyword, including exception handling.
        return (yield from self.future)
