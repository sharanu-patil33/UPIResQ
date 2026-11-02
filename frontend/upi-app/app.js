const $ = (id) => document.getElementById(id);

const SESSION_KEY = "minipay_session";

let currentKey = makeKey();
let currentUser = null;

// ============================================================
// SESSION
// ============================================================

function saveSession(user) {
  currentUser = user;
  localStorage.setItem(SESSION_KEY, JSON.stringify(user));
}

function loadSession() {
  try {
    const saved = localStorage.getItem(SESSION_KEY);

    if (!saved) {
      currentUser = null;
      return null;
    }

    currentUser = JSON.parse(saved);

    if (!currentUser || !currentUser.account_id) {
      clearSession();
      return null;
    }

    return currentUser;
  } catch (error) {
    console.error("Session loading failed:", error);
    clearSession();
    return null;
  }
}

function clearSession() {
  currentUser = null;
  localStorage.removeItem(SESSION_KEY);
}

function isLoggedIn() {
  return !!currentUser && !!currentUser.account_id;
}

// ============================================================
// API
// ============================================================

async function apiCall(method, path, body) {
  const headers = {
    "Content-Type": "application/json",
  };

  if (currentUser && currentUser.token) {
    headers.Authorization = "Bearer " + currentUser.token;
  }

  const options = {
    method,
    headers,
  };

  if (body !== undefined && body !== null) {
    options.body = JSON.stringify(body);
  }

  let res;

  try {
    res = await fetch(CONFIG.API_BASE + path, options);
  } catch (error) {
    const networkError = new Error(
      "Could not connect to MiniPay server."
    );

    networkError.network = true;
    throw networkError;
  }

  if (!res.ok) {
    let detail = res.statusText || "Request failed";

    try {
      const data = await res.json();
      detail = data.detail || data.message || detail;
    } catch (error) {
      // Keep status text.
    }

    const error = new Error(detail);
    error.status = res.status;

    throw error;
  }

  return res.json();
}

// ============================================================
// AUTH UI
// ============================================================

function showAuthScreen(screen) {
  const authScreen = $("auth-screen");
  const loginView = $("login-view");
  const registerView = $("register-view");
  const appView = $("app-view");

  if (authScreen) {
    authScreen.hidden = false;
  }

  if (loginView) {
    loginView.hidden = screen !== "login";
  }

  if (registerView) {
    registerView.hidden = screen !== "register";
  }

  if (appView) {
    appView.hidden = true;
  }

  document.body.classList.remove("authenticated");
}

function showApplication() {
  if (!isLoggedIn()) {
    showAuthScreen("login");
    return;
  }

  const authScreen = $("auth-screen");
  const loginView = $("login-view");
  const registerView = $("register-view");
  const appView = $("app-view");

  if (authScreen) {
    authScreen.hidden = true;
  }

  if (loginView) {
    loginView.hidden = true;
  }

  if (registerView) {
    registerView.hidden = true;
  }

  if (appView) {
    appView.hidden = false;
  }

  document.body.classList.add("authenticated");

  updateUserUI();
  showTab("dashboard");
  loadDashboard();
}

function updateUserUI() {
  if (!currentUser) {
    return;
  }

  const name = currentUser.name || "User";
  const email = currentUser.email || "";
  const phone = currentUser.phone || "";

  const nameElements = [
    $("user-name"),
    $("profile-name"),
    $("sidebar-user-name"),
    $("welcome-name"),
  ];

  for (const element of nameElements) {
    if (element) {
      element.textContent = name;
    }
  }

  const emailElements = [
    $("user-email"),
    $("profile-email"),
    $("sidebar-user-email"),
  ];

  for (const element of emailElements) {
    if (element) {
      element.textContent = email;
    }
  }

  if ($("profile-phone")) {
    $("profile-phone").textContent = phone || "Not provided";
  }

  if ($("profile-account")) {
    $("profile-account").textContent =
      currentUser.account_id || "—";
  }

  const initials = name
    .split(" ")
    .filter(Boolean)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  for (const element of [
    $("user-avatar"),
    $("profile-avatar"),
    $("sidebar-avatar"),
  ]) {
    if (element) {
      element.textContent = initials || "U";
    }
  }
}

