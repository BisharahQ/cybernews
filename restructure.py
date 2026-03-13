#!/usr/bin/env python3
"""
Comprehensive UI restructure — adds CSS classes and replaces inline styles
in both HTML and JS render functions.
"""
import re, sys, os
os.environ['PYTHONIOENCODING'] = 'utf-8'

FILE = 'app/static/index.html'
with open(FILE, 'r', encoding='utf-8') as f:
    content = f.read()

# ═══════════════════════════════════════════════════════════
# PHASE 1: ADD NEW CSS CLASSES (inject before </style>)
# ═══════════════════════════════════════════════════════════

NEW_CSS = """
/* ══════════════════════════════════════
   ADMIN TAB
══════════════════════════════════════ */
.admin-page{overflow-y:auto;padding:18px 24px;gap:18px;display:flex;flex-direction:column}
.admin-card{background:var(--bg-surface);border:1px solid var(--border-default);border-radius:2px;padding:16px}
.admin-card.ai{border-color:rgba(88,166,255,.27)}
.admin-card-header{
  font-size:11px;font-weight:700;color:var(--text-tertiary);
  text-transform:uppercase;letter-spacing:.5px;margin-bottom:12px;
  display:flex;align-items:center;gap:10px;
}
.admin-card-header .subtitle{font-size:9px;color:var(--text-disabled);font-weight:400;letter-spacing:0}
.admin-card-header .spacer{flex:1}
.admin-sub-card{background:var(--bg-base);border:1px solid var(--border-default);border-radius:2px;padding:12px;margin-bottom:12px}
.admin-sub-card:last-child{margin-bottom:0}
.admin-sub-title{font-size:10px;font-weight:600;margin-bottom:8px}
.admin-sub-title.blue{color:var(--blue)}
.admin-sub-title.amber{color:var(--medium-text)}
.admin-sub-title.red{color:var(--critical)}
.admin-grid-2{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:6px}
.admin-grid-3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin-bottom:8px}
.admin-grid-2col{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.admin-input{background:var(--bg-elevated);border:1px solid var(--border-emphasis);border-radius:2px;padding:5px 8px;color:var(--text-secondary);font-size:11px;width:100%;box-sizing:border-box}
.admin-input:focus{outline:none;border-color:var(--accent)}
.admin-textarea{
  width:100%;height:280px;background:var(--bg-base);border-radius:2px;
  color:var(--text-secondary);font-size:10px;padding:6px;
  font-family:'JetBrains Mono',monospace;resize:vertical;box-sizing:border-box;
}
.admin-textarea.crit{border:1px solid rgba(229,83,75,.2)}
.admin-textarea.med{border:1px solid rgba(198,144,38,.2)}
.admin-btn-full{width:100%;padding:6px;font-size:11px;cursor:pointer}
.admin-btn-green{background:var(--green-bg);border:1px solid rgba(63,185,80,.33);color:var(--green);border-radius:2px}
.admin-btn-red{background:var(--critical-bg);border:1px solid rgba(229,83,75,.33);color:var(--critical);border-radius:2px}
.admin-btn-blue{background:var(--accent-bg);border:1px solid rgba(56,139,253,.33);color:var(--blue-text);border-radius:2px}
.admin-status{font-size:10px;color:var(--text-disabled);margin-top:4px}
.admin-flex-row{display:flex;gap:8px;flex-wrap:wrap}
.admin-flex-center{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.admin-stat-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}
.admin-health{background:var(--bg-base);border:1px solid var(--border-default);border-radius:2px;padding:12px 16px}
.admin-log{
  background:var(--bg-base);border:1px solid var(--border-default);border-radius:2px;
  padding:8px;font-size:9px;color:var(--text-tertiary);overflow-y:auto;
  max-height:180px;margin:0;white-space:pre-wrap;word-break:break-all;
  font-family:'JetBrains Mono',monospace;
}
.admin-kw-label{font-size:9px;font-weight:700;margin-bottom:4px;text-transform:uppercase}
.admin-kw-label.crit{color:var(--critical)}
.admin-kw-label.med{color:var(--medium-text)}
.admin-kw-label .count{color:var(--text-disabled)}

/* ══════════════════════════════════════
   SECTION HEADERS (reusable)
══════════════════════════════════════ */
.section-header{
  font-size:10px;font-weight:700;color:var(--text-tertiary);
  text-transform:uppercase;letter-spacing:.5px;
}
.section-header.red{color:var(--critical)}
.section-header.blue{color:var(--blue)}
.section-header.purple{color:var(--purple)}
.section-subtitle{font-size:9px;color:var(--text-disabled);font-weight:400}

/* ══════════════════════════════════════
   BLOCKLIST TAB (proper classes)
══════════════════════════════════════ */
.bl-page{display:flex;flex-direction:column;height:100%;overflow:hidden}
.bl-toolbar{
  padding:12px 20px;background:var(--bg-base);border-bottom:1px solid var(--border-default);
  display:flex;align-items:center;gap:10px;flex-wrap:wrap;flex-shrink:0;
}
.bl-toolbar .spacer{flex:1}
.bl-toolbar .title{font-size:13px;font-weight:700;color:var(--critical);display:flex;align-items:center;gap:4px}
.bl-filter{
  background:var(--bg-elevated);border:1px solid var(--border-emphasis);
  color:var(--text-secondary);padding:4px 8px;border-radius:2px;font-size:10px;
}
.bl-search{
  background:var(--bg-surface);border:1px solid var(--border-emphasis);
  border-radius:2px;padding:4px 8px;color:var(--text-secondary);font-size:10px;width:160px;
}
.bl-search:focus{outline:none;border-color:var(--accent)}
.bl-btn{padding:5px 12px;border-radius:2px;cursor:pointer;font-size:10px;font-weight:700;border:none}
.bl-btn.green{background:var(--green);color:#fff}
.bl-btn.gray{background:var(--bg-overlay);border:1px solid var(--border-emphasis);color:var(--text-tertiary)}
.bl-btn.blue{background:var(--accent-hover);color:#fff}
.bl-stats{
  padding:8px 20px;background:var(--bg-elevated);border-bottom:1px solid var(--border-default);
  display:flex;gap:20px;font-size:10px;flex-shrink:0;
}
.bl-table-wrap{flex:1;overflow-y:auto;padding:0}
.bl-table{width:100%;border-collapse:collapse;font-size:10px;table-layout:fixed}
.bl-table thead{position:sticky;top:0;background:var(--bg-surface);z-index:1}
.bl-table thead tr{border-bottom:1px solid var(--border-emphasis);color:var(--text-tertiary);font-size:9px;text-transform:uppercase}
.bl-table th{text-align:left;padding:6px 8px;font-weight:700;font-family:'JetBrains Mono',monospace;letter-spacing:.3px}
.bl-table th.center{text-align:center}
.bl-table td{padding:4px 8px;border-bottom:1px solid var(--border-muted)}
.bl-table td.center{text-align:center}
.bl-table td.mono{font-family:'JetBrains Mono',monospace;color:var(--text-secondary);white-space:nowrap}
.bl-table td.apt-cell{max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--blue);font-size:9px;font-weight:600;cursor:pointer}
.bl-table td.truncate{font-size:9px;color:var(--text-muted);max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bl-table tr:hover td{background:var(--bg-elevated)}
.bl-table tr.banned{opacity:.5}
.bl-copy-btn{background:none;border:1px solid var(--border-default);color:var(--text-tertiary);padding:2px 5px;border-radius:2px;cursor:pointer;font-size:9px}
.bl-copy-btn:hover{border-color:var(--green);color:var(--green)}

/* ── Inline-style replacement utility classes ── */
.tinted-badge{font-size:8px;padding:1px 5px;border-radius:2px;font-weight:700;font-family:'JetBrains Mono',monospace}
.tier-badge-inline{font-size:8px;padding:1px 5px;border-radius:2px;font-weight:700;font-family:'JetBrains Mono',monospace}
.status-inline{font-size:8px;font-weight:700}
.flex-row{display:flex;gap:8px;align-items:center}
.flex-row.wrap{flex-wrap:wrap}
.flex-col{display:flex;flex-direction:column}
.flex-1{flex:1}
.text-center{text-align:center}
.text-right{text-align:right}
.gap-4{gap:4px}
.gap-6{gap:6px}
.gap-10{gap:10px}
.gap-12{gap:12px}
.gap-14{gap:14px}
.gap-20{gap:20px}
.p-12{padding:12px 14px}
.mb-8{margin-bottom:8px}
.mt-6{margin-top:6px}
.mt-8{margin-top:8px}
.mt-10{margin-top:10px}

/* APT detail section cards */
.apt-section-card{background:var(--bg-elevated);border:1px solid var(--border-emphasis);border-radius:2px;padding:12px 14px}
.apt-section-header{font-size:11px;font-weight:700;color:var(--text-secondary);margin-bottom:8px}
.apt-section-header.red{color:var(--critical-text)}
.apt-section-header.purple{color:var(--purple)}
.apt-section-header.blue{color:var(--blue-text)}
.apt-scroll-200{max-height:200px;overflow-y:auto}
.apt-scroll-250{max-height:250px;overflow-y:auto}
.apt-attack-row{display:flex;gap:8px;align-items:center;padding:4px 0;border-bottom:1px solid var(--bg-surface);font-size:10px}
.apt-attack-date{color:var(--text-disabled);font-family:'JetBrains Mono',monospace;width:80px;flex-shrink:0}
.apt-attack-target{color:var(--critical-text);font-weight:600;width:140px;flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.apt-attack-type{font-size:8px;color:var(--medium-text);background:rgba(198,144,38,.1);padding:1px 5px;border-radius:2px}
.apt-attack-summary{color:var(--text-muted);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.apt-timeline-bars{display:flex;align-items:flex-end;gap:3px;height:80px}
.apt-timeline-labels{display:flex;justify-content:space-between;font-size:8px;color:var(--text-disabled);margin-top:2px}
.apt-msg-item{padding:6px 8px;border-bottom:1px solid var(--bg-surface);font-size:10px}
.apt-msg-meta{display:flex;gap:6px;align-items:center;margin-bottom:3px}
.apt-msg-crit{font-size:8px;font-weight:700;color:var(--critical);background:rgba(229,83,75,.1);padding:1px 5px;border-radius:2px}
.apt-msg-channel{color:var(--blue);font-weight:600}
.apt-msg-time{color:var(--text-disabled);font-size:9px}
.apt-msg-text{color:var(--text-tertiary);line-height:1.4;word-break:break-word}
.apt-ioc-tag{font-size:8px;font-family:'JetBrains Mono',monospace;background:var(--bg-surface);border:1px solid var(--border-default);padding:1px 5px;border-radius:2px;color:var(--blue-text)}
.apt-ioc-tags{margin-top:3px;display:flex;gap:4px;flex-wrap:wrap}
.apt-stat-box{text-align:center}
.apt-stat-value{font-size:20px;font-weight:800;font-family:'JetBrains Mono',monospace}
.apt-stat-label{font-size:8px;color:var(--text-muted);text-transform:uppercase;letter-spacing:.5px}
.apt-dates{font-size:9px;color:var(--text-disabled);margin-top:6px}
.apt-bio{margin:8px 0;padding:8px 12px;background:rgba(22,27,34,.53);border-left:3px solid var(--accent);color:var(--text-tertiary);font-size:10px;line-height:1.5;font-style:italic;display:none}
.apt-status-badge{font-size:10px;padding:2px 8px;border-radius:2px;font-weight:700}
.sector-bar-wrap{display:flex;align-items:center;gap:8px;margin:4px 0}
.bar-track{flex:1;background:var(--border-default);border-radius:2px;overflow:hidden}
.bar-fill{height:16px;border-radius:2px;transition:width .4s}
.bar-value{font-size:10px;color:var(--text-tertiary);width:30px;text-align:right}

/* Matrix table */
.matrix-section{flex-shrink:0;border-bottom:1px solid var(--border-default);padding:8px 14px 10px;display:none}
.matrix-header{display:flex;align-items:center;gap:10px;margin-bottom:6px}
.matrix-table-wrap{overflow-x:auto;max-height:220px;overflow-y:auto}
.matrix-table{border-collapse:collapse;font-size:10px;min-width:100%}
.matrix-table thead{background:var(--bg-base);position:sticky;top:0;z-index:1}
.matrix-table th{padding:4px 8px;font-size:9px;color:var(--text-disabled);font-weight:600;border-bottom:1px solid var(--border-default);white-space:nowrap;font-family:'JetBrains Mono',monospace}
.matrix-table th.left{text-align:left}
.matrix-table th.right{text-align:right}
.matrix-table td{padding:3px 8px}
.matrix-table td.actor{color:var(--text-secondary);white-space:nowrap;max-width:200px;overflow:hidden;text-overflow:ellipsis;padding-left:10px}
.matrix-table td.total{text-align:right;color:var(--medium-text);font-weight:700}

/* Briefing section */
.briefing-strip{flex-shrink:0;background:var(--bg-base);border-bottom:1px solid var(--border-default);padding:8px 14px;display:none}
.briefing-header{display:flex;gap:16px;align-items:center;flex-wrap:wrap}
.briefing-title{font-size:10px;font-weight:700;color:var(--critical);text-transform:uppercase;letter-spacing:.5px}
.briefing-entities{margin-top:5px;display:flex;flex-wrap:wrap;gap:4px}
.briefing-entity-tag{font-size:9px;background:var(--critical-bg);border:1px solid var(--critical-border);color:var(--critical-text);padding:1px 6px;border-radius:2px;cursor:pointer}
.briefing-newest{margin-top:6px;display:none}
.briefing-alert{background:var(--bg-surface);border:1px solid rgba(229,83,75,.27);border-radius:2px;padding:5px 9px;margin-bottom:3px;cursor:pointer}
.briefing-alert-header{display:flex;gap:8px;align-items:center;margin-bottom:2px;flex-wrap:wrap}
.briefing-alert-channel{font-size:9px;font-weight:600;color:var(--blue)}
.briefing-alert-time{font-size:9px;color:var(--text-disabled)}
.briefing-alert-kw{background:var(--medium-bg);color:var(--medium-text);font-size:8px;padding:1px 4px;border-radius:2px;margin-right:2px}
.briefing-alert-text{font-size:10px;color:var(--text-tertiary);line-height:1.35;overflow:hidden;max-height:2.7em}
.briefing-crit-label{font-size:9px;color:var(--text-disabled);font-weight:600;margin-bottom:4px;text-transform:uppercase;letter-spacing:.5px}

/* Trend chart section */
.trend-section{flex-shrink:0;border-top:1px solid var(--border-default);background:var(--bg-base);padding:8px 14px 6px}
.trend-title{font-size:10px;font-weight:700;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:.6px;margin-bottom:6px}
.trend-legend{display:flex;gap:10px;margin-top:3px;font-size:9px;color:var(--text-disabled)}

/* Escalation banner improved */
.escalation-banner{
  display:none;margin:0;padding:14px 18px;
  background:var(--critical-bg);border:2px solid var(--critical);border-radius:2px;
  font-family:'JetBrains Mono',monospace;font-size:13px;color:var(--critical-text);
  animation:escalation-pulse 2s infinite;
}
.escalation-title{font-size:16px;font-weight:bold;color:var(--critical);display:inline-flex;align-items:center;gap:6px}
.escalation-detail{margin-top:6px;font-size:11px;color:var(--critical-text)}

/* Chat (AI chat tab) */
.chat-tab-page{display:flex;flex-direction:column;flex:1;overflow:hidden}
.chat-tab-header{
  padding:10px 16px;background:var(--bg-elevated);
  border-bottom:1px solid var(--border-default);
  display:flex;align-items:center;gap:10px;flex-shrink:0;
}
.chat-tab-msgs{flex:1;overflow-y:auto;padding:14px 20px;display:flex;flex-direction:column;gap:12px}
.chat-tab-input{
  padding:10px 16px;background:var(--bg-surface);
  border-top:1px solid var(--border-default);flex-shrink:0;
  display:flex;gap:8px;align-items:flex-end;
}
.chat-user-bubble{
  display:flex;justify-content:flex-end;
}
.chat-user-inner{max-width:75%}
.chat-user-msg{
  background:rgba(31,111,235,.13);border:1px solid rgba(31,111,235,.33);
  border-radius:2px 10px 2px 10px;padding:10px 14px;
  font-size:12px;color:var(--text-secondary);white-space:pre-wrap;
}
.chat-user-time{font-size:9px;color:var(--text-disabled);text-align:right;margin-top:2px}
.chat-ai-bubble{display:flex;gap:8px;align-items:flex-start;max-width:85%}
.chat-ai-avatar{
  width:28px;height:28px;background:var(--blue-border);border-radius:50%;
  display:flex;align-items:center;justify-content:center;font-size:13px;flex-shrink:0;
}
.chat-ai-inner{flex:1;min-width:0}
.chat-ai-msg{
  background:var(--bg-elevated);border:1px solid var(--border-emphasis);
  border-radius:2px 10px 10px 10px;padding:10px 14px;
  font-size:12px;color:var(--text-secondary);line-height:1.5;
}
.chat-ai-time{font-size:9px;color:var(--text-disabled);margin-top:2px}
.chat-sources-btn{
  margin-top:8px;font-size:9px;padding:3px 9px;
  background:var(--bg-elevated);border:1px solid var(--border-emphasis);
  color:var(--blue);border-radius:2px;cursor:pointer;
}

/* Loading spinner */
.spinner{width:20px;height:20px;border:2px solid var(--border-default);border-top-color:var(--accent);border-radius:50%;animation:spin .6s linear infinite;margin:0 auto}
@keyframes spin{to{transform:rotate(360deg)}}
.loading-center{text-align:center;padding:40px;color:var(--text-disabled);font-size:11px}
.error-msg{color:var(--critical);padding:20px}
"""

