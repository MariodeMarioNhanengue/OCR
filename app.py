import os
import base64
import io
import sys
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from PIL import Image, ImageEnhance, ImageFilter

app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB max

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'tiff', 'tif'}

# ── Tesseract setup ─────────────────────────────────────────
TESSERACT_AVAILABLE = False
try:
    import pytesseract

    if os.name == 'nt':
        import glob
        candidates = [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        ]
        candidates += glob.glob(r'C:\Users\*\AppData\Local\Tesseract-OCR\tesseract.exe')
        candidates += glob.glob(r'C:\tesseract\tesseract.exe')

        for path in candidates:
            if os.path.isfile(path):
                pytesseract.pytesseract.tesseract_cmd = path
                print(f"✅ Tesseract encontrado em: {path}")
                break
        else:
            print("⚠️  Tesseract não encontrado nos caminhos padrão do Windows.")
            print("   Verifique onde instalou e edite a linha abaixo no app.py:")
            print("   pytesseract.pytesseract.tesseract_cmd = r'C:\\...\\tesseract.exe'")

    pytesseract.get_tesseract_version()
    TESSERACT_AVAILABLE = True
    print("✅ Tesseract OCR disponível")
except Exception as e:
    print(f"⚠️  Tesseract não encontrado: {e}")
    if os.name == 'nt':
        print("   → Windows: instale em https://github.com/UB-Mannheim/tesseract/wiki")
    else:
        print("   → Linux: sudo apt install tesseract-ocr tesseract-ocr-por")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def preprocess_image(img, handwriting=False):
    """Melhorar imagem para maior precisão OCR."""
    if img.mode not in ('RGB', 'L'):
        img = img.convert('RGB')

    w, h = img.size

    if w == 0 or h == 0:
        raise ValueError("Imagem com dimensões inválidas (largura ou altura = 0)")

    if handwriting:
        # Para caligrafia: resolução mais alta e pré-processamento suave
        if w < 1200 or h < 1200:
            scale = max(1200 / w, 1200 / h)
            new_w = min(int(w * scale), 6000)
            new_h = min(int(h * scale), 6000)
            img = img.resize((new_w, new_h), Image.LANCZOS)
        # Contraste moderado — evitar degradar letras manuscritas
        img = ImageEnhance.Contrast(img).enhance(1.3)
        img = ImageEnhance.Sharpness(img).enhance(1.5)
    else:
        # Para texto impresso: processamento padrão
        if w < 800 or h < 800:
            scale = max(800 / w, 800 / h)
            new_w = min(int(w * scale), 4000)
            new_h = min(int(h * scale), 4000)
            img = img.resize((new_w, new_h), Image.LANCZOS)
        img = ImageEnhance.Sharpness(img).enhance(2.0)
        img = ImageEnhance.Contrast(img).enhance(1.5)

    return img

def extract_text_tesseract(img, lang='por+eng', handwriting=False):
    """Extrair texto via Tesseract com múltiplas configs."""
    if not TESSERACT_AVAILABLE:
        raise RuntimeError("Tesseract não está instalado neste sistema.")

    preprocessed = preprocess_image(img, handwriting=handwriting)

    if handwriting:
        # Para caligrafia: usar OEM 1 (LSTM puro) que é melhor para manuscrito,
        # e PSM 6 (bloco de texto uniforme) ou PSM 4 (coluna de texto variável).
        # Também tentar PSM 11 (texto disperso) para notas soltas.
        configs = [
            f'--oem 1 --psm 6 -l {lang}',
            f'--oem 1 --psm 4 -l {lang}',
            f'--oem 1 --psm 11 -l {lang}',
            f'--oem 3 --psm 6 -l {lang}',  # fallback com OEM 3
        ]
    else:
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
        except Exception as e:
            print(f"Config {cfg} falhou: {e}")
            continue

    return best_text.strip()

def image_to_base64_str(img, fmt='JPEG'):
    """Converter imagem PIL para base64 string."""
    buf = io.BytesIO()
    if fmt == 'JPEG' and img.mode in ('RGBA', 'P', 'LA'):
        img = img.convert('RGB')
    img.save(buf, format=fmt, quality=92)
    return base64.b64encode(buf.getvalue()).decode('utf-8')

def open_image_safe(data: bytes) -> Image.Image:
    """Abrir imagem a partir de bytes com tratamento de erros."""
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
        return img
    except Exception as e:
        raise ValueError(f"Não foi possível abrir a imagem: {e}")

# ── Endpoints ───────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/diagnose', methods=['GET'])
def diagnose():
    """Endpoint de diagnóstico para verificar o estado do servidor."""
    info = {
        'tesseract': TESSERACT_AVAILABLE,
        'python_version': sys.version,
        'is_https': request.is_secure,
        'host': request.host,
        'protocol': request.scheme,
        'handwriting_support': TESSERACT_AVAILABLE,  # disponível se tesseract estiver instalado
    }
    if TESSERACT_AVAILABLE:
        try:
            info['tesseract_version'] = str(pytesseract.get_tesseract_version())
            langs = pytesseract.get_languages()
            info['tesseract_langs'] = langs
            info['has_portuguese'] = 'por' in langs
        except Exception as e:
            info['tesseract_error'] = str(e)
    return jsonify(info)

