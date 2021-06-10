import io
import digitalio
import board
import adafruit_matrixkeypad
import drivers
import time
import RPi.GPIO as GPIO
import threading
from firebase import firebase
from picamera import PiCamera
from picamera.array import PiRGBArray
from linebot import LineBotApi
from linebot.models import TextSendMessage
from datetime import datetime, timezone, timedelta
import os
from PIL import Image
from google.cloud import storage

GPIO.setmode(GPIO.BCM)

# set url and api
db_url = None
fdb = firebase.FirebaseApplication(db_url, None)
result = fdb.get('/user', '1234')
line_bot_api = LineBotApi(None)

config = {
    "apiKey": None,
    "authDomain": None,
    "databaseURL": None,
    "projectId": None,
    "storageBucket": None,
    "serviceAccount": None
}

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = config["serviceAccount"]

# Global variables
work = True
alarm_run = False
send_flag = True
RCpin = 23
saveImage_flag = False
image = None

# frequency
Do = 262
Re = 294
Mi = 330
Fa = 349
So = 392

# Membrane 3x4 matrix keypad on Raspberry Pi -
cols = [digitalio.DigitalInOut(x) for x in (board.D26, board.D20, board.D21)]
rows = [digitalio.DigitalInOut(x) for x in (board.D5, board.D6, board.D13, board.D19)]

# 3x4 matrix keypad on Raspberry Pi -
# rows and columns are mixed up for https://www.adafruit.com/product/3845
# cols = [digitalio.DigitalInOut(x) for x in (board.D13, board.D5, board.D26)]
# rows = [digitalio.DigitalInOut(x) for x in (board.D6, board.D21, board.D20, board.D19)]

# keyboard
keys = [[1, 2, 3], [4, 5, 6], [7, 8, 9], ["*", 0, "#"]]

keypad = adafruit_matrixkeypad.Matrix_Keypad(rows, cols, keys)

password = []

digit = None

display = drivers.Lcd()


def play(p, frequency, tempo):
    p.ChangeFrequency(frequency)
    time.sleep(0.3 * tempo)


# alarm song
def song():
    global alarm_run
    GPIO.setup(18, GPIO.OUT)
    p = GPIO.PWM(18, 50)
    p.start(50)

    if alarm_run:
        play(p, Do, 2)
    if alarm_run:
        play(p, Re, 2)
    if alarm_run:
        play(p, Mi, 2)
    if alarm_run:
        play(p, Fa, 2)
    if alarm_run:
        play(p, So, 2)
    p.stop()


# keyboard function
def enter_password():
    global result
    global digit
    global alarm_run
    global send_flag
    global work
    global password
    global saveImage_flag

    while work:
        # delete
        if digit and len(password) and digit[0] == "*":
            password.pop()
            display.lcd_clear()
            display.lcd_display_string("".join(password), 1)
            display.lcd_display_string("Delete", 2)
        # input
        elif digit and len(password) != 4:
            password.append(str(digit[0]))
            display.lcd_clear()
            display.lcd_display_string("".join(password), 1)
        # enter
        elif digit and digit[0] == "#":
            display.lcd_display_string("Enter!!", 2)
            # correct password
            if "".join(password) == result["password"]:
                result["alarm_state"] = "off"
                fdb.put('/user', "1234", {"user_id": result["user_id"], "password": result["password"],
                                          "camera_state": result["camera_state"],
                                          "alarm_state": result["alarm_state"]})
                # stop alarm
                alarm_run = False
                # change send state
                send_flag = True
                # change save state
                saveImage_flag = False
                # let led turn off
                GPIO.setup(7, GPIO.OUT)
                GPIO.output(7, GPIO.LOW)
            time.sleep(0.1)
            display.lcd_clear()
            password = []
        digit = keypad.pressed_keys
        # for debug
        if digit:
            print(digit)

        time.sleep(0.2)


#  get data from firebase
def get_data():
    global result
    global alarm_run
    global work

    while work:
        result = fdb.get('/user', '1234')
        if result["alarm_state"] == "off":
            alarm_run = False
        else:
            alarm_run = True


# use pi camera to picture photos
def get_camera():
    global image
    camera = PiCamera()
    camera.resolution = (640, 480)
    rawCapture = PiRGBArray(camera, size=(640, 480))
    time.sleep(1)

    for frame in camera.capture_continuous(rawCapture,
                                           format="rgb",
                                           use_video_port=True):
        if not work:
            break

        image = frame.array
        rawCapture.truncate(0)

# read capacitance value
def RCtime():
    global send_flag
    global result
    global RCpin
    global saveImage_flag

    while work:
        reading = 0
        GPIO.setwarnings(False)
        GPIO.setup(RCpin, GPIO.OUT)
        GPIO.output(RCpin, GPIO.LOW)

        time.sleep(0.1)

        GPIO.setup(RCpin, GPIO.IN)

        while (GPIO.input(RCpin) == GPIO.LOW) & work:
            reading += 1
        print(reading)
        if reading < 100000 and send_flag:
            # alarm start to ring
            result["alarm_state"] = "on"
            fdb.put('/user', "1234", {"user_id": result["user_id"], "password": result["password"],
                                      "camera_state": result["camera_state"],
                                      "alarm_state": result["alarm_state"]})
            # send warning message
            line_bot_api.multicast(result["user_id"],
                                   TextSendMessage(text='Warning! Someone entered your house!!'))
            # change send status
            send_flag = False
            # change save status
            saveImage_flag = True


# pir function
def pir():
    global send_flag

    # Read PIR state
    GPIO.setup(7, GPIO.OUT)
    GPIO.output(7, GPIO.LOW)
    while work:
        GPIO.setup(12, GPIO.IN)
        current_state = GPIO.input(12)
        # Led light
        if current_state and send_flag:
            GPIO.setup(7, GPIO.OUT)
            GPIO.output(7, GPIO.HIGH)
            time.sleep(0.1)

        time.sleep(0.01)


# save image to firebase
def save_image():
    global saveImage_flag
    global image

    client = storage.Client()
    bucket = client.get_bucket(config["storageBucket"])

    while work:
        if saveImage_flag:
            while image is None:
                continue

            temp_img = image

            # Convert numpy array to bytes
            temp_file = Image.fromarray(temp_img)
            temp_file_bytes = io.BytesIO()
            temp_file.save(temp_file_bytes,
                           format="JPEG")

            # Read the bytes from beginning
            temp_file_bytes.seek(0)

            # Grt time at GMT+8
            tz = timezone(timedelta(hours=+8))
            # filename
            image_name = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
            image_blob = bucket.blob(f"{image_name}.jpg")
            image_blob.upload_from_file(temp_file_bytes,
                                        content_type="image/jpeg")
            # storage.child("{}.jpg".format(image_name)).put(temp_file)
        time.sleep(0.5)


# all thread
w = threading.Thread(name='enter_password',
                     target=enter_password)

r = threading.Thread(name='get_data',
                     target=get_data)

c = threading.Thread(name='get_camera',
                     target=get_camera)
p = threading.Thread(name='pir',
                     target=pir)

d = threading.Thread(name='RCtime',
                     target=RCtime)

s = threading.Thread(name='save_image',
                     target=save_image)

# main function
try:
    w.start()
    r.start()
    c.start()
    p.start()
    d.start()
    s.start()
    while work:
        if alarm_run:
            song()

except KeyboardInterrupt:
    work = False
    w.join()
    r.join()
    c.join()
    p.join()
    d.join()
    s.join()
    GPIO.cleanup()
