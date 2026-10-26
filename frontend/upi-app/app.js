const $ = (id) => document.getElementById(id);
let currentKey = makeKey();      // one key per payment attempt

// ---------- API ----------
async function apiCall(method, path, body) {
  const res = await fetch(CONFIG.API_BASE + path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (e) { /* keep statusText */ }
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

// ---------- Screens ----------
function showTab(name) {
  $("send-view").hidden = name !== "send";
  $("history-view").hidden = name !== "history";
  $("tab-send").classList.toggle("active", name === "send");
  $("tab-history").classList.toggle("active", name === "history");
  if (name === "history") loadHistory();
}

function contactName(account) {
  const c = CONFIG.CONTACTS.find((x) => x.account === account);
  return c ? c.name : account;
}

async function loadBalance() {
  try {
    const acc = await apiCall("GET", "/accounts/" + CONFIG.MY_ACCOUNT);
    $("balance").textContent = formatMoney(acc.balance);
  } catch (e) {
    $("balance").textContent = "unavailable";
  }
}

async function loadHistory() {
  const list = $("history-list");
  try {
    const rows = await apiCall("GET", "/transactions?account_id=" + CONFIG.MY_ACCOUNT);
    list.replaceChildren();
    if (rows.length === 0) {
      const li = document.createElement("li");
      li.textContent = "No payments yet";
      list.appendChild(li);
    }
    for (const t of rows) {
      const li = document.createElement("li");
      const sent = t.sender === CONFIG.MY_ACCOUNT;
      const who = contactName(sent ? t.receiver : t.sender);
      const left = document.createElement("span");
      left.textContent = (sent ? "To " : "From ") + who;
      const right = document.createElement("span");
      right.textContent = formatMoney(t.amount) + " - " + describeState(t.state).title;
      right.className = describeState(t.state).tone;
      li.append(left, right);
      li.addEventListener("click", () => { showTab("send"); showStatus(t.id); });
      list.appendChild(li);
    }
  } catch (e) {
    list.textContent = "Could not load history";
  }
}

function renderStatus(s) {
  const d = describeState(s.state);
  $("status-card").hidden = false;
  $("status-title").textContent = d.title;
  $("status-title").className = d.tone;

  const last = s.timeline.length ? s.timeline[s.timeline.length - 1] : null;
  let message = "";
  if (s.state === "COMPLETED") message = "The money has reached the receiver.";
  else if (s.state === "FAILED") message = "Reason: " + ((last && last.detail) || "not available");
  else if (s.diagnosis) message = s.diagnosis.reason;
  $("status-message").textContent = message;

  const banner = $("status-banner");
  if (s.diagnosis) {
    let text = s.diagnosis.user_message;
    if (s.recovery) text += " " + s.recovery.message;
    banner.textContent = text;
    banner.className = "banner" + (s.diagnosis.severity === "HIGH" ? " severe" : "");
    banner.hidden = false;
  } else {
    banner.hidden = true;
  }

  const tl = $("timeline");
  tl.replaceChildren();
  for (const ev of s.timeline) {
    const li = document.createElement("li");
    li.textContent = ev.to + (ev.detail ? " (" + ev.detail + ")" : "");
    tl.appendChild(li);
  }
}

async function showStatus(id) {
  for (let i = 0; i < 30; i++) {            // poll up to about 30 seconds
    const s = await apiCall("GET", "/payment-status/" + id);
    renderStatus(s);
    if (isFinal(s.state)) return s;
    await new Promise((r) => setTimeout(r, 1000));
  }
}

function showFormError(text) {
  $("form-error").textContent = text;
  $("form-error").hidden = false;
}

// ---------- Events ----------
$("pay-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const problem = validateAmount($("amount").value);
  if (problem) return showFormError(problem);
  $("form-error").hidden = true;
  $("pay-btn").disabled = true;                // stops double taps
  try {
    const res = await apiCall("POST", "/transactions", {
      idempotency_key: currentKey,
      sender_account_id: CONFIG.MY_ACCOUNT,
      receiver_account_id: $("receiver").value,
      amount: Number($("amount").value),
    });
    await showStatus(res.transaction_id);
    currentKey = makeKey();                    // it reached the server: next payment is new
    $("amount").value = "";
    loadBalance();
    loadHistory();
  } catch (err) {
    // Keep the SAME key. If the request did reach the server, paying again is safe.
    showFormError(err.status ? err.message
      : "Could not reach the server. Tap Pay again. It is safe to retry.");
  } finally {
    $("pay-btn").disabled = false;
  }
});

$("tab-send").addEventListener("click", () => showTab("send"));
$("tab-history").addEventListener("click", () => showTab("history"));

// ---------- Start ----------
for (const c of CONFIG.CONTACTS) {
  const opt = document.createElement("option");
  opt.value = c.account;
  opt.textContent = c.name;
  $("receiver").appendChild(opt);
}
loadBalance();
loadHistory();
