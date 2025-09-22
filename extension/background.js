const API_URL = "http://localhost:8000/api/conversation/save+analyze";
const PROJECT = "AI Conversation Archiver";

// 툴바 아이콘 클릭 시 현재 탭에 content script 주입 → 수집 → 서버 POST
chrome.action.onClicked.addListener(async (tab) => {
  try {
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      world: "MAIN", // 페이지 DOM 그 자체에서 실행
      func: scrapeConversation,
    });

    if (!result || !Array.isArray(result) || result.length === 0) {
      console.warn("No messages scraped");
      await notify("수집 실패", "메시지를 찾지 못했습니다. 페이지를 새로고침 후 다시 시도.");
      return;
    }

    const payload = {
      project: PROJECT,
      source: new URL(tab.url || location.href).hostname,
      conversation: result
    };

    const resp = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!resp.ok) {
      const t = await resp.text();
      throw new Error(`HTTP ${resp.status}: ${t}`);
    }

    await notify("저장 완료", "Obsidian Vault에 노트가 생성되었습니다.");
    console.log("Saved:", await resp.json());
  } catch (e) {
    console.error(e);
    await notify("에러", String(e).slice(0, 180));
  }
});

// 간단 알림(개발 중엔 console도 같이 확인)
async function notify(title, message) {
  // MV3에선 notifications 권한 없이도 기본 브라우저 알림은 제한됨 → console 병행
  console.log("NOTIFY:", title, message);
  // 필요시 notifications 권한 추가하고 아래 사용
  // chrome.notifications.create({ type:"basic", iconUrl:"icon128.png", title, message });
}

// 페이지에서 실행될 함수(사이트별 스크레이퍼)
function scrapeConversation() {
  const out = [];

  // 1) ChatGPT (chatgpt.com / openai.com)
  try {
    // 신형 UI/구형 UI를 모두 커버하려는 느슨한 셀렉터
    const nodes = document.querySelectorAll('[data-message-author-role], [data-testid="conversation-turn"]');
    if (nodes.length) {
      nodes.forEach(n => {
        let role = n.getAttribute("data-message-author-role");
        if (!role) {
          // 구형: user/assistant 라벨이 내부에 있을 수 있음
          const label = n.querySelector('[data-testid="conversation-turn"] [data-message-author-role]');
          role = label?.getAttribute("data-message-author-role") || "";
        }
        const text = (n.innerText || "").trim();
        if (!role) {
          // 휴지통: role 추정
          if (/^You$|^User$|^나$/.test(n.firstChild?.textContent||"")) role = "user";
          else role = "assistant";
        }
        if (text) out.push({ role, content: text });
      });
    }
  } catch (e) { /* noop */ }

  // 2) Gemini (gemini.google.com) — 너가 붙여준 실제 DOM 태그 기반
  try {
    if (out.length === 0 && /gemini\.google\.com|bard\.google\.com/.test(location.hostname)) {
      const userQs = document.querySelectorAll("user-query .query-text, user-query .user-query-bubble-with-background");
      const modelRs = document.querySelectorAll("message-content .markdown, model-response message-content, message-content");
      userQs.forEach(u => {
        const t = (u.innerText || "").trim();
        if (t) out.push({ role: "user", content: t });
      });
      modelRs.forEach(m => {
        const t = (m.innerText || "").trim();
        if (t) out.push({ role: "assistant", content: t });
      });
    }
  } catch (e) { /* noop */ }

  // 3) 기타(최후의 수단): 채팅 말풍선 비슷한 것들 모조리 긁기
  if (out.length === 0) {
    const guesses = document.querySelectorAll('div[class*="message"], div[class*="bubble"], article, section');
    guesses.forEach(el => {
      const txt = (el.innerText || "").trim();
      if (txt && txt.length > 3) {
        // 유저/어시스턴트 추정
        const role = /you:|user:|나:|질문[:：]/i.test(txt) ? "user" : "assistant";
        out.push({ role, content: txt });
      }
    });
  }

  // 클린업: 너무 긴 블록 잘라내기(서버가 길이 관리 하지만 1차 필터)
  const MAX_LEN = 4000;
  out.forEach(m => {
    if (m.content.length > MAX_LEN) m.content = m.content.slice(0, MAX_LEN);
  });

  return out;
}