// ============================================================
// LOGIN
// ============================================================

async function login(email, password) {
  return apiCall("POST", "/auth/login", {
    email,
    password,
  });
}

// ============================================================
// REGISTER
// ============================================================

async function register(name, phone, email, password) {
  return apiCall("POST", "/auth/register", {
    name,
    phone,
    email,
    password,
  });
}

// ============================================================
// DASHBOARD
// ============================================================

async function loadDashboard() {
  if (!isLoggedIn()) {
    return;
  }

  await Promise.allSettled([
    loadBalance(),
    loadHistory(),
    loadAlerts(),
    loadCases(),
  ]);

  updateDashboardStats();
}

function updateDashboardStats() {
  if ($("dashboard-name")) {
    $("dashboard-name").textContent =
      currentUser?.name || "User";
  }

  if ($("transaction-count")) {
    // Updated by loadHistory when possible.
  }
}

async function loadBalance() {
  if (!currentUser || !currentUser.account_id) {
    return;
  }

  try {
    const account = await apiCall(
      "GET",
      "/accounts/" +
        encodeURIComponent(currentUser.account_id)
    );

    const balance = Number(account.balance);

    if ($("balance")) {
      $("balance").textContent = formatMoney(balance);
    }

    if ($("available-balance")) {
      $("available-balance").textContent =
        formatMoney(balance);
    }

    if ($("dashboard-balance")) {
      $("dashboard-balance").textContent =
        formatMoney(balance);
    }

    currentUser.balance = balance;

    localStorage.setItem(
      SESSION_KEY,
      JSON.stringify(currentUser)
    );
  } catch (error) {
    console.error("Balance loading failed:", error);

    if ($("balance")) {
      $("balance").textContent = "Unavailable";
    }
  }
}

// ============================================================
// CONTACTS
// ============================================================

function contactName(account) {
  const contact = (CONFIG.CONTACTS || []).find(
    (item) => item.account === account
  );

  return contact ? contact.name : account || "Unknown";
}

function populateContacts() {
  const receiver = $("receiver");

  if (!receiver) {
    return;
  }

  receiver.replaceChildren();

  for (const contact of CONFIG.CONTACTS || []) {
    if (
      currentUser &&
      contact.account === currentUser.account_id
    ) {
      continue;
    }

    const option = document.createElement("option");

    option.value = contact.account;
    option.textContent = contact.name;

    receiver.appendChild(option);
  }
}

// ============================================================
// HISTORY
// ============================================================

async function loadHistory() {
  if (!currentUser || !currentUser.account_id) {
    return;
  }

  const list = $("history-list");

  try {
    const rows = await apiCall(
      "GET",
      "/transactions?account_id=" +
        encodeURIComponent(currentUser.account_id)
    );

    if ($("transaction-count")) {
      $("transaction-count").textContent =
        Array.isArray(rows) ? rows.length : 0;
    }

    renderRecentTransactions(rows || []);

    if (!list) {
      return;
    }

    list.replaceChildren();

    if (!rows || rows.length === 0) {
      const empty = document.createElement("li");

      empty.className = "empty-state";
      empty.textContent = "No transactions yet";

      list.appendChild(empty);
      return;
    }

    for (const transaction of rows) {
      const sent =
        transaction.sender === currentUser.account_id;

      const person = contactName(
        sent ? transaction.receiver : transaction.sender
      );

      const state = describeState(transaction.state);

      const item = document.createElement("li");

      item.className = "transaction-item";

      const left = document.createElement("div");

      const direction = document.createElement("strong");
      direction.textContent = sent
        ? "Payment sent"
        : "Payment received";

      const personText = document.createElement("span");
      personText.textContent =
        (sent ? "To " : "From ") + person;

      left.append(direction, personText);

      const right = document.createElement("div");

      const amount = document.createElement("strong");
      amount.textContent =
        (sent ? "- " : "+ ") +
        formatMoney(transaction.amount);

      const status = document.createElement("span");
      status.textContent = state.title;
      status.className = state.tone || "";

      right.append(amount, status);

      item.append(left, right);

      item.addEventListener("click", () => {
        showTransactionDetails(transaction.id);
      });

      list.appendChild(item);
    }
  } catch (error) {
    console.error("History loading failed:", error);

    if (list) {
      list.replaceChildren();

      const errorItem = document.createElement("li");
      errorItem.className = "empty-state";
      errorItem.textContent =
        "Could not load transactions.";

      list.appendChild(errorItem);
    }
  }
}

