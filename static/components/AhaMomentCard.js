(function () {
  'use strict';

  function injectStyles() {
    if (document.getElementById('aha-styles')) return;
    var s = document.createElement('style');
    s.id = 'aha-styles';
    s.textContent = `
      .aha-wrap{font-family:'Outfit',sans-serif;}
      .aha-skeleton{background:rgba(255,255,255,.05);border-radius:12px;padding:20px;}
      .aha-skel-line{height:14px;border-radius:6px;background:linear-gradient(90deg,rgba(255,255,255,.06) 25%,rgba(255,255,255,.12) 50%,rgba(255,255,255,.06) 75%);background-size:200% 100%;animation:ahaSh 1.5s infinite;margin-bottom:10px;}
      @keyframes ahaSh{0%{background-position:200% 0}100%{background-position:-200% 0}}
      .aha-card{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.09);border-radius:12px;padding:20px;}
      .aha-card-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;}
      .aha-type-badge{font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;padding:3px 10px;border-radius:20px;background:rgba(255,255,255,.07);}
      .aha-dismiss{background:none;border:none;color:#40405a;cursor:pointer;font-size:18px;padding:2px 6px;line-height:1;}
      .aha-dismiss:hover{color:#8080a8;}
      .aha-headline{color:#eeeeff;font-weight:700;font-size:17px;margin:0 0 8px;line-height:1.3;}
      .aha-body{color:#8080a8;font-size:14px;line-height:1.6;margin:0 0 14px;}
      .aha-bottom{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;}
      .aha-stat{background:rgba(255,255,255,.06);border-radius:6px;padding:5px 12px;font-size:13px;font-weight:600;color:#eeeeff;}
      .aha-confidence{display:flex;align-items:center;gap:5px;}
      .aha-conf-label{font-size:11px;color:#40405a;}
      .aha-dots{display:flex;gap:3px;}
      .aha-cdot{width:8px;height:8px;border-radius:50%;background:rgba(255,255,255,.1);}
      .aha-cdot.on{background:#34d399;}
      .aha-next{font-size:11px;color:#40405a;margin-top:10px;font-style:italic;}
      .aha-action-btn{margin-top:14px;width:100%;background:linear-gradient(135deg,#4338ca,#0d9488);color:#fff;border:none;border-radius:8px;padding:11px 18px;font-size:14px;font-weight:700;cursor:pointer;font-family:'Outfit',sans-serif;transition:opacity .2s,transform .2s;}
      .aha-action-btn:hover{opacity:.9;transform:translateY(-1px);}
      .aha-empty{text-align:center;padding:24px;color:#40405a;font-size:14px;}
      .aha-error{color:#f87171;font-size:13px;padding:12px;text-align:center;}
    `;
    document.head.appendChild(s);
  }

  function mount(selector, opts) {
    injectStyles();
    opts = opts || {};
    var root = document.querySelector(selector);
    if (!root) return;

    var state = { phase: 'loading', recs: [], idx: 0 };

    function render() {
      root.innerHTML = '';
      var wrap = document.createElement('div');
      wrap.className = 'aha-wrap';

      if (state.phase === 'loading') {
        var sk = document.createElement('div');
        sk.className = 'aha-skeleton';
        sk.innerHTML = '<div class="aha-skel-line" style="width:30%;margin-bottom:14px;"></div><div class="aha-skel-line" style="width:80%;"></div><div class="aha-skel-line" style="width:90%;"></div><div class="aha-skel-line" style="width:60%;"></div>';
        wrap.appendChild(sk);
      } else if (state.phase === 'error') {
        var err = document.createElement('div');
        err.className = 'aha-error';
        err.textContent = 'Could not load recommendations.';
        wrap.appendChild(err);
      } else if (state.phase === 'empty') {
        var emp = document.createElement('div');
        emp.className = 'aha-empty';
        emp.textContent = "You've seen all recommendations. Check back soon!";
        wrap.appendChild(emp);
      } else {
        var rec = state.recs[state.idx];
        if (!rec) { state.phase = 'empty'; render(); return; }
        wrap.appendChild(buildCard(rec));
      }

      root.appendChild(wrap);
    }

    function buildCard(rec) {
      var card = document.createElement('div');
      card.className = 'aha-card';

      var top = document.createElement('div');
      top.className = 'aha-card-top';
      var badge = document.createElement('span');
      badge.className = 'aha-type-badge';
      badge.textContent = rec.type.toUpperCase();
      badge.style.color = rec.type_color;
      badge.style.borderColor = rec.type_color;
      var dismiss = document.createElement('button');
      dismiss.className = 'aha-dismiss';
      dismiss.innerHTML = '&times;';
      dismiss.title = 'Dismiss';
      dismiss.addEventListener('click', function () {
        state.idx++;
        if (state.idx >= state.recs.length) state.phase = 'empty';
        render();
      });
      top.appendChild(badge);
      top.appendChild(dismiss);

      var hl = document.createElement('div');
      hl.className = 'aha-headline';
      hl.textContent = rec.headline;

      var body = document.createElement('div');
      body.className = 'aha-body';
      body.textContent = rec.body;

      var bottom = document.createElement('div');
      bottom.className = 'aha-bottom';
      var stat = document.createElement('span');
      stat.className = 'aha-stat';
      stat.textContent = rec.stat;
      var conf = document.createElement('div');
      conf.className = 'aha-confidence';
      var cLabel = document.createElement('span');
      cLabel.className = 'aha-conf-label';
      cLabel.textContent = 'Confidence';
      var dots = document.createElement('div');
      dots.className = 'aha-dots';
      for (var i = 0; i < 4; i++) {
        var dot = document.createElement('div');
        dot.className = 'aha-cdot' + (i < rec.confidence ? ' on' : '');
        dots.appendChild(dot);
      }
      conf.appendChild(cLabel);
      conf.appendChild(dots);
      bottom.appendChild(stat);
      bottom.appendChild(conf);

      var nextP = document.createElement('div');
      nextP.className = 'aha-next';
      nextP.textContent = rec.next_preview || '';

      var btn = document.createElement('button');
      btn.className = 'aha-action-btn';
      btn.textContent = 'Apply this insight →';
      btn.addEventListener('click', function () {
        if (opts.onCtaClick) opts.onCtaClick(rec);
      });

      card.appendChild(top);
      card.appendChild(hl);
      card.appendChild(body);
      card.appendChild(bottom);
      if (rec.next_preview) card.appendChild(nextP);
      card.appendChild(btn);
      return card;
    }

    fetch('/api/recommendations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: opts.username || '', analysis: opts.data || null })
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.ok && d.recommendations && d.recommendations.length) {
          state.recs = d.recommendations;
          state.phase = 'ready';
        } else {
          state.phase = 'empty';
        }
        render();
      })
      .catch(function () {
        state.phase = 'error';
        render();
      });

    render();
  }

  window.AhaMomentCard = { mount: mount };
})();
