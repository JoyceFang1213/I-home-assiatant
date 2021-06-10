# Import package
import configparser
import os
from flask import Flask, request, abort
from firebase import firebase
from linebot import LineBotApi, WebhookHandler
from linebot.models import (
    MessageEvent,
    TextMessage,
    TextSendMessage,
    TemplateSendMessage,
    ButtonsTemplate,
    MessageTemplateAction
)
import time

# Get cofig token
config = configparser.ConfigParser()
config.read('config.ini')

app = Flask(__name__)
static_tmp_path = os.path.join(os.path.dirname(__file__), 'static', 'tmp')

# Channel Access Token
line_bot_api = LineBotApi(config.get('line-bot', 'channel_access_token'))
# Channel Secret
handler = WebhookHandler(config.get('line-bot', 'channel_secret'))

# firebase url
db_url = 'https://titanium-atlas-305002-default-rtdb.firebaseio.com/'
fdb = firebase.FirebaseApplication(db_url, None)

# Global parameters
user_ID_dict = {}
serial_number = ["1234", "6789"]
serial_number_password = {}
camera_state_dict = {}
alarm_state_dict = {}
for i in range(len(serial_number)):
    serial_number_password[serial_number[i]] = "0000"
    camera_state_dict[serial_number[i]] = "off"
    alarm_state_dict[serial_number[i]] = "off"
flag = 0
get_password = None
serial_number_database = []
user_id = None


# update state to firebase
def update_database():
    global serial_number_database
    for i in range(len(serial_number)):
        list_user_id = []
        for id in user_ID_dict:
            if user_ID_dict[id] == serial_number[i]:
                list_user_id.append(id)
        serial_number_database.append({"user_id": list_user_id, "password": serial_number_password[serial_number[i]],
                                       "camera_state": camera_state_dict[serial_number[i]],
                                       "alarm_state": alarm_state_dict[serial_number[i]]})

    for i in range(len(serial_number_database)):			
        fdb.put('/user', serial_number[i], serial_number_database[i])   
        time.sleep(0.5)
    serial_number_database = []


# Help function
def help_msg(event):
    line_bot_api.reply_message(
        event.reply_token,
        TemplateSendMessage(
            alt_text='Buttons template',
            template=ButtonsTemplate(
                title='Helper',
                text='You can choose following services.',
                actions=[
                    MessageTemplateAction(
                        label='Check state',
                        text='Check state'
                    ),
                    MessageTemplateAction(
                        label='Control camera',
                        text='Control camera'
                    ),
                    MessageTemplateAction(
                        label='Control alarm',
                        text='Control alarm'
                    ),
                    MessageTemplateAction(
                        label='Set password',
                        text='Set password'
                    )
                ]
            )
        )
    )


# Show now state to user
def state(event, user_password, camera_state, alarm_state):
    if user_password == "0000":
        message = TextSendMessage(text=f"Camera : {camera_state}\nAlarm : {alarm_state}\nPassword : default")
        line_bot_api.reply_message(event.reply_token, message)
    else:
        message = TextSendMessage(text=f"Camera : {camera_state}\nAlarm : {alarm_state}\nPassword : set")
        line_bot_api.reply_message(event.reply_token, message)


# Let user change camera state
def camera(event):
    line_bot_api.reply_message(
        event.reply_token,
        TemplateSendMessage(
            alt_text='Buttons template',
            template=ButtonsTemplate(
                title='Control camera',
                text='You want to turn on or turn off.',
                actions=[
                    MessageTemplateAction(
                        label='Camera turns on',
                        text='Camera turns on'
                    ),
                    MessageTemplateAction(
                        label='Camera turns off',
                        text='Camera turns off'
                    )
                ]
            )
        )
    )


# Turn on camera
def turn_on_camera(event):
    message = TextSendMessage(text="Camera turns on now.")
    line_bot_api.reply_message(event.reply_token, message)


# Turn off camera
def turn_off_camera(event):
    message = TextSendMessage(text="Camera turns off now.")
    line_bot_api.reply_message(event.reply_token, message)


# Let user change alarm state
def alarm(event):
    line_bot_api.reply_message(
        event.reply_token,
        TemplateSendMessage(
            alt_text='Buttons template',
            template=ButtonsTemplate(
                title='Control alarm',
                text='You want to turn on or turn off.',
                actions=[
                    MessageTemplateAction(
                        label='Alarm turns on',
                        text='Alarm turns on'
                    ),
                    MessageTemplateAction(
                        label='Alarm turns off',
                        text='Alarm turns off'
                    )
                ]
            )
        )
    )


