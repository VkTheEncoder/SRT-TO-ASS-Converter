import logging
import io
import re
import os
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ----------------------------
# Helper Functions
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
    Convert SRT subtitle text to ASS format using a fixed header with your custom style.
    """
    # ASS header with your provided style
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
        "Style: Default,HelveticaRounded LT Std BdCn,78,&H00FFFFFF,&H000000FF,&H00000000,&H96000000,0,0,0,0,100,100,0,0,1,3,4.5,2,60,60,65,1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    dialogue_lines = []
    # Split the SRT text into subtitle blocks (separated by blank lines)
    blocks = re.split(r'\n\s*\n', srt_text.strip())
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) >= 3:
            # Second line should contain the time range.
            time_line = lines[1].strip()
            if " --> " not in time_line:
                continue
            start_str, end_str = time_line.split(" --> ")
            start_ass = srt_time_to_ass(start_str.strip())
            end_ass = srt_time_to_ass(end_str.strip())
            # Combine remaining lines into dialogue text (using \N for line breaks)
            text = "\\N".join(lines[2:])
            # Use the "Default" style as defined in the header
            dialogue = f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,," + text
            dialogue_lines.append(dialogue)
    return header + "\n".join(dialogue_lines)

def update_ass_styles(ass_text: str) -> str:
    """
    Update (or insert) the [V4+ Styles] section in an ASS file to use the provided custom style.
    """
    # Our custom style header (exactly as provided)
    our_style_header = (
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Default,HelveticaRounded LT Std BdCn,78,&H00FFFFFF,&H000000FF,&H00000000,&H96000000,0,0,0,0,100,100,0,0,1,3,4.5,2,60,60,65,1\n"
    )
    # Look for the [V4+ Styles] section in the ASS file
    pattern = r"(?s)(\[V4\+ Styles\].*?)(\n\[|$)"
    if re.search(pattern, ass_text):
        # Replace the entire [V4+ Styles] section with our custom style header.
        new_text = re.sub(pattern, lambda m: our_style_header + m.group(2), ass_text, count=1)
        return new_text
    else:
        # If no [V4+ Styles] section found, try inserting after [Script Info]
        pattern_script = r"(?s)(\[Script Info\].*?)(\n\[|$)"
        match_script = re.search(pattern_script, ass_text)
        if match_script:
            insert_pos = match_script.end(1)
            new_text = ass_text[:insert_pos] + "\n" + our_style_header + ass_text[insert_pos:]
            return new_text
        else:
            # If neither section is found, simply prepend our style header
            return our_style_header + "\n" + ass_text

# ----------------------------
# Telegram Bot Handlers
# ----------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the /start command is issued."""
    await update.message.reply_text(
        "Hello! Send me an SRT or ASS file and I'll update it to use your custom style."
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle document uploads (SRT or ASS) and process them accordingly."""
    document = update.message.document
    if not document:
        return

    filename = document.file_name.lower()
    if not (filename.endswith(".srt") or filename.endswith(".ass")):
        await update.message.reply_text("Please send a file with a .srt or .ass extension.")
        return

    await update.message.reply_text("Processing your file...")

    try:
        file = await document.get_file()
        file_bytes = await file.download_as_bytearray()
        file_text = file_bytes.decode("utf-8", errors="replace")

        if filename.endswith(".srt"):
            # Convert SRT to ASS using our custom style header.
            processed_text = convert_srt_to_ass(file_text)
            new_extension = ".ass"
        else:
            # Update the styles in the existing ASS file.
            processed_text = update_ass_styles(file_text)
            new_extension = ".ass"  # keep it as ASS

        # Prepare the processed file to send back.
        processed_io = io.BytesIO(processed_text.encode("utf-8"))
        new_filename = document.file_name.rsplit(".", 1)[0] + new_extension
        await update.message.reply_document(document=InputFile(processed_io, filename=new_filename))
    except Exception as e:
        logger.exception("Error processing file: %s", e)
        await update.message.reply_text("Sorry, there was an error processing your file.")

def main() -> None:
    # Retrieve the Telegram bot token from environment variables.
    BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not BOT_TOKEN:
        raise ValueError("No TELEGRAM_BOT_TOKEN provided in environment variables!")

    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    # Accept files with .srt or .ass extensions.
    application.add_handler(MessageHandler(filters.Document.FileExtension("srt") | filters.Document.FileExtension("ass"), handle_document))
    application.run_polling()

if __name__ == "__main__":
    main()
