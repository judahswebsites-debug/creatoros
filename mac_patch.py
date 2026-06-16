#!/usr/bin/env python3
with open('templates/index.html', 'r') as f:
    h = f.read()
changes = 0
def replace(old, new, label):
    global h, changes
    if old in h:
        h = h.replace(old, new, 1); changes += 1; print(f'OK  {label}')
    else:
        print(f'--  Skip: {label}')
replace(
    'function buildBlueprints(blueprints) {\n  var list = document.getElementById(\'blueprints-list\');\n  list.innerHTML = \'\';\n  blueprints.forEach(function(bp, idx) {',
    "function buildBlueprints(blueprints) {\n  var list = document.getElementById('blueprints-list');\n  if (!list) return;\n  if (!Array.isArray(blueprints)) {\n    if (blueprints && Array.isArray(blueprints.video_blueprints)) {\n      blueprints = blueprints.video_blueprints;\n    } else { return; }\n  }\n  list.innerHTML = '';\n  blueprints.forEach(function(bp, idx) {\n    bp = bp || {};\n    bp.rank = bp.rank != null ? bp.rank : (idx + 1);\n    bp.title = bp.title || bp.video_title || bp.name || '(untitled)';\n    bp.hook = bp.hook || bp.opening_hook || bp.hook_line || '';\n    bp.why = bp.why || bp.rationale || bp.reason || '';\n    bp.tags = bp.tags || bp.categories || [];\n    bp.predicted_views = bp.predicted_views || bp.views || bp.estimated_views || '\u2014';\n    bp.saves = bp.saves || bp.estimated_saves || '\u2014';\n    bp.shares = bp.shares || bp.estimated_shares || '\u2014';\n    bp.shot_list = bp.shot_list || bp.shots || [];\n    bp.caption = bp.caption || '';\n    bp.hashtags = bp.hashtags || [];",
    'Defensive buildBlueprints'
)
with open('templates/index.html', 'w') as f:
    f.write(h)
print(f'{changes} changes applied.')
