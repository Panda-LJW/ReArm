class ServoDriver:
    """Hardware protocol is intentionally unspecified in v0; never send guessed packets."""
    def __init__(self, port: str, baudrate: int):
        self.port, self.baudrate = port, baudrate

    def move_to(self, q, speed):
        raise NotImplementedError("TODO: implement confirmed servo protocol, acknowledgements and limits")

    def read_state(self):
        raise NotImplementedError("TODO: read angles, approach direction, load, temperature and voltage")
