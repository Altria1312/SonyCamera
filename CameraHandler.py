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

        return t

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
            self.save_path = save_path
            if not os.path.exists(save_path):
                logger.warning("save path not exist, building dir...")
                os.popen("sudo mkdir %s"%self.save_path, "w").write("%s\n"%self.passwd)

            os.popen("sudo chmod 777 %s"%save_path, "w").write("%s\n"%self.passwd)
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
        self.asnyc_stop = True
        self.camera.exit()
        logger.info("camera disconnected")

    def take_photo(self):
        '''

        :return: CameraFilePath *
        '''
        return self.camera.capture(gp.GP_CAPTURE_IMAGE)

    def trigger_capture(self):
        self.camera.trigger_capture()
        while 1:
            event, data = self.camera.wait_for_event(10)
            if event == gp.GP_EVENT_FILE_ADDED:
                return data
    
    @asnyc_thread
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

                logger.info("taking photo %s"%temp.name)
                num -= 1
            except Exception as err:
                logger.exception(err)
                if num_err > 0:
                    logger.warning("taking wrong, retry")
                    num_err -= 1
                else:
                    logger.info("Take photo error!")
                    break

            time.sleep(interval)

        return filepath_list

    @asnyc_thread
    def trigger_captures(self, num=1, interval=1):
        '''

        :param num: 拍照数量， 小于0为无限拍照模式
        :param interval: 拍照间隔（s）
        :return: CameraFilePath list
        '''
        num_err = 5    # 容许错误次数
        filepath_list = []
        while num != 0:
            try:
                temp = self.trigger_capture()
                if hasattr(self, "filepath_queue"):
                    self.filepath_queue.put((temp.folder, temp.name))
                else:
                    filepath_list.append(temp)

                logger.info("taking photo %s"%temp.name)
                num -= 1
            except Exception as err:
                logger.exception(err)
                if num_err > 0:
                    logger.warning("taking wrong, retry")
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
                        logger.info("%s saved"%name)
                        break
                    except Exception as err:
                        logger.warning("%s failed, retrying..."%name)
                        time.sleep(0.2)
                        num_err -= 1
                else:
                    self.failed_list.append(name)
                    logger.error("%s saved failed"%name)

    @asnyc_thread
    def save_auto_by_queue(self):
        self.get_local_files()
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
                    logger.info("%s saved"%name)
                    break
                except Exception as err:
                    logger.exception(err)
                    logger.warning("%s failed, retrying..."%name)
                    time.sleep(0.2)
                    num_err -= 1
            else:
                self.failed_list.append(name)
                logger.error("%s saved failed"%name)


    def change_config(self, config_name, value):
        try:
            config = self.camera.get_single_config(config_name)
            config.set_value(value)
            self.camera.set_single_config(config_name, config)
        except Exception as err:
            print(err)

    def take_photos_save(self, num=1):
        self.take_photos(num)        
        logger.info("start taking photo")
        time.sleep(2)
        self.save_auto_by_list()
        logger.info("start saving photo")

    def trigger_captures_save(self, num=1):
        t1 = self.trigger_captures(num)
        logger.info("start taking photo")
        time.sleep(2)
        t2 = self.save_auto_by_queue()
        logger.info("start saving photo")

        self.disconnect()

        t1.join()
        t2.join()
        print("done")

    def init(self):
        logger.add(self.log_file)
        logger.info("===========new task==============")
        self.connect()
    
    @asnyc_thread
    def io_test(self):
        while not self.asnyc_stop:
            data = self.camera.wait_for_event(10)[1]
            print(data)

if __name__ == '__main__':
    handler = CameraHandler("/home/cqj")
