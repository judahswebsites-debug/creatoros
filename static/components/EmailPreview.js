(function () {
  'use strict';

  function injectStyles() {
    if (document.getElementById('email-preview-styles')) return;
    var s = document.createElement('style');
    s.id = 'email-preview-styles';
    s.textContent = `
      .ep-overlay{position:fixed;inset:0;background:rgba(0,0,0,.7);backdrop-filter:blur(4px);z-index:9000;display:flex;align-items:center;justify-content:center;padding:20px;}
      @media(max-width:600px){.ep-overlay{align-items:flex-end;padding:0;}}
      .ep-modal{background:#0a0a15;border:1px solid rgba(255,255,255,.1);border-radius:16px;width:100%;max-width:680px;max-height:88vh;display:flex;flex-direction:column;overflow:hidden;}
      @media(max-width:600px){.ep-modal{border-radius:16px 16px 0 0;max-height:92vh;}}
      .ep-header{display:flex;align-items:center;justify-content:space-between;padding:16px 20px;border-bottom:1px solid rgba(255,255,255,.07);}
      .ep-title{color:#eeeeff;font-weight:700;font-size:15px;font-family:'Outfit',sans-serif;}
      .ep-tabs{display:flex;gap:4px;background:rgba(255,255,255,.05);border-radius:8px;padding:3px;}
      .ep-tab{background:none;border:none;color:#8080a8;font-size:13px;padding:5px 14px;border-radius:6px;cursor:pointer;font-family:'Outfit',sans-serif;transition:all .15s;}
      .ep-tab.active{background:rgba(255,255,255,.1);color:#eeeeff;}
      .ep-close{background:none;border:none;color:#40405a;font-size:20px;cursor:pointer;padding:4px 8px;line-height:1;}
      .ep-close:hover{color:#8080a8;}
      .ep-body{flex:1;overflow:hidden;display:flex;flex-direction:column;}
      .ep-iframe{flex:1;border:none;background:#fff;}
      .ep-plain{flex:1;overflow:auto;padding:20px;background:#0f0f1e;}
      .ep-plain pre{color:#8080a8;font-family:'Fira Code',monospace;font-size:13px;line-height:1.7;margin:0;white-space:pre-wrap;}
      .ep-footer{padding:14px 20px;border-top:1px solid rgba(255,255,255,.07);display:flex;align-items:center;justify-content:space-between;gap:12px;}
      .ep-footer-info{color:#40405a;font-size:12px;font-family:'Outfit',sans-serif;}
      .ep-send-btn{background:linear-gradient(135deg,#4338ca,#0d9488);color:#fff;border:none;border-radius:8px;padding:9px 18px;font-size:13px;font-weight:700;cursor:pointer;font-family:'Outfit',sans-serif;transition:opacity .2s;}
      .ep-send-btn:disabled{opacity:.4;cursor:not-allowed;}
      .ep-skeleton-body{padding:24px;display:flex;flex-direction:column;gap:12px;}
      .ep-skel-line{height:13px;border-radius:5px;background:linear-gradient(90deg,rgba(255,255,255,.05) 25%,rgba(255,255,255,.1) 50%,rgba(255,255,255,.05) 75%);background-size:200% 100%;animation:epSh 1.5s infinite;}
      @keyframes epSh{0%{background-position:200% 0}100%{background-position:-200% 0}}
      .ep-trigger-btn{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);border-radius:8px;color:#eeeeff;padding:9px 18px;font-size:13px;cursor:pointer;font-family:'Outfit',sans-serif;transition:all .2s;}
      .ep-trigger-btn:hover{background:rgba(255,255,255,.1);}
    `;
    document.head.appendChild(s);
  }

  var _overlay = null;

  function open(opts) {
    injectStyles();
    opts = opts || {};
    var userId = opts.userId || 'user';

    if (_overlay) _overlay.remove();

    var overlay = document.createElement('div');
    overlay.className = 'ep-overlay';
    _overlay = overlay;

    var modal = document.createElement('div');
    modal.className = 'ep-modal';
    modal.addEventListener('click', function (e) { e.stopPropagation(); });
    overlay.addEventListener('click', close);

    document.addEventListener('keydown', onEsc);

    // Header
    var header = document.createElement('div');
    header.className = 'ep-header';
    var titleWrap = document.createElement('div');
    titleWrap.style.display = 'flex';
    titleWrap.style.alignItems = 'center';
    titleWrap.style.gap = '10px';
    var icon = document.createElement('span');
    icon.textContent = '📧';
    var titleEl = document.createElement('span');
    titleEl.className = 'ep-title';
    titleEl.textContent = 'Weekly Digest Preview';
    titleWrap.appendChild(icon);
    titleWrap.appendChild(titleEl);

    var tabs = document.createElement('div');
    tabs.className = 'ep-tabs';
    var tabEmail = document.createElement('button');
    tabEmail.className = 'ep-tab active';
    tabEmail.textContent = 'Email View';
    var tabPlain = document.createElement('button');
    tabPlain.className = 'ep-tab';
    tabPlain.textContent = 'Plain Text';
    tabs.appendChild(tabEmail);
    tabs.appendChild(tabPlain);

    var closeBtn = document.createElement('button');
    closeBtn.className = 'ep-close';
    closeBtn.innerHTML = '&times;';
    closeBtn.addEventListener('click', close);

    header.appendChild(titleWrap);
    header.appendChild(tabs);
    header.appendChild(closeBtn);

    // Body
    var body = document.createElement('div');
    body.className = 'ep-body';

    // Skeleton while loading
    var skelBody = document.createElement('div');
    skelBody.className = 'ep-skeleton-body';
    skelBody.innerHTML = '<div class="ep-skel-line" style="width:50%"></div><div class="ep-skel-line"></div><div class="ep-skel-line" style="width:85%"></div><div class="ep-skel-line" style="width:70%"></div>';
    body.appendChild(skelBody);

    // Footer
    var footer = document.createElement('div');
    footer.className = 'ep-footer';
    var info = document.createElement('div');
    info.className = 'ep-footer-info';
    info.textContent = 'Sent every Monday at 8:00 AM';
    var sendBtn = document.createElement('button');
    sendBtn.className = 'ep-send-btn';
    sendBtn.textContent = 'Send test email';
    sendBtn.disabled = true;
    footer.appendChild(info);
    footer.appendChild(sendBtn);

    modal.appendChild(header);
    modal.appendChild(body);
    modal.appendChild(footer);
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    var htmlContent = '';
    var plainContent = '';
    var activeTab = 'email';

    function showEmail() {
      body.innerHTML = '';
      var iframe = document.createElement('iframe');
      iframe.className = 'ep-iframe';
      iframe.srcdoc = htmlContent;
      body.appendChild(iframe);
    }

    function showPlain() {
      body.innerHTML = '';
      var pre = document.createElement('div');
      pre.className = 'ep-plain';
      var code = document.createElement('pre');
      code.textContent = plainContent;
      pre.appendChild(code);
      body.appendChild(pre);
    }

    tabEmail.addEventListener('click', function () {
      activeTab = 'email';
      tabEmail.classList.add('active');
      tabPlain.classList.remove('active');
      if (htmlContent) showEmail();
    });

    tabPlain.addEventListener('click', function () {
      activeTab = 'plain';
      tabPlain.classList.add('active');
      tabEmail.classList.remove('active');
      if (plainContent) showPlain();
    });

    fetch('/api/email/preview/' + userId)
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d.ok) return;
        htmlContent = d.html || '';
        plainContent = d.text || '';
        sendBtn.disabled = false;
        if (activeTab === 'email') showEmail();
        else showPlain();
      })
      .catch(function () {
        body.innerHTML = '<div style="padding:24px;color:#f87171;font-size:14px;text-align:center;">Could not load email preview.</div>';
      });
  }

  function close() {
    if (_overlay) {
      _overlay.remove();
      _overlay = null;
    }
    document.removeEventListener('keydown', onEsc);
  }

  function onEsc(e) {
    if (e.key === 'Escape') close();
  }

  function mountTrigger(selector) {
    injectStyles();
    var el = document.querySelector(selector);
    if (!el) return;
    var btn = document.createElement('button');
    btn.className = 'ep-trigger-btn';
    btn.textContent = '📧 Preview Weekly Email';
    btn.addEventListener('click', function () { open({ userId: 'user' }); });
    el.appendChild(btn);
  }

  window.EmailPreview = { open: open, mountTrigger: mountTrigger };
})();