# Find the position just before </style>
style_end_idx = content.index('</style>')
content = content[:style_end_idx] + NEW_CSS + '\n' + content[style_end_idx:]

print(f"Phase 1: Added {len(NEW_CSS)} chars of new CSS classes")

# ═══════════════════════════════════════════════════════════
# PHASE 2: RESTRUCTURE ADMIN TAB HTML
# ═══════════════════════════════════════════════════════════

# Replace admin tab-panel opening
old_admin = '<div id="tab-admin" class="tab-panel" style="overflow-y:auto;padding:18px 24px;gap:18px;display:none;flex-direction:column">'
new_admin = '<div id="tab-admin" class="tab-panel admin-page">'
content = content.replace(old_admin, new_admin)

# System health card
content = content.replace(
    '<div style="background:var(--bg-base);border:1px solid var(--border-default);border-radius:2px;padding:12px 16px">\n      <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">\n        <span style="font-size:10px;font-weight:700;color:var(--text-disabled);text-transform:uppercase;letter-spacing:.5px;min-width:90px">System Health</span>\n        <div style="display:flex;gap:8px;flex-wrap:wrap;flex:1">',
    '<div class="admin-health">\n      <div class="admin-flex-center">\n        <span class="section-header" style="min-width:90px">System Health</span>\n        <div class="admin-flex-row flex-1">'
)

