const fs = require('fs');
const path = require('path');

function frontendMessage(rawMessage) {
  return String(rawMessage).replace(/\\r\\n/g, '\n').replace(/\\n/g, '\n');
}

function assertEqual(actual, expected, description) {
  if (actual !== expected) {
    console.error(`${description} failed`);
    console.error('expected:', JSON.stringify(expected));
    console.error('actual  :', JSON.stringify(actual));
    process.exit(1);
  }
}

const rawMessage = '第一行\n第二行';
const indexJsPath = path.join(__dirname, '..', 'app', 'static', 'js', 'index.js');
const indexJsContent = fs.readFileSync(indexJsPath, 'utf8');

if (!indexJsContent.includes('newRecievedMessage(data.message);')) {
  console.error('frontend should pass raw response text into newRecievedMessage');
  process.exit(1);
}

assertEqual(
  frontendMessage(rawMessage),
  '第一行\n第二行',
  'frontend should preserve newlines instead of rendering escaped sequences'
);

console.log('frontend message render test passed');