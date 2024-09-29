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

# Tesseract OCR configuration
pytesseract.pytesseract.tesseract_cmd = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'  # For Windows

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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
    if not is_user_authorized(update):
        context.bot.send_message(chat_id=update.effective_chat.id, text="You are not authorized.")
        return
    try:
        user_text = update.message.text

        if user_text.lower().startswith('generate image:'):
            # Extract the prompt for image generation
            image_prompt = user_text[len('generate image:'):].strip()
            if not image_prompt:
                context.bot.send_message(chat_id=update.effective_chat.id, text="Please provide a prompt for image generation after 'generate image:'.")
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
            context.bot.send_photo(chat_id=update.effective_chat.id, photo=image_response.content)

            # Log the interaction
            user_id = update.effective_user.id
            user_name = update.effective_user.username or update.effective_user.full_name
            log_interaction(user_id, user_name, 'generate image', image_prompt, 'Image generated')
        elif user_text.lower().startswith('extract text:'):
            # Handle text extraction without OpenAI
            context.bot.send_message(chat_id=update.effective_chat.id, text="Please send the image you want to extract text from, and include 'extract text:' in the caption.")
        else:
            ai_response = get_ai_response(user_text)
            context.bot.send_message(chat_id=update.effective_chat.id, text=ai_response)

            # Log the interaction
            user_id = update.effective_user.id
            user_name = update.effective_user.username or update.effective_user.full_name
            log_interaction(user_id, user_name, 'text', user_text, ai_response)
    except Exception as e:
        logger.error(f"Error in handle_text: {e}", exc_info=True)
        context.bot.send_message(chat_id=update.effective_chat.id, text="Sorry, I couldn't process your message.")

def start(update, context):
    if not is_user_authorized(update):
        context.bot.send_message(chat_id=update.effective_chat.id, text="You are not authorized.")
        return
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Hello! I'm your AI tutor 'Merlin'. Send me a message, and I'll help you out!")

def main():
    # Create Updater and pass in bot token
    updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # Register handlers
    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(MessageHandler(Filters.voice, handle_voice))
    dp.add_handler(MessageHandler(Filters.photo, handle_photo))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))

    # Start the Bot using long polling
    updater.start_polling()

    # Run the bot until you press Ctrl-C
    updater.idle()

if __name__ == '__main__':
    main()
