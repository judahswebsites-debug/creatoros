(function () {
  'use strict';

  function injectStyles() {
    if (document.getElementById('bench-styles')) return;
    var s = document.createElement('style');
    s.id = 'bench-styles';
    s.textContent = `
      .bench-wrap{font-family:'Outfit',sans-serif;}
      .bench-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;}
      .bench-title{color:#eeeeff;font-weight:700;font-size:15px;}
      .bench-bracket{font-size:11px;background:rgba(255,255,255,.07);border-radius:20px;padding:3px 10px;color:#8080a8;}
      .bench-metric{margin-bottom:18px;}
      .bench-metric-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;}
      .bench-label{color:#8080a8;font-size:13px;}
      .bench-vals{display:flex;align-items:center;gap:8px;}
      .bench-user-val{color:#eeeeff;font-family:'Fira Code',monospace;font-weight:700;font-size:14px;}
      .bench-top-val{color:#40405a;font-size:12px;}
      .bench-verdict{font-size:11px;font-weight:700;padding:2px 8px;border-radius:10px;}
      .bench-verdict.ahead{background:rgba(5,150,105,.15);color:#34d399;}
      .bench-verdict.close{background:rgba(180,83,9,.15);color:#fbbf24;}
      .bench-verdict.behind{background:rgba(185,28,28,.15);color:#f87171;}
      .bench-track{position:relative;height:8px;background:rgba(255,255,255,.06);border-radius:4px;overflow:hidden;}
      .bench-bar-top{position:absolute;top:0;left:0;height:100%;background:rgba(255,255,255,.1);border-radius:4px;transition:width 1s cubic-bezier(.4,0,.2,1);}
      .bench-bar-user{position:absolute;top:0;left:0;height:100%;border-radius:4px;transition:width 1s cubic-bezier(.4,0,.2,1);}
      .bench-motivational{margin-top:16px;background:rgba(67,56,202,.1);border:1px solid rgba(67,56,202,.2);border-radius:8px;padding:12px 16px;color:#8080a8;font-size:13px;line-height:1.5;}
      .bench-motivational strong{color:#818cf8;}
      .bench-skeleton{background:rgba(255,255,255,.05);border-radius:10px;padding:16px;}
      .bench-skel-line{height:12px;border-radius:5px;margin-bottom:10px;background:linear-gradient(90deg,rgba(255,255,255,.05) 25%,rgba(255,255,255,.1) 50%,rgba(255,255,255,.05) 75%);background-size:200% 100%;animation:benchSh 1.5s infinite;}
      @keyframes benchSh{0%{background-position:200% 0}100%{background-position:-200% 0}}
    `;
    document.head.appendChild(s);
  }

  function verdictClass(v) {
    if (!v) return 'close';
    var l = v.toLowerCase();
    if (l === 'ahead') return 'ahead';
    if (l === 'behind') return 'behind';
    return 'close';
  }

  function verdictArrow(v) {
    if (!v) return '≈';
    var l = v.toLowerCase();
    if (l === 'ahead') return '↑ Ahead';
    if (l === 'behind') return '↓ Behind';
    return '≈ Close';
  }

  function barColor(v) {
    if (!v) return '#818cf8';
    var l = v.toLowerCase();
    if (l === 'ahead') return '#34d399';
    if (l === 'behind') return '#f87171';
    return '#fbbf24';
  }

  function mount(selector, username, data) {
    injectStyles();
    var root = document.querySelector(selector);
    if (!root) return;

    root.innerHTML = '<div class="bench-skeleton"><div class="bench-skel-line" style="width:40%"></div><div class="bench-skel-line"></div><div class="bench-skel-line" style="width:80%"></div></div>';

    // POST the analysis the client already holds so the result is correct
    // regardless of which Gunicorn worker serves the request.
    fetch('/api/analytics/benchmarks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username || '', analysis: data || null })
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d.ok || !d.metrics) { root.innerHTML = ''; return; }
        render(root, d);
      })
      .catch(function () { root.innerHTML = ''; });
  }

  function render(root, d) {
    root.innerHTML = '';
    var wrap = document.createElement('div');
    wrap.className = 'bench-wrap';

    var header = document.createElement('div');
    header.className = 'bench-header';
    var title = document.createElement('div');
    title.className = 'bench-title';
    title.textContent = 'Your Stats vs Top Creators';
    var bracket = document.createElement('div');
    bracket.className = 'bench-bracket';
    bracket.textContent = 'Your follower range';
    header.appendChild(title);
    header.appendChild(bracket);
    wrap.appendChild(header);

    d.metrics.forEach(function (m) {
      var mc = document.createElement('div');
      mc.className = 'bench-metric';

      var top = document.createElement('div');
      top.className = 'bench-metric-top';
      var label = document.createElement('span');
      label.className = 'bench-label';
      label.textContent = m.label;
      var vals = document.createElement('div');
      vals.className = 'bench-vals';
      var uv = document.createElement('span');
      uv.className = 'bench-user-val';
      uv.textContent = m.user_value + (m.unit || '');
      var tv = document.createElement('span');
      tv.className = 'bench-top-val';
      tv.textContent = '/ Top: ' + m.top_value + (m.unit || '');
      var vd = document.createElement('span');
      vd.className = 'bench-verdict ' + verdictClass(m.verdict);
      vd.textContent = verdictArrow(m.verdict);
      vals.appendChild(uv);
      vals.appendChild(tv);
      vals.appendChild(vd);
      top.appendChild(label);
      top.appendChild(vals);

      var track = document.createElement('div');
      track.className = 'bench-track';
      var barTop = document.createElement('div');
      barTop.className = 'bench-bar-top';
      barTop.style.width = '0%';
      var barUser = document.createElement('div');
      barUser.className = 'bench-bar-user';
      barUser.style.width = '0%';
      barUser.style.background = barColor(m.verdict);
      track.appendChild(barTop);
      track.appendChild(barUser);

      mc.appendChild(top);
      mc.appendChild(track);
      wrap.appendChild(mc);

      setTimeout(function () {
        barTop.style.width = '100%';
        var pct = Math.min(100, (m.user_value / m.top_value) * 100);
        barUser.style.width = pct + '%';
      }, 80);
    });

    if (d.motivational) {
      var mot = document.createElement('div');
      mot.className = 'bench-motivational';
      mot.innerHTML = d.motivational;
      wrap.appendChild(mot);
    }

    root.appendChild(wrap);
  }

  window.BenchmarkStrip = { mount: mount };
})();
