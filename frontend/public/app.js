const backendProtocol = window.location.protocol === 'https:' ? 'https:' : 'http:';
const backendHost = window.location.hostname || '127.0.0.1';
const BACKEND = window.BACKEND_BASE_URL || `${backendProtocol}//${backendHost}:8000`;

// DOM Elements
const deviceId = document.querySelector('#deviceId');
const audioList = document.querySelector('#audioList');
const upload = document.querySelector('#upload');
const message = document.querySelector('#message');
const status = document.querySelector('#status');
const volume = document.querySelector('#volume');
const volumeValue = document.querySelector('#volumeValue');
const audioPreview = document.querySelector('#audioPreview');
const audioRecords = document.querySelector('#audioRecords');
const recordDuration = document.querySelector('#recordDuration');
const recordStart = document.querySelector('#recordStart');
const recordStop = document.querySelector('#recordStop');
const recordCountdown = document.querySelector('#recordCountdown');

// Additional UI Elements
const inmpWaveform = document.querySelector('#inmpWaveform');
const aiResultCard = document.querySelector('#aiResultCard');
const aiConfidenceBadge = document.querySelector('#aiConfidenceBadge');
const aiTranscriptText = document.querySelector('#aiTranscriptText');
const aiCommandResult = document.querySelector('#aiCommandResult');
const aiPublishStatus = document.querySelector('#aiPublishStatus');

const nowPlayingTitle = document.querySelector('#nowPlayingTitle');
const nowPlayingMeta = document.querySelector('#nowPlayingMeta');
const nowPlayingSubtitle = document.querySelector('#nowPlayingSubtitle');

const deviceStatusDot = document.querySelector('#deviceStatusDot');
const telemetryStatusVal = document.querySelector('#telemetryStatusVal');
const telemetryAudioIdVal = document.querySelector('#telemetryAudioIdVal');
const telemetryRequestIdVal = document.querySelector('#telemetryRequestIdVal');
const telemetryEventVal = document.querySelector('#telemetryEventVal');

// 2-Page Navigation Elements
const navStudioBtn = document.querySelector('#navStudioBtn');
const navLibraryBtn = document.querySelector('#navLibraryBtn');
const pageStudio = document.querySelector('#pageStudio');
const pageLibrary = document.querySelector('#pageLibrary');
const libraryCountBadge = document.querySelector('#libraryCountBadge');
const librarySearchInput = document.querySelector('#librarySearchInput');

// Tabs inside Studio
const tabInmpBtn = document.querySelector('#tabInmpBtn');
const tabWebMicBtn = document.querySelector('#tabWebMicBtn');
const paneInmp = document.querySelector('#paneInmp');
const paneWebMic = document.querySelector('#paneWebMic');

// Web Mic elements
const webMicToggle = document.querySelector('#webMicToggle');
const webMicBtnText = document.querySelector('#webMicBtnText');
const webMicStatus = document.querySelector('#webMicStatus');
const webMicLiveText = document.querySelector('#webMicLiveText');
const sendWebMicToTts = document.querySelector('#sendWebMicToTts');
const clearWebMicText = document.querySelector('#clearWebMicText');

// Other Controls
const themeToggle = document.querySelector('#themeToggle');
const refreshAudioBtn = document.querySelector('#refreshAudioBtn');
const toggleRawStatus = document.querySelector('#toggleRawStatus');
const ttsText = document.querySelector('#ttsText');

// State
let activeRecordingId = null;
let recordingEndsAt = 0;
let countdownTimer = null;
let audioCache = [];
let activeFilter = 'all';
let searchQuery = '';
let isWebMicListening = false;
let speechRecognizer = null;

// ==========================================================================
// 2-Page Navigation System
// ==========================================================================
function switchPage(targetPage) {
  if (targetPage === 'library') {
    if (navLibraryBtn) navLibraryBtn.classList.add('active');
    if (navStudioBtn) navStudioBtn.classList.remove('active');
    if (pageLibrary) pageLibrary.classList.add('active');
    if (pageStudio) pageStudio.classList.remove('active');
  } else {
    if (navStudioBtn) navStudioBtn.classList.add('active');
    if (navLibraryBtn) navLibraryBtn.classList.remove('active');
    if (pageStudio) pageStudio.classList.add('active');
    if (pageLibrary) pageLibrary.classList.remove('active');
  }
}