# Status row grid
content = content.replace(
    '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px">',
    '<div class="admin-stat-grid">'
)

# Two column grid
content = content.replace(
    '<!-- Two column layout -->\n    <div style="display:grid;grid-template-columns:1fr 1fr;gap:18px">',
    '<!-- Two column layout -->\n    <div class="admin-grid-2col">'
)

# Channel Manager card
content = content.replace(
    '<div style="background:var(--bg-surface);border:1px solid var(--border-default);border-radius:2px;padding:16px">\n        <div style="font-size:11px;font-weight:700;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:.5px;margin-bottom:12px">Channel Manager</div>',
    '<div class="admin-card">\n        <div class="admin-card-header">Channel Manager</div>'
)

# Add channel sub-card
content = content.replace(
    '<div style="background:var(--bg-base);border:1px solid var(--border-default);border-radius:2px;padding:12px;margin-bottom:12px">\n          <div style="font-size:10px;color:var(--blue);font-weight:600;margin-bottom:8px">ADD / UPDATE CHANNEL</div>',
    '<div class="admin-sub-card">\n          <div class="admin-sub-title blue">ADD / UPDATE CHANNEL</div>'
)

# Add channel form grids
content = content.replace(
    '<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:6px">\n            <input id="adm-ch-user"  type="text" placeholder="@username" style="background:var(--bg-elevated);border:1px solid var(--border-emphasis);border-radius:4px;padding:5px 8px;color:var(--text-secondary);font-size:11px">\n            <input id="adm-ch-label" type="text" placeholder="Display label" style="background:var(--bg-elevated);border:1px solid var(--border-emphasis);border-radius:4px;padding:5px 8px;color:var(--text-secondary);font-size:11px">',
    '<div class="admin-grid-2">\n            <input id="adm-ch-user" class="admin-input" type="text" placeholder="@username">\n            <input id="adm-ch-label" class="admin-input" type="text" placeholder="Display label">'
)

content = content.replace(
    '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin-bottom:8px">\n            <select id="adm-ch-tier" style="background:var(--bg-elevated);border:1px solid var(--border-emphasis);border-radius:4px;padding:5px 8px;color:var(--text-secondary);font-size:11px">',
    '<div class="admin-grid-3">\n            <select id="adm-ch-tier" class="admin-input">'
)

# Fix remaining admin selects
for sel_id in ['adm-ch-threat', 'adm-ch-status']:
    content = content.replace(
        f'<select id="{sel_id}" style="background:var(--bg-elevated);border:1px solid var(--border-emphasis);border-radius:4px;padding:5px 8px;color:var(--text-secondary);font-size:11px">',
        f'<select id="{sel_id}" class="admin-input">'
    )

# Add Channel button
content = content.replace(
    '<button class="primary" onclick="admAddChannel()" style="width:100%;padding:6px;font-size:11px">+ Add Channel &amp; Queue Join</button>',
    '<button class="primary admin-btn-full" onclick="admAddChannel()">+ Add Channel &amp; Queue Join</button>'
)

# Backfill sub-card
content = content.replace(
    '<div style="background:var(--bg-base);border:1px solid var(--border-default);border-radius:2px;padding:12px;margin-bottom:12px">\n          <div style="font-size:10px;color:var(--medium-text);font-weight:600;margin-bottom:8px">BACKFILL MESSAGES</div>',
    '<div class="admin-sub-card">\n          <div class="admin-sub-title amber">BACKFILL MESSAGES</div>'
)

# Backfill form inputs
content = content.replace(
    '<div style="display:grid;grid-template-columns:2fr 1fr;gap:6px;margin-bottom:6px">\n            <input id="adm-bf-channel" type="text" placeholder="@username or select above" style="background:var(--bg-elevated);border:1px solid var(--border-emphasis);border-radius:4px;padding:5px 8px;color:var(--text-secondary);font-size:11px">\n            <input id="adm-bf-limit"   type="number" value="500" min="50" max="2000" style="background:var(--bg-elevated);border:1px solid var(--border-emphasis);border-radius:4px;padding:5px 8px;color:var(--text-secondary);font-size:11px">',
    '<div style="display:grid;grid-template-columns:2fr 1fr;gap:6px;margin-bottom:6px">\n            <input id="adm-bf-channel" class="admin-input" type="text" placeholder="@username or select above">\n            <input id="adm-bf-limit" class="admin-input" type="number" value="500" min="50" max="2000">'
)

content = content.replace(
    '<input id="adm-bf-since" type="text" placeholder="Since date (optional, e.g. 2026-01-01)" style="background:var(--bg-elevated);border:1px solid var(--border-emphasis);border-radius:4px;padding:5px 8px;color:var(--text-secondary);font-size:11px;width:100%;box-sizing:border-box;margin-bottom:6px">',
    '<input id="adm-bf-since" class="admin-input" type="text" placeholder="Since date (optional, e.g. 2026-01-01)" style="margin-bottom:6px">'
)

# Backfill button
content = content.replace(
    '''<button onclick="admQueueBackfill()" style="width:100%;padding:6px;font-size:11px;background:var(--green-bg);border:1px solid var(--green)55;color:var(--green);border-radius:4px;cursor:pointer">''',
    '<button onclick="admQueueBackfill()" class="admin-btn-full admin-btn-green">'
)

content = content.replace(
    '<div id="adm-bf-status" style="font-size:10px;color:var(--text-disabled);margin-top:4px"></div>',
    '<div id="adm-bf-status" class="admin-status"></div>'
)

# Maintenance sub-card
content = content.replace(
    '<div style="background:var(--bg-base);border:1px solid var(--border-default);border-radius:2px;padding:12px">\n          <div style="font-size:10px;color:var(--critical);font-weight:600;margin-bottom:8px">MAINTENANCE</div>\n          <div style="display:flex;gap:8px;flex-wrap:wrap">',
    '<div class="admin-sub-card">\n          <div class="admin-sub-title red">MAINTENANCE</div>\n          <div class="admin-flex-row">'
)

