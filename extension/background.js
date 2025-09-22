function isChatGPTUrl(url) {
  return /^https:\/\/(chatgpt\.com|chat\.openai\.com)\//.test(url || "");
}

async function postToServer(payload) {
  const res = await fetch("http://localhost:8000/api/conversation/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error(`Server responded ${res.status}`);
  return res.json();
}

chrome.action.onClicked.addListener(async (tab) => {
  try {
    if (!tab || !isChatGPTUrl(tab.url)) {
      console.warn("[Saver] Not a ChatGPT tab:", tab?.url);
      // 선택: ChatGPT 탭으로 이동 유도 or 알림
      return;
    }

    console.log("[Saver] Sending extract request to content.js");
    chrome.tabs.sendMessage(tab.id, { action: "extract" }, async (response) => {
      if (chrome.runtime.lastError) {
        console.warn("[Saver] content.js no response, fallback:", chrome.runtime.lastError.message);
      }

      let conversation = response?.conversation;
      if (!conversation || !Array.isArray(conversation) || conversation.length === 0) {
        // ⬇️ 폴백: content.js 없이 바로 DOM 실행해서 추출
        console.log("[Saver] Fallback: executeScript to extract DOM");
        const [{ result }] = await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: () => {
            const msgs = [];
            // 1) 최신 구조 시도
            document.querySelectorAll("[data-message-author-role]").forEach((el) => {
              const role = el.getAttribute("data-message-author-role");
              const text = el.innerText.trim();
              if (text) msgs.push({ role, content: text });
            });
            // 2) 백업 셀렉터 (만약 구조 변경 시)
            if (msgs.length === 0) {
              document.querySelectorAll("main .markdown, main .prose").forEach((el) => {
                const text = el.innerText.trim();
                if (text) msgs.push({ role: "assistant", content: text });
              });
            }
            return msgs;
          }
        });
        conversation = result || [];
      }

      if (!conversation || conversation.length === 0) {
        console.error("[Saver] No messages extracted");
        return;
      }

      const payload = {
        project: "AI Conversation Archiver",
        conversation
      };

      console.log("[Saver] Posting to server:", payload);
      postToServer(payload)
        .then((data) => console.log("[Saver] Saved OK:", data))
        .catch((err) => console.error("[Saver] Server error:", err));
    });
  } catch (e) {
    console.error("[Saver] Unexpected error:", e);
  }
});
