import json
from pathlib import Path
from threading import Lock
from rearm.types import Shot, jsonable


class JsonlShotLog:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = Lock()

    def append(self, shot: Shot) -> None:
        with self.lock, self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(jsonable(shot), ensure_ascii=False, allow_nan=False) + "\n")

    def read(self) -> list[Shot]:
        with self.lock:
            if not self.path.exists():
                return []
            return [Shot(**json.loads(line)) for line in self.path.read_text().splitlines() if line.strip()]
