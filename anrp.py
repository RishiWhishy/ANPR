import tkinter as tk
import cv2
import PIL.Image, PIL.ImageTk
import pytesseract
import numpy as np
import imutils
import re
import requests
import pandas as pd
from pymongo import MongoClient
from datetime import datetime, timedelta

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class App:
    def __init__(self, window, window_title, video_source=0):
        self.window = window
        self.window.title(window_title)
        self.video_source = video_source

        self.vid = MyVideoCapture(self.video_source)

        self.canvas = tk.Canvas(window, width=self.vid.width, height=self.vid.height)
        self.canvas.pack()

        self.delay = 15
        self.last_detected_plate = None
        self.last_detection_time = datetime.min
        self.detection_delay = timedelta(seconds=30)  # 30 seconds delay

        self.update()

        self.window.mainloop()

    def update(self):
        ret, frame = self.vid.get_frame()
        if ret:
            self.photo = PIL.ImageTk.PhotoImage(image=PIL.Image.fromarray(frame))
            self.canvas.create_image(0, 0, image=self.photo, anchor=tk.NW)
            self.process_image(frame)
        self.window.after(self.delay, self.update)

    def process_image(self, frame):
        img = imutils.resize(frame, width=500)
        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray_img = cv2.bilateralFilter(gray_img, 11, 17, 17)
        c_edge = cv2.Canny(gray_img, 170, 200)

        cnt, _ = cv2.findContours(c_edge, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        cnt = sorted(cnt, key=cv2.contourArea, reverse=True)[:30]

        NumberPlateCount = None
        for c in cnt:
            perimeter = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * perimeter, True)
            if len(approx) == 4:
                NumberPlateCount = approx
                break

        if NumberPlateCount is not None:
            masked = np.zeros(gray_img.shape, np.uint8)
            new_image = cv2.drawContours(masked, [NumberPlateCount], 0, 255, -1)
            new_image = cv2.bitwise_and(img, img, mask=masked)
            configr = ('-l eng --oem 1 --psm 3')
            text_no = pytesseract.image_to_string(new_image, config=configr)
            if text_no.strip():
                print(f"Detected Number Plate: {text_no.strip()}")
                self.handle_detection(frame, text_no.strip())

    def handle_detection(self, frame, plate_no):
        current_time = datetime.now()
        if self.last_detected_plate == plate_no and current_time - self.last_detection_time < self.detection_delay:
            print(f"Delay in effect. Skipping log for plate: {plate_no}")
            return

        self.last_detected_plate = plate_no
        self.last_detection_time = current_time
        self.send_to_api(frame, plate_no)

    def send_to_api(self, frame, plate_no):
        image_path = "vehicleplate.jpg"
        cv2.imwrite(image_path, frame)

        regions = ['in']  # Change to your country
        with open(image_path, 'rb') as fp:
            response = requests.post(
                'https://api.platerecognizer.com/v1/plate-reader/',
                data=dict(regions=regions),
                files=dict(upload=fp),
                headers={'Authorization': 'Token 541c8820aad4d36e3a80a71ede91658445ec47f1'}
            )

        try:
            plate = response.json()
            plate_no = str(plate['results'][0]['plate']).upper()
            formatted_plate = self.format_plate_number(plate_no)
            print(f"Formatted Plate No.: {formatted_plate}")

            if self.is_registered_vehicle(formatted_plate):
                self.save_to_csv(formatted_plate)
                self.log_vehicle_event(formatted_plate)
            else:
                print(f"Unregistered vehicle detected: {formatted_plate}")
        except Exception as e:
            print(f"Plate not recognized or API error: {e}. Skipping database entry.")

    def format_plate_number(self, plate_no):
        s = str(plate_no)
        if re.match(r'^[A-Z]{2}[0-9]{1}[A-Z]{2}', s, flags=0):
            s = s[:2] + '0' + s[2:]
        elif re.match(r'^[A-Z]{2}[0-9]{2}[A-Z]{2}[0-9]{3}$', s, flags=0):
            s = s[:6] + '0' + s[6:]
        elif re.match(r'^[A-Z]{2}[0-9]{2}[A-Z]{2}[0-9]{2}$', s, flags=0):
            s = s[:6] + '00' + s[6:]
        elif re.match(r'^[A-Z]{2}[0-9]{2}[A-Z]{2}[0-9]{1}$', s, flags=0):
            s = s[:6] + '000' + s[6:]
        return s

    def save_to_csv(self, plate_no):
        current_time = datetime.now()
        data = {'Date': [current_time], 'Vehicle_number': [plate_no]}
        df = pd.DataFrame(data, columns=['Date', 'Vehicle_number'])
        df.to_csv('Dataset_VehicleNo.csv', mode='a', header=False)

    def log_vehicle_event(self, vehicle_number):
        current_time = datetime.now()
        existing_entry = vehicles_collection.find_one({"vehicle_number": vehicle_number, "exit_time": None})

        if existing_entry:
            vehicles_collection.update_one(
                {"_id": existing_entry["_id"]},
                {"$set": {"exit_time": current_time}}
            )
            print(f"Logged exit for vehicle: {vehicle_number} at {current_time}")
        else:
            entry = {
                "vehicle_number": vehicle_number,
                "entry_time": current_time,
                "exit_time": None
            }
            vehicles_collection.insert_one(entry)
            print(f"Logged entry for vehicle: {vehicle_number} at {current_time}")

    def is_registered_vehicle(self, plate_no):
        registered_vehicle = registered_vehicles_collection.find_one({"vehicle_number": plate_no})
        return registered_vehicle is not None

    def __del__(self):
        del self.vid

class MyVideoCapture:
    def __init__(self, video_source=0):
        self.vid = cv2.VideoCapture(video_source)
        if not self.vid.isOpened():
            raise ValueError("Unable to open video source", video_source)

        self.width = self.vid.get(cv2.CAP_PROP_FRAME_WIDTH)
        self.height = self.vid.get(cv2.CAP_PROP_FRAME_HEIGHT)

    def get_frame(self):
        if self.vid.isOpened():
            ret, frame = self.vid.read()
            if ret:
                return ret, cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                return ret, None
        else:
            return ret, None

    def __del__(self):
        if self.vid.isOpened():
            self.vid.release()

# MongoDB setup
client = MongoClient('localhost', 27017)
db = client['anpr_database']
vehicles_collection = db['vehicle_logs']
registered_vehicles_collection = db['registered_vehicles']
App(tk.Tk(), "Tkinter and OpenCV")
