import os
import base64
import io
import sys
import glob
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from PIL import Image, ImageEnhance

app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024  # 64MB max

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'tiff', 'tif', 'pdf'}

# ── Tesseract setup ─────────────────────────────────────────
TESSERACT_AVAILABLE = False
TESSERACT_PATH = None

def find_tesseract_windows():
    """Procura o executável do Tesseract em locais comuns no Windows."""
    candidates = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        r'C:\Tesseract-OCR\tesseract.exe',
        r'C:\tesseract\tesseract.exe',
    ]
    # Procurar em AppData de qualquer utilizador
    candidates += glob.glob(r'C:\Users\*\AppData\Local\Tesseract-OCR\tesseract.exe')
    candidates += glob.glob(r'C:\Users\*\AppData\Local\Programs\Tesseract-OCR\tesseract.exe')

    for path in candidates:
        if os.path.isfile(path):
            return path
    return None

try:
    import pytesseract

    if os.name == 'nt':
        # Primeiro tenta encontrar automaticamente
        found = find_tesseract_windows()
        if found:
            pytesseract.pytesseract.tesseract_cmd = found
            TESSERACT_PATH = found
            print(f"✅ Tesseract encontrado: {found}")
        else:
            # Tenta pelo PATH do sistema (caso o utilizador tenha adicionado)
            import shutil
            if shutil.which('tesseract'):
                print("✅ Tesseract encontrado no PATH do sistema")
            else:
                print("⚠️  Tesseract não encontrado automaticamente.")
                print("   Instale em: https://github.com/UB-Mannheim/tesseract/wiki")
                print("   Ou defina a variável TESSERACT_CMD no ambiente:")
                print("   set TESSERACT_CMD=C:\\Program Files\\Tesseract-OCR\\tesseract.exe")

        # Suporte a TESSERACT_CMD via variável de ambiente (override manual)
        env_cmd = os.environ.get('TESSERACT_CMD')
        if env_cmd and os.path.isfile(env_cmd):
            pytesseract.pytesseract.tesseract_cmd = env_cmd
            TESSERACT_PATH = env_cmd
            print(f"✅ Tesseract via TESSERACT_CMD: {env_cmd}")

    pytesseract.get_tesseract_version()
    TESSERACT_AVAILABLE = True
    print("✅ Tesseract OCR pronto")

except Exception as e:
    print(f"⚠️  Tesseract não disponível: {e}")
    if os.name == 'nt':
        print("   → Instale em: https://github.com/UB-Mannheim/tesseract/wiki")
        print("   → Marque 'Add to PATH' durante a instalação")
    else:
        print("   → sudo apt install tesseract-ocr tesseract-ocr-por")

# ── pdf2image / Poppler setup ────────────────────────────────
PDF_AVAILABLE = False
POPPLER_PATH = None

def find_poppler_windows():
    """Procura binários do Poppler em locais comuns no Windows."""
    candidates = [
        r'C:\poppler\Library\bin',
        r'C:\poppler\bin',
        r'C:\Program Files\poppler\Library\bin',
        r'C:\Program Files\poppler\bin',
        r'C:\Program Files (x86)\poppler\bin',
        r'C:\tools\poppler\Library\bin',
    ]
    candidates += glob.glob(r'C:\Users\*\poppler*\Library\bin')
    candidates += glob.glob(r'C:\poppler*\Library\bin')
    candidates += glob.glob(r'C:\poppler*\bin')
    # Procurar em PATH
    import shutil
    if shutil.which('pdftoppm'):
        return None  # já está no PATH, pdf2image encontra sozinho

    for path in candidates:
        if os.path.isdir(path) and os.path.isfile(os.path.join(path, 'pdftoppm.exe')):
            return path
    return None

try:
    from pdf2image import convert_from_bytes

    poppler_path = None
    if os.name == 'nt':
        poppler_path = find_poppler_windows()
        if poppler_path:
            POPPLER_PATH = poppler_path
            print(f"✅ Poppler encontrado: {poppler_path}")
        else:
            import shutil
            if shutil.which('pdftoppm'):
                print("✅ Poppler encontrado no PATH do sistema")
            else:
                print("⚠️  Poppler não encontrado. PDFs não serão suportados.")
                print("   Descarregue em: https://github.com/oschwartz10612/poppler-windows/releases")
                print("   Extraia e coloque em C:\\poppler\\")
                raise RuntimeError("Poppler não encontrado")

    # Teste rápido
    convert_from_bytes(b'%PDF', poppler_path=poppler_path if os.name == 'nt' else None)
except RuntimeError as e:
    print(f"⚠️  PDF desactivado: {e}")
except Exception:
    # O teste falhou por PDF inválido mas a biblioteca está presente
    from pdf2image import convert_from_bytes
    PDF_AVAILABLE = True
    print("✅ pdf2image disponível")

