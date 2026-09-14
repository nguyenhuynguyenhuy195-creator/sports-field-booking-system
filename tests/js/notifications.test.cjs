// Offline DOM/timer contract test: executes the production script, no packages.
const assert = require("node:assert/strict");
const vm = require("node:vm");
const fs = require("node:fs");

class Element {
    constructor(tag = "div") { this.tag = tag; this.childNodes = []; this.dataset = {}; this.events = {}; }
    append(...nodes) { this.childNodes.push(...nodes); }
    replaceChildren(fragment) { this.childNodes = [...fragment.childNodes]; }
    contains(node) { return this === node || this.childNodes.some(child => child.contains(node)); }
    setAttribute(key, value) { this[key] = value; }
    addEventListener(key, callback) { this.events[key] = callback; }
    click() { this.events.click?.(); }
    focus() { this.focused = true; }
    set innerHTML(_) { throw Error("Unsafe HTML insertion"); }
}

function setup(loggedIn = true) {
    const center = new Element(), items = new Element(), badge = new Element(), bell = new Element();
    const chatLauncher = new Element("button"), chatPanel = new Element(), chatClose = new Element("button");
    chatPanel.hidden = false;
    chatClose.addEventListener("click", () => { chatPanel.hidden = true; });
    center.dataset = { recentUrl: "/notifications/recent", csrfToken: "test-csrf" };
    center.querySelector = selector => ({"[data-notification-items]": items, "[data-notification-count]": badge, "#notificationBell": bell})[selector];
    const document = { hidden: false, activeElement: null,
        querySelector: selector => loggedIn ? ({"[data-notification-center]": center,
            "[data-chatbot-launcher]": chatLauncher, "[data-chatbot-panel]": chatPanel,
            "[data-chatbot-close]": chatClose})[selector] : null, querySelectorAll: () => [],
        createElement: tag => new Element(tag), createDocumentFragment: () => new Element("fragment") };
    const requests = [], intervals = [], timeouts = [];
    const context = { document, AbortController, Date, console,
        window: {bootstrap: {Dropdown: {getInstance: () => ({hide: () => { bell.dropdownHidden = true; }})}}},
        setTimeout: (fn, ms) => { timeouts.push({fn, ms}); return timeouts.length; }, clearTimeout: () => {},
        setInterval: (fn, ms) => intervals.push({fn, ms}),
        fetch: (url, options) => new Promise((resolve, reject) => requests.push({url, options, resolve, reject})) };
    vm.runInNewContext(fs.readFileSync("app/static/js/notifications.js", "utf8"), context);
    return {document, requests, intervals, timeouts, items, badge, bell, chatLauncher, chatPanel};
}
const tick = () => new Promise(resolve => setImmediate(resolve));
const response = data => ({ok: true, status: 200, redirected: false, json: async () => data});

(async () => {
    const anonymous = setup(false);
    assert.equal(anonymous.requests.length, 0);
    assert.equal(anonymous.intervals.length, 0);
    const app = setup();
    app.bell.events["show.bs.dropdown"]();
    assert.equal(app.chatPanel.hidden, true, "Opening notifications closes the overlapping chatbot panel");
    assert.equal(app.bell.focused, true);
    app.chatLauncher.click();
    assert.equal(app.bell.dropdownHidden, true, "Chat launcher closes the notification dropdown");
    assert.equal(app.requests.length, 1);
    assert.equal(app.requests[0].url, "/notifications/recent");
    assert.equal(app.requests[0].options.credentials, "same-origin");
    assert.equal(app.intervals[0].ms, 30000);
    assert.equal(app.timeouts[0].ms, 10000);
    app.intervals[0].fn();
    assert.equal(app.requests.length, 1, "Only one request may be in flight");
    const data = {unread_count: 7, notifications: Array.from({length: 7}, (_, i) => ({
        id: i + 1, title: "<script>alert(1)</script>", message: "<img onerror=evil>",
        is_read: false, target_url: i ? "/matches/4" : "//evil.test", created_at: "2026-09-14T00:00:00Z"
    }))};
    app.requests[0].resolve(response(data));
    await tick();
    assert.equal(app.items.childNodes.length, 5);
    const first = app.items.childNodes[0];
    assert.equal(first.childNodes[0].href, "/notifications");
    assert.equal(first.childNodes[0].childNodes[0].textContent, data.notifications[0].title);
    assert.equal(first.childNodes[1].method, "post");
    assert.equal(first.childNodes[1].action, "/notifications/1/read");
    assert.equal(first.childNodes[1].childNodes[0].value, "test-csrf");
    assert.equal(app.badge.hidden, false);
    assert.equal(app.badge.textContent, "7");
    app.intervals[0].fn();
    app.requests[1].reject(Error("temporary failure"));
    await tick();
    assert.equal(app.items.childNodes[0], first, "Failure preserves existing UI");
    app.document.hidden = true;
    app.intervals[0].fn();
    assert.equal(app.requests.length, 2);
    app.document.hidden = false;
    app.intervals[0].fn();
    app.requests[2].resolve(response({unread_count: 0, notifications: []}));
    await tick();
    assert.equal(app.badge.hidden, true);
    app.intervals[0].fn();
    app.requests[3].resolve({status: 403});
    await tick();
    app.intervals[0].fn();
    assert.equal(app.requests.length, 4, "Forbidden response stops polling");
    console.log("Notification DOM/polling contract passed");
})().catch(error => { console.error(error); process.exitCode = 1; });
