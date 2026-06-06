/* ============================================================
   LeituraOCR — app.js  (sem câmara, com toggle de tema)
   ============================================================ */

const API = '/api/extract';

// ── State ──────────────────────────────────────────────────
let currentFile = null;

// ── Elements ───────────────────────────────────────────────
const fileInput     = document.getElementById('fileInput');
const dropZone      = document.getElementById('dropZone');
const uploadPreview = document.getElementById('uploadPreview');
const uploadImg     = document.getElementById('uploadPreviewImg');
const clearUpload   = document.getElementById('clearUpload');
const extractBtn    = document.getElementById('extractBtn');
const extractLabel  = document.getElementById('extractLabel');
const extractSpinner= document.getElementById('extractSpinner');
const outputText    = document.getElementById('outputText');
const emptyState    = document.getElementById('emptyState');
const stats         = document.getElementById('stats');
const copyBtn       = document.getElementById('copyBtn');
const downloadBtn   = document.getElementById('downloadBtn');
const toastEl       = document.getElementById('toast');
const themeToggle   = document.getElementById('themeToggle');
const themeLabel    = document.getElementById('themeLabel');

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
  extractBtn.disabled = true;
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
    extractBtn.disabled = false;
  };
  reader.readAsDataURL(file);
}

// ── Extract ────────────────────────────────────────────────
extractBtn.addEventListener('click', async () => {
  if (!currentFile || extractBtn.disabled) return;
  setLoading(true);

  try {
    const form = new FormData();
    form.append('file', currentFile);

    const res  = await fetch(API, { method: 'POST', body: form });
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
