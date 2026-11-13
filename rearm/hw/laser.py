class LaserDriver:
    def __init__(self, channel: str):
        self.channel = channel

    def set_enabled(self, on: bool):
        raise NotImplementedError("TODO: laser transport and fail-safe shutdown")
