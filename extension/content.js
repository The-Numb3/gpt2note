function extractConversation() {
  const messages = [];
  document.querySelectorAll("[data-message-author-role]").forEach((el) => {
    const role = el.getAttribute("data-message-author-role");
    const text = el.innerText.trim();
    if (text) messages.push({ role, content: text });
  });
  return messages;
}

chrome.runtime.onMessage.addListener((req, sender, sendResponse) => {
  if (req.action === "extract") {
    const conv = extractConversation();
    console.log("[Saver] content.js extracted", conv.length, "messages");
    sendResponse({ conversation: conv });
  }
  // MV3: true를 반환하면 비동기 sendResponse 유지. 여기서는 동기 응답이므로 생략.
});
