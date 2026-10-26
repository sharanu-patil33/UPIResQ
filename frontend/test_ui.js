const { JSDOM } = require("jsdom");
const path = require("path");
const API = "http://localhost:8765";
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
async function until(fn, label, ms = 5000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) { if (fn()) return; await wait(50); }
  throw new Error("timed out waiting for: " + label);
}
async function setSim(receiver) {
  await fetch(API + "/sim/config", { method: "POST", headers: { "Content-Type": "application/json" },
                                      body: JSON.stringify({ sender: "SUCCESS", receiver }) });
}
(async () => {
  const dom = await JSDOM.fromFile(path.join(__dirname, "upi-app/index.html"), {
    runScripts: "dangerously", resources: "usable", pretendToBeVisual: true,
    beforeParse(window) { window.fetch = fetch; },
  });
  const w = dom.window, d = w.document;
  await until(() => d.getElementById("receiver").options.length === 2, "contacts loaded");
  w.eval(`CONFIG.API_BASE = "${API}"`);                      // point the page at the test server
  await w.eval("loadBalance()");
  await until(() => /50,000/.test(d.getElementById("balance").textContent), "balance shown");
  console.log("balance shown:", d.getElementById("balance").textContent);

  const pay = async (amount) => {
    d.getElementById("amount").value = String(amount);
    d.getElementById("pay-form").dispatchEvent(new w.Event("submit", { cancelable: true }));
  };

  // 1. empty amount is rejected on screen
  await pay("");
  await until(() => !d.getElementById("form-error").hidden, "validation error");
  console.log("validation:", d.getElementById("form-error").textContent);

  // 2. normal payment
  await setSim("SUCCESS");
  await pay(1000);
  await until(() => d.getElementById("status-title").textContent === "Payment completed", "completed");
  console.log("normal   :", d.getElementById("status-title").textContent, "| banner hidden:", d.getElementById("status-banner").hidden);

  // 3. receiver never credits -> stuck state, banner with do-not-retry + recovery estimate
  await until(() => !d.getElementById("pay-btn").disabled, "button re-enabled");
  await setSim("TIMEOUT");
  await pay(500);
  await until(() => d.getElementById("status-title").textContent === "Payment under review", "under review");
  const banner = d.getElementById("status-banner");
  console.log("stuck    :", d.getElementById("status-title").textContent, "| banner:", !banner.hidden);
  console.log("  banner text:", banner.textContent.slice(0, 110) + "...");
  if (!/do not retry/i.test(banner.textContent) || !/estimate/i.test(banner.textContent)) throw new Error("banner missing guidance");

  // 4. history lists both payments
  await until(() => d.getElementById("history-list").children.length >= 2, "history rows");
  console.log("history  :", d.getElementById("history-list").children.length, "rows");

  // 5. network failure keeps the same idempotency key
  await until(() => !d.getElementById("pay-btn").disabled, "button re-enabled");
  const keyBefore = w.eval("currentKey");
  w.eval(`CONFIG.API_BASE = "http://localhost:1"`);     // nothing listens here
  await pay(200);
  await until(() => /safe to retry/i.test(d.getElementById("form-error").textContent), "network error msg");
  console.log("offline  :", d.getElementById("form-error").textContent);
  console.log("same key kept after network failure:", keyBefore === w.eval("currentKey"));
  if (keyBefore !== w.eval("currentKey")) throw new Error("key changed after network failure");
  w.close();
  console.log("UI test: all checks passed");
  process.exit(0);
})().catch((e) => { console.error("UI test FAILED:", e.message); process.exit(1); });