if not PDF_AVAILABLE:
    try:
        from pdf2image import convert_from_bytes
        PDF_AVAILABLE = True
        print("✅ pdf2image disponível (suporte a PDF activo)")
    except ImportError:
        print("⚠️  pdf2image não instalado: pip install pdf2image")


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def preprocess_image(img, handwriting=False):
    if img.mode not in ('RGB', 'L'):
        img = img.convert('RGB')
    w, h = img.size
    if w == 0 or h == 0:
        raise ValueError("Imagem com dimensões inválidas")

    if handwriting:
        if w < 1200 or h < 1200:
            scale = max(1200 / w, 1200 / h)
            img = img.resize((min(int(w * scale), 6000), min(int(h * scale), 6000)), Image.LANCZOS)
        img = ImageEnhance.Contrast(img).enhance(1.3)
        img = ImageEnhance.Sharpness(img).enhance(1.5)
    else:
        if w < 800 or h < 800:
            scale = max(800 / w, 800 / h)
            img = img.resize((min(int(w * scale), 4000), min(int(h * scale), 4000)), Image.LANCZOS)
        img = ImageEnhance.Sharpness(img).enhance(2.0)
        img = ImageEnhance.Contrast(img).enhance(1.5)
    return img

def extract_text_tesseract(img, lang='por+eng', handwriting=False):
    if not TESSERACT_AVAILABLE:
        raise RuntimeError("Tesseract não está instalado.")
    preprocessed = preprocess_image(img, handwriting=handwriting)

    configs = (
        [f'--oem 1 --psm 6 -l {lang}', f'--oem 1 --psm 4 -l {lang}',
         f'--oem 1 --psm 11 -l {lang}', f'--oem 3 --psm 6 -l {lang}']
        if handwriting else
        [f'--oem 3 --psm 3 -l {lang}', f'--oem 3 --psm 6 -l {lang}',
         f'--oem 3 --psm 11 -l {lang}']
    )

    best_text = ""
    for cfg in configs:
        try:
            text = pytesseract.image_to_string(preprocessed, config=cfg)
            if len(text.strip()) > len(best_text.strip()):
                best_text = text
        except Exception as e:
            print(f"Config {cfg} falhou: {e}")
    return best_text.strip()

def open_image_safe(data: bytes) -> Image.Image:
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
        return img
    except Exception as e:
        raise ValueError(f"Não foi possível abrir a imagem: {e}")

def ocr_image(img, handwriting=False):
    """Executar OCR numa imagem PIL. Devolve (text, lang_used)."""
    try:
        return extract_text_tesseract(img, lang='por+eng', handwriting=handwriting), 'por+eng'
    except Exception:
        try:
            return extract_text_tesseract(img, lang='eng', handwriting=handwriting), 'eng'
        except Exception as e2:
            raise RuntimeError(f"Falha OCR: {e2}")

def pdf_to_images(file_bytes):
    """Converter PDF em lista de imagens PIL."""
    kwargs = {'dpi': 200}
    if os.name == 'nt' and POPPLER_PATH:
        kwargs['poppler_path'] = POPPLER_PATH
    return convert_from_bytes(file_bytes, **kwargs)

# ── Endpoints ────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/diagnose', methods=['GET'])
def diagnose():
    info = {
        'tesseract': TESSERACT_AVAILABLE,
        'tesseract_path': TESSERACT_PATH,
        'pdf_support': PDF_AVAILABLE,
        'poppler_path': POPPLER_PATH,
        'python_version': sys.version,
        'platform': os.name,
        'is_https': request.is_secure,
        'host': request.host,
        'protocol': request.scheme,
        'handwriting_support': TESSERACT_AVAILABLE,
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
    try:
        img = None
        source = None
        handwriting = False

        if request.is_json:
            data = request.get_json(force=True, silent=True) or {}
            if 'image' not in data:
                return jsonify({'error': 'JSON sem campo "image"'}), 400
            img_data = data['image']
            if not img_data:
                return jsonify({'error': 'Campo "image" vazio'}), 400
            if ',' in img_data:
                img_data = img_data.split(',', 1)[1]
            try:
                img = open_image_safe(base64.b64decode(img_data))
                source = 'base64'
            except Exception as e:
                return jsonify({'error': f'Base64 inválido: {e}'}), 400
            handwriting = bool(data.get('handwriting', False))

        elif 'file' in request.files:
            file = request.files['file']
            if not file.filename:
                return jsonify({'error': 'Nenhum ficheiro selecionado'}), 400
            if not allowed_file(file.filename):
                return jsonify({'error': f'Formato não suportado. Use: {", ".join(ALLOWED_EXTENSIONS)}'}), 400

            ext = file.filename.rsplit('.', 1)[1].lower()
            file_bytes = file.read()
            if not file_bytes:
                return jsonify({'error': 'Ficheiro vazio'}), 400

            handwriting = request.form.get('handwriting', '0') in ('1', 'true', 'True')

            if ext == 'pdf':
                if not PDF_AVAILABLE:
                    return jsonify({
                        'error': 'Suporte a PDF não disponível.',
                        'install_hint': 'pip install pdf2image  +  instale Poppler (ver README)'
                    }), 503
                return _process_pdf(file_bytes, handwriting)

            try:
                img = open_image_safe(file_bytes)
                source = 'file'
            except Exception as e:
                return jsonify({'error': f'Erro a ler ficheiro: {e}'}), 400

        elif request.content_type and request.content_type.startswith('image/'):
            img_bytes = request.get_data()
            if not img_bytes:
                return jsonify({'error': 'Corpo vazio'}), 400
            try:
                img = open_image_safe(img_bytes)
                source = 'raw'
            except Exception as e:
                return jsonify({'error': str(e)}), 400
        else:
            return jsonify({'error': 'Nenhuma imagem recebida.'}), 400

        if not TESSERACT_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Tesseract OCR não está instalado.',
                'install_hint': 'https://github.com/UB-Mannheim/tesseract/wiki' if os.name == 'nt' else 'sudo apt install tesseract-ocr tesseract-ocr-por',
            }), 503

        try:
            text, lang_used = ocr_image(img, handwriting=handwriting)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

        if not text:
            return jsonify({
                'success': True, 'text': '',
                'message': 'Nenhum texto detetado. Tente com uma imagem mais nítida.',
                'lang_used': lang_used, 'handwriting_mode': handwriting,
            })

        return jsonify({
            'success': True, 'text': text,
            'char_count': len(text), 'word_count': len(text.split()),
            'lang_used': lang_used, 'handwriting_mode': handwriting,
        })

    except Exception as e:
        import traceback
        return jsonify({'error': f'Erro interno: {e}', 'detail': traceback.format_exc()}), 500