content = content.replace(
    '<button onclick="admCompact()" style="flex:1;padding:6px;font-size:11px;background:var(--critical-bg);border:1px solid var(--critical)55;color:var(--critical);border-radius:4px;cursor:pointer">',
    '<button onclick="admCompact()" class="admin-btn-full admin-btn-red" style="flex:1">'
)

content = content.replace(
    '<div id="adm-compact-status" style="font-size:10px;color:var(--text-disabled);margin-top:4px"></div>',
    '<div id="adm-compact-status" class="admin-status"></div>'
)

# Right column - keyword manager
content = content.replace(
    '<div style="display:flex;flex-direction:column;gap:12px">\n\n        <!-- Keyword manager -->\n        <div style="background:var(--bg-surface);border:1px solid var(--border-default);border-radius:2px;padding:16px;flex:1">',
    '<div class="flex-col" style="gap:12px">\n\n        <!-- Keyword manager -->\n        <div class="admin-card" style="flex:1">'
)

content = content.replace(
    '<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">\n            <span style="font-size:11px;font-weight:700;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:.5px">Keyword Lists</span>\n            <span style="font-size:9px;color:var(--text-disabled)">Restart monitor after saving</span>\n            <div style="flex:1"></div>',
    '<div class="admin-card-header">\n            <span>Keyword Lists</span>\n            <span class="subtitle">Restart monitor after saving</span>\n            <div class="spacer"></div>'
)

content = content.replace(
    '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">\n            <div>\n              <div style="font-size:9px;color:var(--critical);font-weight:700;margin-bottom:4px;text-transform:uppercase">CRITICAL <span id="adm-kw-crit-count" style="color:var(--text-disabled)"></span></div>',
    '<div class="admin-grid-2" style="gap:10px">\n            <div>\n              <div class="admin-kw-label crit">CRITICAL <span id="adm-kw-crit-count" class="count"></span></div>'
)

content = content.replace(
    '<textarea id="adm-kw-crit" oninput="admKwCount()" style="width:100%;height:280px;background:var(--bg-base);border:1px solid var(--critical)33;border-radius:4px;color:var(--text-secondary);font-size:10px;padding:6px;font-family:monospace;resize:vertical;box-sizing:border-box" placeholder="One keyword per line..."></textarea>',
    '<textarea id="adm-kw-crit" class="admin-textarea crit" oninput="admKwCount()" placeholder="One keyword per line..."></textarea>'
)

content = content.replace(
    '<div style="font-size:9px;color:var(--medium-text);font-weight:700;margin-bottom:4px;text-transform:uppercase">MEDIUM <span id="adm-kw-med-count" style="color:var(--text-disabled)"></span></div>',
    '<div class="admin-kw-label med">MEDIUM <span id="adm-kw-med-count" class="count"></span></div>'
)

content = content.replace(
    '<textarea id="adm-kw-med" oninput="admKwCount()" style="width:100%;height:280px;background:var(--bg-base);border:1px solid var(--medium-text)33;border-radius:4px;color:var(--text-secondary);font-size:10px;padding:6px;font-family:monospace;resize:vertical;box-sizing:border-box" placeholder="One keyword per line..."></textarea>',
    '<textarea id="adm-kw-med" class="admin-textarea med" oninput="admKwCount()" placeholder="One keyword per line..."></textarea>'
)

content = content.replace(
    '<div id="adm-kw-status" style="font-size:10px;color:var(--text-disabled);margin-top:6px"></div>',
    '<div id="adm-kw-status" class="admin-status" style="margin-top:6px"></div>'
)

# Monitor log
content = content.replace(
    '<div style="background:var(--bg-surface);border:1px solid var(--border-default);border-radius:2px;padding:16px">\n          <div style="font-size:11px;font-weight:700;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px">Monitor Log (last 30 lines)</div>\n          <pre id="adm-log" style="background:var(--bg-base);border:1px solid var(--border-default);border-radius:4px;padding:8px;font-size:9px;color:var(--text-tertiary);overflow-y:auto;max-height:180px;margin:0;white-space:pre-wrap;word-break:break-all"></pre>',
    '<div class="admin-card">\n          <div class="admin-card-header" style="margin-bottom:8px">Monitor Log (last 30 lines)</div>\n          <pre id="adm-log" class="admin-log"></pre>'
)

# Backfill queue
content = content.replace(
    '<div style="background:var(--bg-surface);border:1px solid var(--border-default);border-radius:2px;padding:16px">\n          <div style="font-size:11px;font-weight:700;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px">Backfill Queue</div>\n          <div id="adm-bfq" style="font-size:10px;color:var(--text-disabled)">',
    '<div class="admin-card">\n          <div class="admin-card-header" style="margin-bottom:8px">Backfill Queue</div>\n          <div id="adm-bfq" class="admin-status">'
)

# Channel table
content = content.replace(
    '<!-- Channel table -->\n    <div style="background:var(--bg-surface);border:1px solid var(--border-default);border-radius:2px;padding:16px">\n      <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">\n        <span style="font-size:11px;font-weight:700;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:.5px">All Monitored Channels</span>',
    '<!-- Channel table -->\n    <div class="admin-card">\n      <div class="admin-card-header">\n        <span>All Monitored Channels</span>'
)

content = content.replace(
    '<span id="adm-ch-count" style="font-size:10px;color:var(--text-disabled)"></span>\n      </div>\n      <div style="overflow-x:auto">\n        <table style="border-collapse:collapse;width:100%;font-size:10px">',
    '<span id="adm-ch-count" class="subtitle"></span>\n      </div>\n      <div style="overflow-x:auto">\n        <table class="bl-table">'
)

content = content.replace(
    '<thead>\n            <tr style="background:var(--bg-base);border-bottom:1px solid var(--border-default)">\n              <th style="padding:5px 10px;text-align:left;color:var(--text-disabled)">Username</th>\n              <th style="padding:5px 10px;text-align:left;color:var(--text-disabled)">Label</th>\n              <th style="padding:5px 8px;text-align:center;color:var(--text-disabled)">Tier</th>\n              <th style="padding:5px 8px;text-align:center;color:var(--text-disabled)">Threat</th>\n              <th style="padding:5px 8px;text-align:center;color:var(--text-disabled)">Status</th>\n              <th style="padding:5px 8px;text-align:center;color:var(--text-disabled)">Actions</th>\n            </tr>\n          </thead>',
    '<thead>\n            <tr>\n              <th>Username</th>\n              <th>Label</th>\n              <th class="center">Tier</th>\n              <th class="center">Threat</th>\n              <th class="center">Status</th>\n              <th class="center">Actions</th>\n            </tr>\n          </thead>'
)

content = content.replace(
    '<tbody id="adm-ch-tbody"><tr><td colspan="6" style="padding:12px;text-align:center;color:var(--text-disabled)">Loading\u2026</td></tr></tbody>',
    '<tbody id="adm-ch-tbody"><tr><td colspan="6" class="loading-center">Loading\u2026</td></tr></tbody>'
)

# AI Agent Panel
content = content.replace(
    '<div style="background:var(--bg-surface);border:1px solid var(--blue)44;border-radius:2px;padding:16px">',
    '<div class="admin-card ai">'
)

content = content.replace(
    '<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">\n        <span style="font-size:11px;font-weight:700;color:var(--blue);text-transform:uppercase;letter-spacing:.5px">',
    '<div class="admin-card-header" style="margin-bottom:12px">\n        <span class="section-header blue">'
)

content = content.replace(
    '<span style="font-size:9px;color:var(--text-disabled)">4 autonomous loops: critical enrichment',
    '<span class="subtitle">4 autonomous loops: critical enrichment'
)

print("Phase 2: Restructured Admin tab HTML")

# ═══════════════════════════════════════════════════════════
# PHASE 3: RESTRUCTURE IOC/BLOCKLIST TAB HTML
# ═══════════════════════════════════════════════════════════

content = content.replace(
    '<div style="display:flex;flex-direction:column;height:100%;overflow:hidden">\n      <!-- Toolbar -->\n      <div style="padding:12px 20px;background:var(--bg-base);border-bottom:1px solid var(--border-default);display:flex;align-items:center;gap:10px;flex-wrap:wrap;flex-shrink:0">',
    '<div class="bl-page">\n      <!-- Toolbar -->\n      <div class="bl-toolbar">'
)

