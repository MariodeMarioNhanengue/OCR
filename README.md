# LeituraOCR

Extrai texto de imagens via OCR — upload de ficheiro e câmara.

---

## Instalação

```bash
pip install flask flask-cors pillow pytesseract cryptography pyngrok
```

Tesseract (motor OCR):
```bash
# Ubuntu/Debian
sudo apt install tesseract-ocr tesseract-ocr-por

# macOS
brew install tesseract
```

---

## ▶️ Iniciar o servidor

### Opção A — ngrok (recomendado, funciona no telemóvel sem avisos)

```bash
python start.py
```

O terminal mostrará um link `https://xxxx.ngrok-free.app` — abra esse link no telemóvel. A câmara funcionará imediatamente, sem aceitar nenhum aviso de segurança.

> Requer conta gratuita em https://ngrok.com e configurar o authtoken:
> ```bash
> ngrok config add-authtoken SEU_TOKEN_AQUI
> ```

---

### Opção B — HTTPS local (sem ngrok, só para PC na mesma rede)

```bash
python app.py
```

Acesse `https://10.198.1.169:5000` no browser do PC.

**No telemóvel com HTTPS local:**
- Chrome Android: na página de aviso, escreva `thisisunsafe` (sem clicar, só escrever)
- Safari iOS: Definições → Geral → VPN e Gestão de Dispositivos → confiar no certificado
- Firefox: Avançado → Aceitar o risco e continuar

---

## ⚠️ Por que a câmara precisa de HTTPS?

Os browsers bloqueiam `getUserMedia()` em HTTP por segurança, excepto em `localhost`.
Como a app corre em IP de rede local, é obrigatório HTTPS — ou ngrok.
