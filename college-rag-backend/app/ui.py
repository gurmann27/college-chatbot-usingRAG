"""Built-in web chat frontend served directly by FastAPI at `/`."""
from __future__ import annotations

INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Bennett University — Multilingual AI Campus Assistant</title>
  <style>
    :root {
      --bg: #f5f5f7;
      --panel: rgba(255, 255, 255, 0.86);
      --card: #ffffff;
      --border: rgba(0, 0, 0, 0.08);
      --ink: #1d1d1f;
      --muted: #6e6e73;
      --accent: #0071e3;
      --accent-soft: rgba(0, 113, 227, 0.1);
      --green: #1d8348;
      --green-soft: rgba(29, 131, 72, 0.12);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Inter, sans-serif;
      background: var(--bg);
      color: var(--ink);
      height: 100vh;
      display: flex;
      overflow: hidden;
    }
    aside {
      width: 280px;
      background: var(--panel);
      backdrop-filter: blur(20px);
      border-right: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      padding: 16px;
      gap: 12px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
      font-weight: 700;
      font-size: 16px;
      padding: 4px 6px;
    }
    .brand-badge {
      width: 32px;
      height: 32px;
      border-radius: 10px;
      background: linear-gradient(135deg, #c0392b, #0071e3);
      color: #fff;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 800;
      font-size: 14px;
    }
    .btn {
      border: 1px solid var(--border);
      background: var(--card);
      color: var(--ink);
      border-radius: 12px;
      padding: 10px 12px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      transition: all 0.15s ease;
    }
    .btn:hover { background: #eef1f6; }
    .btn-primary {
      background: var(--accent);
      color: #fff;
      border-color: var(--accent);
    }
    .btn-primary:hover { background: #005bb5; }
    .section-label {
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--muted);
      margin-top: 6px;
      padding: 0 4px;
    }
    .doc-list, .session-list {
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .doc-list { flex: 1; }
    .doc-item {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 8px 10px;
      font-size: 12px;
      display: flex;
      flex-direction: column;
      gap: 4px;
      cursor: pointer;
    }
    .doc-item.selected {
      border-color: var(--accent);
      background: var(--accent-soft);
    }
    .doc-title {
      font-weight: 600;
      word-break: break-word;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 6px;
    }
    .doc-meta {
      color: var(--muted);
      font-size: 11px;
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
    }
    .pill {
      padding: 2px 6px;
      border-radius: 999px;
      font-size: 10px;
      font-weight: 600;
      background: var(--green-soft);
      color: var(--green);
      white-space: nowrap;
      flex-shrink: 0;
    }
    .doc-actions {
      display: flex;
      justify-content: flex-end;
      margin-top: 2px;
    }
    .mini-btn {
      border: 1px solid var(--border);
      background: #f8f9fb;
      color: var(--accent);
      border-radius: 6px;
      padding: 3px 7px;
      font-size: 10px;
      font-weight: 600;
      cursor: pointer;
    }
    .mini-btn:hover {
      background: var(--accent-soft);
    }
    main {
      flex: 1;
      display: flex;
      flex-direction: column;
      height: 100vh;
      min-width: 0;
    }
    header {
      height: 58px;
      padding: 0 24px;
      border-bottom: 1px solid var(--border);
      background: var(--panel);
      backdrop-filter: blur(20px);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .chat-scroll {
      flex: 1;
      overflow-y: auto;
      padding: 24px;
      display: flex;
      flex-direction: column;
      gap: 16px;
      max-width: 900px;
      width: 100%;
      margin: 0 auto;
    }
    .welcome {
      margin: auto;
      text-align: center;
      max-width: 640px;
      padding: 24px;
    }
    .welcome h2 {
      font-size: 26px;
      margin: 0 0 8px;
      letter-spacing: -0.02em;
    }
    .welcome p {
      color: var(--muted);
      font-size: 14px;
      margin: 0 0 20px;
    }
    .chips {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      justify-content: center;
    }
    .chip {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 8px 14px;
      font-size: 13px;
      cursor: pointer;
      transition: all 0.15s;
    }
    .chip:hover {
      border-color: var(--accent);
      color: var(--accent);
    }
    .msg {
      display: flex;
      flex-direction: column;
      gap: 6px;
      max-width: 82%;
    }
    .msg.user { align-self: flex-end; align-items: flex-end; }
    .msg.assistant { align-self: flex-start; align-items: flex-start; }
    .bubble {
      padding: 12px 16px;
      border-radius: 16px;
      font-size: 14px;
      line-height: 1.55;
      white-space: pre-wrap;
    }
    .msg.user .bubble {
      background: var(--accent);
      color: #fff;
      border-bottom-right-radius: 4px;
    }
    .msg.assistant .bubble {
      background: var(--card);
      border: 1px solid var(--border);
      border-bottom-left-radius: 4px;
    }
    .sources {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 4px;
    }
    .source-tag {
      font-size: 11px;
      background: var(--accent-soft);
      color: var(--accent);
      padding: 4px 8px;
      border-radius: 8px;
      font-weight: 600;
    }
    .composer-wrap {
      padding: 14px 24px 20px;
      background: linear-gradient(to top, var(--bg) 70%, transparent);
    }
    .composer {
      max-width: 860px;
      margin: 0 auto;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 8px 10px 8px 16px;
      display: flex;
      align-items: center;
      gap: 10px;
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.05);
    }
    .composer input {
      flex: 1;
      border: none;
      outline: none;
      font-size: 14px;
      background: transparent;
      color: var(--ink);
    }
  </style>
</head>
<body>
  <aside>
    <div class="brand">
      <div class="brand-badge">BU</div>
      <div>
        <div>College RAG Chat</div>
        <div style="font-size:11px;color:var(--muted);font-weight:500;">Azure Blob + Hybrid Search</div>
      </div>
    </div>

    <button class="btn btn-primary" onclick="newChat()">+ New Conversation</button>
    <input id="pdfFileInput" type="file" accept=".pdf,.docx,.txt,.md" style="display:none;" onchange="handleFileUpload(event)" />
    <button id="uploadNewBtn" class="btn" onclick="document.getElementById('pdfFileInput').click()">📄 + Upload New PDF (Local + Azure)</button>
    <button id="syncBtn" class="btn" onclick="syncAzureBlob()">☁️ Push Bennett-Brochure.pdf to Azure</button>
    <div id="syncStatus" style="font-size:11px;color:var(--green);padding:0 4px;display:none;word-break:break-word;"></div>

    <div class="section-label">Azure Blob Container (college-docs)</div>
    <div style="font-size:11px;color:var(--muted);padding:0 4px;">Click a document to filter answers to that PDF, or leave unselected to search all.</div>
    <div id="docList" class="doc-list">Loading documents...</div>
  </aside>

  <main>
    <header>
      <div style="font-weight:600;font-size:15px;" id="chatTitle">Multilingual Campus Assistant</div>
      <div style="display:flex;gap:8px;align-items:center;">
        <span id="filterBadge" style="font-size:12px;color:var(--accent);font-weight:600;"></span>
        <a href="/docs" target="_blank" class="btn" style="text-decoration:none;padding:6px 10px;font-size:12px;">API Docs (/docs)</a>
      </div>
    </header>

    <div id="chatScroll" class="chat-scroll">
      <div id="welcomeBox" class="welcome">
        <h2>Ask anything from your College Documents</h2>
        <p>Grounded answers in English, Hindi, Hinglish, Tamil, Telugu & more with exact page citations from <strong>Bennett-Brochure.pdf</strong> and campus circulars.</p>
        <div class="chips">
          <div class="chip" onclick="askSample('How many acres is the Bennett University campus and what is the hostel capacity?')">Campus size & Hostel capacity (Bennett Brochure)</div>
          <div class="chip" onclick="askSample('What programs are offered in the School of Artificial Intelligence at Bennett University?')">School of AI Programs (Bennett Brochure)</div>
          <div class="chip" onclick="askSample('Who is the Chancellor and Vice Chancellor of Bennett University?')">Chancellor & Vice Chancellor</div>
          <div class="chip" onclick="askSample('हॉस्टल में रात को वापस आने का समय क्या है?')">हॉस्टल का समय (Hindi)</div>
          <div class="chip" onclick="askSample('B.Tech ki annual tuition fee kitni hai?')">B.Tech Fee (Hinglish)</div>
        </div>
      </div>
    </div>

    <div class="composer-wrap">
      <form class="composer" onsubmit="sendMessage(event)">
        <input id="queryInput" type="text" placeholder="Ask a question in English, हिंदी, Hinglish..." autocomplete="off" />
        <button id="sendBtn" type="submit" class="btn btn-primary">Send</button>
      </form>
    </div>
  </main>

  <script>
    let sessionId = null;
    let documents = [];
    let selectedDocIds = new Set();

    function getClientId() {
      let id = localStorage.getItem('rag_client_id');
      if (!id) {
        id = 'client-' + Math.random().toString(36).slice(2, 10);
        localStorage.setItem('rag_client_id', id);
      }
      return id;
    }

    async function loadDocuments() {
      const el = document.getElementById('docList');
      try {
        const res = await fetch('/api/v1/documents', { headers: { 'X-Client-Id': getClientId() } });
        documents = await res.json();
        renderDocuments();
      } catch (e) {
        el.innerHTML = '<div style="color:#c0392b;font-size:12px;">Failed to load documents</div>';
      }
    }

    function renderDocuments() {
      const el = document.getElementById('docList');
      const badge = document.getElementById('filterBadge');
      badge.textContent = selectedDocIds.size ? `${selectedDocIds.size} doc filter active` : '';
      if (!documents.length) {
        el.innerHTML = '<div style="font-size:12px;color:var(--muted);">No indexed documents</div>';
        return;
      }
      el.innerHTML = documents.map(d => {
        const sel = selectedDocIds.has(d.id) ? 'selected' : '';
        return `
          <div class="doc-item ${sel}" onclick="toggleDoc('${d.id}')">
            <div class="doc-title">
              <span>${d.name}</span>
              <span class="pill">${d.status}</span>
            </div>
            <div class="doc-meta">
              <span>${d.category || 'general'}</span>
              ${d.pages ? `<span>• ${d.pages} pages</span>` : ''}
              ${d.effective_date ? `<span>• ${d.effective_date}</span>` : ''}
            </div>
            <div class="doc-actions">
              <button type="button" class="mini-btn" onclick="event.stopPropagation(); syncAzureBlob('${d.id}', '${d.name}')">☁️ Push to Azure Blob</button>
            </div>
          </div>
        `;
      }).join('');
    }

    function toggleDoc(id) {
      if (selectedDocIds.has(id)) selectedDocIds.delete(id);
      else selectedDocIds.add(id);
      renderDocuments();
    }

    function newChat() {
      sessionId = null;
      const scroll = document.getElementById('chatScroll');
      scroll.innerHTML = document.getElementById('welcomeBox') ? scroll.innerHTML : '';
      location.reload();
    }

    function askSample(text) {
      document.getElementById('queryInput').value = text;
      sendMessage(new Event('submit'));
    }

    function appendMessage(role, text, sources = [], lang = '') {
      const welcome = document.getElementById('welcomeBox');
      if (welcome) welcome.remove();
      const scroll = document.getElementById('chatScroll');
      const wrap = document.createElement('div');
      wrap.className = 'msg ' + role;

      const bubble = document.createElement('div');
      bubble.className = 'bubble';
      bubble.textContent = text;
      wrap.appendChild(bubble);

      if (sources && sources.length) {
        const srcRow = document.createElement('div');
        srcRow.className = 'sources';
        sources.forEach((s, idx) => {
          const tag = document.createElement('span');
          tag.className = 'source-tag';
          tag.textContent = `[${idx + 1}] ${s.document_name}` + (s.page ? ` (p. ${s.page})` : '');
          tag.title = s.snippet || '';
          srcRow.appendChild(tag);
        });
        wrap.appendChild(srcRow);
      }

      scroll.appendChild(wrap);
      scroll.scrollTop = scroll.scrollHeight;
      return wrap;
    }

    async function sendMessage(e) {
      if (e && e.preventDefault) e.preventDefault();
      const input = document.getElementById('queryInput');
      const btn = document.getElementById('sendBtn');
      const query = input.value.trim();
      if (!query) return;

      input.value = '';
      btn.disabled = true;
      appendMessage('user', query);
      const pending = appendMessage('assistant', 'Searching documents & generating grounded answer...');

      try {
        const payload = { query };
        if (sessionId) payload.session_id = sessionId;
        if (selectedDocIds.size > 0) payload.document_ids = Array.from(selectedDocIds);

        const res = await fetch('/api/v1/chat', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Client-Id': getClientId(),
          },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        pending.remove();
        if (!res.ok) {
          appendMessage('assistant', 'Error: ' + (data.detail || res.statusText));
        } else {
          sessionId = data.session_id || sessionId;
          appendMessage('assistant', data.answer, data.sources || [], data.language);
        }
      } catch (err) {
        pending.remove();
        appendMessage('assistant', 'Network error connecting to backend.');
      } finally {
        btn.disabled = false;
        input.focus();
      }
    }

    async function syncAzureBlob(docId = '', docName = 'Bennett-Brochure.pdf') {
      const btn = document.getElementById('syncBtn');
      const status = document.getElementById('syncStatus');
      btn.disabled = true;
      btn.textContent = '☁️ Uploading to Azure...';
      status.style.display = 'block';
      status.style.color = 'var(--muted)';
      status.textContent = `Uploading ${docName} to Azure Blob...`;
      try {
        const q = docId ? `?document_id=${encodeURIComponent(docId)}` : '';
        const res = await fetch('/api/v1/cloud-sync' + q, { method: 'POST' });
        const data = await res.json();
        if (!res.ok) {
          status.style.color = '#c0392b';
          status.textContent = 'Upload failed: ' + (data.detail || res.statusText);
        } else {
          status.style.color = 'var(--green)';
          status.textContent = `✅ Uploaded to Azure: ${data.container}/${data.blob_name}`;
        }
      } catch (e) {
        status.style.color = '#c0392b';
        status.textContent = 'Error connecting to server.';
      } finally {
        btn.disabled = false;
        btn.textContent = '☁️ Push Bennett-Brochure.pdf to Azure';
      }
    }

    async function handleFileUpload(event) {
      const file = event.target.files && event.target.files[0];
      if (!file) return;
      const btn = document.getElementById('uploadNewBtn');
      const status = document.getElementById('syncStatus');
      btn.disabled = true;
      btn.textContent = '📄 Indexing & Uploading...';
      status.style.display = 'block';
      status.style.color = 'var(--muted)';
      status.textContent = `Uploading & indexing ${file.name}...`;
      try {
        const buf = await file.arrayBuffer();
        const url = `/api/v1/upload-file?filename=${encodeURIComponent(file.name)}&category=admissions`;
        const res = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/octet-stream' },
          body: buf,
        });
        const data = await res.json();
        if (!res.ok) {
          status.style.color = '#c0392b';
          status.textContent = 'Upload failed: ' + (data.detail || res.statusText);
        } else {
          status.style.color = 'var(--green)';
          status.textContent = `✅ Indexed ${data.name} (${data.pages || 1} pages)` +
            (data.azure_synced ? ` & uploaded to Azure (${data.blob_name})` : (data.azure_error ? ` | Azure: ${data.azure_error}` : ''));
          await loadDocuments();
        }
      } catch (e) {
        status.style.color = '#c0392b';
        status.textContent = 'Error uploading file.';
      } finally {
        btn.disabled = false;
        btn.textContent = '📄 + Upload New PDF (Local + Azure)';
        event.target.value = '';
      }
    }

    loadDocuments();
  </script>
</body>
</html>
"""

