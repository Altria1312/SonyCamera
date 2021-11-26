from loguru import logger
from queue import Queue
import gphoto2 as gp
import threading
import time
import os

def asnyc_thread(f):
    def warp(*args, **kwargs):
        t = threading.Thread(target=f, args=args, kwargs=kwargs)
        t.start()

    return warp


class CameraHandler():
    def __init__(self, save_path, use_queue=False):
        self.passwd = "sirope12348848"
        self.add_save_path(save_path)
        self.failed_list =[]
        self.asnyc_stop = False
        self.log_file = "./sonylog.log"
        if use_queue: self.filepath_queue = Queue(100)


    def add_save_path(self, save_path):
        try:
            if os.path.exists(save_path):
                self.save_path = save_path
                os.popen("sudo chmod 777 %s"%save_path, "w").write(self.passwd)
            else:
                print("save path not exist")
        except Exception as err:
            logger.exception(err)

    def connect(self, timeout=30):
        self.camera = gp.Camera()

        t0 = time.time()
        t1 = time.time()
        logger.info("Searching Camera...")
        while t1 - t0 < timeout:
            try:
                self.camera.init()
            except gp.GPhoto2Error as err:
                if err.code == gp.GP_ERROR_MODEL_NOT_FOUND:
                    t1 = time.time()
                    time.sleep(2)
                    continue

                raise Exception(err)
            logger.info("camera connected")
            break
        else:
            logger.error("timeout %ds, camera not found"%timeout)

    def disconnect(self):
        self.camera.exit()
        logger.info("camera disconnected")

    def take_photo(self):
        '''

        :return: CameraFilePath *
        '''
        return self.camera.capture(gp.GP_CAPTURE_IMAGE)

    def take_photos(self, num=1, interval=1):
        '''

        :param num: 拍照数量， 小于0为无限拍照模式
        :param interval: 拍照间隔（s）
        :return: CameraFilePath list
        '''
        num_err = 5    # 容许错误次数
        filepath_list = []
        while num != 0:
            try:
                temp = self.take_photo()
                if hasattr(self, "filepath_queue"):
                    self.filepath_queue.put((temp.folder, temp.name))
                else:
                    filepath_list.append(temp)
                num -= 1
            except Exception as err:
                logger.exception(err)
                if num_err > 0:
                    num_err -= 1
                else:
                    logger.info("Take photo error!")
                    break

            time.sleep(interval)

        return filepath_list

    def get_camera_files(self, folder="/"):
        cam_files = self.camera.folder_list_files(folder)
        self.cam_files = []

        for i in range(cam_files.count()):
            self.cam_files.append(cam_files.get_name(i))

    def get_local_files(self):
        temp = os.listdir(self.save_path)
        self.loc_files = [item for item in temp if ".jpg" in item]

    def save_photo(self, folder, name):
        cam_file = self.camera.file_get(folder, name, gp.GP_FILE_TYPE_NORMAL)
        path = os.path.join(self.save_path, name)
        err = gp.gp_file_save(cam_file, path)

        if err != gp.GP_OK:
            return err

        return path

    @asnyc_thread
    def save_auto_by_list(self):
        self.get_local_files()
        folder = "/"
        while not self.asnyc_stop:
            num_err = 5
            self.get_camera_files(folder)
            if len(self.cam_files) == 0 or len(self.loc_files) == len(self.cam_files):
                time.sleep(2)
                continue

            for name in self.cam_files:
                if name in self.loc_files:
                    continue

                while num_err > 0:
                    try:
                        res = self.save_photo(folder, name)
                        if not isinstance(res, str):
                            time.sleep(0.2)
                            num_err -= 1
                            continue

                        self.loc_files.append(name)
                        break
                    except Exception as err:
                        time.sleep(0.2)
                        num_err -= 1
                else:
                    self.failed_list.append(name)

    @asnyc_thread
    def save_auto_by_queue(self):
        while not self.asnyc_stop:
            num_err = 5
            while num_err > 0:
                try:
                    folder, name = self.filepath_queue.get()
                    res = self.save_photo(folder, name)
                    if not isinstance(res, str):
                        time.sleep(0.2)
                        num_err -= 1
                        continue

                    self.loc_files.append(name)
                    break
                except Exception as err:
                    time.sleep(0.2)
                    num_err -= 1
            else:
                self.failed_list.append(name)


    def change_config(self, config_name, value):
        try:
            config = self.camera.get_single_config(config_name)
            config.set_value(value)
            self.camera.set_single_config(config_name, config)
        except Exception as err:
            print(err)

    def init(self):
        self.connect()
        logger.add(self.log_file)

if __name__ == '__main__':
    handler = CameraHandler("/home/cqj")