function renderRecentTransactions(rows) {
  const container = $("recent-transactions");

  if (!container) {
    return;
  }

  container.replaceChildren();

  const recent = Array.isArray(rows)
    ? rows.slice(0, 5)
    : [];

  if (recent.length === 0) {
    container.textContent = "No recent transactions";
    return;
  }

  for (const transaction of recent) {
    const sent =
      transaction.sender === currentUser.account_id;

    const row = document.createElement("div");

    row.className = "recent-transaction";

    const name = document.createElement("span");

    name.textContent =
      (sent ? "To " : "From ") +
      contactName(
        sent
          ? transaction.receiver
          : transaction.sender
      );

    const amount = document.createElement("strong");

    amount.textContent =
      (sent ? "- " : "+ ") +
      formatMoney(transaction.amount);

    row.append(name, amount);

    row.addEventListener("click", () => {
      showTransactionDetails(transaction.id);
    });

    container.appendChild(row);
  }
}

// ============================================================
// TRANSACTION DETAILS
// ============================================================

async function showTransactionDetails(id) {
  try {
    const status = await apiCall(
      "GET",
      "/payment-status/" +
        encodeURIComponent(id)
    );

    renderStatus(status);

    const details = $("transaction-details");

    if (details) {
      details.hidden = false;

      details.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
    }

    const transactionView = $("transaction-view");

    if (transactionView) {
      transactionView.hidden = false;
    }
  } catch (error) {
    console.error(
      "Transaction details failed:",
      error
    );
  }
}

// ============================================================
// PAYMENT STATUS
// ============================================================

function renderStatus(status) {
  const statusCard = $("status-card");

  if (!statusCard) {
    return;
  }

  const description = describeState(status.state);

  statusCard.hidden = false;

  const title = $("status-title");

  if (title) {
    title.textContent = description.title;
    title.className = description.tone || "";
  }

  const last =
    status.timeline && status.timeline.length
      ? status.timeline[status.timeline.length - 1]
      : null;

  let message = "";

  if (status.state === "COMPLETED") {
    message =
      "The payment was completed successfully.";
  } else if (status.state === "FAILED") {
    message =
      "Reason: " +
      ((last && last.detail) ||
        "Payment could not be completed.");
  } else if (status.state === "TIMEOUT") {
    message =
      "We're checking the payment status. Please do not retry.";
  } else if (
    status.state === "RECONCILIATION_REQUIRED"
  ) {
    message =
      "The payment requires reconciliation. Please do not retry.";
  } else {
    message =
      "Your payment is being processed.";
  }

  const messageElement = $("status-message");

  if (messageElement) {
    messageElement.textContent = message;
  }

  const banner = $("status-banner");

  if (banner) {
    if (status.diagnosis) {
      let text =
        status.diagnosis.user_message ||
        status.diagnosis.reason ||
        "";

      if (
        status.recovery &&
        status.recovery.message
      ) {
        text += " " + status.recovery.message;
      }

      banner.textContent = text;

      banner.className =
        "banner" +
        (status.diagnosis.severity === "HIGH"
          ? " severe"
          : "");

      banner.hidden = false;
    } else {
      banner.hidden = true;
    }
  }

  const timeline = $("timeline");

  if (timeline) {
    timeline.replaceChildren();

    for (const event of status.timeline || []) {
      const item = document.createElement("li");

      const state = document.createElement("strong");
      state.textContent = event.to;

      const detail = document.createElement("span");

      if (event.detail) {
        detail.textContent = " — " + event.detail;
      }

      item.append(state, detail);

      timeline.appendChild(item);
    }
  }

  const icon = $("status-icon");

  if (icon) {
    switch (status.state) {
      case "COMPLETED":
        icon.textContent = "✓";
        break;

      case "FAILED":
        icon.textContent = "×";
        break;

      case "TIMEOUT":
        icon.textContent = "⏳";
        break;

      case "RECONCILIATION_REQUIRED":
        icon.textContent = "!";
        break;

      default:
        icon.textContent = "•";
    }
  }
}