@app.route('/api/extract-pdf', methods=['POST'])
def extract_pdf():
    if not PDF_AVAILABLE:
        hint = 'pip install pdf2image  +  Poppler: https://github.com/oschwartz10612/poppler-windows/releases' if os.name == 'nt' \
               else 'pip install pdf2image  +  apt install poppler-utils'
        return jsonify({'error': 'Suporte a PDF não disponível.', 'install_hint': hint}), 503
    if not TESSERACT_AVAILABLE:
        return jsonify({'error': 'Tesseract não instalado.'}), 503
    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum ficheiro PDF enviado'}), 400

    file = request.files['file']
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext != 'pdf':
        return jsonify({'error': 'Este endpoint aceita apenas ficheiros PDF'}), 400

    file_bytes = file.read()
    if not file_bytes:
        return jsonify({'error': 'Ficheiro PDF vazio'}), 400

    handwriting = request.form.get('handwriting', '0') in ('1', 'true', 'True')
    return _process_pdf(file_bytes, handwriting)


def _process_pdf(file_bytes, handwriting=False):
    try:
        pages = pdf_to_images(file_bytes)
    except Exception as e:
        hint = ''
        if os.name == 'nt' and not POPPLER_PATH:
            hint = ' Instale Poppler: https://github.com/oschwartz10612/poppler-windows/releases e extraia em C:\\poppler\\'
        return jsonify({'error': f'Não foi possível converter o PDF: {e}.{hint}'}), 400

    if not pages:
        return jsonify({'error': 'PDF sem páginas'}), 400

    all_texts, errors, lang_used = [], [], ''
    for i, page_img in enumerate(pages):
        try:
            text, lang = ocr_image(page_img, handwriting=handwriting)
            lang_used = lang
            all_texts.append({'page': i + 1, 'text': text,
                               'char_count': len(text), 'word_count': len(text.split())})
        except Exception as e:
            errors.append({'page': i + 1, 'error': str(e)})

    full_text = '\n\n'.join(
        f"--- Página {p['page']} ---\n{p['text']}" for p in all_texts if p['text'].strip()
    )

    return jsonify({
        'success': True, 'text': full_text, 'pages': all_texts,
        'total_pages': len(pages), 'char_count': len(full_text),
        'word_count': len(full_text.split()), 'lang_used': lang_used,
        'handwriting_mode': handwriting, 'errors': errors,
    })


if __name__ == '__main__':
    ssl_cert, ssl_key = 'cert.pem', 'key.pem'

    if not (os.path.exists(ssl_cert) and os.path.exists(ssl_key)):
        print("🔐 A gerar certificado SSL...")
        try:
            import generate_cert
            generate_cert.generate()
        except Exception as e:
            print(f"⚠️  Certificado não gerado: {e}")
            ssl_cert = ssl_key = None

    ssl_context = (ssl_cert, ssl_key) if ssl_cert else None

    if ssl_context:
        print("✅ A iniciar em HTTPS")
        print("   https://localhost:5000")
    else:
        print("⚠️  A iniciar em HTTP (câmara bloqueada pelo browser)")

    app.run(debug=True, host='0.0.0.0', port=5000, ssl_context=ssl_context)
