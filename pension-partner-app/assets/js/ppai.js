/* ════════════════════════════════════════════════════════════════
   PENSION PARTNER — ppAI gateway (ppai.js)  · PROMPT V5 · Pass 2 (vision)
   The single AI entry point for the whole app. No component calls
   window.claude.complete directly any more — everything goes through
   window.ppAI. Two modes:
     · "integrated" — inside Claude, delegates to window.claude.complete
                      (text); attempts a key-less vision call for documents
                      and degrades gracefully to text if unavailable.
     · "byok"       — exported file, fetches api.anthropic.com with the
                      user's own key (held in memory only, never stored).
                      Full native PDF/image vision.
   NEW in Pass 2: completeJSONWithDocs() sends the actual PDF/image to the
   model as document/image content blocks, so scanned returns and phone
   photos are read by Claude's vision instead of failing pdf.js text.
   window.ppAI
   ════════════════════════════════════════════════════════════════ */
(function () {
  // BYOK key. Pass 3: optionally REMEMBERED in this browser (localStorage),
  // like the original CFO build's "API key remembered". Cleared on Forget or
  // when the API rejects it (401/403). Set window.PP_AI_REMEMBER=false before
  // load to force memory-only.
  var STORE_KEY = "pp_api_key";
  var REMEMBER = (window.PP_AI_REMEMBER !== false);
  var KEY = null;
  if (REMEMBER) { try { var s = window.localStorage && localStorage.getItem(STORE_KEY); if (s && /^sk-ant-/.test(s)) KEY = s; } catch (e) {} }
  function persist(k) { if (!REMEMBER) return; try { if (k) localStorage.setItem(STORE_KEY, k); else localStorage.removeItem(STORE_KEY); } catch (e) {} }
  var inflight = 0, queue = [];   // simple concurrency limiter (max 2)
  var MAX = 2;

  // ── centralised model + API config (change in one place) ────────
  var MODEL = "claude-sonnet-4-6";   // verify the current recommended model at docs.claude.com
  var API_VERSION = "2023-06-01";
  var MAX_TOKENS = 2000;
  // expose for easy override without editing the file
  if (window.PP_AI_MODEL) MODEL = window.PP_AI_MODEL;

  function hasIntegrated() { return !!(window.claude && typeof window.claude.complete === "function"); }

  var ppAI = {
    get mode() { return hasIntegrated() ? "integrated" : (KEY ? "byok" : "byok"); },
    get ready() { return hasIntegrated() || !!KEY; },
    needsKey: function () { return !hasIntegrated() && !KEY; },
  };

  // ── network queue ───────────────────────────────────────────────
  function pump() {
    while (inflight < MAX && queue.length) {
      var job = queue.shift();
      inflight++;
      job.run().then(function (v) { inflight--; job.resolve(v); pump(); },
        function (e) { inflight--; job.reject(e); pump(); });
    }
  }
  function enqueue(run, signal) {
    return new Promise(function (resolve, reject) {
      if (signal && signal.aborted) { reject(new Error("aborted")); return; }
      queue.push({ run: run, resolve: resolve, reject: reject });
      pump();
    });
  }

  // ── extract joined text from a messages response ────────────────
  function textOf(j) {
    return (j.content || []).filter(function (b) { return b.type === "text"; }).map(function (b) { return b.text; }).join("");
  }

  // ── raw byok fetch · `content` may be a string OR a blocks array ─
  function byokCall(content, key) {
    return fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-api-key": key || KEY,
        "anthropic-version": API_VERSION,
        "anthropic-dangerous-direct-browser-access": "true",
      },
      body: JSON.stringify({
        model: MODEL,
        max_tokens: MAX_TOKENS,
        messages: [{ role: "user", content: content }],
      }),
    }).then(function (r) {
      if (!r.ok) return r.text().then(function (t) { throw new Error("HTTP " + r.status + " " + t.slice(0, 160)); });
      return r.json();
    }).then(textOf);
  }

  // ── key-less fetch for INTEGRATED (Claude) runtime · vision attempt ─
  // Inside Claude the runtime injects auth, so no x-api-key is sent.
  // Used only for document/image content; on any failure the caller
  // degrades to window.claude.complete(text).
  function keylessCall(content) {
    return fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ model: MODEL, max_tokens: MAX_TOKENS, messages: [{ role: "user", content: content }] }),
    }).then(function (r) {
      if (!r.ok) return r.text().then(function (t) { throw new Error("HTTP " + r.status + " " + t.slice(0, 120)); });
      return r.json();
    }).then(textOf);
  }

  // ── File → base64 (no data: prefix) ─────────────────────────────
  function fileToB64(file) {
    return new Promise(function (res, rej) {
      var r = new FileReader();
      r.onload = function () { res(String(r.result).split(",")[1] || ""); };
      r.onerror = function () { rej(new Error("read-failed")); };
      r.readAsDataURL(file);
    });
  }

  // ── docs[] (File or {data,mime}) → document/image content blocks ─
  function toBlocks(docs) {
    return Promise.all((docs || []).map(function (d) {
      var mime = (d && (d.mime || d.type)) || "application/pdf";
      var p = (d && d.data) ? Promise.resolve(d.data) : fileToB64(d);
      return p.then(function (b64) {
        if (/^image\//.test(mime)) return { type: "image", source: { type: "base64", media_type: mime, data: b64 } };
        return { type: "document", source: { type: "base64", media_type: "application/pdf", data: b64 } };
      });
    }));
  }
  function contentArray(prompt, blocks) { return blocks.concat([{ type: "text", text: prompt }]); }

  // ── public: complete (raw text) ─────────────────────────────────
  ppAI.complete = function (prompt, opts) {
    opts = opts || {};
    return enqueue(function () {
      if (hasIntegrated()) return Promise.resolve(window.claude.complete(prompt));
      if (KEY) return byokCall(prompt, KEY).catch(function (e) {
        if (/HTTP 401|HTTP 403/.test(String(e.message))) { KEY = null; persist(null); ppAI._fireKeyError(String(e.message)); }
        throw e;
      });
      ppAI._fireKeyNeeded();
      return Promise.reject(new Error("no-engine"));
    }, opts.signal);
  };

  // ── public: completeJSON (robust parse + 1 silent retry) ────────
  function parseJSON(raw) {
    if (raw == null) throw new Error("empty");
    var s = String(raw).replace(/```json/gi, "").replace(/```/g, "");
    var a = s.indexOf("{"), b = s.lastIndexOf("}");
    var aa = s.indexOf("["), bb = s.lastIndexOf("]");
    // prefer whichever bracket type appears first / is outermost
    if (aa !== -1 && (aa < a || a === -1)) { return JSON.parse(s.slice(aa, bb + 1)); }
    if (a === -1) throw new Error("no-json");
    return JSON.parse(s.slice(a, b + 1));
  }
  ppAI.completeJSON = function (prompt, opts) {
    return ppAI.complete(prompt, opts).then(function (raw) {
      try { return parseJSON(raw); }
      catch (e) {
        // one silent retry with a stricter nudge
        return ppAI.complete(prompt + "\n\nReturn ONLY valid JSON, no prose, no code fences.", opts).then(parseJSON);
      }
    });
  };

  // ── public: can we send documents to vision right now? ──────────
  ppAI.canVision = function () { return hasIntegrated() || !!KEY; };

  // ── public: completeWithDocs (prompt + actual PDF/image files) ──
  // `docs` = array of File objects (or {data:b64, mime}). The prompt
  // SHOULD also embed a text dump of the document as a fallback, so the
  // integrated degrade-path (window.claude.complete, text-only) still works.
  ppAI.completeWithDocs = function (prompt, docs, opts) {
    opts = opts || {};
    return enqueue(function () {
      return toBlocks(docs).then(function (blocks) {
        if (KEY) {
          return byokCall(contentArray(prompt, blocks), KEY).catch(function (e) {
            if (/HTTP 401|HTTP 403/.test(String(e.message))) { KEY = null; persist(null); ppAI._fireKeyError(String(e.message)); }
            throw e;
          });
        }
        if (hasIntegrated()) {
          // try native vision via the key-less runtime; degrade to text on any failure
          return keylessCall(contentArray(prompt, blocks))
            .catch(function () { return window.claude.complete(prompt); });
        }
        ppAI._fireKeyNeeded();
        return Promise.reject(new Error("no-engine"));
      });
    }, opts.signal);
  };

  ppAI.completeJSONWithDocs = function (prompt, docs, opts) {
    return ppAI.completeWithDocs(prompt, docs, opts).then(function (raw) {
      try { return parseJSON(raw); }
      catch (e) {
        return ppAI.completeWithDocs(prompt + "\n\nReturn ONLY valid JSON, no prose, no code fences.", docs, opts).then(parseJSON);
      }
    });
  };

  // ── public: connect (validate key with a tiny real call) ────────
  ppAI.connect = function (apiKey) {
    var k = (apiKey || "").trim();
    if (!/^sk-ant-/.test(k)) return Promise.reject(new Error("That doesn't look like an Anthropic key (it should start with sk-ant-)."));
    return byokCall("Reply with the single word: ok", k).then(function (txt) {
      KEY = k;
      persist(k);
      ppAI._fireChange();
      return true;
    }).catch(function (e) {
      var m = String(e.message || "");
      if (/HTTP 401|HTTP 403/.test(m)) throw new Error("That key was rejected. Check it and try again.");
      if (/Failed to fetch|NetworkError/i.test(m)) throw new Error("Couldn't reach Anthropic. Check your connection.");
      throw new Error("Couldn't validate the key. " + m.slice(0, 120));
    });
  };
  ppAI.disconnect = function () { KEY = null; persist(null); ppAI._fireChange(); };

  // ── tiny event bus for the key modal + footer badge ─────────────
  var listeners = { change: [], keyNeeded: [], keyError: [] };
  ppAI.on = function (ev, fn) { (listeners[ev] || (listeners[ev] = [])).push(fn); return function () { listeners[ev] = listeners[ev].filter(function (f) { return f !== fn; }); }; };
  ppAI._fireChange = function () { listeners.change.forEach(function (f) { try { f(ppAI.mode); } catch (e) {} }); };
  ppAI._fireKeyNeeded = function () { listeners.keyNeeded.forEach(function (f) { try { f(); } catch (e) {} }); };
  ppAI._fireKeyError = function (m) { listeners.keyError.forEach(function (f) { try { f(m); } catch (e) {} }); };

  ppAI.badgeLabel = function () { return hasIntegrated() ? "Engine: integrated" : (KEY ? "Engine: personal key" : "Engine: not connected"); };

  window.ppAI = ppAI;
})();