if (navStudioBtn) {
  navStudioBtn.addEventListener('click', () => switchPage('studio'));
}

if (navLibraryBtn) {
  navLibraryBtn.addEventListener('click', () => switchPage('library'));
}

// ==========================================================================
// Theme Management
// ==========================================================================
function initTheme() {
  const savedTheme = localStorage.getItem('esp32_theme') || 'dark';
  document.documentElement.setAttribute('data-theme', savedTheme);
}

if (themeToggle) {
  themeToggle.addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('esp32_theme', next);
  });
}
initTheme();

// ==========================================================================
// Notifications & Status Messages
// ==========================================================================
function showMessage(text) {
  if (message) {
    message.textContent = text;
    message.style.display = text ? 'flex' : 'none';
  }
}

// ==========================================================================
// INMP441 Countdown & Waveform
// ==========================================================================
function updateRecordingCountdown() {
  if (!recordCountdown) return;
  if (!recordingEndsAt) {
    recordCountdown.textContent = '';
    if (inmpWaveform) inmpWaveform.classList.remove('active');
    return;
  }
  const remaining = Math.max(0, Math.ceil((recordingEndsAt - Date.now()) / 1000));
  recordCountdown.textContent = remaining > 0 ? `Còn ${remaining}s` : 'Đang ghép WAV...';
  if (remaining === 0 && countdownTimer) {
    clearInterval(countdownTimer);
    countdownTimer = null;
    if (inmpWaveform) inmpWaveform.classList.remove('active');
  }
}

function startRecordingCountdown(duration) {
  if (countdownTimer) clearInterval(countdownTimer);
  recordingEndsAt = Date.now() + duration * 1000;
  if (inmpWaveform) inmpWaveform.classList.add('active');
  if (deviceStatusDot) {
    deviceStatusDot.className = 'status-dot recording';
  }
  updateRecordingCountdown();
  countdownTimer = setInterval(updateRecordingCountdown, 250);
}

function stopRecordingCountdown(messageText = '') {
  if (countdownTimer) clearInterval(countdownTimer);
  countdownTimer = null;
  recordingEndsAt = 0;
  if (inmpWaveform) inmpWaveform.classList.remove('active');
  if (recordCountdown) recordCountdown.textContent = messageText;
}

// ==========================================================================
// API Client
// ==========================================================================
async function api(path, options = {}) {
  const response = await fetch(`${BACKEND}${path}`, options);
  const contentType = response.headers.get('content-type') || '';
  const payload = contentType.includes('application/json')
    ? await response.json()
    : { success: false, error: { message: await response.text() } };
  if (!response.ok || payload.success === false) {
    throw new Error(payload.error?.message || `HTTP ${response.status}`);
  }
  return payload.data;
}

function streamUrl(audioId) {
  return `${BACKEND}/api/v1/audio/${encodeURIComponent(audioId)}/stream`;
}

function downloadUrl(audioId) {
  return `${BACKEND}/api/v1/audio/${encodeURIComponent(audioId)}/download`;
}

// ==========================================================================
// Now Playing & Subtitle Display
// ==========================================================================
function updateNowPlayingDisplay(record) {
  if (!record) {
    if (nowPlayingTitle) nowPlayingTitle.textContent = 'Chưa chọn tệp âm thanh';
    if (nowPlayingMeta) nowPlayingMeta.textContent = 'IDLE';
    if (nowPlayingSubtitle) nowPlayingSubtitle.textContent = 'Chọn một bài hát hoặc tệp ghi âm để phát...';
    return;
  }

  const name = record.original_filename || record.filename || record.audio_id;
  const duration = record.duration ? `${Number(record.duration).toFixed(2)}s` : '--';
  const format = (record.format || 'wav').toUpperCase();

  if (nowPlayingTitle) nowPlayingTitle.textContent = name;
  if (nowPlayingMeta) nowPlayingMeta.textContent = `${format} · ${duration}`;

  // Hiển thị chữ nhận diện từ Mic hoặc nội dung Text TTS
  let textContent = record.ai_text || record.ai_label || record.text;
  if (!textContent) {
    if (record.source === 'INMP441') {
      textContent = 'Ghi âm từ Micro INMP441 (Chưa có từ khóa)';
    } else if (record.source === 'tts') {
      textContent = `Văn bản TTS: "${record.original_filename}"`;
    } else {
      textContent = `Tệp âm thanh: ${name}`;
    }
  }

  if (nowPlayingSubtitle) {
    nowPlayingSubtitle.textContent = textContent;
  }
}

