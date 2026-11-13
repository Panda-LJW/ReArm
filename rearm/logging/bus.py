from threading import RLock
from collections.abc import Callable
from rearm.types import Event


class LocalEventBus:
    def __init__(self):
        self._subscribers: list[Callable[[Event], None]] = []
        self._lock = RLock()

    def subscribe(self, callback: Callable[[Event], None]) -> Callable[[], None]:
        with self._lock:
            self._subscribers.append(callback)
        def unsubscribe():
            with self._lock:
                if callback in self._subscribers:
                    self._subscribers.remove(callback)
        return unsubscribe

    def publish(self, event: Event) -> None:
        with self._lock:
            subscribers = tuple(self._subscribers)
        for callback in subscribers:
            callback(event)
