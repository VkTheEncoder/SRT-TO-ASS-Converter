import logging
import io
import re
from telegram import Update, InputFile
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ----------------------------
# Helper Functions for Conversion
# ----------------------------

def srt_time_to_ass(time_str: str) -> str:
    """
    Convert SRT time format (e.g., "00:00:05,000") to ASS time format (e.g., "0:00:05.00").
    """
    match = re.match(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})', time_str)
    if not match:
        return time_str  # fallback if parsing fails
    hours, minutes, seconds, millis = match.groups()
    hours = int(hours)
    minutes = int(minutes)
    seconds = int(seconds)
    centiseconds = int(millis) // 10  # convert ms to centiseconds
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"

def convert_srt_to_ass(srt_text: str) -> str:
    """
    Convert SRT subtitle text to ASS format using a fixed header with the custom style.
    """
    # ASS header with your updated custom style.
    header = (
        "[Script Info]\n"
        "Title: Converted Subtitles\n"
        "ScriptType: v4.00+\n"
        "Collisions: Normal\n"
        "PlayResX: 1280\n"
        "PlayResY: 720\n"
        "Timer: 100.0000\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Perfect World,Arial Rounded MT Bold,56,&H00FFFFFF,&H000000FF,&H00000000,&H76151518,-1,0,0,0,87,108,0,0,1,2.7,3.7,2,10,10,95,1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    dialogue_lines = []
    # Split the SRT by double newlines to get individual subtitle blocks.
    blocks = re.split(r'\n\s*\n', srt_text.strip())
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) >= 3:
            # The first line is the subtitle number (ignored)
            # The second line contains the time range.
            time_line = lines[1].strip()
            if " --> " not in time_line:
                continue
            start_str, end_str = time_line.split(" --> ")
            start_ass = srt_time_to_ass(start_str.strip())
            end_ass = srt_time_to_ass(end_str.strip())
            # The remaining lines are the subtitle text. Join them with \N for line breaks.
            text = "\\N".join(lines[2:])
            dialogue = (
                f"Dialogue: 0,{start_ass},{end_ass},Perfect World,,0,0,0,," + text
            )
            dialogue_lines.append(dialogue)
    ass_text = header + "\n".join(dialogue_lines)
    return ass_text

# ----------------------------
# Telegram Bot Handlers
# ----------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the /start command is issued."""
    await update.message.reply_text(
        "Hello! Send me an SRT file and I'll convert it to an ASS file with your custom style."
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle document uploads; convert SRT files to ASS files."""
    document = update.message.document
    if not document:
        return

    # Check if the file is an SRT file based on its filename.
    if not document.file_name.lower().endswith(".srt"):
        await update.message.reply_text("Please send a file with a .srt extension.")
        return

    await update.message.reply_text("Processing your SRT file...")

    try:
        # Download the file as bytes.
        file = await document.get_file()
        file_bytes = await file.download_as_bytearray()
        srt_text = file_bytes.decode("utf-8", errors="replace")

        # Convert SRT to ASS.
        ass_text = convert_srt_to_ass(srt_text)

        # Prepare the ASS file to send back.
        ass_io = io.BytesIO(ass_text.encode("utf-8"))
        ass_filename = document.file_name.rsplit(".", 1)[0] + ".ass"

        await update.message.reply_document(document=InputFile(ass_io, filename=ass_filename))
    except Exception as e:
        logger.exception("Error processing file: %s", e)
        await update.message.reply_text("Sorry, there was an error processing your file.")

# ----------------------------
# Main Function to Run the Bot
# ----------------------------

def main() -> None:
    # Replace 'YOUR_TELEGRAM_BOT_TOKEN' with your actual bot token.
    application = Application.builder().token("7070027599:AAHJ3zf_UZghJxf32n3bB2UMMb3-_NiC0II").build()

    # Handlers for commands and document uploads.
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Document.FileExtension("srt"), handle_document))

    application.run_polling()

if __name__ == "__main__":
    main()