content = content.replace(
    '<span style="font-size:13px;font-weight:700;color:var(--critical)"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg> BLOCKLIST</span>\n        <span style="font-size:10px;color:var(--text-disabled)">External IOCs verified via AbuseIPDB</span>\n        <div style="flex:1"></div>',
    '<span class="bl-toolbar title"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg> BLOCKLIST</span>\n        <span class="section-subtitle">External IOCs verified via AbuseIPDB</span>\n        <div class="spacer"></div>'
)

# IOC filters
for filt_id in ['bl-apt-filter', 'bl-type-filter', 'bl-verdict-filter']:
    content = content.replace(
        f'<select id="{filt_id}" onchange="loadBlocklist()" style="background:var(--bg-elevated);border:1px solid var(--border-emphasis);color:var(--text-secondary);padding:4px 8px;border-radius:4px;font-size:10px">',
        f'<select id="{filt_id}" class="bl-filter" onchange="loadBlocklist()">'
    )

content = content.replace(
    '<input type="text" id="bl-search" placeholder="Search IOCs..." oninput="loadBlocklist()" style="background:var(--bg-surface);border:1px solid var(--border-emphasis);border-radius:4px;padding:4px 8px;color:var(--text-secondary);font-size:10px;width:160px">',
    '<input type="text" id="bl-search" class="bl-search" placeholder="Search IOCs..." oninput="loadBlocklist()">'
)

# Blocklist buttons
content = content.replace(
    """<button onclick="window.location='/api/blocklist/export?verdict='+encodeURIComponent(document.getElementById('bl-verdict-filter').value)" style="background:var(--green);border:none;color:#fff;padding:5px 12px;border-radius:4px;cursor:pointer;font-size:10px;font-weight:700">EXPORT CSV</button>""",
    """<button onclick="window.location='/api/blocklist/export?verdict='+encodeURIComponent(document.getElementById('bl-verdict-filter').value)" class="bl-btn green">EXPORT CSV</button>"""
)

content = content.replace(
    '<button onclick="copyBlocklistIPs()" style="background:var(--border-default);border:1px solid var(--border-emphasis);color:var(--text-tertiary);padding:5px 12px;border-radius:4px;cursor:pointer;font-size:10px;font-weight:700">COPY ALL IPs</button>',
    '<button onclick="copyBlocklistIPs()" class="bl-btn gray">COPY ALL IPs</button>'
)

content = content.replace(
    '<button onclick="generateReport(this)" style="background:var(--accent-hover);border:none;color:#fff;padding:5px 12px;border-radius:4px;cursor:pointer;font-size:10px;font-weight:700">',
    '<button onclick="generateReport(this)" class="bl-btn blue">'
)

# Stats bar
content = content.replace(
    '<div id="bl-stats" style="padding:8px 20px;background:var(--bg-elevated);border-bottom:1px solid var(--border-default);display:flex;gap:20px;font-size:10px;flex-shrink:0"></div>',
    '<div id="bl-stats" class="bl-stats"></div>'
)

# Table wrap
content = content.replace(
    '<div style="flex:1;overflow-y:auto;padding:0">\n        <table style="width:100%;border-collapse:collapse;font-size:10px;table-layout:fixed" id="bl-table">',
    '<div class="bl-table-wrap">\n        <table class="bl-table" id="bl-table">'
)

# Thead
content = content.replace(
    '<thead style="position:sticky;top:0;background:var(--bg-surface);z-index:1">\n            <tr style="border-bottom:1px solid var(--border-emphasis);color:var(--text-tertiary);font-size:9px;text-transform:uppercase">\n              <th style="text-align:left;padding:6px 8px">APT Group</th>\n              <th style="text-align:left;padding:6px">Type</th>\n              <th style="text-align:left;padding:6px">Value</th>\n              <th style="text-align:center;padding:6px">Verdict</th>\n              <th style="text-align:center;padding:6px">Score</th>\n              <th style="text-align:left;padding:6px">CC</th>\n              <th style="text-align:left;padding:6px">Src</th>\n              <th style="text-align:left;padding:6px">Context</th>\n              <th style="padding:6px"></th>\n            </tr>\n          </thead>',
    '<thead>\n            <tr>\n              <th>APT Group</th>\n              <th>Type</th>\n              <th>Value</th>\n              <th class="center">Verdict</th>\n              <th class="center">Score</th>\n              <th>CC</th>\n              <th>Src</th>\n              <th>Context</th>\n              <th></th>\n            </tr>\n          </thead>'
)

content = content.replace(
    '<tr><td colspan="9" style="text-align:center;padding:40px;color:var(--text-disabled)">Loading blocklist...</td></tr>',
    '<tr><td colspan="9" class="loading-center">Loading blocklist...</td></tr>'
)

print("Phase 3: Restructured IOC/Blocklist tab HTML")

# ═══════════════════════════════════════════════════════════
# PHASE 4: RESTRUCTURE DASHBOARD HTML SECTIONS
# ═══════════════════════════════════════════════════════════

# Escalation banner
content = content.replace(
    '<div id="escalation-banner" style="display:none;margin:0 0 16px 0;padding:14px 18px;\n         background:var(--critical-bg);border:2px solid var(--critical);border-radius:2px;\n         font-family:monospace;font-size:13px;color:var(--critical-text);">\n      <span style="font-size:16px;font-weight:bold;color:var(--critical);">',
    '<div id="escalation-banner" class="escalation-banner">\n      <span class="escalation-title">'
)

content = content.replace(
    '</span>\n      &nbsp;|&nbsp;<span id="esc-urgency" style="font-weight:bold;"></span>\n      &nbsp;|&nbsp;<span id="esc-summary"></span>\n      <div style="margin-top:6px;font-size:11px;color:var(--critical-text);">',
    '</span>\n      &nbsp;|&nbsp;<span id="esc-urgency" style="font-weight:bold"></span>\n      &nbsp;|&nbsp;<span id="esc-summary"></span>\n      <div class="escalation-detail">'
)

# Matrix section
content = content.replace(
    '<div id="matrix-section" style="flex-shrink:0;border-bottom:1px solid var(--border-default);padding:8px 14px 10px;display:none">\n        <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">\n          <span style="font-size:10px;font-weight:700;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:.5px">THREAT ACTOR MATRIX</span>\n          <span style="font-size:9px;color:var(--text-disabled)">Actor \u00d7 Target Category \u00b7 Critical messages only</span>\n          <span id="matrix-badge" style="font-size:9px;background:var(--critical)22;color:var(--critical);border:1px solid var(--critical)44;border-radius:2px;padding:1px 7px"></span>\n        </div>\n        <div id="matrix-table" style="overflow-x:auto;max-height:220px;overflow-y:auto"></div>',
    '<div id="matrix-section" class="matrix-section">\n        <div class="matrix-header">\n          <span class="section-header">THREAT ACTOR MATRIX</span>\n          <span class="section-subtitle">Actor \u00d7 Target Category \u00b7 Critical messages only</span>\n          <span id="matrix-badge" class="tinted-badge" style="background:rgba(229,83,75,.13);color:var(--critical);border:1px solid rgba(229,83,75,.27)"></span>\n        </div>\n        <div id="matrix-table" class="matrix-table-wrap"></div>'
)

# Heatmap hint
content = content.replace(
    '<span style="font-size:9px;color:var(--text-disabled);font-weight:400">Click to filter feed \u2192</span>',
    '<span class="section-subtitle">Click to filter feed \u2192</span>'
)

# Trend chart section
content = content.replace(
    '<div style="flex-shrink:0;border-top:1px solid var(--border-default);background:var(--bg-base);padding:8px 14px 6px">\n            <div style="font-size:10px;font-weight:700;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:.6px;margin-bottom:6px">\n              30-Day Alert Trend\n            </div>',
    '<div class="trend-section">\n            <div class="trend-title">30-Day Alert Trend</div>'
)

content = content.replace(
    '<div style="display:flex;gap:10px;margin-top:3px;font-size:9px;color:var(--text-disabled)">\n              <span style="color:var(--critical)">\u25a0 Critical</span>\n              <span style="color:var(--medium-text)">\u25a0 Medium</span>\n            </div>',
    '<div class="trend-legend">\n              <span style="color:var(--critical)">\u25a0 Critical</span>\n              <span style="color:var(--medium-text)">\u25a0 Medium</span>\n            </div>'
)

# Briefing strip
content = content.replace(
    '<div id="briefing-strip" style="flex-shrink:0;background:var(--bg-base);border-bottom:1px solid var(--border-default);padding:8px 14px;display:none">',
    '<div id="briefing-strip" class="briefing-strip">'
)

