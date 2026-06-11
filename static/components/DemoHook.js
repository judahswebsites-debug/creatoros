(function () {
  'use strict';

  var LOADING_MSGS = [
    'Pulling their posts…',
    'Finding what’s working…',
    'Building your insight…',
  ];

  function injectStyles() {
    if (document.getElementById('demo-hook-styles')) return;
    var s = document.createElement('style');
    s.id = 'demo-hook-styles';
    s.textContent = `
      .dh-wrap{max-width:640px;margin:0 auto;font-family:'Outfit',sans-serif;}
      .dh-input-row{display:flex;align-items:center;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.12);border-radius:50px;padding:6px 6px 6px 20px;gap:8px;}
      .dh-icon{width:36px;height:36px;border-radius:50%;background:linear-gradient(45deg,#f09433,#e6683c,#dc2743,#cc2366,#bc1888);display:flex;align-items:center;justify-content:center;flex-shrink:0;}
      .dh-icon svg{width:18px;height:18px;fill:none;stroke:#fff;stroke-width:2;}
      .dh-inp{flex:1;background:none;border:none;outline:none;color:#eeeeff;font-size:15px;font-family:'Outfit',sans-serif;}
      .dh-inp::placeholder{color:#40405a;}
      .dh-btn{background:linear-gradient(135deg,#4338ca,#0d9488);color:#fff;border:none;border-radius:50px;padding:10px 22px;font-size:14px;font-weight:700;cursor:pointer;white-space:nowrap;transition:opacity .2s,transform .2s;}
      .dh-btn:hover{opacity:.9;transform:translateY(-1px);}
      .dh-btn:disabled{opacity:.5;cursor:not-allowed;transform:none;}
      .dh-loading{text-align:center;padding:24px 0;color:#8080a8;font-size:14px;}
      .dh-dots{display:inline-flex;gap:4px;margin-left:8px;}
      .dh-dot{width:5px;height:5px;border-radius:50%;background:#4338ca;animation:dhBounce 1.2s infinite;}
      .dh-dot:nth-child(2){animation-delay:.2s;}
      .dh-dot:nth-child(3){animation-delay:.4s;}
      @keyframes dhBounce{0%,80%,100%{transform:scale(0.6);opacity:.4}40%{transform:scale(1);opacity:1}}
      .dh-handle-row{display:flex;align-items:center;gap:10px;margin-bottom:16px;}
      .dh-avatar{width:38px;height:38px;border-radius:50%;background:linear-gradient(135deg,#4338ca,#0d9488);display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:15px;}
      .dh-handle{color:#eeeeff;font-weight:700;font-size:15px;}
      .dh-stats{display:flex;gap:16px;flex-wrap:wrap;}
      .dh-stat{background:rgba(255,255,255,.05);border-radius:8px;padding:6px 14px;font-size:13px;color:#8080a8;}
      .dh-stat strong{color:#eeeeff;font-family:'Fira Code',monospace;}
      .dh-cards{display:flex;flex-direction:column;gap:12px;margin-top:16px;}
      .dh-card{background:rgba(255,255,255,.05);border-radius:10px;padding:16px 18px;border-left:3px solid transparent;}
      .dh-card-type{font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;margin-bottom:6px;}
      .dh-card-headline{color:#eeeeff;font-weight:700;font-size:15px;margin:0 0 6px;}
      .dh-card-body{color:#8080a8;font-size:13px;line-height:1.55;margin:0 0 8px;}
      .dh-card-stat{display:inline-block;font-size:12px;font-weight:600;background:rgba(255,255,255,.06);padding:3px 10px;border-radius:20px;color:#eeeeff;}
      .dh-cta{position:relative;overflow:hidden;background:linear-gradient(135deg,#4338ca,#0d9488);border-radius:10px;padding:16px 22px;margin-top:16px;display:flex;align-items:center;justify-content:space-between;cursor:pointer;}
      .dh-cta-text{color:#fff;font-weight:700;font-size:15px;}
      .dh-cta-sub{color:rgba(255,255,255,.7);font-size:12px;margin-top:2px;}
      .dh-cta-arrow{color:#fff;font-size:22px;}
      .dh-cta::after{content:'';position:absolute;top:0;left:-100%;width:60%;height:100%;background:linear-gradient(90deg,transparent,rgba(255,255,255,.18),transparent);animation:dhShimmer 2.2s infinite;}
      @keyframes dhShimmer{0%{left:-100%}100%{left:200%}}
      .dh-again{text-align:center;margin-top:12px;}
      .dh-again a{color:#818cf8;font-size:13px;cursor:pointer;text-decoration:underline;}
      .dh-error{color:#f87171;font-size:13px;text-align:center;padding:12px;}
    `;
    document.head.appendChild(s);
  }

  function mount(selector) {
    injectStyles();
    var root = document.querySelector(selector);
    if (!root) return;

    var state = { phase: 'idle', data: null, handle: '' };

    function render() {
      root.innerHTML = '';
      var wrap = document.createElement('div');
      wrap.className = 'dh-wrap';

      if (state.phase === 'idle' || state.phase === 'error') {
        wrap.appendChild(buildInput());
        if (state.phase === 'error') {
          var err = document.createElement('div');
          err.className = 'dh-error';
          err.textContent = 'Something went wrong. Try again.';
          wrap.appendChild(err);
        }
      } else if (state.phase === 'loading') {
        wrap.appendChild(buildInput(true));
        wrap.appendChild(buildLoading());
      } else if (state.phase === 'results') {
        wrap.appendChild(buildResults());
      }

      root.appendChild(wrap);
    }

    function buildInput(disabled) {
      var row = document.createElement('div');
      row.className = 'dh-input-row';

      var icon = document.createElement('div');
      icon.className = 'dh-icon';
      icon.innerHTML = '<svg viewBox="0 0 24 24"><rect x="2" y="2" width="20" height="20" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1"/></svg>';

      var inp = document.createElement('input');
      inp.className = 'dh-inp';
      inp.type = 'text';
      inp.placeholder = 'Enter Instagram username…';
      inp.value = state.handle;
      if (disabled) inp.disabled = true;
      inp.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') submit(inp.value);
      });

      var btn = document.createElement('button');
      btn.className = 'dh-btn';
      btn.textContent = 'Analyze free →';
      if (disabled) btn.disabled = true;
      btn.addEventListener('click', function () { submit(inp.value); });

      row.appendChild(icon);
      row.appendChild(inp);
      row.appendChild(btn);
      return row;
    }

    var loadingInterval = null;
    function buildLoading() {
      var div = document.createElement('div');
      div.className = 'dh-loading';
      var msgEl = document.createElement('span');
      msgEl.textContent = LOADING_MSGS[0];
      var dots = document.createElement('span');
      dots.className = 'dh-dots';
      dots.innerHTML = '<span class="dh-dot"></span><span class="dh-dot"></span><span class="dh-dot"></span>';
      div.appendChild(msgEl);
      div.appendChild(dots);

      var idx = 0;
      loadingInterval = setInterval(function () {
        idx = (idx + 1) % LOADING_MSGS.length;
        msgEl.textContent = LOADING_MSGS[idx];
      }, 1500);

      return div;
    }

    function buildResults() {
      var d = state.data;
      var frag = document.createDocumentFragment();

      var handleRow = document.createElement('div');
      handleRow.className = 'dh-handle-row';
      var av = document.createElement('div');
      av.className = 'dh-avatar';
      av.textContent = (d.handle || 'U')[0].toUpperCase();
      var hn = document.createElement('div');
      hn.className = 'dh-handle';
      hn.textContent = '@' + d.handle;
      handleRow.appendChild(av);
      handleRow.appendChild(hn);
      frag.appendChild(handleRow);

      var stats = document.createElement('div');
      stats.className = 'dh-stats';
      var s1 = document.createElement('div');
      s1.className = 'dh-stat';
      s1.innerHTML = '<strong>' + fmtNum(d.follower_count) + '</strong> followers';
      var s2 = document.createElement('div');
      s2.className = 'dh-stat';
      s2.innerHTML = '<strong>' + d.avg_engagement_rate + '%</strong> avg engagement';
      var s3 = document.createElement('div');
      s3.className = 'dh-stat';
      s3.innerHTML = '<strong>' + d.posts_analyzed + '</strong> posts analyzed';
      stats.appendChild(s1);
      stats.appendChild(s2);
      stats.appendChild(s3);
      frag.appendChild(stats);

      var cards = document.createElement('div');
      cards.className = 'dh-cards';
      (d.insights || []).forEach(function (ins) {
        var card = document.createElement('div');
        card.className = 'dh-card';
        card.style.borderLeftColor = ins.color;
        var tp = document.createElement('div');
        tp.className = 'dh-card-type';
        tp.style.color = ins.color;
        tp.textContent = ins.type.toUpperCase();
        var hl = document.createElement('div');
        hl.className = 'dh-card-headline';
        hl.textContent = ins.headline;
        var bd = document.createElement('div');
        bd.className = 'dh-card-body';
        bd.textContent = ins.body;
        var st = document.createElement('span');
        st.className = 'dh-card-stat';
        st.textContent = ins.stat;
        card.appendChild(tp);
        card.appendChild(hl);
        card.appendChild(bd);
        card.appendChild(st);
        cards.appendChild(card);
      });
      frag.appendChild(cards);

      var cta = document.createElement('div');
      cta.className = 'dh-cta';
      var ctaL = document.createElement('div');
      ctaL.innerHTML = '<div class="dh-cta-text">Get your full growth report</div><div class="dh-cta-sub">6 modules · AI-powered · Free</div>';
      var ctaR = document.createElement('div');
      ctaR.className = 'dh-cta-arrow';
      ctaR.textContent = '→';
      cta.appendChild(ctaL);
      cta.appendChild(ctaR);
      cta.addEventListener('click', function () {
        var mainInp = document.getElementById('main-inp');
        if (mainInp) {
          mainInp.value = d.handle;
          mainInp.scrollIntoView({ behavior: 'smooth', block: 'center' });
          mainInp.focus();
        }
      });
      frag.appendChild(cta);

      var again = document.createElement('div');
      again.className = 'dh-again';
      var aLink = document.createElement('a');
      aLink.textContent = 'Analyze another account';
      aLink.addEventListener('click', function () {
        if (loadingInterval) clearInterval(loadingInterval);
        state.phase = 'idle';
        state.handle = '';
        state.data = null;
        render();
      });
      again.appendChild(aLink);
      frag.appendChild(again);

      var wrap = document.createElement('div');
      wrap.appendChild(frag);
      return wrap;
    }

    function submit(raw) {
      var handle = raw.replace(/^@/, '').trim();
      if (!handle) return;
      state.handle = handle;
      state.phase = 'loading';
      render();

      fetch('/api/demo/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ handle: handle }),
      })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (loadingInterval) clearInterval(loadingInterval);
          state.data = d;
          state.phase = 'results';
          render();
        })
        .catch(function () {
          if (loadingInterval) clearInterval(loadingInterval);
          state.phase = 'error';
          render();
        });
    }

    function fmtNum(n) {
      if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
      if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
      return String(n);
    }

    render();
  }

  window.DemoHook = { mount: mount };
})();