@app.route('/api/extract', methods=['POST'])
def extract():
    """Endpoint principal de extracção OCR."""
    try:
        img = None
        source = None
        handwriting = False  # modo caligrafia

        # ── 1. JSON com imagem base64 (câmara ou base64 directo) ──
        if request.is_json:
            data = request.get_json(force=True, silent=True) or {}
            if 'image' in data:
                img_data = data['image']
                if not img_data:
                    return jsonify({'error': 'Campo "image" está vazio'}), 400
                if ',' in img_data:
                    img_data = img_data.split(',', 1)[1]
                try:
                    img_bytes = base64.b64decode(img_data)
                    img = open_image_safe(img_bytes)
                    source = 'base64'
                except Exception as e:
                    return jsonify({'error': f'Base64 inválido: {e}'}), 400
                # Flag de caligrafia via JSON
                handwriting = bool(data.get('handwriting', False))
            else:
                return jsonify({'error': 'JSON recebido mas sem campo "image"'}), 400

        # ── 2. Multipart file upload ──
        elif 'file' in request.files:
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'Nenhum ficheiro selecionado'}), 400
            if not allowed_file(file.filename):
                return jsonify({
                    'error': f'Formato não suportado: {file.filename}. Use: {", ".join(ALLOWED_EXTENSIONS)}'
                }), 400
            try:
                file_bytes = file.read()
                if len(file_bytes) == 0:
                    return jsonify({'error': 'Ficheiro vazio'}), 400
                img = open_image_safe(file_bytes)
                source = 'file'
            except Exception as e:
                return jsonify({'error': f'Erro a ler ficheiro: {e}'}), 400
            # Flag de caligrafia via form field
            handwriting = request.form.get('handwriting', '0') in ('1', 'true', 'True')

        # ── 3. Raw bytes (content-type image/*) ──
        elif request.content_type and request.content_type.startswith('image/'):
            try:
                img_bytes = request.get_data()
                if not img_bytes:
                    return jsonify({'error': 'Corpo da requisição vazio'}), 400
                img = open_image_safe(img_bytes)
                source = 'raw'
            except Exception as e:
                return jsonify({'error': f'Erro a ler imagem raw: {e}'}), 400

        else:
            return jsonify({
                'error': 'Nenhuma imagem recebida. Use: JSON com campo "image" (base64), '
                         'multipart/form-data com campo "file", ou envie bytes raw com Content-Type: image/*'
            }), 400

        # ── OCR ──
        if not TESSERACT_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Tesseract OCR não está instalado neste servidor.',
                'install_hint': 'sudo apt install tesseract-ocr tesseract-ocr-por',
                'image_info': {
                    'size': img.size,
                    'mode': img.mode,
                    'source': source,
                }
            }), 503

        # Tentar primeiro com português+inglês, depois só inglês
        text = ""
        lang_used = ""
        try:
            text = extract_text_tesseract(img, lang='por+eng', handwriting=handwriting)
            lang_used = 'por+eng'
        except Exception as e1:
            try:
                text = extract_text_tesseract(img, lang='eng', handwriting=handwriting)
                lang_used = 'eng'
            except Exception as e2:
                return jsonify({'error': f'Falha OCR: {e2}'}), 500

        if not text:
            return jsonify({
                'success': True,
                'text': '',
                'message': 'Nenhum texto detetado. Tente com uma imagem mais nítida ou com mais contraste.',
                'lang_used': lang_used,
                'handwriting_mode': handwriting,
                'image_info': {'size': img.size, 'mode': img.mode},
            })

        return jsonify({
            'success': True,
            'text': text,
            'char_count': len(text),
            'word_count': len(text.split()),
            'lang_used': lang_used,
            'handwriting_mode': handwriting,
        })

    except Exception as e:
        import traceback
        return jsonify({
            'error': f'Erro interno: {str(e)}',
            'detail': traceback.format_exc()
        }), 500


if __name__ == '__main__':
    ssl_cert = 'cert.pem'
    ssl_key  = 'key.pem'

    if not (os.path.exists(ssl_cert) and os.path.exists(ssl_key)):
        print("🔐 Certificado SSL não encontrado. A gerar...")
        try:
            import generate_cert
            generate_cert.generate()
        except Exception as e:
            print(f"⚠️  Não foi possível gerar certificado: {e}")
            ssl_cert = None
            ssl_key  = None

    ssl_context = (ssl_cert, ssl_key) if ssl_cert else None

    if ssl_context:
        print("✅ A iniciar em HTTPS — câmara funcionará normalmente.")
        print("   Acesso local:     https://localhost:5000")
        print("   Acesso em rede:   https://<SEU-IP>:5000")
        print("   ⚠️  Aceite o aviso de segurança do browser (certificado auto-assinado).")
    else:
        print("⚠️  A iniciar em HTTP.")
        print("   Câmara bloqueada pelo browser (requer HTTPS).")
        print("   Upload de ficheiros funciona normalmente.")

    app.run(
        debug=True,
        host='0.0.0.0',
        port=5000,
        ssl_context=ssl_context,
    )
