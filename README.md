# LeituraOCR

Extrai texto de imagens e PDFs via OCR — upload de ficheiro, câmara e PDF multipágina.

---

## ⚙️ Instalação no Windows

### 1. Python
Instale Python 3.10+ em https://www.python.org/downloads/  
✅ Marque **"Add Python to PATH"** durante a instalação.

### 2. Dependências Python
Abra o **Prompt de Comando** (cmd) e execute:
```
pip install flask flask-cors pillow pytesseract pdf2image pyngrok cryptography
```

### 3. Tesseract OCR
Descarregue o instalador em:  
https://github.com/UB-Mannheim/tesseract/wiki

- Execute o instalador
- Na secção **Additional language data**, seleccione **Portuguese**
- ✅ Marque **"Add to PATH"** (ou instale em `C:\Program Files\Tesseract-OCR\`)

### 4. Poppler (para suporte a PDF)
Descarregue em:  
https://github.com/oschwartz10612/poppler-windows/releases

- Extraia o ZIP
- Mova a pasta extraída para `C:\poppler\`  
  (o caminho final deve ser `C:\poppler\Library\bin\pdftoppm.exe`)

> **Alternativa:** Se colocar o poppler noutro sítio, defina a variável de ambiente:  
> `set POPPLER_PATH=C:\caminho\para\poppler\Library\bin`

---

## ▶️ Iniciar o servidor

### Opção A — ngrok (recomendado, funciona no telemóvel)
```
python start.py
```
O terminal mostrará um link `https://xxxx.ngrok-free.app`.  
Requer conta gratuita em https://ngrok.com:
```
ngrok config add-authtoken SEU_TOKEN_AQUI
```

### Opção B — HTTPS local (só PC na mesma rede)
```
python app.py
```
Acesse `https://localhost:5000` no browser.

---

## 🔧 Problemas comuns no Windows

| Problema | Solução |
|---|---|
| `tesseract is not installed` | Instale o Tesseract e marque "Add to PATH" |
| Tesseract instalado mas não encontrado | Defina `set TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe` |
| PDF não funciona | Instale o Poppler em `C:\poppler\` |
| `Port 5000 in use` | Feche outras aplicações na porta 5000, ou mude `port=5000` no app.py |
| Câmara não funciona | Use HTTPS (`python app.py`) ou ngrok |

---

## ⚠️ Por que a câmara precisa de HTTPS?
Os browsers bloqueiam `getUserMedia()` em HTTP por segurança, excepto em `localhost`.
