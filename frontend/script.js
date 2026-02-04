// ─────────────────────────────────────────────
// LOGIN PAGE LOGIC
// ─────────────────────────────────────────────
const loginBtn = document.getElementById("loginBtn");

if (loginBtn) {
  loginBtn.addEventListener("click", async () => {
    const emailInput = document.getElementById("emailInput");
    const email = emailInput ? emailInput.value.trim() : "";

    if (!email) {
      alert("Please enter your email");
      return;
    }

    loginBtn.disabled = true;
    loginBtn.textContent = "Please wait...";

    try {
      const res = await fetch("http://127.0.0.1:8000/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });

      if (!res.ok) {
        const err = await res.text();
        console.error("Login failed:", err);
        alert("Login failed. Please try again.");
        return;
      }

      const data = await res.json();

      if (!data.user_id) {
        console.error("Invalid login response:", data);
        alert("Login failed. Invalid server response.");
        return;
      }

      localStorage.setItem("user_id", data.user_id);
      window.location.href = "chat.html";
    } catch (error) {
      console.error("Network error:", error);
      alert("Backend not reachable");
    } finally {
      loginBtn.disabled = false;
      loginBtn.textContent = "Continue";
    }
  });
}


// ─────────────────────────────────────────────
// CHAT PAGE GUARD (VERY IMPORTANT)
// ─────────────────────────────────────────────
const chatWindow = document.getElementById("chatWindow");
const userInput = document.getElementById("userInput");
const sendBtn = document.getElementById("sendBtn");
const typingIndicator = document.getElementById("typingIndicator");

if (chatWindow) {
  const userId = localStorage.getItem("user_id");

  if (!userId || userId === "undefined") {
    alert("Session expired. Please login again.");
    localStorage.removeItem("user_id");
    window.location.href = "login.html";
  }
}


// ─────────────────────────────────────────────
// CHAT PAGE LOGIC
// ─────────────────────────────────────────────
if (sendBtn && userInput) {
  sendBtn.addEventListener("click", sendMessage);

  userInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      sendMessage();
    }
  });
}

async function sendMessage() {
  const message = userInput.value.trim();
  if (!message) return;

  const userId = localStorage.getItem("user_id");
  if (!userId) return;

  appendMessage(message, "user");
  userInput.value = "";

  if (typingIndicator) {
    typingIndicator.classList.remove("hidden");
  }

  try {
    const res = await fetch("http://127.0.0.1:8000/chat/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, message }),
    });

    if (!res.ok) {
      appendMessage("Something went wrong. Try again.", "niva");
      return;
    }

    const data = await res.json();
    renderNivaReply(data.reply);

  } catch (error) {
    appendMessage("Backend not reachable.", "niva");
  } finally {
    if (typingIndicator) {
      typingIndicator.classList.add("hidden");
    }
  }
}


// ─────────────────────────────────────────────
// MESSAGE RENDERING
// ─────────────────────────────────────────────

function escapeHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function formatInlineMarkdown(text) {
  let escaped = escapeHtml(text);
  // **bold**
  escaped = escaped.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  return escaped;
}

function formatMarkdownBlock(text) {
  const lines = text.split("\n");
  let html = "";
  let inList = false;

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;

    if (trimmed.startsWith("- ")) {
      if (!inList) {
        html += "<ul>";
        inList = true;
      }
      const item = trimmed.slice(2);
      html += "<li>" + formatInlineMarkdown(item) + "</li>";
    } else {
      if (inList) {
        html += "</ul>";
        inList = false;
      }
      html += "<p>" + formatInlineMarkdown(trimmed) + "</p>";
    }
  }

  if (inList) html += "</ul>";
  return html || formatInlineMarkdown(text);
}

function appendMessage(text, sender) {
  if (!chatWindow) return;

  const bubble = document.createElement("div");
  bubble.className = `bubble ${sender}`;

  if (sender === "niva") {
    bubble.innerHTML = formatMarkdownBlock(text);
  } else {
    bubble.textContent = text;
  }

  chatWindow.appendChild(bubble);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function renderNivaReply(replyText) {
  if (!replyText) return;

  // Expect up to 3 logical parts separated by newlines:
  // 1) short acknowledgement ("hmm samajh gayi")
  // 2) short validation/appreciation
  // 3) main detailed answer (may itself contain internal newlines / markdown)
  const rawParts = replyText
    .split("\n")
    .map((p) => p.trim())
    .filter((p) => p.length > 0);

  if (rawParts.length === 0) return;

  let greet = "";
  let appreciate = "";
  let main = "";

  if (rawParts.length === 1) {
    main = rawParts[0];
  } else if (rawParts.length === 2) {
    greet = rawParts[0];
    main = rawParts[1];
  } else {
    greet = rawParts[0];
    appreciate = rawParts[1];
    main = rawParts.slice(2).join("\n");
  }

  if (greet) appendMessage(greet, "niva");
  if (appreciate) appendMessage(appreciate, "niva");
  if (main) appendMessage(main, "niva");
}

