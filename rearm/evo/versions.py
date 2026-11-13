from __future__ import annotations
import json
import os
import re
import time
from pathlib import Path
from threading import RLock
from rearm.interfaces import EventBus, Recognizer
from rearm.types import Event, Params, Shot, Version, jsonable


class FileVersionStore:
    def __init__(self, path: str | Path, bus: EventBus, recognizer: Recognizer):
        self.path, self.bus, self.recognizer = Path(path), bus, recognizer
        self.path.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()

    def _atomic(self, path: Path, text: str) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)

    def _write(self, params, residual_id, accepted, meta, reasons):
        with self.lock:
            numbers = [int(p.stem[1:]) for p in self.path.glob("v[0-9]*.json")]
            version_id = f"v{max(numbers, default=0) + 1:04d}"
            version = Version(version_id, params, residual_id, accepted, meta, reasons)
            self._atomic(self.path / f"{version_id}.json", json.dumps(jsonable(version), ensure_ascii=False, indent=2, allow_nan=False))
            if accepted:
                self._atomic(self.path / "HEAD", version_id + "\n")
            return version_id

    def commit(self, params: Params, residual_id: str, meta: dict) -> str:
        result = self._write(params, residual_id, True, meta, ())
        self.bus.publish(Event("version_committed", time.time(), {"version_id": result, "meta": meta}))
        return result

    def reject(self, params: Params, meta: dict, reasons: tuple[str, ...]) -> str:
        result = self._write(params, self.head().residual_id, False, meta, reasons)
        self.bus.publish(Event("rejected", time.time(), {"version_id": result, "reasons": reasons}))
        return result

    def get(self, version_id: str) -> Version:
        if not re.fullmatch(r"v[0-9]+", version_id):
            raise ValueError("invalid version id")
        data = json.loads((self.path / f"{version_id}.json").read_text())
        data["params"], data["reasons"] = Params(**data["params"]), tuple(data["reasons"])
        return Version(**data)

    def head(self) -> Version:
        return self.get((self.path / "HEAD").read_text().strip())

    def list(self) -> list[Version]:
        return [self.get(p.stem) for p in sorted(self.path.glob("v[0-9]*.json"))]

    def checkout(self, version_id: str, component: str = "both") -> Version:
        with self.lock:
            target, old = self.get(version_id), self.head()
            if not target.accepted:
                raise ValueError("cannot activate a rejected version")
            if component == "both":
                self._atomic(self.path / "HEAD", target.id + "\n")
            elif component in ("geometry", "residual"):
                params = target.params if component == "geometry" else old.params
                residual_id = target.residual_id if component == "residual" else old.residual_id
                self.commit(params, residual_id, {"rollback_component": component, "source": target.id, "previous": old.id})
            else:
                raise ValueError("component must be both, geometry or residual")
            result = self.head()
        self.bus.publish(Event("rollback", time.time(), {"from": old.id, "to": result.id, "component": component}))
        return result

    def match(self, probe: list[Shot]) -> tuple[str, float] | None:
        return self.recognizer.match(probe, self.list())
