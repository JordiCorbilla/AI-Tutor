# Copyright 2024 Jordi Corbilla. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

import logging
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import openai
from io import BytesIO
from gtts import gTTS
from PIL import Image
import pytesseract
import pyodbc
import os
import tempfile
import configparser
import re
import threading
import time
from datetime import datetime, timedelta
import requests

# Configuration section
config = configparser.ConfigParser()
config.read('C:/repo/AI-Tutor/config.ini')

TELEGRAM_BOT_TOKEN = config['TELEGRAM']['BOT_TOKEN']
AUTHORIZED_USERS = config['TELEGRAM']['AUTHORIZED_USERS']

AUTHORIZED_USERS_SET = set(user.strip().lower() for user in AUTHORIZED_USERS.split(','))
print(f'Authorized Users:{AUTHORIZED_USERS_SET}')

OPENAI_API_KEY = config['OPENAI']['API_KEY']
openai.api_key = OPENAI_API_KEY

DATABASE_CONFIG = {
    'server': config['DATABASE']['SERVER'],
    'database': config['DATABASE']['DATABASE'],
    'driver': config['DATABASE']['DRIVER']
}

# Tesseract OCR configuration For Windows
pytesseract.pytesseract.tesseract_cmd = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

reminders = []

def add_reminder(user_id, reminder_time, message, inner_context):
    reminders.append({
        "user_id": user_id,
        "time": reminder_time,
        "message": message,
        'context': inner_context
    })
    logger.info(f"Reminder added for user {user_id} at {reminder_time} with message: '{message}'")

def send_reminder():
    current_time = datetime.now()
    for reminder in reminders.copy():  
        try:
            if reminder["time"] <= current_time:

                logger.info(f"Sending reminder to user {reminder['user_id']} at {current_time}: {reminder['message']}")
                
                inner_context = reminder['context']
                inner_context.bot.send_message(chat_id = reminder["user_id"], text = f"Reminder!!\n{reminder['message']}")  
                logger.info(f"Reminder sent to user {reminder['user_id']} for message: '{reminder['message']}'")
                
                reminders.remove(reminder)  
        except Exception as e:
            logger.error(f"Error sending reminder to user {reminder['user_id']}: {e}", exc_info=True)

def check_reminders():
    while True:
        send_reminder()
        time.sleep(10) 

def get_db_connection():
    conn = pyodbc.connect(
        'DRIVER={driver};SERVER={server};DATABASE={database};Trusted_Connection=yes;'.format(**DATABASE_CONFIG)
    )
    return conn

