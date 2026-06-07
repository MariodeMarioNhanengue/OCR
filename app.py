import os
import base64
import io
import sys
import glob
import json
from flask import Flask, request, jsonify, render_template, send_file
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
    candidates = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        r'C:\Tesseract-OCR\tesseract.exe',
        r'C:\tesseract\tesseract.exe',
    ]
    candidates += glob.glob(r'C:\Users\*\AppData\Local\Tesseract-OCR\tesseract.exe')
    candidates += glob.glob(r'C:\Users\*\AppData\Local\Programs\Tesseract-OCR\tesseract.exe')
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None

try:
    import pytesseract
    if os.name == 'nt':
        found = find_tesseract_windows()
        if found:
            pytesseract.pytesseract.tesseract_cmd = found
            TESSERACT_PATH = found
        env_cmd = os.environ.get('TESSERACT_CMD')
        if env_cmd and os.path.isfile(env_cmd):
            pytesseract.pytesseract.tesseract_cmd = env_cmd
            TESSERACT_PATH = env_cmd
    pytesseract.get_tesseract_version()
    TESSERACT_AVAILABLE = True
    print("✅ Tesseract OCR pronto")
except Exception as e:
    print(f"⚠️  Tesseract não disponível: {e}")

# ── pdf2image / Poppler setup ────────────────────────────────
PDF_AVAILABLE = False
POPPLER_PATH = None

def find_poppler_windows():
    candidates = [
        r'C:\poppler\Library\bin', r'C:\poppler\bin',
        r'C:\Program Files\poppler\Library\bin', r'C:\Program Files\poppler\bin',
    ]
    candidates += glob.glob(r'C:\Users\*\poppler*\Library\bin')
    candidates += glob.glob(r'C:\poppler*\Library\bin')
    import shutil
    if shutil.which('pdftoppm'):
        return None
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
        else:
            import shutil
            if not shutil.which('pdftoppm'):
                raise RuntimeError("Poppler não encontrado")
    convert_from_bytes(b'%PDF', poppler_path=poppler_path if os.name == 'nt' else None)
except RuntimeError as e:
    print(f"⚠️  PDF desactivado: {e}")
except Exception:
    from pdf2image import convert_from_bytes
    PDF_AVAILABLE = True
    print("✅ pdf2image disponível")

if not PDF_AVAILABLE:
    try:
        from pdf2image import convert_from_bytes
        PDF_AVAILABLE = True
    except ImportError:
        pass

# ── fpdf2 para geração de PDF ────────────────────────────────
PDF_GEN_AVAILABLE = False
try:
    from fpdf import FPDF
    PDF_GEN_AVAILABLE = True
    print("✅ fpdf2 disponível (download PDF activo)")
except ImportError:
    print("⚠️  fpdf2 não instalado: pip install fpdf2")

# ── Anthropic (IA) ───────────────────────────────────────────
ANTHROPIC_KEY = os.environ.get('ANTHROPIC_API_KEY', '')


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
    try:
        return extract_text_tesseract(img, lang='por+eng', handwriting=handwriting), 'por+eng'
    except Exception:
        try:
            return extract_text_tesseract(img, lang='eng', handwriting=handwriting), 'eng'
        except Exception as e2:
            raise RuntimeError(f"Falha OCR: {e2}")

def pdf_to_images(file_bytes):
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
        'pdf_gen_support': PDF_GEN_AVAILABLE,
        'poppler_path': POPPLER_PATH,
        'python_version': sys.version,
        'platform': os.name,
        'is_https': request.is_secure,
        'host': request.host,
        'protocol': request.scheme,
        'handwriting_support': TESSERACT_AVAILABLE,
        'ai_available': bool(ANTHROPIC_KEY),
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


