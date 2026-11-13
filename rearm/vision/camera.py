import cv2


class OpenCVCamera:
    """Explicit camera adapter; only opened when constructed by an application."""
    def __init__(self, device: int | str):
        self.capture = cv2.VideoCapture(device)
        if not self.capture.isOpened():
            self.capture.release()
            raise OSError("camera could not be opened")

    def read(self):
        success, frame = self.capture.read()
        if not success:
            raise OSError("camera frame unavailable")
        return frame

    def close(self):
        self.capture.release()
