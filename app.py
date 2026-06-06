import os
import base64
import io
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract

app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'tiff'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def preprocess_image(img):
    """Enhance image for better OCR accuracy."""
    # Convert to RGB if needed
    if img.mode not in ('RGB', 'L'):
        img = img.convert('RGB')
    
    # Upscale small images
    w, h = img.size
    if w < 1000 or h < 1000:
        scale = max(1000 / w, 1000 / h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    
    # Enhance sharpness and contrast
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    img = ImageEnhance.Contrast(img).enhance(1.5)
    
    return img

def extract_text(img, lang='por+eng'):
    """Extract text using Tesseract with multiple configs."""
    preprocessed = preprocess_image(img)
    
    # Try different PSM modes and pick best result
    configs = [
        f'--oem 3 --psm 3 -l {lang}',
        f'--oem 3 --psm 6 -l {lang}',
        f'--oem 3 --psm 11 -l {lang}',
    ]
    
    best_text = ""
    for cfg in configs:
        try:
            text = pytesseract.image_to_string(preprocessed, config=cfg)
            if len(text.strip()) > len(best_text.strip()):
                best_text = text
        except Exception:
            continue
    
    return best_text.strip()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/extract', methods=['POST'])
def extract():
    try:
        img = None
        
        # Handle base64 image (from camera capture)
        if request.is_json:
            data = request.get_json()
            if 'image' in data:
                img_data = data['image']
                if ',' in img_data:
                    img_data = img_data.split(',')[1]
                img_bytes = base64.b64decode(img_data)
                img = Image.open(io.BytesIO(img_bytes))
        
        # Handle file upload
        elif 'file' in request.files:
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'Nenhum ficheiro selecionado'}), 400
            if not allowed_file(file.filename):
                return jsonify({'error': 'Formato de ficheiro não suportado'}), 400
            img = Image.open(file.stream)
        
        else:
            return jsonify({'error': 'Nenhuma imagem recebida'}), 400
        
        # Extract text — try Portuguese+English, fallback to English only
        try:
            text = extract_text(img, lang='por+eng')
        except Exception:
            text = extract_text(img, lang='eng')
        
        if not text:
            return jsonify({
                'success': True,
                'text': '',
                'message': 'Nenhum texto detetado na imagem. Tente com uma imagem mais nítida.'
            })
        
        return jsonify({
            'success': True,
            'text': text,
            'char_count': len(text),
            'word_count': len(text.split())
        })
    
    except Exception as e:
        return jsonify({'error': f'Erro ao processar imagem: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
