# AI Tutor Telegram Bot Project

## Overview
This project is an AI-powered Telegram bot named Merlin, designed to assist users by providing helpful and succinct answers. The bot can handle text messages, voice messages, images, and can generate images based on user prompts.
The bot now supports user authorization based on a list defined in the config.ini file. Only authorized users can interact with the bot.

### Features
1 User Authorization:
- Access Control: Only users listed in the `AUTHORIZED_USERS` configuration can use the bot.
- ![image](https://github.com/user-attachments/assets/96417927-41a7-4c0f-a2da-15f98214c0d2)
- Unauthorized Access: If an unauthorized user tries to interact with the bot, they receive a message saying "You are not authorized."

2 Text Interaction:
- Users can send text messages, and Merlin will respond with helpful answers generated using OpenAI's GPT-4 model.
- ![image](https://github.com/user-attachments/assets/1713da47-5f0f-4afa-9ccb-408925b0d565)
  
3 Voice Interaction:
- Users can send voice messages.
- ![image](https://github.com/user-attachments/assets/2b2ecf3b-5236-43b6-a5c0-ef99feb2c9d5)
- The bot transcribes the voice message using OpenAI's Whisper model.
- Generates a response using GPT-4.
- Sends back both the text response and an audio file of the response using text-to-speech.

4 Image Interaction:
- Users can send images with or without captions.
- The bot extracts text from the image using OCR (Tesseract).
- ![image](https://github.com/user-attachments/assets/11d5ac8d-1b92-4d0e-9a1b-265e26bc0b42)
- Includes any caption text provided by the user.
- Combines the extracted text and caption, and generates a response using GPT-4.

5 Image Generation:
- Users can request image generation by sending a message starting with `generate image:`.
- ![image](https://github.com/user-attachments/assets/7f781e35-a0fe-4f29-8129-b77e7bde25cf)
- The bot uses OpenAI's image generation API to create an image based on the provided prompt.
- Sends the generated image back to the user.

6 Text Extraction from Images:
- Users can extract text from images without involving OpenAI by sending an image with the caption starting with extract text:.
- The bot processes the image using Tesseract OCR and sends back the extracted text.

7 Logging and Database Interaction:
- All interactions are logged into a `SQL Server` database for record-keeping and analysis.
- Includes user ID, username, message type, user message, and bot response.

8 Configuration File:
- Sensitive information like API keys, tokens, and authorized users are stored in a `config.ini` file.
- Makes it easier to manage configurations without altering the main script.

9 Enhanced Logging and Error Handling:
- The bot includes detailed logging for easier debugging and monitoring.
- Exception handling ensures the bot remains operational even when unexpected errors occur.

## Setup Instructions
### Prerequisites
- Python 3.x
- Telegram account and a bot token from BotFather
- OpenAI API key with access to GPT-4 and image generation
- SQL Server instance for logging interactions
- Tesseract OCR installed on your system
- Required Python packages:
  - python-telegram-bot
  - openai
  - gTTS
  - pytesseract
  - pyodbc
  - pydub
  - requests
  - configparser
  - Installation Steps

1 Clone the Repository:

```
git clone https://github.com/JordiCorbilla/AI-Tutor.git
cd ai-tutor
```

2 Install Required Packages:

```
pip install -r requirements.txt
```

3 Set Up Configuration File:

```
[TELEGRAM]
BOT_TOKEN = your-telegram-bot-token
AUTHORIZED_USERS = user1,user2,user3

[OPENAI]
API_KEY = your-openai-api-key

[DATABASE]
SERVER = your-database-server
DATABASE = your-database-name
DRIVER = your-database-driver
```

- Replace placeholders with your actual configuration values.
- AUTHORIZED_USERS: Provide a comma-separated list of authorized usernames, full names, or user IDs.

4 Install Tesseract OCR:
- Windows: Download and install from https://github.com/UB-Mannheim/tesseract/wiki.

5 Run the bot:

```
PS C:\repo\AI-Tutor\venv\Scripts> & c:/repo/AI-Tutor/venv/Scripts/python.exe c:/repo/AI-Tutor/ai_tutor_telegram_bot.py
```

### Usage
- Start the Bot:
  - Open Telegram and start a chat with your bot.
  - Send /start to receive a greeting message.
- User Authorization:
  - Only users listed in the AUTHORIZED_USERS can interact with the bot.
  - Unauthorized users will receive "You are not authorized."
- Text Messages:
  - Send any text message, and the bot will reply with an AI-generated response.
- Voice Messages:
  - Send a voice message.
  - The bot will transcribe it, generate a response, and send back both text and audio.
- Images with Optional Captions:
  - Send an image.
  - Optionally include a caption.
  - The bot will extract text from the image and combine it with the caption to generate a response.
- Image Generation:
  - Send a message starting with generate image: followed by your prompt.
  - Example: generate image: a futuristic cityscape at sunset
  - The bot will generate an image based on your prompt and send it back.
- Text Extraction from Images:
  - Send an image with the caption starting with extract text:.
  - The bot will extract text from the image and send it back to you.

### Logging and Monitoring
- Logs:
  - All logs are written to bot.log in the project directory.
- Database:
  - Interactions are logged into the Interactions table in your specified SQL Server database.
- Unauthorized Access Attempts:
  - Unauthorized access attempts are logged with user details for security auditing.


### Error Handling
- The bot is designed to handle exceptions gracefully.
- In case of errors, appropriate messages are sent to the user without exposing technical details.
- Detailed error information is logged for developers to review.

### Contributing
- Contributions are welcome! Feel free to open issues or submit pull requests.
- Please ensure that your code adheres to the existing style and includes necessary logging and error handling.
