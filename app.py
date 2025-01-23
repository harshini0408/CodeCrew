from flask import Flask, request, send_file, jsonify, render_template
from deep_translator import GoogleTranslator
import pdfplumber
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.units import inch
from gtts import gTTS
import tempfile
import os
import io
import re

app = Flask(__name__)

FONT_PATHS = {
    "default": "static/fonts/NotoSans-Regular.ttf",
    "hi": "static/fonts/NotoSansDevanagari-Regular.ttf",
    "ta": "static/fonts/NotoSansTamil-Regular.ttf",
    "ml": "static/fonts/NotoSansMalayalam-Regular.ttf",
    "kn": "static/fonts/NotoSansKannada-Regular.ttf",
    "gu": "static/fonts/Gujarati-Regular.ttf",
    "pa": "static/fonts/NotoSans-Regular.ttf",
    "or": "static/fonts/NotoSansOriya-Regular.ttf",
    "bn": "static/fonts/NotoSansBengali-Regular.ttf",
    "te": "static/fonts/NotoSansTelugu-Regular.ttf",
}

# Language code mapping for gTTS
GTTS_LANG_MAP = {
    'hi': 'hi',  # Hindi
    'ta': 'ta',  # Tamil
    'ml': 'ml',  # Malayalam
    'kn': 'kn',  # Kannada
    'gu': 'gu',  # Gujarati
    'pa': 'pa',  # Punjabi
    'or': 'or',  # Oriya
    'bn': 'bn',  # Bengali
    'te': 'te',  # Telugu
}

for lang, font_path in FONT_PATHS.items():
    try:
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont(lang, font_path))
    except Exception as e:
        print(f"Error registering font {lang}: {e}")

def clean_text(text):
    return re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', '', str(text))).strip()

def safe_translate_text(text, dest_lang):
    if not text or len(text.strip()) < 1:
        return ""
    
    try:
        cleaned_text = clean_text(text)
        translator = GoogleTranslator(source='auto', target=dest_lang)
        return translator.translate(cleaned_text)
    except Exception as e:
        print(f"Translation error: {e}")
        return text

def generate_audio(text, lang):
    """Generate audio for translated text"""
    # Fallback to English if language not supported by gTTS
    gtts_lang = GTTS_LANG_MAP.get(lang, 'en')
    
    try:
        # Create temporary audio file
        audio_filename = f"translated_audio_{os.urandom(8).hex()}.mp3"
        audio_filepath = os.path.join('static', 'downloads', audio_filename)
        
        # Generate audio
        tts = gTTS(text=text, lang=gtts_lang)
        tts.save(audio_filepath)
        
        return audio_filename
    except Exception as e:
        print(f"Audio generation error: {e}")
        return None

@app.route('/translate', methods=['POST'])
def translate_pdf():
    if 'file' not in request.files or 'language' not in request.form:
        return jsonify({"error": "File and language are required"}), 400

    file = request.files['file']
    target_lang = request.form['language']
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_input:
            file.save(temp_input.name)
        
        output_buffer = io.BytesIO()
        c = canvas.Canvas(output_buffer, pagesize=letter)
        
        original_text = []
        translated_text = []

        with pdfplumber.open(temp_input.name) as pdf:
            for page in pdf.pages:
                text_lines = page.extract_text_lines()
                
                c.setFont(target_lang, 10)

                for line in text_lines:
                    try:
                        x = line['x0']
                        y = letter[1] - line['top']
                        
                        original_line = line.get('text', '').strip()
                        original_text.append(original_line)
                        
                        translated_line = safe_translate_text(original_line, target_lang)
                        translated_text.append(translated_line)
                        
                        c.drawString(x, y, translated_line)
                    except Exception as line_error:
                        print(f"Error processing line: {line_error}")

                # Preserve images
                for img in page.images:
                    try:
                        x0, top, x1, bottom = img["x0"], img["top"], img["x1"], img["bottom"]
                        width, height = x1 - x0, bottom - top

                        if 0 <= x0 <= letter[0] and 0 <= (letter[1] - top - height) <= letter[1]:
                            bbox_image = page.within_bbox((x0, top, x1, bottom)).to_image()
                            img_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                            bbox_image.save(img_temp.name, format="PNG")
                            c.drawImage(img_temp.name, x0, letter[1] - top - height, width, height)
                            os.unlink(img_temp.name)
                    except Exception as img_error:
                        print(f"Error processing image: {img_error}")

                c.showPage()

        c.save()
        output_buffer.seek(0)

        # Generate a unique filename for PDF
        filename = f"translated_{os.urandom(8).hex()}.pdf"
        with open(os.path.join('static', 'downloads', filename), 'wb') as f:
            f.write(output_buffer.getvalue())

        # Generate audio file
        full_translated_text = "\n".join(translated_text)
        audio_filename = generate_audio(full_translated_text, target_lang)

        return jsonify({
            "original_text": "\n".join(original_text),
            "translated_text": full_translated_text,
            "filename": filename,
            "audio_filename": audio_filename
        })

    except Exception as e:
        print(f"Translation error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if 'temp_input' in locals() and os.path.exists(temp_input.name):
            os.unlink(temp_input.name)

@app.route('/download/<filename>')
def download_pdf(filename):
    return send_file(os.path.join('static', 'downloads', filename), 
                     as_attachment=True, 
                     mimetype='application/pdf')

@app.route('/audio/<filename>')
def download_audio(filename):
    return send_file(os.path.join('static', 'downloads', filename), 
                     as_attachment=True, 
                     mimetype='audio/mpeg')

@app.route('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    # Ensure downloads directory exists
    os.makedirs(os.path.join('static', 'downloads'), exist_ok=True)
    app.run(debug=True, host='0.0.0.0', port=5000)