// ─────────────────────────────────────────────
// LOGIN PAGE LOGIC
// ─────────────────────────────────────────────
const loginBtn = document.getElementById("loginBtn");

if (loginBtn) {
  loginBtn.addEventListener("click", async () => {
    const emailInput = document.getElementById("emailInput");
    const email = emailInput.value.trim();

    if (!email) {
      alert("Please enter your email");
      return;
    }

    try {
      const res = await fetch("http://127.0.0.1:8000/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });

      if (!res.ok) {
        const err = await res.text();
        console.error("Login failed:", err);
        alert("Login failed. Check backend logs.");
        return;
      }

      const data = await res.json();
      localStorage.setItem("user_id", data.user_id);

      window.location.href = "chat.html";
    } catch (error) {
      console.error("Network error:", error);
      alert("Backend not reachable");
    }
  });
}


// ─────────────────────────────────────────────
// CHAT PAGE LOGIC
// ─────────────────────────────────────────────
const sendBtn = document.getElementById("sendBtn");
const userInput = document.getElementById("userInput");
const chatWindow = document.getElementById("chatWindow");
const typingIndicator = document.getElementById("typingIndicator");

if (sendBtn) {
  sendBtn.addEventListener("click", sendMessage);
}

if (userInput) {
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
  if (!userId) {
    alert("User not logged in. Please login again.");
    window.location.href = "login.html";
    return;
  }

  // Show user message
  appendMessage(message, "user");
  userInput.value = "";

  // Show typing indicator
  typingIndicator.style.display = "block";

  try {
    const res = await fetch("http://127.0.0.1:8000/chat/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: userId,
        message: message,
      }),
    });

    if (!res.ok) {
      const err = await res.text();
      console.error("Chat error:", err);
      appendMessage("Something went wrong. Please try again.", "niva");
      typingIndicator.style.display = "none";
      return;
    }

    const data = await res.json();

    typingIndicator.style.display = "none";
    appendMessage(data.reply, "niva");

  } catch (error) {
    console.error("Network error:", error);
    typingIndicator.style.display = "none";
    appendMessage("Backend not reachable.", "niva");
  }
}


// ─────────────────────────────────────────────
// MESSAGE RENDERING (🔥 FIXED PART 🔥)
// ─────────────────────────────────────────────
function appendMessage(text, sender) {
  const bubble = document.createElement("div");
  bubble.className = `bubble ${sender}`;

  // ✅ Render Markdown properly
  if (sender === "niva" && window.marked) {
    bubble.innerHTML = marked.parse(text);
  } else {
    bubble.textContent = text;
  }

  chatWindow.appendChild(bubble);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}
