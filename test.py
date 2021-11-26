from CameraHandler import CameraHandler
import time

if __name__ == "__main__":
    h = CameraHandler("/home/cqj/001", True)
    h.init()
    h.take_photos(10)
    time.sleep(2)
    h.save_auto_by_queue()
    time.sleep(30)
    h.disconnect()
