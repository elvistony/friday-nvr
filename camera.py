import os
import cv2
import configparser
import threading
from datetime import datetime

config = configparser.ConfigParser()
config.read('config.ini')

class CameraManager:
    def __init__(self):
        self.cameras = []
        self.recording_path = config['DEFAULT']['recording_path']
        self.max_space = int(config['DEFAULT']['max_space']) * 1024 * 1024
        if not os.path.exists(self.recording_path):
            os.makedirs(self.recording_path)
        self.recording_status = {}
        self.last_frames = {}
        self.total_consumed_size=0
        self.chunk_size = int(config['DEFAULT']['chunk_size']) * 1024 * 1024
        self.load_cameras()

    def load_cameras(self):
        cameras = config['DEFAULT']['cameras']
        if cameras:
            for i, camera in enumerate(cameras.split(',')):
                url, nickname = camera.split('|')
                self.add_camera(url, nickname)

    def add_camera(self, url, nickname):
        camera_id = len(self.cameras)
        self.cameras.append({'id': camera_id, 'url': url, 'nickname': nickname})
        self.recording_status[camera_id] = False
        self.last_frames[camera_id] = 'static/placeholder.jpg'
        self.capture_initial_frame(camera_id, url)

    def remove_camera(self, camera_id):
        self.cameras = [cam for cam in self.cameras if cam['id'] != camera_id]
        if camera_id in self.recording_status:
            self.recording_status.pop(camera_id)
        if camera_id in self.last_frames:
            self.last_frames.pop(camera_id)

    def edit_camera(self, camera_id, url, nickname):
        for cam in self.cameras:
            if cam['id'] == camera_id:
                cam['url'] = url
                cam['nickname'] = nickname
                self.capture_initial_frame(camera_id, url)

    def get_cameras(self):
        for cam in self.cameras:
            cam['status'] = self.check_camera_status(cam['url'])
            cam['recording'] = self.recording_status[cam['id']]
        return self.cameras

    def set_recording_path(self, path):
        self.recording_path = path
        if not os.path.exists(self.recording_path):
            os.makedirs(self.recording_path)

    def set_max_space(self, max_space):
        self.max_space = max_space * 1024 * 1024

    def flush_recording(self, camera_id):
        self.stop_recording(camera_id)
        self.start_recording(camera_id)

    def get_recordings(self):
        recordings = {}
        sizes = {}
        for cam in self.cameras:
            cam_id = cam['id']
            cam_folder = os.path.join(self.recording_path, f'camera_{cam_id}')
            recordings[cam_id] = []
            
            if os.path.exists(cam_folder):
                for root, dirs, files in os.walk(cam_folder):
                    for file in files:
                        path = os.path.join(root, file)
                        sizes[path] = round(os.path.getsize(path)/1024/1024,1)
                        recordings[cam_id].append(path)
        return recordings,sizes

    def check_storage_space(self):
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(self.recording_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total_size += os.path.getsize(fp)
        self.total_consumed_size = total_size

        while total_size > self.max_space:
            oldest_file = min((os.path.join(dirpath, f) for dirpath, _, filenames in os.walk(self.recording_path) for f in filenames), key=os.path.getctime)
            total_size -= os.path.getsize(oldest_file)
            os.remove(oldest_file)
    
    def get_total_consumed_size(self):
        return round(self.total_consumed_size/1024/1024,2)
    
    def check_chunk_size(self,file,camera_id):
        # print(os.path.getsize(file),'out of',self.chunk_size)
        if(round(os.path.getsize(file),1) > self.chunk_size):
            self.stop_recording(camera_id)
            self.start_recording(camera_id)
        else:
            pass


    def check_camera_status(self, url):
        cap = cv2.VideoCapture(url)
        if cap.isOpened():
            cap.release()
            print(f"Camera connected successfully: {url}")
            return 'Online'
        else:
            print(f"Failed to connect camera: {url}")
            return 'Offline'

    def start_recording(self, camera_id):
        camera = next((cam for cam in self.cameras if cam['id'] == camera_id), None)
        if camera:
            url = camera['url']
            cap = cv2.VideoCapture(url)
            if cap.isOpened():
                self.recording_status[camera_id] = True
                filename = os.path.join(self.recording_path, f'camera_{camera_id}', f'{datetime.now().strftime("%Y%m%d_%H%M%S")}.avi')
                if not os.path.exists(os.path.dirname(filename)):
                    os.makedirs(os.path.dirname(filename))
                fourcc = cv2.VideoWriter_fourcc(*'XVID')
                out = cv2.VideoWriter(filename, fourcc, 20.0, (int(cap.get(3)), int(cap.get(4))))

                def record():
                    while self.recording_status[camera_id]:
                        ret, frame = cap.read()
                        if not ret:
                            print(f"Failed to capture frame from camera {camera_id}")
                            break
                        out.write(frame)
                        self.check_storage_space()
                        self.check_chunk_size(filename,camera_id)
                    cap.release()
                    out.release()

                threading.Thread(target=record).start()
            else:
                print(f"Failed to open camera stream for camera {camera_id}")

    def stop_recording(self, camera_id):
        if camera_id in self.recording_status:
            self.recording_status[camera_id] = False

    def get_last_frame(self, camera_id):
        return self.last_frames.get(camera_id, 'static/placeholder.jpg')

    def capture_initial_frame(self, camera_id, url):
        cap = cv2.VideoCapture(url)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                init_frame_path = os.path.join(self.recording_path, f'camera_{camera_id}', 'init.jpg')
                if not os.path.exists(os.path.dirname(init_frame_path)):
                    os.makedirs(os.path.dirname(init_frame_path))
                try:
                    cv2.imwrite(init_frame_path, frame)
                    self.last_frames[camera_id] = init_frame_path
                    print(f"Initial frame captured for camera {camera_id} at {url}")
                except Exception as e:
                    print(f"Error saving initial frame: {e}")
            cap.release()
        else:
            print(f"Failed to open camera stream for camera {camera_id}")

    def refresh_last_frame(self, camera_id):
        camera = next((cam for cam in self.cameras if cam['id'] == camera_id), None)
        if camera:
            url = camera['url']
            cap = cv2.VideoCapture(url)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    last_frame_path = os.path.join(self.recording_path, f'camera_{camera_id}', 'last_frame.jpg')
                    if not os.path.exists(os.path.dirname(last_frame_path)):
                        os.makedirs(os.path.dirname(last_frame_path))
                    try:
                        cv2.imwrite(last_frame_path, frame)
                        self.last_frames[camera_id] = last_frame_path
                        print(f"Last frame refreshed for camera {camera_id} at {url}")
                    except Exception as e:
                        print(f"Error saving last frame: {e}")
                cap.release()
            else:
                print(f"Failed to open camera stream for camera {camera_id}")
