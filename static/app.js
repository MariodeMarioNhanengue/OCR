/* ============================================================
   LeituraOCR — app.js (versão corrigida)
   Melhorias:
   - Diagnóstico automático ao carregar
   - Câmara com detecção HTTPS clara
   - Melhor tratamento de erros
   - Feedback detalhado ao utilizador
   ============================================================ */

const API         = '/api/extract';
const API_DIAG    = '/api/diagnose';

// ── State ──────────────────────────────────────────────────
let currentFile    = null;
let currentCamData = null;
let activeTab      = 'upload';
let stream         = null;
let diagInfo       = null;

// ── Elements ───────────────────────────────────────────────
const fileInput      = document.getElementById('fileInput');
const dropZone       = document.getElementById('dropZone');
const uploadPreview  = document.getElementById('uploadPreview');
const uploadImg      = document.getElementById('uploadPreviewImg');
const clearUpload    = document.getElementById('clearUpload');
const extractBtn     = document.getElementById('extractBtn');
const extractLabel   = document.getElementById('extractLabel');
const extractSpinner = document.getElementById('extractSpinner');
const outputText     = document.getElementById('outputText');
const emptyState     = document.getElementById('emptyState');
const stats          = document.getElementById('stats');
const copyBtn        = document.getElementById('copyBtn');
const downloadBtn    = document.getElementById('downloadBtn');
const toastEl        = document.getElementById('toast');
const themeToggle    = document.getElementById('themeToggle');
const themeLabel     = document.getElementById('themeLabel');

// Camera
const camPlaceholder = document.getElementById('camPlaceholder');
const camHttpsNote   = document.getElementById('camHttpsNote');
const btnActivate    = document.getElementById('btnActivate');
const camVideo       = document.getElementById('camVideo');
const camCanvas      = document.getElementById('camCanvas');
const camPreview     = document.getElementById('camPreview');
const camPreviewImg  = document.getElementById('camPreviewImg');
const clearCam       = document.getElementById('clearCam');
const btnCapture     = document.getElementById('btnCapture');
const btnRetake      = document.getElementById('btnRetake');

// ── Diagnóstico inicial ────────────────────────────────────
async function runDiagnosis() {
  try {
    const res = await fetch(API_DIAG);
    diagInfo = await res.json();
    console.log('Diagnóstico servidor:', diagInfo);

    if (!diagInfo.tesseract) {
      showBanner('warning',
        '⚠️ Tesseract OCR não instalado no servidor. ' +
        'Execute: <code>sudo apt install tesseract-ocr tesseract-ocr-por</code>'
      );
    } else if (diagInfo.has_portuguese === false) {
      showBanner('info',
        'ℹ️ Tesseract instalado mas sem suporte a Português. ' +
        'Execute: <code>sudo apt install tesseract-ocr-por</code>'
      );
    }
  } catch (e) {
    console.warn('Não foi possível contactar /api/diagnose:', e);
  }
}

function showBanner(type, html) {
  let banner = document.getElementById('diagBanner');
  if (!banner) {
    banner = document.createElement('div');
    banner.id = 'diagBanner';
    banner.style.cssText = `
      padding: 12px 20px; margin: 12px 0; border-radius: 8px; font-size: 13px;
      background: ${type === 'warning' ? 'rgba(255,180,0,0.12)' : 'rgba(80,160,255,0.1)'};
      border: 1px solid ${type === 'warning' ? 'rgba(255,180,0,0.3)' : 'rgba(80,160,255,0.3)'};
      color: var(--text-primary, #eee);
    `;
    const main = document.querySelector('main');
    if (main) main.prepend(banner);
  }
  banner.innerHTML = html;
}

// ── Theme ──────────────────────────────────────────────────
const html = document.documentElement;
let isDark = true;

themeToggle.addEventListener('click', () => {
  isDark = !isDark;
  html.setAttribute('data-theme', isDark ? 'dark' : 'light');
  themeLabel.textContent = isDark ? 'Claro' : 'Escuro';
});

// ── Toast ──────────────────────────────────────────────────
function showToast(msg, type = '') {
  toastEl.textContent = msg;
  toastEl.className = 'toast show' + (type ? ' ' + type : '');
  clearTimeout(toastEl._t);
  toastEl._t = setTimeout(() => toastEl.classList.remove('show'), 3500);
}

// ── Tabs ───────────────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const tab = btn.dataset.tab;
    if (tab === activeTab) return;

    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + tab).classList.add('active');
    activeTab = tab;

    if (tab !== 'camera') stopStream();
    updateExtractBtn();
  });
});