content = content.replace(
    '<div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap">\n              <span style="font-size:10px;font-weight:700;color:var(--critical);text-transform:uppercase;letter-spacing:.5px">24H BRIEFING</span>',
    '<div class="briefing-header">\n              <span class="briefing-title">24H BRIEFING</span>'
)

content = content.replace(
    '<div id="bf-entities" style="margin-top:5px;display:flex;flex-wrap:wrap;gap:4px"></div>',
    '<div id="bf-entities" class="briefing-entities"></div>'
)

content = content.replace(
    '<div id="bf-newest" style="margin-top:6px;display:none"></div>',
    '<div id="bf-newest" class="briefing-newest"></div>'
)

print("Phase 4: Restructured Dashboard HTML sections")

# ═══════════════════════════════════════════════════════════
# PHASE 5: UPDATE JS RENDER FUNCTIONS
# ═══════════════════════════════════════════════════════════

# --- renderThreatMatrix ---
old_matrix = """  let html = `<table style="border-collapse:collapse;font-size:10px;min-width:100%">
    <thead><tr style="background:var(--bg-base);position:sticky;top:0;z-index:1">
      <th style="padding:4px 10px;text-align:left;font-size:9px;color:var(--text-disabled);font-weight:600;border-bottom:1px solid var(--border-default);white-space:nowrap">Threat Actor</th>
      <th style="padding:4px 6px;font-size:9px;color:var(--text-disabled);font-weight:600;border-bottom:1px solid var(--border-default);text-align:center">Tier</th>
      ${cats.map(c=>`<th style="padding:4px 8px;font-size:9px;color:var(--text-disabled);font-weight:600;text-align:center;border-bottom:1px solid var(--border-default);white-space:nowrap">${esc(c)}</th>`).join('')}
      <th style="padding:4px 8px;font-size:9px;color:var(--text-disabled);font-weight:600;text-align:right;border-bottom:1px solid var(--border-default)">Total</th>
    </tr></thead><tbody>`;
  actors.forEach((a,idx) => {
    const tc  = TIER_COL[a.tier] || 'var(--text-disabled)';
    const rowBg = idx % 2 === 0 ? 'var(--bg-surface)' : 'var(--bg-base)';
    html += `<tr style="background:${rowBg}">
      <td style="padding:3px 10px;color:var(--text-secondary);white-space:nowrap;max-width:200px;overflow:hidden;text-overflow:ellipsis" title="${esc(a.channel)}">${esc(a.label||a.channel)}</td>
      <td style="padding:3px 6px;text-align:center"><span style="font-size:8px;padding:1px 5px;border-radius:3px;background:${tc}22;color:${tc};border:1px solid ${tc}44;font-weight:700">T${a.tier||'?'}</span></td>
      ${cats.map(c => {
        const v   = a[c] || 0;
        const int = v / maxCell;
        const bg  = v > 0 ? `rgba(218,54,51,${(int * 0.75 + 0.1).toFixed(2)})` : 'transparent';
        const col = v > 0 ? '#fff' : 'var(--border-emphasis)';
        return `<td style="padding:3px 8px;text-align:center;background:${bg};color:${col};font-weight:${v>0?'600':'400'}" title="${esc(c)}: ${v}">${v||'\\xb7'}</td>`;
      }).join('')}
      <td style="padding:3px 8px;text-align:right;color:var(--medium-text);font-weight:700">${a.total}</td>
    </tr>`;
  });
  html += '</tbody></table>';"""

new_matrix = """  let html = `<table class="matrix-table">
    <thead><tr>
      <th class="left">Threat Actor</th>
      <th>Tier</th>
      ${cats.map(c=>`<th>${esc(c)}</th>`).join('')}
      <th class="right">Total</th>
    </tr></thead><tbody>`;
  actors.forEach((a,idx) => {
    const tc  = TIER_COL[a.tier] || 'var(--text-disabled)';
    const rowBg = idx % 2 === 0 ? 'var(--bg-surface)' : 'var(--bg-base)';
    html += `<tr style="background:${rowBg}">
      <td class="actor" title="${esc(a.channel)}">${esc(a.label||a.channel)}</td>
      <td class="text-center"><span class="tier-badge-inline" style="background:${tc}22;color:${tc};border:1px solid ${tc}44">T${a.tier||'?'}</span></td>
      ${cats.map(c => {
        const v   = a[c] || 0;
        const int = v / maxCell;
        const bg  = v > 0 ? `rgba(218,54,51,${(int * 0.75 + 0.1).toFixed(2)})` : 'transparent';
        const col = v > 0 ? '#fff' : 'var(--border-emphasis)';
        return `<td class="text-center" style="background:${bg};color:${col};font-weight:${v>0?'600':'400'}" title="${esc(c)}: ${v}">${v||'\\xb7'}</td>`;
      }).join('')}
      <td class="total">${a.total}</td>
    </tr>`;
  });
  html += '</tbody></table>';"""

content = content.replace(old_matrix, new_matrix)

# --- loadBriefing: top entities ---
content = content.replace(
    """'<span style="font-size:9px;color:var(--text-disabled);margin-right:4px">TOP TARGETED:</span>' +
        b.top_targeted_entities.slice(0,10).map(([kw,cnt])=>
          `<span style="font-size:9px;background:var(--critical-bg);border:1px solid var(--critical-border);color:var(--critical-text);padding:1px 6px;border-radius:3px;cursor:pointer" onclick="filterByKeyword('${esc(kw)}')">${esc(kw)} (${cnt})</span>`
        ).join('');""",
    """'<span class="section-subtitle" style="margin-right:4px">TOP TARGETED:</span>' +
        b.top_targeted_entities.slice(0,10).map(([kw,cnt])=>
          `<span class="briefing-entity-tag" onclick="filterByKeyword('${esc(kw)}')">${esc(kw)} (${cnt})</span>`
        ).join('');"""
)

# --- loadBriefing: newest critical ---
content = content.replace(
    """'<div style="font-size:9px;color:var(--text-disabled);font-weight:600;margin-bottom:4px;text-transform:uppercase;letter-spacing:.5px">&#x1F534; Latest Critical Alerts (24h)</div>' +""",
    """'<div class="briefing-crit-label">&#x1F534; Latest Critical Alerts (24h)</div>' +"""
)

content = content.replace(
    """`<span style="background:var(--medium-bg);color:var(--medium-text);font-size:8px;padding:1px 4px;border-radius:2px;margin-right:2px">${esc(k)}</span>`""",
    """`<span class="briefing-alert-kw">${esc(k)}</span>`"""
)

content = content.replace(
    """`<div style="background:var(--bg-surface);border:1px solid var(--critical)44;border-radius:4px;padding:5px 9px;margin-bottom:3px;cursor:pointer" onclick="${onclick}">
            <div style="display:flex;gap:8px;align-items:center;margin-bottom:2px;flex-wrap:wrap">
              <span style="font-size:9px;font-weight:600;color:var(--blue)">@${esc(m.channel_username||'')}</span>
              <span style="font-size:9px;color:var(--text-disabled)">${ts}</span>
              <div style="flex:1"></div>
              ${kws}
            </div>
            <div style="font-size:10px;color:var(--text-tertiary);line-height:1.35;overflow:hidden;max-height:2.7em">${txt}</div>
          </div>`""",
    """`<div class="briefing-alert" onclick="${onclick}">
            <div class="briefing-alert-header">
              <span class="briefing-alert-channel">@${esc(m.channel_username||'')}</span>
              <span class="briefing-alert-time">${ts}</span>
              <div class="flex-1"></div>
              ${kws}
            </div>
            <div class="briefing-alert-text">${txt}</div>
          </div>`"""
)

# --- renderAPTDetail: _aptStatBox ---
content = content.replace(
    """function _aptStatBox(label, value, color) {
  return '<div style="text-align:center"><div style="font-size:20px;font-weight:800;color:' + color + '">' + (value || 0) + '</div><div style="font-size:8px;color:var(--text-muted);text-transform:uppercase;letter-spacing:.5px">' + label + '</div></div>';
}""",
    """function _aptStatBox(label, value, color) {
  return '<div class="apt-stat-box"><div class="apt-stat-value" style="color:' + color + '">' + (value || 0) + '</div><div class="apt-stat-label">' + label + '</div></div>';
}"""
)

# --- renderAPTDetail: summary bio ---
content = content.replace(
    """'<div id="apt-summary-bio" style="margin:8px 0;padding:8px 12px;background:var(--bg-elevated)88;border-left:3px solid var(--accent);color:var(--text-tertiary);font-size:10px;line-height:1.5;font-style:italic;display:none"></div>'""",
    """'<div id="apt-summary-bio" class="apt-bio"></div>'"""
)

