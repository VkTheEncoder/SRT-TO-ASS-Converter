import logging
import io
import re
import os
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
    Convert SRT subtitle text to ASS format using the provided style header.
    """
    # ASS header with your provided styles
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
        "Style: B1,Open Sans Semibold,130,&H00FFFFFF,&H0000FFFF,&H00000000,&H7F404040,-1,0,0,0,100,100,0,0,1,4.5,2.2,2,211,211,90,0\n"
        "Style: OS,Open Sans Semibold,74,&H00FFFFFF,&H0000FFFF,&H00000000,&H7F404040,-1,0,0,0,100,100,0,0,1,4.5,2.2,8,2,2,45,0\n"
        "Style: Default,HelveticaRounded LT Std BdCn,78,&H00FFFFFF,&H000000FF,&H00000000,&H96000000,0,0,0,0,100,100,0,0,1,3,4.5,2,60,60,65,1\n"
        "Style: Italics,Open Sans Semibold,81,&H00FFFFFF,&H000000FF,&H00020713,&H00000000,-1,-1,0,0,100,100,0,0,1,3.8,0,2,0,0,63,0\n"
        "Style: Ep Title,Open Sans Semibold,74,&H00FFFFFF,&H0000FFFF,&H00000000,&H7F404040,-1,0,0,0,100,100,0,0,1,4.5,2.2,3,514,211,61,0\n"
        "Style: Copy of Ep Title,Open Sans Semibold,74,&H00FFFFFF,&H0000FFFF,&H00000000,&H7F404040,-1,0,0,0,100,100,0,0,1,4.5,2.2,3,211,682,196,0\n"
        "Style: On Top,Open Sans Semibold,81,&H00FFFFFF,&H0000FFFF,&H00000000,&H7F404040,-1,0,0,0,100,100,0,0,1,4.5,2.2,8,61,61,65,0\n"
        "Style: Copy of OS,Open Sans Semibold,74,&H00FFFFFF,&H0000FFFF,&H00000000,&H7F404040,-1,0,0,0,100,100,0,0,1,4.5,2.2,9,61,61,61,0\n"
        "Style: DefaultLow,Open Sans Semibold,81,&H00FFFFFF,&H000000FF,&H00020713,&H00000000,-1,0,0,0,100,100,0,0,1,3.8,0,2,0,0,63,0\n"
        "Style: onscreensigns,Open Sans Semibold,74,&H00FFFFFF,&H0000FFFF,&H00000000,&H7F404040,-1,0,0,0,100,100,0,0,1,4.5,2.2,3,1207,120,61,0\n"
        "Style: onscreensign2,Open Sans Semibold,74,&H00FFFFFF,&H0000FFFF,&H00000000,&H7F404040,-1,0,0,0,100,100,0,0,1,4.5,2.2,1,91,120,119,0\n"
        "Style: TwCEN,Tw Cen MT Condensed Extra Bold,48,&HA5FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,85,75,0,0,1,0,0,5,15,15,15,1\n"
        "Style: EnCEN,Tw Cen MT Condensed Extra Bold,34,&H77FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,122,60,0,0,1,0,0,1,10,10,10,1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    dialogue_lines = []
    # Split the SRT text into subtitle blocks separated by one or more blank lines.
    blocks = re.split(r'\n\s*\n', srt_text.strip())
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) >= 3:
            # First line is typically the subtitle number (ignored)
            time_line = lines[1].strip()
            if " --> " not in time_line:
                continue
            start_str, end_str = time_line.split(" --> ")
            start_ass = srt_time_to_ass(start_str.strip())
            end_ass = srt_time_to_ass(end_str.strip())
            # Combine remaining lines as the dialogue text; use \N for line breaks.
            text = "\\N".join(lines[2:])
            # Use "Default" as the style for dialogues (change if needed).
            dialogue = f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,," + text
            dialogue_lines.append(dialogue)
    ass_text = header + "\n".join(dialogue_lines)
    return ass_text

# ----------------------------
# Telegram Bot Handlers
# ----------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message on /start command."""
    await update.message.reply_text(
        "Hello! Send me an SRT file and I'll convert it to an ASS file using your custom styles."
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming SRT file uploads and convert them to ASS format."""
    document = update.message.document
    if not document:
        return

    if not document.file_name.lower().endswith(".srt"):
        await update.message.reply_text("Please send a file with a .srt extension.")
        return

    await update.message.reply_text("Processing your SRT file...")

    try:
        file = await document.get_file()
        file_bytes = await file.download_as_bytearray()
        srt_text = file_bytes.decode("utf-8", errors="replace")

        # Convert SRT content to ASS format
        ass_text = convert_srt_to_ass(srt_text)

        # Create an in-memory file and send it back with an .ass extension.
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
    # Retrieve the bot token from an environment variable for security.
    BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not BOT_TOKEN:
        raise ValueError("No TELEGRAM_BOT_TOKEN provided in environment variables!")
    
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Document.FileExtension("srt"), handle_document))
    
    application.run_polling()

if __name__ == "__main__":
    main()