# Turn on alarm
def turn_on_alarm(event):
    message = TextSendMessage(text="Alarm turns on now.")
    line_bot_api.reply_message(event.reply_token, message)


# Turn off alarm
def turn_off_alarm(event):
    message = TextSendMessage(text="Alarm turns off now.")
    line_bot_api.reply_message(event.reply_token, message)


# Let user change password
def set_password(event):
    line_bot_api.reply_message(
        event.reply_token,
        TemplateSendMessage(
            alt_text='Buttons template',
            template=ButtonsTemplate(
                title='Set password',
                text='The default password is 0000',
                actions=[
                    MessageTemplateAction(
                        label='Change password',
                        text='Change password'
                    )
                ]
            )
        )
    )


# Change password successfully
def success_set_password(event, password):
    message = TextSendMessage(text=f"Success set new password!\nYour new password is {password}.")
    line_bot_api.reply_message(event.reply_token, message)


@app.route("/password", methods=['POST'])
def password():
    global get_password
    global user_id
    get_password = request.form['password']
    get_serial_number = request.form['serial_number']

    if get_password == serial_number_password[get_serial_number]:
        alarm_state_dict[get_serial_number] = "off"
        return 'Success off'
    else:
        return 'Error on'


@app.route("/helper", methods=['POST'])
def helper():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']
    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except Exception as e:
        print(e)
        abort(400)

    return 'OK'


# Input message
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    # Let parameter become global
    global user_ID_dict
    global camera_state_dict
    global alarm_state_dict
    global flag
    global get_password
    global user_id

    # Get user ID
    user_id = event.source.user_id
    # Get input message
    msg = event.message.text

    # First, let user input serial number
    if user_id not in user_ID_dict:
        if msg not in serial_number:
            message = TextSendMessage(text="Sorry,\nNot found this serial number!\nTry again~")
            line_bot_api.reply_message(event.reply_token, message)
        else:
            user_ID_dict[user_id] = msg
            serial_number_password[user_ID_dict[user_id]] = "0000"
            message = [TextSendMessage(text="Success!! Enjoy it!"),
                       TextSendMessage(text="You can input 'help' to start.")]
            line_bot_api.reply_message(event.reply_token, message)
            
    # Second, according to different inputs response different outputs
    else:
        if msg == "help":
            help_msg(event)
        elif msg == "Check state":
            state(event, serial_number_password[user_ID_dict[user_id]],
                  camera_state_dict[user_ID_dict[user_id]], alarm_state_dict[user_ID_dict[user_id]])
        elif msg == "Control camera":
            camera(event)
        elif msg == "Camera turns on":
            turn_on_camera(event)
            camera_state_dict[user_ID_dict[user_id]] = "on"
        elif msg == "Camera turns off":
            turn_off_camera(event)
            camera_state_dict[user_ID_dict[user_id]] = "off"
        elif msg == "Control alarm":
            alarm(event)
        elif msg == "Alarm turns on":
            turn_on_alarm(event)
            alarm_state_dict[user_ID_dict[user_id]] = "on"
        elif msg == "Alarm turns off":
            turn_off_alarm(event)
            alarm_state_dict[user_ID_dict[user_id]] = "off"
        elif msg == "Set password":
            set_password(event)
        elif msg == "Change password":
            message = TextSendMessage(text="Input your old password.")
            line_bot_api.reply_message(event.reply_token, message)
        elif flag == 1 and msg == serial_number_password[user_ID_dict[user_id]]:
            message = TextSendMessage(text="Correct!! Now, input your new password.")
            line_bot_api.reply_message(event.reply_token, message)
        elif flag == 1 and msg != serial_number_password[user_ID_dict[user_id]]:
            message = TextSendMessage(text="Sorry!! Your input is error.")
            line_bot_api.reply_message(event.reply_token, message)
        elif flag == 2:
            success_set_password(event, msg)
            serial_number_password[user_ID_dict[user_id]] = msg
        else:
            message = TextSendMessage(text="Sorry!! You can input 'help'.\nI will try my best to help you~")
            line_bot_api.reply_message(event.reply_token, message)

        if msg == "Change password":
            flag = 1
        elif flag == 1 and msg == serial_number_password[user_ID_dict[user_id]]:
            flag = 2
        else:
            flag = 0

    update_database()


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
