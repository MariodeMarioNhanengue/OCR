/* ============================================================
   LeituraOCR — app.js  (com câmara + toggle de tema)
   ============================================================ */

const API = '/api/extract';

// ── State ──────────────────────────────────────────────────
let currentFile    = null;   // File object (upload tab)
let currentCamData = null;   // base64 string (camera tab)
let activeTab      = 'upload';
let stream         = null;

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
  toastEl._t = setTimeout(() => toastEl.classList.remove('show'), 2800);
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

    // Parar câmara ao sair do tab
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
  if (!file.type.startsWith('image/')) {
    showToast('Ficheiro não é uma imagem válida');
    return;
  }
  currentFile = file;
  const reader = new FileReader();
  reader.onload = e => {
    uploadImg.src = e.target.result;
    dropZone.classList.add('hidden');
    uploadPreview.classList.remove('hidden');
    updateExtractBtn();
  };
  reader.readAsDataURL(file);
}

// ── Camera ─────────────────────────────────────────────────
btnActivate.addEventListener('click', async () => {
  // Verificar se é HTTPS (ou localhost)
  const isSecure = location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1';
  if (!isSecure) {
    camHttpsNote.style.display = 'block';
    showToast('Câmara requer HTTPS. Ver instruções abaixo.');
    return;
  }

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    showToast('Câmara não suportada neste browser');
    return;
  }

  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } }
    });
    camVideo.srcObject = stream;
    camPlaceholder.classList.add('hidden');
    camVideo.classList.remove('hidden');
    btnCapture.classList.remove('hidden');
    showToast('Câmara activada!', 'accent');
  } catch (err) {
    console.error(err);
    if (err.name === 'NotAllowedError') {
      showToast('Permissão à câmara negada pelo utilizador');
    } else if (err.name === 'NotFoundError') {
      showToast('Nenhuma câmara detectada neste dispositivo');
    } else {
      showToast('Erro ao aceder à câmara: ' + err.message);
    }
  }
});

btnCapture.addEventListener('click', () => {
  const w = camVideo.videoWidth  || 640;
  const h = camVideo.videoHeight || 480;
  camCanvas.width  = w;
  camCanvas.height = h;
  camCanvas.getContext('2d').drawImage(camVideo, 0, 0, w, h);

  const dataUrl = camCanvas.toDataURL('image/jpeg', 0.92);
  currentCamData = dataUrl; // mantemos o data URL completo para preview + envio

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
      res = await fetch(API, { method: 'POST', body: form });

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

    const data = await res.json();

    if (!res.ok || data.error) {
      showToast('Erro: ' + (data.error || 'Falha no servidor'));
      setLoading(false);
      return;
    }

    const text = data.text || '';
    outputText.value = text;
    emptyState.style.display = text ? 'none' : '';

    if (text) {
      stats.textContent = `${data.word_count} palavras · ${data.char_count} caracteres`;
      showToast('Texto extraído com sucesso!', 'accent');
    } else {
      stats.textContent = '';
      showToast('Nenhum texto detectado. Tente uma imagem mais nítida.');
    }

  } catch (err) {
    showToast('Erro de ligação ao servidor');
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
