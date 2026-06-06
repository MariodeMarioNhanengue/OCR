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
    if img.mode not in ('RGB', 'L'):
        img = img.convert('RGB')
    w, h = img.size
    if w < 1000 or h < 1000:
        scale = max(1000 / w, 1000 / h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    img = ImageEnhance.Contrast(img).enhance(1.5)
    return img

def extract_text(img, lang='por+eng'):
    """Extract text using Tesseract with multiple configs."""
    preprocessed = preprocess_image(img)
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
        if request.is_json:
            data = request.get_json()
            if 'image' in data:
                img_data = data['image']
                if ',' in img_data:
                    img_data = img_data.split(',')[1]
                img_bytes = base64.b64decode(img_data)
                img = Image.open(io.BytesIO(img_bytes))
        elif 'file' in request.files:
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'Nenhum ficheiro selecionado'}), 400
            if not allowed_file(file.filename):
                return jsonify({'error': 'Formato de ficheiro não suportado'}), 400
            img = Image.open(file.stream)
        else:
            return jsonify({'error': 'Nenhuma imagem recebida'}), 400

        try:
            text = extract_text(img, lang='por+eng')
        except Exception:
            text = extract_text(img, lang='eng')

        if not text:
            return jsonify({
                'success': True,
                'text': '',
                'message': 'Nenhum texto detetado. Tente com uma imagem mais nítida.'
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
    # ── HTTPS via certificado auto-assinado ──────────────────────────────────
    # Os browsers bloqueiam acesso à câmara em HTTP puro.
    # Este bloco gera/reutiliza cert.pem + key.pem e serve via HTTPS.
    # Ao abrir no browser aparecerá um aviso "Conexão não segura" —
    # é esperado com certificados auto-assinados. Clique em
    # "Avançado" → "Continuar para o site" para aceitar.
    # --------------------------------------------------------------------
    ssl_cert = 'cert.pem'
    ssl_key  = 'key.pem'

    if not (os.path.exists(ssl_cert) and os.path.exists(ssl_key)):
        print("🔐 Certificado SSL não encontrado. A gerar...")
        try:
            import generate_cert
            generate_cert.generate()
        except Exception as e:
            print(f"⚠️  Não foi possível gerar certificado: {e}")
            print("   Execute manualmente: python generate_cert.py")
            print("   A iniciar em HTTP (câmara não funcionará em rede local)...")
            ssl_cert = None
            ssl_key  = None

    ssl_context = (ssl_cert, ssl_key) if ssl_cert else None

    if ssl_context:
        print("✅ A iniciar em HTTPS — câmara funcionará normalmente.")
        print("   Acesso: https://<SEU-IP>:5000")
        print("   ⚠️  Aceite o aviso de segurança do browser (certificado auto-assinado).")
    else:
        print("⚠️  A iniciar em HTTP — câmara bloqueada pelo browser.")

    app.run(
        debug=True,
        host='0.0.0.0',
        port=5000,
        ssl_context=ssl_context,
    )
