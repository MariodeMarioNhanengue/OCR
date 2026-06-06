/* ============================================================
   LeituraOCR — app.js  v1.2
   Funcionalidades:
   - Upload de imagem (drag & drop)
   - Câmara com flash/tocha
   - PDF multipágina
   - Modo caligrafia
   - Diagnóstico automático
   - Tema claro/escuro
   - Copiar / Descarregar / Limpar resultado
   ============================================================ */

const API        = '/api/extract';
const API_PDF    = '/api/extract-pdf';
const API_DIAG   = '/api/diagnose';

// ── State ──────────────────────────────────────────────────
let currentFile    = null;   // ficheiro de imagem
let currentPdfFile = null;   // ficheiro PDF
let currentCamData = null;   // base64 da câmara
let activeTab      = 'upload';
let stream         = null;
let diagInfo       = null;
let flashOn        = false;
let handwritingMode = false;

// ── Elements ───────────────────────────────────────────────
const fileInput       = document.getElementById('fileInput');
const dropZone        = document.getElementById('dropZone');
const uploadPreview   = document.getElementById('uploadPreview');
const uploadImg       = document.getElementById('uploadPreviewImg');
const clearUpload     = document.getElementById('clearUpload');

const pdfInput        = document.getElementById('pdfInput');
const dropZonePdf     = document.getElementById('dropZonePdf');
const pdfSelected     = document.getElementById('pdfSelected');
const pdfName         = document.getElementById('pdfName');
const pdfSize         = document.getElementById('pdfSize');
const clearPdf        = document.getElementById('clearPdf');
const pdfPagesResult  = document.getElementById('pdfPagesResult');

const extractBtn      = document.getElementById('extractBtn');
const extractLabel    = document.getElementById('extractLabel');
const extractSpinner  = document.getElementById('extractSpinner');
const outputText      = document.getElementById('outputText');
const emptyState      = document.getElementById('emptyState');
const stats           = document.getElementById('stats');
const copyBtn         = document.getElementById('copyBtn');
const downloadBtn     = document.getElementById('downloadBtn');
const clearOutputBtn  = document.getElementById('clearOutputBtn');
const toastEl         = document.getElementById('toast');
const themeToggle     = document.getElementById('themeToggle');
const themeLabel      = document.getElementById('themeLabel');

