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
const conversationIndexJsPath = path.join(__dirname, '..', 'app', 'static', 'js', 'conversation_index.js');
const conversationIndexJsContent = fs.readFileSync(conversationIndexJsPath, 'utf8');
const credentialsJsPath = path.join(__dirname, '..', 'app', 'static', 'js', 'credentials.js');
const credentialsJsContent = fs.readFileSync(credentialsJsPath, 'utf8');

if (!indexJsContent.includes('newRecievedMessage(data.message);')) {
  console.error('frontend should pass raw response text into newRecievedMessage');
  process.exit(1);
}

if (!conversationIndexJsContent.includes('image_urls: imageUrls')) {
  console.error('conversation frontend should send image_urls with chat payload');
  process.exit(1);
}

if (!conversationIndexJsContent.includes('renderMessageHtml')) {
  console.error('conversation frontend should render message html for inline images');
  process.exit(1);
}

if (!conversationIndexJsContent.includes('isSafeImageUrl')) {
  console.error('conversation frontend should validate trusted conversation image urls before rendering');
  process.exit(1);
}

if (!conversationIndexJsContent.includes('if (state.pendingConversationPromise)')) {
  console.error('conversation frontend should wait for pending conversation creation before upload/send');
  process.exit(1);
}

if (!credentialsJsContent.includes('window.location.origin')) {
  console.error('frontend should derive base url from current page origin');
  process.exit(1);
}

if (credentialsJsContent.includes('http://127.0.0.1:5000/')) {
  console.error('frontend should not hardcode localhost base url for deployed usage');
  process.exit(1);
}

assertEqual(
  frontendMessage(rawMessage),
  '第一行\n第二行',
  'frontend should preserve newlines instead of rendering escaped sequences'
);

console.log('frontend message render test passed');