// ── Upload / Drop ──────────────────────────────────────────
dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', e => {
  e.preventDefault(); dropZone.classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  if (file) handleFile(file);
});
fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) handleFile(fileInput.files[0]);
});

clearUpload.addEventListener('click', () => {
  currentFile = null;
  uploadPreview.classList.add('hidden');
  dropZone.classList.remove('hidden');
  fileInput.value = '';
  updateExtractBtn();
});

function handleFile(file) {
  // Aceitar qualquer tipo de imagem (não apenas os com MIME correcto)
  const isImage = file.type.startsWith('image/') ||
    /\.(png|jpe?g|gif|bmp|webp|tiff?|heic|heif)$/i.test(file.name);

  if (!isImage) {
    showToast('Ficheiro não reconhecido como imagem. Formatos suportados: PNG, JPG, WEBP, BMP, TIFF');
    return;
  }

  if (file.size > 32 * 1024 * 1024) {
    showToast('Ficheiro demasiado grande (máx. 32 MB)');
    return;
  }

  currentFile = file;
  const reader = new FileReader();
  reader.onerror = () => showToast('Erro ao ler o ficheiro');
  reader.onload = e => {
    uploadImg.src = e.target.result;
    dropZone.classList.add('hidden');
    uploadPreview.classList.remove('hidden');
    updateExtractBtn();
    showToast('Imagem carregada!', 'accent');
  };
  reader.readAsDataURL(file);
}

// ── Camera ─────────────────────────────────────────────────
function isSecureContext() {
  return (
    location.protocol === 'https:' ||
    location.hostname === 'localhost' ||
    location.hostname === '127.0.0.1' ||
    location.hostname.endsWith('.local')
  );
}

btnActivate.addEventListener('click', async () => {
  if (!isSecureContext()) {
    camHttpsNote.style.display = 'block';
    camHttpsNote.innerHTML = `
      ⚠️ <strong>Câmara bloqueada.</strong><br>
      O browser exige HTTPS para aceder à câmara.<br><br>
      <strong>Solução:</strong><br>
      1. Inicie o servidor com <code>python app.py</code> (gera certificado SSL automático)<br>
      2. Aceda via <code>https://&lt;SEU-IP&gt;:5000</code><br>
      3. Aceite o aviso de segurança do browser<br><br>
      <em>Alternativa: use o <strong>separador Upload</strong> para enviar fotos tiradas noutro dispositivo.</em>
    `;
    showToast('Câmara requer HTTPS. Ver instruções abaixo.', 'error');
    return;
  }

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    showToast('Câmara não suportada neste browser');
    return;
  }

  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: { ideal: 'environment' }, // câmara traseira em mobile
        width:  { ideal: 1920 },
        height: { ideal: 1080 },
      }
    });

    camVideo.srcObject = stream;
    camPlaceholder.classList.add('hidden');
    camVideo.classList.remove('hidden');
    btnCapture.classList.remove('hidden');
    showToast('Câmara activada!', 'accent');

  } catch (err) {
    let msg = 'Não foi possível aceder à câmara.';
    if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
      msg = 'Permissão negada. Autorize o acesso à câmara nas definições do browser.';
    } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
      msg = 'Nenhuma câmara encontrada neste dispositivo.';
    } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
      msg = 'Câmara em uso por outra aplicação.';
    } else if (err.name === 'OverconstrainedError') {
      // Tentar sem constraints de resolução
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: true });
        camVideo.srcObject = stream;
        camPlaceholder.classList.add('hidden');
        camVideo.classList.remove('hidden');
        btnCapture.classList.remove('hidden');
        return;
      } catch (e2) {
        msg = 'Câmara não suporta as configurações pedidas.';
      }
    }
    showToast(msg);
    console.error('Camera error:', err);
  }
});

btnCapture.addEventListener('click', () => {
  const w = camVideo.videoWidth  || 1280;
  const h = camVideo.videoHeight || 720;
  camCanvas.width  = w;
  camCanvas.height = h;
  camCanvas.getContext('2d').drawImage(camVideo, 0, 0, w, h);

  // Usar qualidade mais alta para melhor OCR
  const dataUrl = camCanvas.toDataURL('image/jpeg', 0.95);
  currentCamData = dataUrl;

  camPreviewImg.src = dataUrl;
  camVideo.classList.add('hidden');
  camPreview.classList.remove('hidden');
  btnCapture.classList.add('hidden');
  btnRetake.classList.remove('hidden');

  stopStream();
  updateExtractBtn();
  showToast('Foto capturada!', 'accent');
});