async function showStatus(id) {
  for (let attempt = 0; attempt < 30; attempt++) {
    const status = await apiCall(
      "GET",
      "/payment-status/" +
        encodeURIComponent(id)
    );

    renderStatus(status);

    if (isFinal(status.state)) {
      return status;
    }

    await new Promise((resolve) =>
      setTimeout(resolve, 1000)
    );
  }

  return null;
}

// ============================================================
// SEND MONEY
// ============================================================

function showFormError(message) {
  const error = $("form-error");

  if (!error) {
    return;
  }

  error.textContent = message;
  error.hidden = false;
}

function clearFormError() {
  const error = $("form-error");

  if (error) {
    error.hidden = true;
    error.textContent = "";
  }
}

async function sendPayment(event) {
  event.preventDefault();

  if (!isLoggedIn()) {
    showAuthScreen("login");
    return;
  }

  const amountInput = $("amount");
  const receiverInput = $("receiver");
  const payButton = $("pay-btn");

  const problem = validateAmount(
    amountInput ? amountInput.value : ""
  );

  if (problem) {
    showFormError(problem);
    return;
  }

  if (!receiverInput || !receiverInput.value) {
    showFormError("Select a receiver.");
    return;
  }

  if (
    receiverInput.value ===
    currentUser.account_id
  ) {
    showFormError(
      "You cannot send money to your own account."
    );
    return;
  }

  clearFormError();

  if (payButton) {
    payButton.disabled = true;
    payButton.textContent = "Processing...";
  }

  try {
    const response = await apiCall(
      "POST",
      "/transactions",
      {
        idempotency_key: currentKey,
        sender_account_id:
          currentUser.account_id,
        receiver_account_id:
          receiverInput.value,
        amount: Number(amountInput.value),
      }
    );

    await showStatus(response.transaction_id);

    currentKey = makeKey();

    if (amountInput) {
      amountInput.value = "";
    }

    await loadBalance();
    await loadHistory();
  } catch (error) {
    console.error("Payment failed:", error);

    if (error.status) {
      showFormError(error.message);
    } else {
      showFormError(
        "Could not reach the payment server. You can safely retry."
      );
    }
  } finally {
    if (payButton) {
      payButton.disabled = false;
      payButton.textContent = "Pay";
    }
  }
}

// ============================================================
// TABS / NAVIGATION
// ============================================================

function showTab(name) {
  if (!isLoggedIn()) {
    showAuthScreen("login");
    return;
  }

  const views = {
    send: $("send-view"),
    history: $("history-view"),
    dashboard: $("dashboard-view"),
    security: $("security-view"),
    profile: $("profile-view"),
  };

  for (const [key, element] of Object.entries(views)) {
    if (element) {
      element.hidden = key !== name;
    }
  }

  const tabs = {
    send: $("tab-send"),
    history: $("tab-history"),
    dashboard: $("tab-dashboard"),
    security: $("tab-security"),
    profile: $("tab-profile"),
  };

  for (const [key, element] of Object.entries(tabs)) {
    if (element) {
      element.classList.toggle(
        "active",
        key === name
      );
    }
  }

  if (name === "history") {
    loadHistory();
  }

  if (name === "dashboard") {
    loadDashboard();
  }

  if (name === "security") {
    loadSecurityData();
  }

  if (name === "profile") {
    updateUserUI();
  }
}

// ============================================================
// SECURITY
// ============================================================

async function loadSecurityData() {
  try {
    const [alerts, cases] = await Promise.all([
      apiCall("GET", "/alerts"),
      apiCall("GET", "/cases"),
    ]);

    renderAlerts(alerts);
    renderCases(cases);
  } catch (error) {
    console.error(
      "Security data loading failed:",
      error
    );
  }
}

function renderAlerts(alerts) {
  const container = $("alerts-list");

  if (!container) {
    return;
  }

  container.replaceChildren();

  if (!alerts || alerts.length === 0) {
    const empty = document.createElement("div");

    empty.textContent = "No security alerts.";

    container.appendChild(empty);

    return;
  }

  for (const alert of alerts) {
    const item = document.createElement("div");

    item.className =
      "security-alert " +
      String(alert.severity || "").toLowerCase();

    const title = document.createElement("strong");

    title.textContent =
      (alert.severity || "INFO") +
      " alert";

    const message = document.createElement("p");

    message.textContent =
      alert.message ||
      "Security event detected.";

    item.append(title, message);

    container.appendChild(item);
  }
}