function updatePreview() {
  if (!audioPreview) return;
  audioPreview.removeAttribute('src');
  if (audioList.value) {
    const record = audioCache.find((r) => r.audio_id === audioList.value);
    audioPreview.src = streamUrl(audioList.value);
    updateNowPlayingDisplay(record);
  } else {
    updateNowPlayingDisplay(null);
  }
  audioPreview.load();
}

// ==========================================================================
// Render Audio Library with Full Cloud Metadata
// ==========================================================================
function formatFileSize(bytes) {
  if (!bytes || bytes <= 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function filterAndRenderRecords() {
  if (!audioRecords) return;
  audioRecords.replaceChildren();

  let filtered = audioCache;

  // Filter by Source
  if (activeFilter !== 'all') {
    filtered = filtered.filter((r) => r.source === activeFilter);
  }

  // Filter by Search Query
  if (searchQuery.trim()) {
    const q = searchQuery.toLowerCase();
    filtered = filtered.filter((r) => {
      const name = (r.original_filename || r.filename || '').toLowerCase();
      const text = (r.ai_text || r.ai_label || r.text || '').toLowerCase();
      return name.includes(q) || text.includes(q);
    });
  }

  if (!filtered.length) {
    const empty = document.createElement('div');
    empty.className = 'hint';
    empty.style.padding = '24px';
    empty.textContent = searchQuery
      ? `Không tìm thấy tệp nào phù hợp với từ khóa "${searchQuery}".`
      : 'Không có bản ghi nào trong mục này.';
    audioRecords.appendChild(empty);
    return;
  }

  for (const record of filtered) {
    const card = document.createElement('article');
    card.className = 'audio-card';

    // Top Row: Title & Badges
    const top = document.createElement('div');
    top.className = 'audio-card-top';

    const titleGroup = document.createElement('div');
    titleGroup.className = 'audio-card-title-group';

    const heading = document.createElement('h3');
    heading.className = 'audio-card-title';
    heading.textContent = record.original_filename || record.filename || record.audio_id;
    titleGroup.appendChild(heading);

    const filenameSub = document.createElement('span');
    filenameSub.className = 'audio-card-filename';
    filenameSub.textContent = `📁 Backend: ${record.filename || record.audio_id}`;
    titleGroup.appendChild(filenameSub);
    top.appendChild(titleGroup);

    // Badges
    const badges = document.createElement('div');
    badges.className = 'audio-badges';

    const sourceBadge = document.createElement('span');
    let sourceClass = 'badge-upload';
    let sourceName = (record.source || 'upload').toUpperCase();
    if (record.source === 'INMP441') {
      sourceClass = 'badge-inmp';
      sourceName = '🎙️ INMP441';
    } else if (record.source === 'tts') {
      sourceClass = 'badge-tts';
      sourceName = '✍️ TTS';
    } else if (record.source === 'webmic') {
      sourceClass = 'badge-webmic';
      sourceName = '🎤 WEB MIC';
    }
    sourceBadge.className = `badge ${sourceClass}`;
    sourceBadge.textContent = sourceName;
    badges.appendChild(sourceBadge);

    const formatBadge = document.createElement('span');
    formatBadge.className = 'badge';
    formatBadge.style.background = 'rgba(255,255,255,0.1)';
    formatBadge.textContent = (record.format || 'wav').toUpperCase();
    badges.appendChild(formatBadge);

    top.appendChild(badges);
    card.appendChild(top);

    // AI Recognized Text Banner (if present)
    if (record.ai_text || record.ai_label || record.text) {
      const aiBox = document.createElement('div');
      aiBox.className = 'card-ai-text-box';
      const confText = record.ai_confidence ? ` (${(record.ai_confidence * 100).toFixed(1)}%)` : '';
      const textVal = record.ai_text || record.ai_label || record.text;
      aiBox.innerHTML = `<span>🗣️ <strong>Văn bản nhận diện:</strong> "${textVal}"${confText}</span>`;
      card.appendChild(aiBox);
    }

    // Detailed Cloud Metadata Grid (All User Requested Fields)
    const techGrid = document.createElement('div');
    techGrid.className = 'metadata-tech-grid';

    // 1. Duration
    const durField = document.createElement('div');
    durField.className = 'meta-field';
    durField.innerHTML = `<span class="field-name">Thời lượng</span><span class="field-val">${record.duration ? Number(record.duration).toFixed(3) + 's' : '--'}</span>`;
    techGrid.appendChild(durField);

    // 2. Sample Rate
    const srField = document.createElement('div');
    srField.className = 'meta-field';
    srField.innerHTML = `<span class="field-name">Tần số mẫu</span><span class="field-val">${record.sample_rate ? record.sample_rate.toLocaleString() + ' Hz' : '--'}</span>`;
    techGrid.appendChild(srField);

    // 3. Channels
    const chField = document.createElement('div');
    chField.className = 'meta-field';
    const chName = record.channels === 1 ? '1 (Mono)' : (record.channels === 2 ? '2 (Stereo)' : record.channels || '--');
    chField.innerHTML = `<span class="field-name">Kênh âm</span><span class="field-val">${chName}</span>`;
    techGrid.appendChild(chField);

    // 4. Bits per sample
    const bitsField = document.createElement('div');
    bitsField.className = 'meta-field';
    bitsField.innerHTML = `<span class="field-name">Độ sâu Bit</span><span class="field-val">${record.bits_per_sample ? record.bits_per_sample + '-bit' : '--'}</span>`;
    techGrid.appendChild(bitsField);

    // 5. Size
    const sizeField = document.createElement('div');
    sizeField.className = 'meta-field';
    sizeField.innerHTML = `<span class="field-name">Dung lượng</span><span class="field-val">${formatFileSize(record.size)}</span>`;
    techGrid.appendChild(sizeField);

    // 6. Status
    const statusField = document.createElement('div');
    statusField.className = 'meta-field';
    statusField.innerHTML = `<span class="field-name">Trạng thái</span><span class="field-val" style="color:var(--emerald);">${record.status || 'READY'}</span>`;
    techGrid.appendChild(statusField);

    card.appendChild(techGrid);

    // Built-in Audio Player
    const player = document.createElement('audio');
    player.controls = true;
    player.preload = 'none';
    player.src = streamUrl(record.audio_id);
    player.addEventListener('play', () => updateNowPlayingDisplay(record));
    card.appendChild(player);

    // Action Buttons
    const actions = document.createElement('div');
    actions.className = 'audio-card-actions';

    const playDeviceBtn = document.createElement('button');
    playDeviceBtn.className = 'btn btn-outline small';
    playDeviceBtn.type = 'button';
    playDeviceBtn.innerHTML = '🔊 Phát trên ESP32';
    playDeviceBtn.addEventListener('click', () => {
      audioList.value = record.audio_id;
      updatePreview();
      switchPage('studio');
      sendCommand('play', { audio_id: record.audio_id });
    });
    actions.appendChild(playDeviceBtn);

    const rightActions = document.createElement('div');
    rightActions.style.display = 'flex';
    rightActions.style.alignItems = 'center';
    rightActions.style.gap = '10px';

    const download = document.createElement('a');
    download.className = 'download-link';
    download.href = downloadUrl(record.audio_id);
    download.textContent = '⬇️ Tải về';
    download.setAttribute('download', record.filename || `${record.audio_id}.${record.format || 'wav'}`);
    rightActions.appendChild(download);

    const remove = document.createElement('button');
    remove.className = 'delete-button';
    remove.type = 'button';
    remove.textContent = 'Xóa';
    remove.addEventListener('click', () => deleteAudio(record.audio_id, record.original_filename || record.filename));
    rightActions.appendChild(remove);

    actions.appendChild(rightActions);
    card.appendChild(actions);

    audioRecords.appendChild(card);
  }
}

function renderAudioRecords(records) {
  audioCache = records || [];
  if (libraryCountBadge) {
    libraryCountBadge.textContent = `${audioCache.length} tệp`;
  }
  filterAndRenderRecords();
}

async function deleteAudio(audioId, filename) {
  if (!window.confirm(`Bạn có chắc muốn xóa tệp "${filename || audioId}"?`)) return;
  try {
    await api(`/api/v1/audio/${encodeURIComponent(audioId)}`, { method: 'DELETE' });
    showMessage(`Đã xóa tệp "${filename || audioId}".`);
    await refreshAudio();
  } catch (error) {
    showMessage(`Xóa audio thất bại: ${error.message}`);
  }
}

async function refreshAudio() {
  try {
    const selectedId = audioList.value;
    const records = await api('/api/v1/audio');
    audioList.replaceChildren();

    for (const record of records) {
      const option = document.createElement('option');
      option.value = record.audio_id;
      const durationText = record.duration ? ` · ${Number(record.duration).toFixed(1)}s` : '';
      const textSnippet = record.ai_text ? ` [${record.ai_text}]` : '';
      option.textContent = `${record.original_filename || record.filename} (${(record.format || 'wav').toUpperCase()}${durationText})${textSnippet}`;
      audioList.appendChild(option);
    }

    if (!records.length) {
      audioList.add(new Option('Chưa có tệp âm thanh nào', ''));
    } else {
      audioList.value = records.some((record) => record.audio_id === selectedId)
        ? selectedId
        : records[0].audio_id;
    }

    updatePreview();
    renderAudioRecords(records);
  } catch (error) {
    showMessage(`Lỗi tải danh sách âm thanh: ${error.message}`);
  }
}

// ==========================================================================
// Filter & Search Event Listeners
// ==========================================================================
if (librarySearchInput) {
  librarySearchInput.addEventListener('input', (e) => {
    searchQuery = e.target.value;
    filterAndRenderRecords();
  });
}

document.querySelectorAll('.filter-chip').forEach((chip) => {
  chip.addEventListener('click', () => {
    document.querySelectorAll('.filter-chip').forEach((c) => c.classList.remove('active'));
    chip.classList.add('active');
    activeFilter = chip.getAttribute('data-filter') || 'all';
    filterAndRenderRecords();
  });
});

// ==========================================================================
// Device Commands & Telemetry Polling
// ==========================================================================
async function sendCommand(action, body = {}) {
  try {
    const data = await api(`/api/v1/devices/${encodeURIComponent(deviceId.value)}/${action}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    showMessage(`Lệnh ${action.toUpperCase()} thành công (Request ID: ${data.request_id || 'OK'})`);
    await refreshStatus();
  } catch (error) {
    showMessage(`Lệnh ${action.toUpperCase()} thất bại: ${error.message}`);
  }
}

async function refreshStatus() {
  try {
    const state = await api(`/api/v1/devices/${encodeURIComponent(deviceId.value)}/status`);
    if (status) {
      status.textContent = JSON.stringify(state, null, 2);
    }

    // Update Visual Telemetry Stats
    if (telemetryStatusVal) telemetryStatusVal.textContent = state.status || 'OFFLINE';
    if (telemetryAudioIdVal) telemetryAudioIdVal.textContent = state.audio_id || state.recording_id || '--';
    if (telemetryRequestIdVal) telemetryRequestIdVal.textContent = state.request_id || '--';
    if (telemetryEventVal) {
      telemetryEventVal.textContent = state.last_event?.event || (state.error ? `Lỗi: ${state.error.code}` : '--');
    }

    // Update Status Dot Indicator
    if (deviceStatusDot) {
      if (state.status === 'RECORDING') {
        deviceStatusDot.className = 'status-dot recording';
      } else if (state.status === 'PLAYING') {
        deviceStatusDot.className = 'status-dot playing';
      } else if (['ONLINE', 'IDLE', 'PAUSED'].includes(state.status)) {
        deviceStatusDot.className = 'status-dot online';
      } else {
        deviceStatusDot.className = 'status-dot';
      }
    }

    // Update AI Voice Command Result on Card if event received
    if (state.last_event && (state.last_event.event === 'VOICE_COMMAND_RESULT' || state.last_event.ai_label)) {
      const evt = state.last_event;
      if (aiConfidenceBadge) {
        aiConfidenceBadge.textContent = evt.ai_confidence ? `Độ tin cậy: ${(evt.ai_confidence * 100).toFixed(1)}%` : 'Đã nhận diện';
      }
      if (aiTranscriptText) {
        aiTranscriptText.textContent = evt.ai_text ? `"${evt.ai_text}"` : (evt.ai_label || 'Không nhận diện được');
      }
      if (aiCommandResult) {
        aiCommandResult.textContent = `Lệnh: ${evt.ai_command || 'Không'} (${evt.ai_state || 'N/A'})`;
      }
      if (aiPublishStatus) {
        aiPublishStatus.textContent = evt.ai_published ? 'MQTT: Đã gửi lệnh đèn' : 'MQTT: Sẵn sàng';
      }
    }

    // Handle recording completion
    if (activeRecordingId && state.recording_id === activeRecordingId
        && ['STOPPED', 'ERROR', 'IDLE'].includes(state.status)) {
      activeRecordingId = null;
      recordStart.disabled = false;
      recordStop.disabled = true;
      stopRecordingCountdown();
      await refreshAudio();
    }
  } catch (error) {
    if (status) {
      status.textContent = `Không lấy được trạng thái: ${error.message}`;
    }
  }
}

// ==========================================================================
// INMP441 Recording Controls
// ==========================================================================
async function startRecording() {
  const duration = Number(recordDuration.value);
  if (!Number.isInteger(duration) || duration < 1 || duration > 60) {
    showMessage('Thời lượng ghi phải là số nguyên từ 1 đến 60 giây.');
    return;
  }
  try {
    const data = await api(`/api/v1/devices/${encodeURIComponent(deviceId.value)}/record/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ duration_seconds: duration }),
    });
    activeRecordingId = data.recording_id;
    recordStart.disabled = true;
    recordStop.disabled = false;
    startRecordingCountdown(duration);
    showMessage(`Đã gửi lệnh ghi âm ${duration}s (${data.recording_id}).`);
    await refreshStatus();
  } catch (error) {
    showMessage(`Bắt đầu ghi thất bại: ${error.message}`);
  }
}