def log_interaction(user_id, user_name, message_type, user_message, bot_response):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Interactions (UserID, UserName, MessageType, UserMessage, BotResponse)
            VALUES (?, ?, ?, ?, ?)
        """, user_id, user_name, message_type, user_message, bot_response)
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error logging interaction: {e}", exc_info=True)

def is_user_authorized(update):
    user = update.effective_user
    username = (user.username or '').lower()
    full_name = (user.full_name or '').lower()
    user_id = str(user.id)
    if username in AUTHORIZED_USERS_SET or full_name in AUTHORIZED_USERS_SET or user_id in AUTHORIZED_USERS_SET:
        return True
    else:
        logger.warning(f"Unauthorized access attempt by user: [{user_id}] - [{full_name}] - [@{username}]")
        return False

def voice_to_text(file_bytes):
    try:
        audio_file = BytesIO(file_bytes)
        audio_file.name = 'audio.ogg' 
        transcript = openai.Audio.transcribe("whisper-1", audio_file)
        return transcript['text']
    except Exception as e:
        logger.error(f"Error in voice_to_text: {e}", exc_info=True)
        return ""

def text_to_speech(text):
    try:
        tts = gTTS(text=text, lang='en')
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        temp_file.name = 'ai_tutor_response.mp3'
        tts.save(temp_file.name)
        temp_file.close()
        return temp_file.name
    except Exception as e:
        logger.error(f"Error in text_to_speech: {e}", exc_info=True)
        return ""

def image_to_text(file_bytes):
    try:
        image = Image.open(BytesIO(file_bytes))
        text = pytesseract.image_to_string(image)
        return text
    except Exception as e:
        logger.error(f"Error in image_to_text: {e}", exc_info=True)
        return ""

def get_ai_response(prompt):
    try:
        logger.debug(f"Sending messages to OpenAI: {prompt}")
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Your name is Merlin and you are a very helpful tutor and provide succinct answers to us."},
                {"role": "user", "content": prompt}
            ]
        )
        ai_response = response.choices[0].message.content
        logger.debug(f"Received AI response: {ai_response}")
        return ai_response
    except Exception as e:
        logger.error(f"Error in get_ai_response: {e}", exc_info=True)
        return "Sorry, I'm having trouble generating a response right now."

def handle_voice(update, context):
    if not is_user_authorized(update):
        context.bot.send_message(chat_id=update.effective_chat.id, text="You are not authorized.")
        return
    try:
        logger.info('Handling voice message')
        file_id = update.message.voice.file_id
        new_file = context.bot.get_file(file_id)
        file_bytes = new_file.download_as_bytearray()
        transcribed_text = voice_to_text(file_bytes)
        logger.debug(f'Transcribed text: {transcribed_text}')
        ai_response = get_ai_response(transcribed_text)
        audio_file_path = text_to_speech(ai_response)
        logger.debug(f'Generated audio file at: {audio_file_path}')

        context.bot.send_message(chat_id=update.effective_chat.id, text=ai_response)

        with open(audio_file_path, 'rb') as audio_file:
            context.bot.send_document(chat_id=update.effective_chat.id, document=audio_file)
        
        # Clean up the temporary file
        os.remove(audio_file_path) 

        # Log the interaction
        user_id = update.effective_user.id
        user_name = update.effective_user.username or update.effective_user.full_name
        log_interaction(user_id, user_name, 'voice', transcribed_text, ai_response)
    except Exception as e:
        logger.error(f"Error in handle_voice: {e}", exc_info=True)
        context.bot.send_message(chat_id=update.effective_chat.id, text="Sorry, I couldn't process your voice message.")

def handle_photo(update, context):
    if not is_user_authorized(update):
        context.bot.send_message(chat_id=update.effective_chat.id, text="You are not authorized.")
        return
    try:
        logger.info('Handling photo message')
        photo_file = update.message.photo[-1].get_file()
        file_bytes = photo_file.download_as_bytearray()
        extracted_text = image_to_text(file_bytes)
        logger.debug(f'Extracted text from image: {extracted_text}')

        # Get caption text if any as part of the request
        caption_text = update.message.caption or ''
        logger.debug(f'Caption text: {caption_text}')

        # Check if the caption starts specifically with 'extract text:'
        # This interaction will skip open ai and just use tesseract
        if caption_text.lower().startswith('extract text:'):
            # Send back the extracted text without involving OpenAI
            context.bot.send_message(chat_id=update.effective_chat.id, text=f"Extracted Text:\n{extracted_text}")

            # Log the interaction
            user_id = update.effective_user.id
            user_name = update.effective_user.username or update.effective_user.full_name
            log_interaction(user_id, user_name, 'extract text', extracted_text, extracted_text)
        else:
            # Combine caption text and extracted text
            combined_text = caption_text + '\n' + extracted_text if extracted_text else caption_text

            if not combined_text.strip():
                context.bot.send_message(chat_id=update.effective_chat.id, text="Sorry, I couldn't read any text in the image or caption.")
                return

            logger.debug(f'Combined text: {combined_text}')
            ai_response = get_ai_response(combined_text)
            context.bot.send_message(chat_id=update.effective_chat.id, text=ai_response)

            # Log the interaction
            user_id = update.effective_user.id
            user_name = update.effective_user.username or update.effective_user.full_name
            log_interaction(user_id, user_name, 'photo', combined_text, ai_response)
    except Exception as e:
        logger.error(f"Error in handle_photo: {e}", exc_info=True)
        context.bot.send_message(chat_id=update.effective_chat.id, text="Sorry, I couldn't process your image.")

def handle_text(update, context):
    user_id = update.effective_user.id
    user_name = update.effective_user.username or update.effective_user.full_name
    user_text = update.message.text

    reminder_match = re.search(r'remind me in (\d+) (second|seconds|minute|minutes|hour|hours|day|days)(.*)', user_text.lower())
    if reminder_match:
        time_value = int(reminder_match.group(1))
        time_unit = reminder_match.group(2)
        reminder_content = reminder_match.group(3).strip()
        reminder_content = reminder_content.replace('s ', '')
        if 'second' in time_unit:
            reminder_time = datetime.now() + timedelta(seconds=time_value)
        elif 'minute' in time_unit:
            reminder_time = datetime.now() + timedelta(minutes=time_value)
        elif 'hour' in time_unit:
            reminder_time = datetime.now() + timedelta(hours=time_value)
        elif 'day' in time_unit:
            reminder_time = datetime.now() + timedelta(days=time_value)
        else:
            context.bot.send_message(chat_id=user_id, text="Sorry, I didn't understand the time unit.")
            return

        reminder_message = f"You have a reminder set for [{reminder_time.strftime('%Y/%m/%d %H:%M:%S')}]: '{reminder_content}'."
        add_reminder(user_id, reminder_time, reminder_content, context)

        context.bot.send_message(chat_id=user_id, text=reminder_message)
        return  

    # Proceed with regular text processing
    if user_text.lower().startswith('generate image:'):

        image_prompt = user_text[len('generate image:'):].strip()
        if not image_prompt:
            context.bot.send_message(chat_id=user_id, text="Please provide a prompt for image generation after 'generate image:'.")
            return

        # Generate image using OpenAI API
        response = openai.Image.create(
            prompt=image_prompt,
            n=1,
            size="512x512"
        )
        image_url = response['data'][0]['url']

        # Download the image from the URL
        image_response = requests.get(image_url)

        # Send the image back to the user
        context.bot.send_photo(chat_id=user_id, photo=image_response.content)

        # Log the interaction
        log_interaction(user_id, user_name, 'generate image', image_prompt, 'Image generated')
    elif user_text.lower().startswith('extract text:'):
        context.bot.send_message(chat_id=user_id, text="Please send the image you want to extract text from, and include 'extract text:' in the caption.")
    else:
        ai_response = get_ai_response(user_text)
        context.bot.send_message(chat_id=user_id, text=ai_response)

        log_interaction(user_id, user_name, 'text', user_text, ai_response)


def start(update, context):
    if not is_user_authorized(update):
        context.bot.send_message(chat_id=update.effective_chat.id, text="You are not authorized.")
        return
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Hello! I'm your AI tutor 'Merlin' v1.0. Send me a message, and I'll help you out! Type **/help** for more info.")

def help_command(update, context):
    help_text = (
        "Hello! I'm your AI tutor 'Merlin' v1.0. Here are the commands you can use:\n\n"
        "**/start** - Start interacting with the bot.\n"
        "Send me a message to get help on a specific topic.\n\n"
        "Reminders:\n"
        "You can set reminders by saying:\n"
        "  'Hey **remind me in X [seconds/minutes/hours/days]**' - Set a reminder for a specific duration.\n"
        "  Example: 'Hey remind me in 5 minutes to do my math homework.'\n\n"
        "Voice Messages:\n"
        "Send me a voice message, and I'll transcribe it into text and provide assistance.\n\n"
        "Image Text Extraction:\n"
        "Send me a photo, and I will extract the text from it.\n"
        "If you want to extract text specifically, include **'extract text:'** in the caption of the photo.\n\n"
        "Text Queries:\n"
        "You can ask me any question, and I'll do my best to provide a helpful answer.\n"
        "If you want to generate an image, type:\n"
        "  **'generate image:** [your prompt]'\n"
        "  Example: 'generate image: a sunny beach with palm trees.'\n\n"
        "For any other queries, just type your message and I will assist you!\n"
        "If you need to extract text from an image, please use the caption format **'extract text:** [your text]'."
    )
    context.bot.send_message(chat_id=update.effective_chat.id, text=help_text)                             

def main():
    # Create Updater and pass in bot token
    updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # Register handlers
    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(CommandHandler('help', help_command))
    dp.add_handler(MessageHandler(Filters.voice, handle_voice))
    dp.add_handler(MessageHandler(Filters.photo, handle_photo))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))

    # Start the Bot using long polling
    updater.start_polling()

    threading.Thread(target=check_reminders, args=(), daemon=True).start()

    # Run the bot until you press Ctrl-C
    updater.idle()

if __name__ == '__main__':
    main()