function renderCases(cases) {
  const container =
    $("cases-list") ||
    $("fraud-cases-list");

  if (!container) {
    return;
  }

  container.replaceChildren();

  if (!cases || cases.length === 0) {
    const empty = document.createElement("div");

    empty.textContent = "No fraud cases.";

    container.appendChild(empty);

    return;
  }

  for (const fraudCase of cases) {
    const item = document.createElement("div");

    item.className = "fraud-case";

    const title = document.createElement("strong");

    title.textContent =
      fraudCase.reason || "Fraud case";

    const status = document.createElement("span");

    status.textContent =
      fraudCase.status || "OPEN";

    item.append(title, status);

    container.appendChild(item);
  }
}

// ============================================================
// LOGOUT
// ============================================================

async function logout() {
  try {
    if (currentUser && currentUser.token) {
      await apiCall("POST", "/auth/logout");
    }
  } catch (error) {
    console.warn(
      "Server logout failed:",
      error
    );
  }

  clearSession();

  currentKey = makeKey();

  if ($("amount")) {
    $("amount").value = "";
  }

  if ($("status-card")) {
    $("status-card").hidden = true;
  }

  if ($("status-banner")) {
    $("status-banner").hidden = true;
  }

  showAuthScreen("login");

  const loginForm = $("login-form");

  if (loginForm) {
    loginForm.reset();
  }

  const registerForm = $("register-form");

  if (registerForm) {
    registerForm.reset();
  }
}

// ============================================================
// AUTH FORM EVENTS
// ============================================================