async function stopRecording() {
  if (!activeRecordingId) {
    showMessage('Không có phiên ghi âm đang hoạt động.');
    return;
  }
  try {
    await api(`/api/v1/devices/${encodeURIComponent(deviceId.value)}/record/stop`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ recording_id: activeRecordingId }),
    });
    stopRecordingCountdown('Đang ghép WAV...');
    showMessage('Đã gửi lệnh dừng ghi; đang chờ Backend lưu WAV và chạy AI nhận diện.');
  } catch (error) {
    showMessage(`Dừng ghi thất bại: ${error.message}`);
  }
}

// ==========================================================================
// Browser Web Mic & Real-time Speech-to-Text
// ==========================================================================
function setupWebSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    if (webMicStatus) webMicStatus.textContent = 'Trình duyệt không hỗ trợ Web Speech API';
    return;
  }

  speechRecognizer = new SpeechRecognition();
  speechRecognizer.continuous = true;
  speechRecognizer.interimResults = true;
  speechRecognizer.lang = 'vi-VN';

  speechRecognizer.onstart = () => {
    isWebMicListening = true;
    if (webMicStatus) webMicStatus.textContent = '🔴 Đang lắng nghe tiếng Việt...';
    if (webMicBtnText) webMicBtnText.textContent = 'Dừng Micro Trình duyệt';
    if (webMicToggle) webMicToggle.className = 'btn btn-rose';
  };

  speechRecognizer.onresult = (event) => {
    let interim = '';
    let final = '';
    for (let i = event.resultIndex; i < event.results.length; ++i) {
      if (event.results[i].isFinal) {
        final += event.results[i][0].transcript;
      } else {
        interim += event.results[i][0].transcript;
      }
    }
    const currentText = final || interim;
    if (webMicLiveText && currentText) {
      webMicLiveText.textContent = currentText;
    }
  };

  speechRecognizer.onerror = (event) => {
    if (webMicStatus) webMicStatus.textContent = `Lỗi mic: ${event.error}`;
  };

  speechRecognizer.onend = () => {
    isWebMicListening = false;
    if (webMicStatus) webMicStatus.textContent = 'Đã dừng lắng nghe';
    if (webMicBtnText) webMicBtnText.textContent = 'Bật Micro Trình duyệt (Nói tiếng Việt)';
    if (webMicToggle) webMicToggle.className = 'btn btn-indigo';
  };
}

