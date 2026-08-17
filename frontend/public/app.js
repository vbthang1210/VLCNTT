const BACKEND = window.BACKEND_BASE_URL || 'http://127.0.0.1:8000';
const deviceId = document.querySelector('#deviceId');
const audioList = document.querySelector('#audioList');
const upload = document.querySelector('#upload');
const message = document.querySelector('#message');
const status = document.querySelector('#status');
const volume = document.querySelector('#volume');
const volumeValue = document.querySelector('#volumeValue');

function showMessage(text) {
  if (message) {
    message.textContent = text;
  }
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

async function refreshAudio() {
  try {
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
    }
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
  } catch (error) {
    status.textContent = `Không lấy được trạng thái: ${error.message}`;
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

volume.addEventListener('input', () => {
  if (volumeValue) volumeValue.textContent = volume.value;
});

volume.addEventListener('change', () => {
  sendCommand('volume', { volume: Number(volume.value) });
});

deviceId.addEventListener('change', refreshStatus);

// Khởi chạy ban đầu
refreshAudio();
refreshStatus();
setInterval(refreshStatus, 3000);