function setupAuthEvents() {
  // ----------------------------------------------------------
  // LOGIN FORM
  // ----------------------------------------------------------

  const loginForm = $("login-form");

  if (loginForm) {
    loginForm.addEventListener(
      "submit",
      async (event) => {
        event.preventDefault();

        const emailInput = $("login-email");
        const passwordInput = $("login-password");
        const error = $("login-error");
        const button = $("login-btn");

        const email =
          emailInput
            ? emailInput.value.trim()
            : "";

        const password =
          passwordInput
            ? passwordInput.value
            : "";

        if (!email || !password) {
          if (error) {
            error.textContent =
              "Enter your email and password.";
            error.hidden = false;
          }

          return;
        }

        if (button) {
          button.disabled = true;
          button.textContent = "Signing in...";
        }

        if (error) {
          error.hidden = true;
        }

        try {
          const result = await login(
            email,
            password
          );

          saveSession(result);

          showApplication();
        } catch (err) {
          console.error(
            "Login failed:",
            err
          );

          if (error) {
            error.textContent =
              err.message ||
              "Unable to sign in.";

            error.hidden = false;
          }
        } finally {
          if (button) {
            button.disabled = false;
            button.textContent = "Sign in";
          }
        }
      }
    );
  }

  // ----------------------------------------------------------
  // REGISTER FORM
  // ----------------------------------------------------------

  const registerForm = $("register-form");

  if (registerForm) {
    registerForm.addEventListener(
      "submit",
      async (event) => {
        event.preventDefault();

        const nameInput = $("register-name");
        const phoneInput = $("register-phone");
        const emailInput = $("register-email");
        const passwordInput = $("register-password");

        const error = $("register-error");
        const button = $("register-btn");

        const name =
          nameInput
            ? nameInput.value.trim()
            : "";

        const phone =
          phoneInput
            ? phoneInput.value.trim()
            : "";

        const email =
          emailInput
            ? emailInput.value.trim()
            : "";

        const password =
          passwordInput
            ? passwordInput.value
            : "";

        if (
          !name ||
          !phone ||
          !email ||
          !password
        ) {
          if (error) {
            error.textContent =
              "Please complete all fields.";
            error.hidden = false;
          }

          return;
        }

        if (password.length < 6) {
          if (error) {
            error.textContent =
              "Password must contain at least 6 characters.";
            error.hidden = false;
          }

          return;
        }

        if (button) {
          button.disabled = true;
          button.textContent =
            "Creating account...";
        }

        if (error) {
          error.hidden = true;
        }

        try {
          const result = await register(
            name,
            phone,
            email,
            password
          );

          if (result && result.account_id) {
            saveSession(result);
            showApplication();
          } else {
            showAuthScreen("login");

            const loginEmail =
              $("login-email");

            if (loginEmail) {
              loginEmail.value = email;
            }

            const loginError =
              $("login-error");

            if (loginError) {
              loginError.textContent =
                "Account created successfully. Please sign in.";
              loginError.hidden = false;
            }
          }
        } catch (err) {
          console.error(
            "Registration failed:",
            err
          );

          if (error) {
            error.textContent =
              err.message ||
              "Unable to create account.";

            error.hidden = false;
          }
        } finally {
          if (button) {
            button.disabled = false;
            button.textContent =
              "Create account";
          }
        }
      }
    );
  }

  // ----------------------------------------------------------
  // LOGIN -> REGISTER
  // ----------------------------------------------------------

  const showRegister = $("show-register");

  if (showRegister) {
    showRegister.addEventListener(
      "click",
      (event) => {
        event.preventDefault();

        const error = $("register-error");

        if (error) {
          error.hidden = true;
          error.textContent = "";
        }

        showAuthScreen("register");
      }
    );
  }

  // Backwards compatibility.
  const createAccount =
    $("create-account");

  if (createAccount) {
    createAccount.addEventListener(
      "click",
      (event) => {
        event.preventDefault();
        showAuthScreen("register");
      }
    );
  }

  // ----------------------------------------------------------
  // REGISTER -> LOGIN
  // ----------------------------------------------------------

  const showLogin = $("show-login");

  if (showLogin) {
    showLogin.addEventListener(
      "click",
      (event) => {
        event.preventDefault();

        const error = $("login-error");

        if (error) {
          error.hidden = true;
          error.textContent = "";
        }

        showAuthScreen("login");
      }
    );
  }

  // Backwards compatibility.
  const backToLogin =
    $("back-to-login");

  if (backToLogin) {
    backToLogin.addEventListener(
      "click",
      (event) => {
        event.preventDefault();
        showAuthScreen("login");
      }
    );
  }

  // ----------------------------------------------------------
  // LOGOUT BUTTONS
  // ----------------------------------------------------------

  for (const id of [
    "logout-btn",
    "topbar-logout",
    "sign-out",
    "sidebar-sign-out",
    "profile-logout-btn",
  ]) {
    const button = $(id);

    if (button) {
      button.addEventListener(
        "click",
        (event) => {
          event.preventDefault();
          logout();
        }
      );
    }
  }
}

// ============================================================
// NAVIGATION EVENTS
// ============================================================

function setupNavigation() {
  const navigation = {
    "tab-send": "send",
    "tab-history": "history",
    "tab-dashboard": "dashboard",
    "tab-security": "security",
    "tab-profile": "profile",
  };

  for (
    const [id, tab] of Object.entries(navigation)
  ) {
    const element = $(id);

    if (element) {
      element.addEventListener(
        "click",
        (event) => {
          event.preventDefault();
          showTab(tab);
        }
      );
    }
  }

  const dashboardHistoryButton =
    $("dashboard-history-btn");

  if (dashboardHistoryButton) {
    dashboardHistoryButton.addEventListener(
      "click",
      (event) => {
        event.preventDefault();
        showTab("history");
      }
    );
  }

  const transactionBackButton =
    $("transaction-back-btn");

  if (transactionBackButton) {
    transactionBackButton.addEventListener(
      "click",
      (event) => {
        event.preventDefault();

        const transactionView =
          $("transaction-view");

        if (transactionView) {
          transactionView.hidden = true;
        }

        showTab("history");
      }
    );
  }
}

// ============================================================
// STARTUP
// ============================================================

function initializeApp() {
  loadSession();

  setupAuthEvents();
  setupNavigation();

  const paymentForm = $("pay-form");

  if (paymentForm) {
    paymentForm.addEventListener(
      "submit",
      sendPayment
    );
  }

  populateContacts();

  if (isLoggedIn()) {
    showApplication();
  } else {
    showAuthScreen("login");
  }
}

initializeApp();