const backendProtocol = window.location.protocol === 'https:' ? 'https:' : 'http:';
const backendHost = window.location.hostname || '127.0.0.1';
const BACKEND = window.BACKEND_BASE_URL || `${backendProtocol}//${backendHost}:8000`;
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
let activeRecordingId = null;
let recordingEndsAt = 0;
let countdownTimer = null;

function showMessage(text) {
  if (message) {
    message.textContent = text;
  }
}

function updateRecordingCountdown() {
  if (!recordCountdown) return;
  if (!recordingEndsAt) {
    recordCountdown.textContent = '';
    return;
  }
  const remaining = Math.max(0, Math.ceil((recordingEndsAt - Date.now()) / 1000));
  recordCountdown.textContent = remaining > 0 ? `Còn ${remaining}s` : 'Đang hoàn tất...';
  if (remaining === 0 && countdownTimer) {
    clearInterval(countdownTimer);
    countdownTimer = null;
  }
}

function startRecordingCountdown(duration) {
  if (countdownTimer) clearInterval(countdownTimer);
  recordingEndsAt = Date.now() + duration * 1000;
  updateRecordingCountdown();
  countdownTimer = setInterval(updateRecordingCountdown, 250);
}

function stopRecordingCountdown(messageText = '') {
  if (countdownTimer) clearInterval(countdownTimer);
  countdownTimer = null;
  recordingEndsAt = 0;
  if (recordCountdown) recordCountdown.textContent = messageText;
}

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

function updatePreview() {
  if (!audioPreview) return;
  audioPreview.removeAttribute('src');
  if (audioList.value) {
    audioPreview.src = streamUrl(audioList.value);
  }
  audioPreview.load();
}

function renderAudioRecords(records) {
  if (!audioRecords) return;
  audioRecords.replaceChildren();
  if (!records.length) {
    const empty = document.createElement('p');
    empty.className = 'hint';
    empty.textContent = 'Chưa có bản ghi nào.';
    audioRecords.appendChild(empty);
    return;
  }
  for (const record of records) {
    const item = document.createElement('article');
    item.className = 'audio-record';

    const heading = document.createElement('strong');
    heading.textContent = record.original_filename || record.filename;
    item.appendChild(heading);

    const metadata = document.createElement('span');
    const duration = record.duration
      ? `${Number(record.duration).toFixed(1)}s`
      : 'không rõ thời lượng';
    const format = (record.format || 'wav').toUpperCase();
    const source = record.source === 'INMP441' ? 'INMP441' : format;
    metadata.textContent = `${source} · ${duration} · ${record.status}`;
    item.appendChild(metadata);

    const player = document.createElement('audio');
    player.controls = true;
    player.preload = 'none';
    player.src = streamUrl(record.audio_id);
    item.appendChild(player);

    const actions = document.createElement('div');
    actions.className = 'audio-actions';

    const download = document.createElement('a');
    download.className = 'download-link';
    download.href = downloadUrl(record.audio_id);
    download.textContent = 'Tải về';
    download.setAttribute('download', record.filename);
    actions.appendChild(download);

    const remove = document.createElement('button');
    remove.className = 'delete-button';
    remove.type = 'button';
    remove.textContent = 'Xóa';
    remove.addEventListener('click', () => deleteAudio(record.audio_id, record.filename));
    actions.appendChild(remove);
    item.appendChild(actions);
    audioRecords.appendChild(item);
  }
}

async function deleteAudio(audioId, filename) {
  if (!window.confirm(`Xóa tệp ${filename || audioId}?`)) return;
  try {
    await api(`/api/v1/audio/${encodeURIComponent(audioId)}`, { method: 'DELETE' });
    showMessage(`Đã xóa ${filename || audioId}.`);
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
      const durationText = record.duration ? ` - ${Math.round(record.duration)}s` : '';
      option.textContent = `${record.original_filename} (${record.format}${durationText}, ${record.status})`;
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
    status.textContent = JSON.stringify(state, null, 2);
    if (activeRecordingId && state.recording_id === activeRecordingId
        && ['STOPPED', 'ERROR'].includes(state.status)) {
      activeRecordingId = null;
      recordStart.disabled = false;
      recordStop.disabled = true;
      stopRecordingCountdown();
      await refreshAudio();
    }
  } catch (error) {
    status.textContent = `Không lấy được trạng thái: ${error.message}`;
  }
}

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
    showMessage(`Đã gửi lệnh ghi ${duration}s (${data.recording_id}).`);
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
    stopRecordingCountdown('Đang hoàn tất...');
    showMessage('Đã gửi lệnh dừng ghi; đang chờ Backend ghép WAV.');
  } catch (error) {
    showMessage(`Dừng ghi thất bại: ${error.message}`);
  }
}

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

// Khởi chạy ban đầu
refreshAudio();
refreshStatus();
setInterval(refreshStatus, 3000);