btnRetake.addEventListener('click', async () => {
  currentCamData = null;
  camPreview.classList.add('hidden');
  btnRetake.classList.add('hidden');
  updateExtractBtn();

  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: 'environment' } }
    });
    camVideo.srcObject = stream;
    camVideo.classList.remove('hidden');
    btnCapture.classList.remove('hidden');
  } catch (err) {
    camPlaceholder.classList.remove('hidden');
    showToast('Erro ao reactivar câmara: ' + err.message);
  }
});

clearCam.addEventListener('click', () => {
  currentCamData = null;
  camPreview.classList.add('hidden');
  btnRetake.classList.add('hidden');
  camPlaceholder.classList.remove('hidden');
  stopStream();
  updateExtractBtn();
});

function stopStream() {
  if (stream) {
    stream.getTracks().forEach(t => t.stop());
    stream = null;
  }
  camVideo.classList.add('hidden');
  camVideo.srcObject = null;
}

// ── Extract Button state ───────────────────────────────────
function updateExtractBtn() {
  const hasUpload = activeTab === 'upload' && currentFile !== null;
  const hasCam    = activeTab === 'camera' && currentCamData !== null;
  extractBtn.disabled = !(hasUpload || hasCam);
}

// ── Extract ────────────────────────────────────────────────
extractBtn.addEventListener('click', async () => {
  if (extractBtn.disabled) return;
  setLoading(true);

  try {
    let res;

    if (activeTab === 'upload' && currentFile) {
      // Enviar como multipart/form-data
      const form = new FormData();
      form.append('file', currentFile);
      res = await fetch(API, {
        method: 'POST',
        body: form,
        // NÃO definir Content-Type — o browser faz isso automaticamente com o boundary
      });

    } else if (activeTab === 'camera' && currentCamData) {
      // Enviar como JSON com base64
      res = await fetch(API, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: currentCamData }),
      });
    } else {
      showToast('Nenhuma imagem disponível');
      setLoading(false);
      return;
    }

    let data;
    try {
      data = await res.json();
    } catch (parseErr) {
      showToast('Erro: resposta inválida do servidor');
      setLoading(false);
      return;
    }

    if (!res.ok || data.error) {
      const errMsg = data.error || `Erro HTTP ${res.status}`;
      showToast('Erro: ' + errMsg);
      console.error('Detalhes do erro:', data);

      // Mostrar dica de instalação se tesseract não estiver disponível
      if (data.install_hint) {
        showBanner('warning',
          `⚠️ Tesseract não instalado. Execute no terminal: <code>${data.install_hint}</code>`
        );
      }
      setLoading(false);
      return;
    }

    const text = data.text || '';
    outputText.value = text;
    emptyState.style.display = text ? 'none' : '';

    if (text) {
      const langLabel = data.lang_used ? ` · ${data.lang_used}` : '';
      stats.textContent = `${data.word_count} palavras · ${data.char_count} caracteres${langLabel}`;
      showToast('Texto extraído com sucesso!', 'accent');
    } else {
      stats.textContent = '';
      const msg = data.message || 'Nenhum texto detectado. Tente uma imagem mais nítida.';
      showToast(msg);
    }

  } catch (err) {
    if (err.name === 'TypeError' && err.message.includes('fetch')) {
      showToast('Erro: não foi possível contactar o servidor');
    } else {
      showToast('Erro: ' + err.message);
    }
    console.error(err);
  }

  setLoading(false);
});

function setLoading(on) {
  extractBtn.disabled = on;
  extractLabel.textContent = on ? 'A extrair...' : 'Extrair Texto';
  extractSpinner.classList.toggle('hidden', !on);
}

// ── Copy ───────────────────────────────────────────────────
copyBtn.addEventListener('click', () => {
  const text = outputText.value;
  if (!text) { showToast('Nada para copiar'); return; }
  navigator.clipboard.writeText(text).then(() => {
    copyBtn.classList.add('success');
    showToast('Texto copiado!', 'accent');
    setTimeout(() => copyBtn.classList.remove('success'), 2000);
  }).catch(() => {
    // Fallback para browsers sem clipboard API
    outputText.select();
    document.execCommand('copy');
    showToast('Texto copiado!', 'accent');
  });
});

// ── Download ───────────────────────────────────────────────
downloadBtn.addEventListener('click', () => {
  const text = outputText.value;
  if (!text) { showToast('Nada para descarregar'); return; }
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'texto_ocr_' + Date.now() + '.txt';
  a.click();
  URL.revokeObjectURL(a.href);
  showToast('Ficheiro descarregado!', 'accent');
});

// ── Inicialização ──────────────────────────────────────────
runDiagnosis();