if (webMicToggle) {
  webMicToggle.addEventListener('click', () => {
    if (!speechRecognizer) {
      setupWebSpeechRecognition();
    }
    if (!speechRecognizer) {
      showMessage('Trình duyệt của bạn không hỗ trợ nhận diện giọng nói Web Speech.');
      return;
    }
    if (isWebMicListening) {
      speechRecognizer.stop();
    } else {
      try {
        speechRecognizer.start();
      } catch (err) {
        speechRecognizer.stop();
      }
    }
  });
}

if (sendWebMicToTts) {
  sendWebMicToTts.addEventListener('click', () => {
    if (webMicLiveText && ttsText) {
      const text = webMicLiveText.textContent.trim();
      if (text && text !== 'Chữ nhận diện từ giọng nói sẽ hiển thị trực tiếp tại đây...') {
        ttsText.value = text;
        ttsText.focus();
        showMessage('Đã chuyển văn bản nhận diện sang Text-to-Speech!');
      }
    }
  });
}

if (clearWebMicText) {
  clearWebMicText.addEventListener('click', () => {
    if (webMicLiveText) {
      webMicLiveText.textContent = 'Chữ nhận diện từ giọng nói sẽ hiển thị trực tiếp tại đây...';
    }
  });
}

// ==========================================================================
// Tabs & UI Switchers inside Studio
// ==========================================================================
if (tabInmpBtn && tabWebMicBtn) {
  tabInmpBtn.addEventListener('click', () => {
    tabInmpBtn.classList.add('active');
    tabWebMicBtn.classList.remove('active');
    if (paneInmp) paneInmp.classList.add('active');
    if (paneWebMic) paneWebMic.classList.remove('active');
  });

  tabWebMicBtn.addEventListener('click', () => {
    tabWebMicBtn.classList.add('active');
    tabInmpBtn.classList.remove('active');
    if (paneWebMic) paneWebMic.classList.add('active');
    if (paneInmp) paneInmp.classList.remove('active');
    if (!speechRecognizer) setupWebSpeechRecognition();
  });
}

