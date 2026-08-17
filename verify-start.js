const http = require('http');

const host = '127.0.0.1';
const port = Number(process.env.PORT || 8000);
let served = false;

const server = http.createServer((request, response) => {
  if (served) {
    response.writeHead(404);
    response.end();
    return;
  }
  served = true;
  response.writeHead(200, { 'Content-Type': 'text/plain; charset=utf-8' });
  response.end('verification-ready\n', () => {
    server.close(() => process.exit(0));
  });
});

server.listen(port, host);