// Camera
const camPlaceholder  = document.getElementById('camPlaceholder');
const camHttpsNote    = document.getElementById('camHttpsNote');
const btnActivate     = document.getElementById('btnActivate');
const camVideo        = document.getElementById('camVideo');
const camCanvas       = document.getElementById('camCanvas');
const camPreview      = document.getElementById('camPreview');
const camPreviewImg   = document.getElementById('camPreviewImg');
const clearCam        = document.getElementById('clearCam');
const btnCapture      = document.getElementById('btnCapture');
const btnRetake       = document.getElementById('btnRetake');
const btnFlash        = document.getElementById('btnFlash');
const handwritingToggle = document.getElementById('handwritingToggle');

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

    // Desabilitar tab PDF se não houver suporte
    if (diagInfo.pdf_support === false) {
      const pdfTab = document.querySelector('[data-tab="pdf"]');
      if (pdfTab) {
        pdfTab.title = 'PDF não disponível: instale pdf2image + poppler-utils';
        pdfTab.style.opacity = '0.45';
      }
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
    const closeBtn = document.createElement('button');
    closeBtn.innerHTML = '✕';
    closeBtn.style.cssText = 'float:right;background:none;border:none;cursor:pointer;color:inherit;font-size:14px;padding:0 0 0 12px;';
    closeBtn.onclick = () => banner.remove();
    banner.appendChild(closeBtn);

    const main = document.querySelector('main');
    if (main) main.prepend(banner);
  }
  banner.style.cssText = `
    padding: 12px 20px; margin: 12px 0; border-radius: 8px; font-size: 13px; position: relative;
    background: ${type === 'warning' ? 'rgba(255,180,0,0.12)' : 'rgba(80,160,255,0.1)'};
    border: 1px solid ${type === 'warning' ? 'rgba(255,180,0,0.3)' : 'rgba(80,160,255,0.3)'};
    color: var(--text);
  `;
  // Manter o botão fechar
  const existing = banner.querySelector('button');
  banner.innerHTML = html;
  if (existing) banner.appendChild(existing);
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
  const isImage = file.type.startsWith('image/') ||
    /\.(png|jpe?g|gif|bmp|webp|tiff?|heic|heif)$/i.test(file.name);

  if (!isImage) {
    showToast('Ficheiro não reconhecido como imagem. Use PNG, JPG, WEBP, BMP ou TIFF');
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

// ── PDF Upload ─────────────────────────────────────────────
dropZonePdf.addEventListener('click', () => pdfInput.click());
dropZonePdf.addEventListener('dragover', e => { e.preventDefault(); dropZonePdf.classList.add('dragover'); });
dropZonePdf.addEventListener('dragleave', () => dropZonePdf.classList.remove('dragover'));
dropZonePdf.addEventListener('drop', e => {
  e.preventDefault(); dropZonePdf.classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  if (file) handlePdf(file);
});
pdfInput.addEventListener('change', () => {
  if (pdfInput.files[0]) handlePdf(pdfInput.files[0]);
});

clearPdf.addEventListener('click', () => {
  currentPdfFile = null;
  pdfSelected.classList.add('hidden');
  dropZonePdf.classList.remove('hidden');
  pdfPagesResult.classList.add('hidden');
  pdfPagesResult.innerHTML = '';
  pdfInput.value = '';
  updateExtractBtn();
});

function handlePdf(file) {
  const isPdf = file.type === 'application/pdf' || /\.pdf$/i.test(file.name);
  if (!isPdf) {
    showToast('Este campo aceita apenas ficheiros PDF');
    return;
  }
  if (file.size > 64 * 1024 * 1024) {
    showToast('PDF demasiado grande (máx. 64 MB)');
    return;
  }

  currentPdfFile = file;
  pdfName.textContent = file.name;
  pdfSize.textContent = formatBytes(file.size);
  dropZonePdf.classList.add('hidden');
  pdfSelected.classList.remove('hidden');
  pdfPagesResult.classList.add('hidden');
  pdfPagesResult.innerHTML = '';
  updateExtractBtn();
  showToast('PDF carregado!', 'accent');
}

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// ── Flash / Tocha ──────────────────────────────────────────
async function setFlash(on) {
  if (!stream) return;
  const track = stream.getVideoTracks()[0];
  if (!track) return;
  const capabilities = track.getCapabilities ? track.getCapabilities() : {};
  if (!capabilities.torch) {
    showToast('Este dispositivo não suporta flash/tocha');
    return;
  }
  try {
    await track.applyConstraints({ advanced: [{ torch: on }] });
    flashOn = on;
    updateFlashBtn();
  } catch (err) {
    showToast('Erro ao controlar o flash: ' + err.message);
  }
}

function updateFlashBtn() {
  if (!btnFlash) return;
  if (flashOn) {
    btnFlash.classList.add('active');
    btnFlash.title = 'Desactivar flash';
    btnFlash.querySelector('.flash-label').textContent = 'Flash ON';
  } else {
    btnFlash.classList.remove('active');
    btnFlash.title = 'Activar flash';
    btnFlash.querySelector('.flash-label').textContent = 'Flash';
  }
}

function showFlashBtn(visible) {
  if (!btnFlash) return;
  btnFlash.classList.toggle('hidden', !visible);
}

btnFlash && btnFlash.addEventListener('click', () => setFlash(!flashOn));

// ── Handwriting mode ───────────────────────────────────────
handwritingToggle && handwritingToggle.addEventListener('change', () => {
  handwritingMode = handwritingToggle.checked;
  showToast(handwritingMode
    ? 'Modo caligrafia activado — optimizado para texto manuscrito'
    : 'Modo normal activado'
  , handwritingMode ? 'accent' : '');
});

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
      <em>Alternativa: use o separador <strong>Upload</strong> para enviar fotos tiradas noutro dispositivo.</em>
    `;
    showToast('Câmara requer HTTPS. Ver instruções abaixo.');
    return;
  }

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    showToast('Câmara não suportada neste browser');
    return;
  }

  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: { ideal: 'environment' },
        width:  { ideal: 1920 },
        height: { ideal: 1080 },
      }
    });

    camVideo.srcObject = stream;
    camPlaceholder.classList.add('hidden');
    camVideo.classList.remove('hidden');
    btnCapture.classList.remove('hidden');

    const track = stream.getVideoTracks()[0];
    if (track) {
      const caps = track.getCapabilities ? track.getCapabilities() : {};
      showFlashBtn(!!caps.torch);
    }

    flashOn = false;
    updateFlashBtn();
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
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: true });
        camVideo.srcObject = stream;
        camPlaceholder.classList.add('hidden');
        camVideo.classList.remove('hidden');
        btnCapture.classList.remove('hidden');
        const track = stream.getVideoTracks()[0];
        if (track) {
          const caps = track.getCapabilities ? track.getCapabilities() : {};
          showFlashBtn(!!caps.torch);
        }
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

  const dataUrl = camCanvas.toDataURL('image/jpeg', 0.95);
  currentCamData = dataUrl;

  camPreviewImg.src = dataUrl;
  camVideo.classList.add('hidden');
  camPreview.classList.remove('hidden');
  btnCapture.classList.add('hidden');
  btnRetake.classList.remove('hidden');
  showFlashBtn(false);
  setFlash(false);
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
    const track = stream.getVideoTracks()[0];
    if (track) {
      const caps = track.getCapabilities ? track.getCapabilities() : {};
      showFlashBtn(!!caps.torch);
    }
    flashOn = false;
    updateFlashBtn();
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
  showFlashBtn(false);
  setFlash(false);
  stopStream();
  updateExtractBtn();
});

function stopStream() {
  if (stream) {
    const track = stream.getVideoTracks()[0];
    if (track && flashOn) {
      track.applyConstraints({ advanced: [{ torch: false }] }).catch(() => {});
    }
    stream.getTracks().forEach(t => t.stop());
    stream = null;
  }
  flashOn = false;
  updateFlashBtn();
  camVideo.classList.add('hidden');
  camVideo.srcObject = null;
}

// ── Extract Button state ───────────────────────────────────
function updateExtractBtn() {
  const hasUpload = activeTab === 'upload' && currentFile !== null;
  const hasCam    = activeTab === 'camera' && currentCamData !== null;
  const hasPdf    = activeTab === 'pdf' && currentPdfFile !== null;
  extractBtn.disabled = !(hasUpload || hasCam || hasPdf);
}

// ── Extract ────────────────────────────────────────────────
extractBtn.addEventListener('click', async () => {
  if (extractBtn.disabled) return;
  setLoading(true);
  clearOutput();

  try {
    let res;

    // Imagem via upload
    if (activeTab === 'upload' && currentFile) {
      const form = new FormData();
      form.append('file', currentFile);
      if (handwritingMode) form.append('handwriting', '1');
      res = await fetch(API, { method: 'POST', body: form });

    // Imagem via câmara
    } else if (activeTab === 'camera' && currentCamData) {
      res = await fetch(API, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: currentCamData, handwriting: handwritingMode }),
      });

    // PDF
    } else if (activeTab === 'pdf' && currentPdfFile) {
      const form = new FormData();
      form.append('file', currentPdfFile);
      if (handwritingMode) form.append('handwriting', '1');
      res = await fetch(API_PDF, { method: 'POST', body: form });

    } else {
      showToast('Nenhuma imagem disponível');
      setLoading(false);
      return;
    }

    let data;
    try {
      data = await res.json();
    } catch {
      showToast('Erro: resposta inválida do servidor');
      setLoading(false);
      return;
    }

    if (!res.ok || data.error) {
      const errMsg = data.error || `Erro HTTP ${res.status}`;
      showToast('Erro: ' + errMsg);
      if (data.install_hint) {
        showBanner('warning',
          `⚠️ Dependência em falta. Execute no terminal: <code>${data.install_hint}</code>`
        );
      }
      setLoading(false);
      return;
    }

    const text = data.text || '';
    outputText.value = text;

    if (text) {
      emptyState.style.display = 'none';
      outputText.style.display = '';
      const langLabel = data.lang_used ? ` · ${data.lang_used}` : '';
      const modeLabel = data.handwriting_mode ? ' · ✍️ caligrafia' : '';
      const pagesLabel = data.total_pages ? ` · ${data.total_pages} páginas` : '';
      stats.textContent = `${data.word_count} palavras · ${data.char_count} chars${langLabel}${modeLabel}${pagesLabel}`;
      clearOutputBtn.style.display = '';
      showToast('Texto extraído com sucesso!', 'accent');

      // Para PDF: mostrar resumo por páginas
      if (activeTab === 'pdf' && data.pages && data.pages.length > 1) {
        renderPdfPages(data.pages);
      }
    } else {
      emptyState.style.display = '';
      outputText.style.display = 'none';
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

function renderPdfPages(pages) {
  if (!pdfPagesResult) return;
  pdfPagesResult.innerHTML = '<p class="pdf-pages-label">Resumo por página:</p>' +
    pages.map(p => `
      <div class="pdf-page-item ${p.text.trim() ? '' : 'empty'}">
        <span class="pdf-page-num">Pág. ${p.page}</span>
        <span class="pdf-page-words">${p.word_count} palavras</span>
        ${!p.text.trim() ? '<span class="pdf-page-empty">sem texto</span>' : ''}
      </div>
    `).join('');
  pdfPagesResult.classList.remove('hidden');
}

function setLoading(on) {
  extractBtn.disabled = on;
  extractLabel.textContent = on ? 'A extrair...' : 'Extrair Texto';
  extractSpinner.classList.toggle('hidden', !on);
  if (!on) updateExtractBtn(); // restaurar estado correto
}

// ── Clear Output ───────────────────────────────────────────
function clearOutput() {
  outputText.value = '';
  outputText.style.display = 'none';
  emptyState.style.display = '';
  stats.textContent = '';
  clearOutputBtn.style.display = 'none';
}

clearOutputBtn.addEventListener('click', () => {
  clearOutput();
  showToast('Resultado limpo');
});

// ── Copy ───────────────────────────────────────────────────
copyBtn.addEventListener('click', () => {
  const text = outputText.value;
  if (!text) { showToast('Nada para copiar'); return; }
  navigator.clipboard.writeText(text).then(() => {
    copyBtn.classList.add('success');
    showToast('Texto copiado!', 'accent');
    setTimeout(() => copyBtn.classList.remove('success'), 2000);
  }).catch(() => {
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

// ── Init ───────────────────────────────────────────────────
clearOutput();
runDiagnosis();