// Quick Prompt Chips for TTS
document.querySelectorAll('.chip').forEach((chip) => {
  chip.addEventListener('click', () => {
    const text = chip.getAttribute('data-text');
    if (text && ttsText) {
      ttsText.value = text;
      ttsText.focus();
    }
  });
});

// Toggle Raw Status JSON Box
if (toggleRawStatus && status) {
  toggleRawStatus.addEventListener('click', () => {
    status.classList.toggle('expanded');
    toggleRawStatus.textContent = status.classList.contains('expanded') ? 'Ẩn Raw JSON' : 'Hiển thị Raw JSON';
  });
}

if (refreshAudioBtn) {
  refreshAudioBtn.addEventListener('click', refreshAudio);
}

// ==========================================================================
// Upload & TTS Listeners
// ==========================================================================
upload.addEventListener('change', async () => {
  if (!upload.files[0]) return;
  const file = upload.files[0];
  const form = new FormData();
  form.append('file', file);
  showMessage(`Đang tải lên ${file.name}...`);
  try {
    await api('/api/v1/audio/upload', { method: 'POST', body: form });
    showMessage(`Tải lên thành công: ${file.name}`);
    await refreshAudio();
  } catch (error) {
    showMessage(`Tải lên thất bại: ${error.message}`);
  }
});

