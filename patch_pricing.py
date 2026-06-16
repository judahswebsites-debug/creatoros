import subprocess

with open('templates/index.html', 'r') as f:
    s = f.read()

old = '      <div class="section-badge">Pricing</div>\n      <h2 class="section-h2">Start free, scale when ready</h2>\n      <p class="section-sub">No credit card required to try.</p>\n      <div class="pricing-grid" style="max-width:860px;margin:0 auto;">\n        <div class="plan-card">\n          <div class="plan-name">Free</div>\n          <div class="plan-price fira">$0</div>\n          <div class="plan-desc">For creators getting started</div>\n          <ul class="plan-features">\n            <li>3 analyses per month</li>\n            <li>Overview + Score</li>\n            <li>1 Video Blueprint</li>\n            <li>Growth Agent (5 msgs)</li>\n          </ul>\n          <button class="plan-btn plan-btn-outline" onclick="focusHeroInput()">Get Started Free</button>\n        </div>\n        <div class="plan-card popular">\n          <div class="plan-badge">Most Popular</div>\n          <div class="plan-name">Pro</div>\n          <div class="plan-price fira">$29<span>/mo</span></div>\n          <div class="plan-desc">For serious creators</div>\n          <ul class="plan-features">\n            <li>Unlimited analyses</li>\n            <li>All 6 modules</li>\n            <li>Competitor Intelligence</li>\n            <li>Unlimited Growth Agent</li>\n            <li>Weekly email digest</li>\n            <li>PDF export</li>\n          </ul>\n          <button class="plan-btn plan-btn-grad" onclick="focusHeroInput()">Start Pro Trial</button>\n        </div>\n        <div class="plan-card">\n          <div class="plan-name">Agency</div>\n          <div class="plan-price fira">$99<span>/mo</span></div>\n          <div class="plan-desc">For agencies and managers</div>\n          <ul class="plan-features">\n            <li>50 accounts</li>\n            <li>Everything in Pro</li>\n            <li>White-label reports</li>\n            <li>API access</li>\n            <li>Priority support</li>\n          </ul>\n          <button class="plan-btn plan-btn-outline" onclick="focusHeroInput()">Contact Sales</button>\n        </div>\n      </div>'
new = '      <div class="section-badge">Pricing</div>\n      <h2 class="section-h2">Serious tools for serious creators</h2>\n      <p class="section-sub">Start with 1 free scan \xe2\x80\x94 no credit card needed. Upgrade when you\'re ready to grow.</p>\n      <div class="pricing-grid" style="max-width:700px;margin:0 auto;grid-template-columns:repeat(2,1fr);">\n        <div class="plan-card popular">\n          <div class="plan-badge">Most Popular</div>\n          <div class="plan-name">Pro</div>\n          <div class="plan-price fira">$29.99<span>/mo</span></div>\n          <div class="plan-desc">For serious creators ready to grow</div>\n          <ul class="plan-features">\n            <li>10 analyses per month</li>\n            <li>All 6 insight modules</li>\n            <li>Competitor Intelligence</li>\n            <li>Growth Agent (20 msgs/mo)</li>\n            <li>PDF export</li>\n          </ul>\n          <button class="plan-btn plan-btn-grad" onclick="startCheckout()">Start Pro Trial \xe2\x86\x92</button>\n        </div>\n        <div class="plan-card" style="border-color:rgba(139,92,246,.5);background:rgba(139,92,246,.06);">\n          <div class="plan-badge" style="background:linear-gradient(135deg,#7c3aed,#a855f7);">Best Value</div>\n          <div class="plan-name">Max</div>\n          <div class="plan-price fira">$69.99<span>/mo</span></div>\n          <div class="plan-desc">For creators who want every edge</div>\n          <ul class="plan-features">\n            <li>Unlimited analyses</li>\n            <li>Everything in Pro</li>\n            <li>Unlimited Growth Agent</li>\n            <li>Weekly email digest</li>\n            <li>White-label PDF exports</li>\n            <li>Priority support</li>\n          </ul>\n          <button class="plan-btn plan-btn-grad" style="background:linear-gradient(135deg,#7c3aed,#a855f7);" onclick="startMaxCheckout()">Get Max \xe2\x86\x92</button>\n        </div>\n      </div>'

if old in s:
    s = s.replace(old, new, 1)
    print('Pricing section replaced')
else:
    print('WARNING: pricing section not found - check indentation')

s = s.replace(
    '    <a href="#pricing">Pricing</a>\n  </div>\n  <div class="nav-right">',
    '    <a href="#pricing" onclick="openPricingModal();return false;">Pricing</a>\n  </div>\n  <div class="nav-right">',
    1
)
print('Nav link wired')

with open('templates/index.html', 'w') as f:
    f.write(s)
print('index.html saved')

subprocess.run(['git', 'add', 'templates/index.html'])
subprocess.run(['git', 'commit', '-m', 'Replace pricing section with Pro/Max cards, wire nav Pricing link'])
subprocess.run(['git', 'push', 'origin', 'main'])
print('Done.')