# --- renderAPTDetail: stat boxes container ---
content = content.replace(
    """'<div style="display:flex;gap:20px;margin-top:10px;flex-wrap:wrap">';""",
    """'<div class="flex-row wrap gap-20 mt-10">';"""
)

# IOC count stat
content = content.replace(
    """'<div style="text-align:center"><div id="apt-ioc-count" style="font-size:20px;font-weight:800;color:var(--purple)">...</div><div style="font-size:8px;color:var(--text-muted);text-transform:uppercase;letter-spacing:.5px">Intel IOCs</div></div>';""",
    """'<div class="apt-stat-box"><div id="apt-ioc-count" class="apt-stat-value" style="color:var(--purple)">...</div><div class="apt-stat-label">Intel IOCs</div></div>';"""
)

# Dates line
content = content.replace(
    """'<div style="font-size:9px;color:var(--text-disabled);margin-top:6px">First seen: ' + (data.first_seen || 'N/A').slice(0,10) + ' | Last seen: ' + (data.last_seen || 'N/A').slice(0,10) + '</div>';""",
    """'<div class="apt-dates">First seen: ' + (data.first_seen || 'N/A').slice(0,10) + ' | Last seen: ' + (data.last_seen || 'N/A').slice(0,10) + '</div>';"""
)

# Two-column layout
content = content.replace(
    """html += '<div style="display:flex;gap:14px">';""",
    """html += '<div class="flex-row gap-14">';"""
)

# Sector section
content = content.replace(
    """html += '<div style="flex:1;background:var(--bg-elevated);border:1px solid var(--border-emphasis);border-radius:2px;padding:12px 14px">';
    html += '<div style="font-size:11px;font-weight:700;color:var(--text-secondary);margin-bottom:8px">TARGET SECTORS</div>';""",
    """html += '<div class="apt-section-card flex-1">';
    html += '<div class="apt-section-header">TARGET SECTORS</div>';"""
)

# Sector bar inner
content = content.replace(
    """html += '<div style="flex:1;background:var(--border-default);border-radius:2px;overflow:hidden"><div style="width:' + pct + '%;height:16px;background:' + col + ';border-radius:2px;transition:width .4s"></div></div>';
      html += '<span style="font-size:10px;color:var(--text-tertiary);width:30px;text-align:right">' + sectors[s] + '</span></div>';
    });
    html += '</div>';
  }

  // Attack types
  const atypes = data.attack_types || {};
  const atypeKeys = Object.keys(atypes);
  if (atypeKeys.length > 0) {
    const maxA = Math.max(...Object.values(atypes));
    html += '<div style="flex:1;background:var(--bg-elevated);border:1px solid var(--border-emphasis);border-radius:2px;padding:12px 14px">';
    html += '<div style="font-size:11px;font-weight:700;color:var(--text-secondary);margin-bottom:8px">ATTACK TYPES</div>';""",
    """html += '<div class="bar-track"><div class="bar-fill" style="width:' + pct + '%;background:' + col + '"></div></div>';
      html += '<span class="bar-value">' + sectors[s] + '</span></div>';
    });
    html += '</div>';
  }

  // Attack types
  const atypes = data.attack_types || {};
  const atypeKeys = Object.keys(atypes);
  if (atypeKeys.length > 0) {
    const maxA = Math.max(...Object.values(atypes));
    html += '<div class="apt-section-card flex-1">';
    html += '<div class="apt-section-header">ATTACK TYPES</div>';"""
)

# Attack type bar inner
content = content.replace(
    """html += '<div style="flex:1;background:var(--border-default);border-radius:2px;overflow:hidden"><div style="width:' + pct + '%;height:16px;background:' + col + ';border-radius:2px;transition:width .4s"></div></div>';
      html += '<span style="font-size:10px;color:var(--text-tertiary);width:30px;text-align:right">' + atypes[a] + '</span></div>';""",
    """html += '<div class="bar-track"><div class="bar-fill" style="width:' + pct + '%;background:' + col + '"></div></div>';
      html += '<span class="bar-value">' + atypes[a] + '</span></div>';"""
)

# External threat intel section
content = content.replace(
    """html += '<div style="background:var(--bg-elevated);border:1px solid var(--border-emphasis);border-radius:2px;padding:12px 14px">';
  html += '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">';
  html += '<div style="font-size:11px;font-weight:700;color:var(--purple)">EXTERNAL THREAT INTELLIGENCE</div>';
  html += '<span style="font-size:9px;color:var(--text-disabled)">Sources: OTX, ThreatFox, GPT-4o | Verified via AbuseIPDB</span>';
  html += '</div>';
  html += '<div id="apt-research-results"><div style="text-align:center;padding:15px;color:var(--text-disabled);font-size:11px"><div class="spinner" style="margin:0 auto 8px"></div>Loading threat intelligence...</div></div>';
  html += '</div>';""",
    """html += '<div class="apt-section-card">';
  html += '<div class="flex-row" style="justify-content:space-between;margin-bottom:8px">';
  html += '<div class="apt-section-header purple">EXTERNAL THREAT INTELLIGENCE</div>';
  html += '<span class="section-subtitle">Sources: OTX, ThreatFox, GPT-4o | Verified via AbuseIPDB</span>';
  html += '</div>';
  html += '<div id="apt-research-results"><div class="loading-center"><div class="spinner" style="margin-bottom:8px"></div>Loading threat intelligence...</div></div>';
  html += '</div>';"""
)

# Jordan attacks section
content = content.replace(
    """html += '<div style="background:var(--bg-elevated);border:1px solid var(--border-emphasis);border-radius:2px;padding:12px 14px">';
    html += '<div style="font-size:11px;font-weight:700;color:var(--critical-text);margin-bottom:8px">\U0001f1ef\U0001f1f4 JORDAN-TARGETING ATTACKS (' + attacks.length + ')</div>';
    html += '<div style="max-height:200px;overflow-y:auto">';
    attacks.slice(0, 30).forEach(a => {
      html += '<div style="display:flex;gap:8px;align-items:center;padding:4px 0;border-bottom:1px solid var(--bg-surface);font-size:10px">';
      html += '<span style="color:var(--text-disabled);font-family:monospace;width:80px;flex-shrink:0">' + esc(a.date) + '</span>';
      html += '<span style="color:var(--critical-text);font-weight:600;width:140px;flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + esc(a.target) + '</span>';
      html += '<span style="font-size:8px;color:var(--medium-text);background:var(--medium-text)18;padding:1px 5px;border-radius:2px">' + esc(a.type) + '</span>';
      html += '<span style="color:var(--text-muted);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + esc(a.summary) + '</span>';
      html += '</div>';""",
    """html += '<div class="apt-section-card">';
    html += '<div class="apt-section-header red">\U0001f1ef\U0001f1f4 JORDAN-TARGETING ATTACKS (' + attacks.length + ')</div>';
    html += '<div class="apt-scroll-200">';
    attacks.slice(0, 30).forEach(a => {
      html += '<div class="apt-attack-row">';
      html += '<span class="apt-attack-date">' + esc(a.date) + '</span>';
      html += '<span class="apt-attack-target">' + esc(a.target) + '</span>';
      html += '<span class="apt-attack-type">' + esc(a.type) + '</span>';
      html += '<span class="apt-attack-summary">' + esc(a.summary) + '</span>';
      html += '</div>';"""
)

# Activity timeline
content = content.replace(
    """html += '<div style="background:var(--bg-elevated);border:1px solid var(--border-emphasis);border-radius:2px;padding:12px 14px">';
    html += '<div style="font-size:11px;font-weight:700;color:var(--text-secondary);margin-bottom:8px">ACTIVITY TIMELINE</div>';""",
    """html += '<div class="apt-section-card">';
    html += '<div class="apt-section-header">ACTIVITY TIMELINE</div>';"""
)

content = content.replace(
    """html += '<div style="display:flex;align-items:flex-end;gap:3px;height:80px">';""",
    """html += '<div class="apt-timeline-bars">';"""
)

content = content.replace(
    """html += '<div style="display:flex;justify-content:space-between;font-size:8px;color:var(--text-disabled);margin-top:2px"><span>'""",
    """html += '<div class="apt-timeline-labels"><span>'"""
)

