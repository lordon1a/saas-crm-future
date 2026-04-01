(function () {
  var script = document.currentScript;
  var workspaceId = script && script.getAttribute('data-workspace');
  if (!workspaceId) {
    return;
  }

  var host = window.location.origin;
  var container = document.createElement('div');
  container.style.position = 'fixed';
  container.style.right = '20px';
  container.style.bottom = '20px';
  container.style.zIndex = '999999';
  container.style.width = '320px';
  container.style.height = '420px';
  container.style.border = '1px solid #e5e7eb';
  container.style.borderRadius = '12px';
  container.style.background = '#ffffff';
  container.style.boxShadow = '0 12px 40px rgba(0,0,0,0.12)';
  container.style.display = 'none';

  var toggle = document.createElement('button');
  toggle.innerText = 'Chat';
  toggle.style.position = 'fixed';
  toggle.style.right = '20px';
  toggle.style.bottom = '20px';
  toggle.style.zIndex = '999999';
  toggle.style.border = 'none';
  toggle.style.borderRadius = '9999px';
  toggle.style.padding = '12px 18px';
  toggle.style.background = '#0ea5e9';
  toggle.style.color = '#fff';
  toggle.style.cursor = 'pointer';

  var body = document.createElement('div');
  body.style.display = 'flex';
  body.style.flexDirection = 'column';
  body.style.height = '100%';

  var messages = document.createElement('div');
  messages.style.flex = '1';
  messages.style.overflowY = 'auto';
  messages.style.padding = '12px';

  var form = document.createElement('form');
  form.style.display = 'flex';
  form.style.gap = '8px';
  form.style.padding = '12px';

  var input = document.createElement('input');
  input.type = 'text';
  input.placeholder = 'Mesajınızı yazın';
  input.style.flex = '1';
  input.style.padding = '8px 10px';

  var send = document.createElement('button');
  send.type = 'submit';
  send.innerText = 'Gönder';

  form.appendChild(input);
  form.appendChild(send);
  body.appendChild(messages);
  body.appendChild(form);
  container.appendChild(body);
  document.body.appendChild(container);
  document.body.appendChild(toggle);

  var sessionId = null;
  var lastId = 0;

  function addMessage(text, from) {
    var item = document.createElement('div');
    item.style.marginBottom = '8px';
    item.style.fontSize = '14px';
    item.style.textAlign = from === 'visitor' ? 'right' : 'left';
    item.innerText = text;
    messages.appendChild(item);
    messages.scrollTop = messages.scrollHeight;
  }

  function poll() {
    if (!sessionId) return;
    fetch(host + '/api/v1/public/chat/' + sessionId + '/poll?since_id=' + lastId)
      .then(function (res) { return res.json(); })
      .then(function (data) {
        (data.messages || []).forEach(function (msg) {
          lastId = Math.max(lastId, msg.id || 0);
          addMessage(msg.content, msg.sender_type);
        });
      })
      .catch(function () {});
  }

  function init() {
    fetch(host + '/api/v1/public/chat/init?workspace_id=' + encodeURIComponent(workspaceId))
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (!data.session) return;
        sessionId = data.session.id;
        setInterval(poll, 3000);
        poll();
      })
      .catch(function () {});
  }

  toggle.addEventListener('click', function () {
    var open = container.style.display === 'block';
    container.style.display = open ? 'none' : 'block';
  });

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    if (!sessionId || !input.value.trim()) return;
    var text = input.value.trim();
    input.value = '';
    addMessage(text, 'visitor');

    fetch(host + '/api/v1/public/chat/' + sessionId + '/message', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: text })
    }).catch(function () {});
  });

  init();
})();