document.querySelector('#tts').addEventListener('click', async () => {
  const text = document.querySelector('#ttsText').value.trim();
  if (!text) return showMessage('Vui lòng nhập văn bản trước!');
  showMessage('Đang gửi yêu cầu TTS...');
  try {
    await api('/api/v1/audio/tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
    showMessage('Tạo TTS thành công!');
    await refreshAudio();
  } catch (error) {
    showMessage(`Tạo TTS thất bại: ${error.message}`);
  }
});

// ==========================================================================
// Playback Control Buttons
// ==========================================================================
document.querySelector('#play').addEventListener('click', () => {
  if (!audioList.value) return showMessage('Vui lòng chọn một tệp âm thanh trước!');
  sendCommand('play', { audio_id: audioList.value });
});

document.querySelector('#stop').addEventListener('click', () => sendCommand('stop'));
document.querySelector('#pause').addEventListener('click', () => sendCommand('pause'));
document.querySelector('#resume').addEventListener('click', () => sendCommand('resume'));
recordStart.addEventListener('click', startRecording);
recordStop.addEventListener('click', stopRecording);

volume.addEventListener('input', () => {
  if (volumeValue) volumeValue.textContent = volume.value;
});

volume.addEventListener('change', () => {
  sendCommand('volume', { volume: Number(volume.value) });
});

deviceId.addEventListener('change', refreshStatus);
audioList.addEventListener('change', updatePreview);

// ==========================================================================
// Initial Load & Heartbeat
// ==========================================================================
setupWebSpeechRecognition();
refreshAudio();
refreshStatus();
setInterval(refreshStatus, 3000);