# ── NOVO: Melhorar texto com IA (Claude) ─────────────────────
@app.route('/api/ai-enhance', methods=['POST'])
def ai_enhance():
    """
    Envia o texto extraído pelo OCR à API Claude para correcção e melhoria.
    O frontend passa { text, mode } onde mode pode ser:
      'correct'  — corrigir erros OCR e ortografia
      'clean'    — limpar e formatar
      'summarize'— resumir o conteúdo
      'translate'— traduzir para inglês
    """
    import urllib.request

    if not ANTHROPIC_KEY:
        return jsonify({
            'error': 'ANTHROPIC_API_KEY não configurada no servidor.',
            'hint': 'Defina a variável de ambiente ANTHROPIC_API_KEY antes de iniciar o servidor.'
        }), 503

    data = request.get_json(force=True, silent=True) or {}
    text = (data.get('text') or '').strip()
    mode = data.get('mode', 'correct')

    if not text:
        return jsonify({'error': 'Texto vazio'}), 400

    prompts = {
        'correct': (
            "Corrija os erros de OCR, ortografia e formatação do seguinte texto. "
            "Mantenha o conteúdo e idioma originais. Devolva apenas o texto corrigido, sem comentários."
        ),
        'clean': (
            "Limpe e formate o seguinte texto extraído por OCR: remova caracteres estranhos, "
            "corrija parágrafos quebrados e normalize o espaçamento. Devolva apenas o texto limpo."
        ),
        'summarize': (
            "Crie um resumo conciso do seguinte texto em português. "
            "Destaque os pontos principais. Devolva apenas o resumo."
        ),
        'translate': (
            "Traduza o seguinte texto para inglês de forma natural e precisa. "
            "Devolva apenas a tradução, sem comentários."
        ),
        'structure': (
            "Analise e estruture o seguinte texto extraído por OCR em secções lógicas com títulos. "
            "Corrija erros de OCR. Devolva apenas o texto estruturado em Markdown."
        ),
    }

    instruction = prompts.get(mode, prompts['correct'])
    user_message = f"{instruction}\n\n---\n{text}\n---"

    # Tenta modelos por ordem de preferência
    models_to_try = [
        "claude-haiku-4-5-20251001",
        "claude-haiku-3-5-20241022",
        "claude-3-haiku-20240307",
    ]

    last_error = None
    for model in models_to_try:
        payload = json.dumps({
            "model": model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": user_message}]
        }).encode('utf-8')

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                enhanced_text = result['content'][0]['text']
                return jsonify({
                    'success': True,
                    'text': enhanced_text,
                    'mode': mode,
                    'model_used': model,
                    'original_chars': len(text),
                    'result_chars': len(enhanced_text),
                })
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='replace')
            last_error = f'Modelo {model} -> HTTP {e.code}: {body}'
            print(f"aviso: {last_error}")
            if e.code == 401:
                return jsonify({'error': 'Chave API invalida ou expirada. Verifique ANTHROPIC_API_KEY.', 'detail': body}), 401
            continue
        except Exception as e:
            last_error = str(e)
            print(f"Erro com modelo {model}: {e}")
            continue

    return jsonify({'error': f'Todos os modelos falharam. Ultimo erro: {last_error}'}), 502


# ── NOVO: Download como PDF ───────────────────────────────────
@app.route('/api/download-pdf', methods=['POST'])
def download_pdf():
    """Gera um PDF a partir do texto e devolve-o para download."""
    if not PDF_GEN_AVAILABLE:
        return jsonify({
            'error': 'fpdf2 não instalado.',
            'hint': 'pip install fpdf2'
        }), 503

    data = request.get_json(force=True, silent=True) or {}
    text = (data.get('text') or '').strip()
    title = (data.get('title') or 'Texto Extraído OCR').strip()

    if not text:
        return jsonify({'error': 'Texto vazio'}), 400

    try:
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # Título
        pdf.set_font('Helvetica', 'B', 16)
        pdf.set_text_color(30, 30, 30)
        pdf.cell(0, 10, title.encode('latin-1', 'replace').decode('latin-1'), ln=True)
        pdf.ln(4)

        # Linha separadora
        pdf.set_draw_color(180, 180, 180)
        pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y())
        pdf.ln(6)

        # Corpo do texto
        pdf.set_font('Helvetica', '', 11)
        pdf.set_text_color(50, 50, 50)

        for line in text.split('\n'):
            safe_line = line.encode('latin-1', 'replace').decode('latin-1')
            pdf.multi_cell(0, 6, safe_line)

        pdf_bytes = pdf.output()
        buf = io.BytesIO(bytes(pdf_bytes))
        buf.seek(0)

        return send_file(
            buf,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='texto_extraido.pdf'
        )

    except Exception as e:
        import traceback
        return jsonify({'error': f'Erro ao gerar PDF: {e}', 'detail': traceback.format_exc()}), 500


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
        print("✅ A iniciar em HTTPS — https://localhost:5000")
    else:
        print("⚠️  A iniciar em HTTP")

    app.run(debug=True, host='0.0.0.0', port=5000, ssl_context=ssl_context)