# Recent critical messages section
content = content.replace(
    """html += '<div style="background:var(--bg-elevated);border:1px solid var(--border-emphasis);border-radius:2px;padding:12px 14px">';
    html += '<div style="font-size:11px;font-weight:700;color:var(--text-secondary);margin-bottom:8px">RECENT CRITICAL MESSAGES (' + msgs.length + ')</div>';
    html += '<div style="max-height:250px;overflow-y:auto">';""",
    """html += '<div class="apt-section-card">';
    html += '<div class="apt-section-header">RECENT CRITICAL MESSAGES (' + msgs.length + ')</div>';
    html += '<div class="apt-scroll-250">';"""
)

content = content.replace(
    """html += '<div style="padding:6px 8px;border-bottom:1px solid var(--bg-surface);font-size:10px">';
      html += '<div style="display:flex;gap:6px;align-items:center;margin-bottom:3px">';
      html += '<span style="font-size:8px;font-weight:700;color:var(--critical);background:var(--critical)18;padding:1px 5px;border-radius:2px">CRIT</span>';
      html += '<span style="color:var(--blue);font-weight:600">@' + esc(m.channel) + '</span>';
      html += '<span style="color:var(--text-disabled);font-size:9px">' + (m.timestamp || '').slice(0,16).replace('T',' ') + '</span>';
      html += '</div>';
      html += '<div style="color:var(--text-tertiary);line-height:1.4;word-break:break-word">' + esc(m.text) + '</div>';""",
    """html += '<div class="apt-msg-item">';
      html += '<div class="apt-msg-meta">';
      html += '<span class="apt-msg-crit">CRIT</span>';
      html += '<span class="apt-msg-channel">@' + esc(m.channel) + '</span>';
      html += '<span class="apt-msg-time">' + (m.timestamp || '').slice(0,16).replace('T',' ') + '</span>';
      html += '</div>';
      html += '<div class="apt-msg-text">' + esc(m.text) + '</div>';"""
)

content = content.replace(
    """html += '<div style="margin-top:3px;display:flex;gap:4px;flex-wrap:wrap">';
        iocKeys.forEach(k => {
          (m.iocs[k] || []).forEach(v => {
            html += '<span style="font-size:8px;font-family:monospace;background:var(--bg-surface);border:1px solid var(--border-default);padding:1px 5px;border-radius:2px;color:var(--blue-text)">' + esc(k) + ':' + esc(v) + '</span>';""",
    """html += '<div class="apt-ioc-tags">';
        iocKeys.forEach(k => {
          (m.iocs[k] || []).forEach(v => {
            html += '<span class="apt-ioc-tag">' + esc(k) + ':' + esc(v) + '</span>';"""
)

# --- renderAPTSidebar: tier section header ---
content = content.replace(
    """html += '<div style="padding:6px 10px;font-size:8px;font-weight:800;color:' + tierColor + ';letter-spacing:1px;border-bottom:1px solid var(--border-default);background:var(--bg-surface);position:sticky;top:0;z-index:1">' + tierLabel + '</div>';""",
    """html += '<div class="section-header" style="padding:6px 10px;font-size:8px;color:' + tierColor + ';border-bottom:1px solid var(--border-default);background:var(--bg-surface);position:sticky;top:0;z-index:1">' + tierLabel + '</div>';"""
)

# APT sidebar stats
content = content.replace(
    """if (p.critical_count > 0) html += '<span style="color:var(--critical);font-weight:700">' + p.critical_count + ' CRIT</span>';
    if (p.ioc_count > 0) html += '<span style="color:var(--blue)">' + p.ioc_count + ' IOC</span>';""",
    """if (p.critical_count > 0) html += '<span class="status-inline" style="color:var(--critical)">' + p.critical_count + ' CRIT</span>';
    if (p.ioc_count > 0) html += '<span class="status-inline" style="color:var(--blue)">' + p.ioc_count + ' IOC</span>';"""
)

# --- loadAdminChannels ---
old_admin_ch = """return `<tr style="border-bottom:1px solid var(--border-default)11;${isBanned?'opacity:.5':''}">
        <td style="padding:4px 10px;color:var(--blue);font-family:monospace">@${esc(un)}</td>
        <td style="padding:4px 10px;color:var(--text-secondary)">${esc(meta.label||un)}</td>
        <td style="padding:4px 8px;text-align:center"><span style="font-size:8px;padding:1px 5px;border-radius:3px;background:${tc}22;color:${tc};border:1px solid ${tc}44">T${meta.tier||'?'}</span></td>
        <td style="padding:4px 8px;text-align:center"><span style="font-size:8px;padding:1px 5px;border-radius:3px;background:${ht}22;color:${ht}">${esc(meta.threat||'')}</span></td>
        <td style="padding:4px 8px;text-align:center"><span style="font-size:8px;color:${isBanned?'var(--critical)':'var(--green)'}">${isBanned?'BANNED':'active'}</span></td>
        <td style="padding:4px 8px;text-align:center;display:flex;gap:4px;justify-content:center">
          <button onclick="admFillChannel('${esc(un)}')" style="font-size:9px;padding:2px 7px;background:var(--green-bg);border:1px solid var(--green)44;color:var(--green);border-radius:3px;cursor:pointer">Backfill</button>
          <button onclick="admDeleteChannel('${esc(un)}')" style="font-size:9px;padding:2px 7px;background:var(--critical-bg);border:1px solid var(--critical)44;color:var(--critical);border-radius:3px;cursor:pointer">Remove</button>
        </td>
      </tr>`;"""

new_admin_ch = """return `<tr class="${isBanned?'banned':''}">
        <td class="mono" style="color:var(--blue)">@${esc(un)}</td>
        <td>${esc(meta.label||un)}</td>
        <td class="center"><span class="tier-badge-inline" style="background:${tc}22;color:${tc};border:1px solid ${tc}44">T${meta.tier||'?'}</span></td>
        <td class="center"><span class="tier-badge-inline" style="background:${ht}22;color:${ht}">${esc(meta.threat||'')}</span></td>
        <td class="center"><span class="status-inline" style="color:${isBanned?'var(--critical)':'var(--green)'}">${isBanned?'BANNED':'active'}</span></td>
        <td class="center"><div class="flex-row gap-4" style="justify-content:center">
          <button class="btn-sm admin-btn-green" onclick="admFillChannel('${esc(un)}')">Backfill</button>
          <button class="btn-sm admin-btn-red" onclick="admDeleteChannel('${esc(un)}')">Remove</button>
        </div></td>
      </tr>`;"""

content = content.replace(old_admin_ch, new_admin_ch)

# --- selectAPT loading state ---
content = content.replace(
    """panel.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-disabled)"><div class="spinner" style="margin:0 auto 12px"></div>Loading ' + esc(name) + '...</div>';""",
    """panel.innerHTML = '<div class="loading-center"><div class="spinner" style="margin-bottom:12px"></div>Loading ' + esc(name) + '...</div>';"""
)

content = content.replace(
    """panel.innerHTML = '<div style="color:var(--critical);padding:20px">Error: ' + esc(e.message) + '</div>';""",
    """panel.innerHTML = '<div class="error-msg">Error: ' + esc(e.message) + '</div>';"""
)

# Status badge in APT header
content = content.replace(
    """' <span style="font-size:10px;padding:2px 8px;border-radius:3px;background:' + statusColor + '22;color:' + statusColor + ';font-weight:700;border:1px solid ' + statusColor + '44">' + status.toUpperCase() + '</span>';""",
    """' <span class="apt-status-badge" style="background:' + statusColor + '22;color:' + statusColor + ';border:1px solid ' + statusColor + '44">' + status.toUpperCase() + '</span>';"""
)

print("Phase 5: Updated JS render functions")

# ═══════════════════════════════════════════════════════════
# PHASE 6: Clean up remaining border-radius:3px/4px → 2px
# ═══════════════════════════════════════════════════════════

# In the remaining inline styles, fix any border-radius:3px or 4px to 2px
# But be careful not to change border-radius:50% (for dots)
content = re.sub(r'border-radius:\s*3px', 'border-radius:2px', content)
content = re.sub(r'border-radius:\s*4px', 'border-radius:2px', content)

print("Phase 6: Cleaned up remaining border-radius values")

# ═══════════════════════════════════════════════════════════
# WRITE OUTPUT
# ═══════════════════════════════════════════════════════════

with open(FILE, 'w', encoding='utf-8') as f:
    f.write(content)

total_lines = content.count('\n') + 1
print(f"\nDone! File saved: {total_lines} lines")
print(f"Total size: {len(content):,} bytes")
