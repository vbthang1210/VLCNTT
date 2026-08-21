const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const app = fs.readFileSync(path.join(__dirname, 'public', 'app.js'), 'utf8');
const html = fs.readFileSync(path.join(__dirname, 'public', 'index.html'), 'utf8');

assert.match(app, /window\.location\.hostname/);
assert.match(app, /method: ['"]DELETE['"]/);
assert.match(app, /recordCountdown/);
assert.match(app, /updateRecordingCountdown/);
assert.match(html, /id="recordCountdown"/);
assert.match(app, /sendCommand\('resume'/);
assert.match(html, /id="resume"/);
assert.match(app, /local_available === false/);
assert.match(app, /metadata Cloud/);
assert.match(app, /option\.disabled = record\.local_available === false/);
