"""Web UI - 组件化单文件结构"""

# ==================== CSS 样式 ====================
CSS_BASE = '''
* { margin: 0; padding: 0; box-sizing: border-box; }
:root { --bg: #fafafa; --card: #fff; --border: #e5e5e5; --text: #1a1a1a; --muted: #666; --accent: #000; --success: #22c55e; --error: #ef4444; --warn: #f59e0b; --info: #3b82f6; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #0a0a0a; --card: #141414; --border: #262626; --text: #fafafa; --muted: #a3a3a3; --accent: #fff; }
}
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }
.container { max-width: 1400px; margin: 0 auto; padding: 2rem 1rem; }
'''

CSS_LAYOUT = '''
header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; padding-bottom: 1rem; border-bottom: 1px solid var(--border); }
h1 { font-size: 1.5rem; font-weight: 600; display: flex; align-items: center; gap: 0.5rem; }
h1 img { width: 28px; height: 28px; }
.status { font-size: 0.875rem; color: var(--muted); display: flex; align-items: center; gap: 1rem; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; }
.status-dot.ok { background: var(--success); }
.status-dot.err { background: var(--error); }
.tabs { display: flex; gap: 0.5rem; margin-bottom: 1.5rem; flex-wrap: wrap; }
.tab { padding: 0.5rem 1rem; border: 1px solid var(--border); background: var(--card); cursor: pointer; font-size: 0.875rem; transition: all 0.2s; border-radius: 6px; }
.tab.active { background: var(--accent); color: var(--bg); border-color: var(--accent); }
.panel { display: none; }
.panel.active { display: block; }
.footer { text-align: center; color: var(--muted); font-size: 0.75rem; margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--border); }
'''

CSS_COMPONENTS = '''
.card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 1.5rem; margin-bottom: 1rem; }
.card h3 { font-size: 1rem; margin-bottom: 1rem; display: flex; justify-content: space-between; align-items: center; }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 1rem; margin-bottom: 1rem; }
.stat-item { text-align: center; padding: 1rem; background: var(--bg); border-radius: 6px; }
.stat-value { font-size: 1.5rem; font-weight: 600; }
.stat-label { font-size: 0.75rem; color: var(--muted); }
.badge { display: inline-block; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: 500; }
.badge.success { background: #dcfce7; color: #166534; }
.badge.error { background: #fee2e2; color: #991b1b; }
.badge.warn { background: #fef3c7; color: #92400e; }
.badge.info { background: #dbeafe; color: #1e40af; }
@media (prefers-color-scheme: dark) {
  .badge.success { background: #14532d; color: #86efac; }
  .badge.error { background: #7f1d1d; color: #fca5a5; }
  .badge.warn { background: #78350f; color: #fde68a; }
  .badge.info { background: #1e3a5f; color: #93c5fd; }
}
'''

CSS_FORMS = '''
.input-row { display: flex; gap: 0.5rem; }
.input-row input, .input-row select { flex: 1; padding: 0.75rem 1rem; border: 1px solid var(--border); border-radius: 6px; background: var(--card); color: var(--text); font-size: 1rem; }
button { padding: 0.75rem 1.5rem; background: var(--accent); color: var(--bg); border: none; border-radius: 6px; cursor: pointer; font-size: 0.875rem; font-weight: 500; transition: opacity 0.2s; }
button:hover { opacity: 0.8; }
button:disabled { opacity: 0.5; cursor: not-allowed; }
button.secondary { background: var(--card); color: var(--text); border: 1px solid var(--border); }
button.small { padding: 0.25rem 0.5rem; font-size: 0.75rem; }
select { padding: 0.6rem 0.75rem; border: 1px solid var(--border); border-radius: 6px; background: var(--card); color: var(--text); font-size: 0.875rem; cursor: pointer; appearance: none; background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%23666' d='M6 8L1 3h10z'/%3E%3C/svg%3E"); background-repeat: no-repeat; background-position: right 0.5rem center; padding-right: 2rem; }
select:hover { border-color: var(--accent); }
select:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 2px rgba(0,0,0,0.1); }
input[type="text"], input[type="number"], input[type="search"] { padding: 0.6rem 0.75rem; border: 1px solid var(--border); border-radius: 6px; background: var(--card); color: var(--text); font-size: 0.875rem; }
input[type="text"]:hover, input[type="number"]:hover, input[type="search"]:hover { border-color: var(--accent); }
input[type="text"]:focus, input[type="number"]:focus, input[type="search"]:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 2px rgba(0,0,0,0.1); }
input::placeholder { color: var(--muted); }
pre { background: var(--bg); border: 1px solid var(--border); border-radius: 6px; padding: 1rem; overflow-x: auto; font-size: 0.8rem; }
table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
th, td { padding: 0.75rem; text-align: left; border-bottom: 1px solid var(--border); }
th { font-weight: 500; color: var(--muted); }
@media (prefers-color-scheme: dark) {
  select { background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%23999' d='M6 8L1 3h10z'/%3E%3C/svg%3E"); }
  select:focus, input:focus { box-shadow: 0 0 0 2px rgba(255,255,255,0.1); }
}
'''

CSS_ACCOUNTS = '''
.account-card { border: 1px solid var(--border); border-radius: 8px; padding: 1rem; margin-bottom: 0.75rem; background: var(--card); }
.account-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; }
.account-name { font-weight: 500; display: flex; align-items: center; gap: 0.5rem; }
.account-meta { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 0.5rem; font-size: 0.8rem; color: var(--muted); }
.account-meta-item { display: flex; justify-content: space-between; padding: 0.25rem 0; }
.account-actions { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid var(--border); }
'''

CSS_API = '''
.endpoint { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem; }
.method { padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }
.method.get { background: #dcfce7; color: #166534; }
.method.post { background: #fef3c7; color: #92400e; }
@media (prefers-color-scheme: dark) {
  .method.get { background: #14532d; color: #86efac; }
  .method.post { background: #78350f; color: #fde68a; }
}
.copy-btn { padding: 0.25rem 0.5rem; font-size: 0.75rem; background: var(--card); border: 1px solid var(--border); color: var(--text); }
'''

CSS_DOCS = '''
.docs-container { display: flex; gap: 1.5rem; min-height: 500px; }
.docs-nav { width: 200px; flex-shrink: 0; }
.docs-nav-item { display: block; padding: 0.5rem 0.75rem; margin-bottom: 0.25rem; border-radius: 6px; cursor: pointer; font-size: 0.875rem; color: var(--text); text-decoration: none; transition: background 0.2s; }
.docs-nav-item:hover { background: var(--bg); }
.docs-nav-item.active { background: var(--accent); color: var(--bg); }
.docs-content { flex: 1; min-width: 0; }
.docs-content h1 { font-size: 1.5rem; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 1px solid var(--border); }
.docs-content h2 { font-size: 1.25rem; margin: 1.5rem 0 0.75rem; color: var(--text); }
.docs-content h3 { font-size: 1rem; margin: 1rem 0 0.5rem; color: var(--text); }
.docs-content h4 { font-size: 0.9rem; margin: 0.75rem 0 0.5rem; color: var(--muted); }
.docs-content p { margin: 0.5rem 0; }
.docs-content ul, .docs-content ol { margin: 0.5rem 0; padding-left: 1.5rem; }
.docs-content li { margin: 0.25rem 0; }
.docs-content code { background: var(--bg); padding: 0.2em 0.4em; border-radius: 3px; font-size: 0.9em; }
.docs-content pre { margin: 0.75rem 0; }
.docs-content pre code { background: none; padding: 0; }
.docs-content table { margin: 0.75rem 0; }
.docs-content blockquote { margin: 0.75rem 0; padding: 0.5rem 1rem; border-left: 3px solid var(--border); color: var(--muted); background: var(--bg); border-radius: 0 6px 6px 0; }
.docs-content hr { margin: 1.5rem 0; border: none; border-top: 1px solid var(--border); }
.docs-content a { color: var(--info); text-decoration: none; }
.docs-content a:hover { text-decoration: underline; }
@media (max-width: 768px) {
  .docs-container { flex-direction: column; }
  .docs-nav { width: 100%; display: flex; flex-wrap: wrap; gap: 0.5rem; }
  .docs-nav-item { margin-bottom: 0; }
}
'''

# ==================== UI 组件库样式 ====================
CSS_UI_COMPONENTS = '''
/* Modal 模态框 */
.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; opacity: 0; visibility: hidden; transition: all 0.2s; }
.modal-overlay.active { opacity: 1; visibility: visible; }
.modal { background: var(--card); border-radius: 12px; max-width: 500px; width: 90%; max-height: 90vh; overflow: hidden; transform: scale(0.9); transition: transform 0.2s; }
.modal-overlay.active .modal { transform: scale(1); }
.modal-header { padding: 1rem 1.5rem; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
.modal-header h3 { font-size: 1.1rem; font-weight: 600; }
.modal-close { background: none; border: none; font-size: 1.5rem; cursor: pointer; color: var(--muted); padding: 0; line-height: 1; }
.modal-body { padding: 1.5rem; overflow-y: auto; max-height: 60vh; }
.modal-footer { padding: 1rem 1.5rem; border-top: 1px solid var(--border); display: flex; justify-content: flex-end; gap: 0.5rem; }
.modal.danger .modal-header { background: #fee2e2; }
.modal.warning .modal-header { background: #fef3c7; }
@media (prefers-color-scheme: dark) {
  .modal.danger .modal-header { background: #7f1d1d; }
  .modal.warning .modal-header { background: #78350f; }
}

/* Toast 通知 */
.toast-container { position: fixed; top: 1rem; right: 1rem; z-index: 1100; display: flex; flex-direction: column; gap: 0.5rem; }
.toast { padding: 0.75rem 1rem; border-radius: 8px; background: var(--card); border: 1px solid var(--border); box-shadow: 0 4px 12px rgba(0,0,0,0.15); display: flex; align-items: center; gap: 0.5rem; animation: slideIn 0.3s ease; min-width: 250px; }
.toast.success { border-left: 4px solid var(--success); }
.toast.error { border-left: 4px solid var(--error); }
.toast.warning { border-left: 4px solid var(--warn); }
.toast.info { border-left: 4px solid var(--info); }
.toast-close { margin-left: auto; background: none; border: none; cursor: pointer; color: var(--muted); font-size: 1.2rem; padding: 0; }
@keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }

/* Select 下拉选择 */
.custom-select { position: relative; }
.custom-select-trigger { padding: 0.75rem 1rem; border: 1px solid var(--border); border-radius: 6px; background: var(--card); cursor: pointer; display: flex; justify-content: space-between; align-items: center; }
.custom-select-trigger::after { content: "▼"; font-size: 0.7rem; color: var(--muted); }
.custom-select-options { position: absolute; top: 100%; left: 0; right: 0; background: var(--card); border: 1px solid var(--border); border-radius: 6px; margin-top: 4px; max-height: 200px; overflow-y: auto; z-index: 100; display: none; }
.custom-select.open .custom-select-options { display: block; }
.custom-select-option { padding: 0.5rem 1rem; cursor: pointer; }
.custom-select-option:hover { background: var(--bg); }
.custom-select-option.selected { background: var(--accent); color: var(--bg); }

/* ProgressBar 进度条 */
.progress-bar { height: 8px; background: var(--bg); border-radius: 4px; overflow: hidden; }
.progress-bar.large { height: 12px; }
.progress-bar.small { height: 4px; }
.progress-fill { height: 100%; background: var(--info); transition: width 0.3s; }
.progress-fill.success { background: var(--success); }
.progress-fill.warning { background: var(--warn); }
.progress-fill.error { background: var(--error); }
.progress-label { display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--muted); margin-top: 0.25rem; }

/* Dropdown 下拉菜单 */
.dropdown { position: relative; display: inline-block; }
.dropdown-menu { position: absolute; top: 100%; right: 0; background: var(--card); border: 1px solid var(--border); border-radius: 8px; min-width: 120px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); z-index: 100; display: none; margin-top: 4px; overflow: hidden; }
.dropdown.open .dropdown-menu { display: block; }
.dropdown-item { padding: 0.5rem 0.75rem; cursor: pointer; display: flex; align-items: center; gap: 0.5rem; font-size: 0.875rem; white-space: nowrap; }
.dropdown-item:hover { background: var(--bg); }
.dropdown-item.danger { color: var(--error); }
.dropdown-divider { height: 1px; background: var(--border); margin: 0.25rem 0; }

/* 账号卡片增强 */
.account-card-enhanced { border: 1px solid var(--border); border-radius: 12px; padding: 1.25rem; margin-bottom: 1rem; background: var(--card); }
.account-card-enhanced.priority { border-color: var(--info); border-width: 2px; }
.account-card-enhanced.active { box-shadow: 0 0 0 2px var(--success); }
.account-card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem; }
.account-card-title { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
.account-card-badges { display: flex; gap: 0.25rem; flex-wrap: wrap; }
.account-quota-section { margin: 1rem 0; }
.quota-header { display: flex; justify-content: space-between; margin-bottom: 0.5rem; font-size: 0.875rem; }
.quota-detail { display: flex; gap: 1rem; font-size: 0.75rem; color: var(--muted); margin-top: 0.5rem; flex-wrap: wrap; }
.account-stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.5rem; margin: 1rem 0; }
.account-stat { text-align: center; padding: 0.5rem; background: var(--bg); border-radius: 6px; }
.account-stat-value { font-weight: 600; font-size: 0.9rem; }
.account-stat-label { font-size: 0.7rem; color: var(--muted); }

/* 账号网格布局 - 动态自适应 */
.accounts-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 0.75rem; margin-top: 1rem; }
.account-card-compact { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 0.875rem; transition: all 0.2s; }
.account-card-compact:hover { border-color: var(--accent); }
.account-card-compact.priority { border-color: var(--info); border-width: 2px; }
.account-card-compact.low-balance { border-color: var(--warn); }
.account-card-compact.exhausted { border-color: var(--error); border-width: 2px; }
.account-card-compact.unavailable { opacity: 0.6; }
.account-card-top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.75rem; }
.account-card-info { flex: 1; min-width: 0; }
.account-card-name { font-weight: 600; font-size: 0.95rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 0.25rem; }
.account-card-email { font-size: 0.75rem; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.account-card-status { display: flex; gap: 0.25rem; flex-wrap: wrap; }
.account-card-quota { margin: 0.75rem 0; }
.account-card-quota-bar { height: 6px; background: var(--bg); border-radius: 3px; overflow: hidden; }
.account-card-quota-fill { height: 100%; transition: width 0.3s; }
.account-card-quota-text { display: flex; justify-content: space-between; font-size: 0.7rem; color: var(--muted); margin-top: 0.25rem; }
.account-card-stats { display: flex; gap: 1rem; font-size: 0.75rem; color: var(--muted); margin-bottom: 0.75rem; }
.account-card-actions { display: flex; gap: 0.5rem; flex-wrap: wrap; padding-top: 0.75rem; border-top: 1px solid var(--border); }
.account-card-actions button { flex: 1; min-width: 60px; }

/* 紧凑汇总面板 */
.summary-compact { display: flex; gap: 1.5rem; flex-wrap: wrap; align-items: center; padding: 0.75rem; background: var(--bg); border-radius: 8px; }
.summary-compact-item { display: flex; align-items: center; gap: 0.5rem; }
.summary-compact-value { font-weight: 600; font-size: 1.1rem; }
.summary-compact-label { font-size: 0.75rem; color: var(--muted); }
.summary-compact-divider { width: 1px; height: 24px; background: var(--border); }
.summary-quota-bar { flex: 1; min-width: 150px; max-width: 300px; }

/* 全局进度条 - 批量刷新操作进度显示 */
.global-progress-bar { position: fixed; top: 0; left: 0; right: 0; z-index: 1200; background: var(--card); border-bottom: 1px solid var(--border); box-shadow: 0 2px 8px rgba(0,0,0,0.1); transform: translateY(-100%); transition: transform 0.3s ease; }
.global-progress-bar.active { transform: translateY(0); }
.global-progress-bar-inner { max-width: 1400px; margin: 0 auto; padding: 0.75rem 1rem; }
.global-progress-bar-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }
.global-progress-bar-title { font-weight: 600; font-size: 0.9rem; display: flex; align-items: center; gap: 0.5rem; }
.global-progress-bar-title .spinner { display: inline-block; width: 14px; height: 14px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 1s linear infinite; }
.global-progress-bar-stats { display: flex; gap: 1rem; font-size: 0.8rem; color: var(--muted); }
.global-progress-bar-stats span { display: flex; align-items: center; gap: 0.25rem; }
.global-progress-bar-stats .success { color: var(--success); }
.global-progress-bar-stats .error { color: var(--error); }
.global-progress-bar-track { height: 6px; background: var(--bg); border-radius: 3px; overflow: hidden; margin-bottom: 0.5rem; }
.global-progress-bar-fill { height: 100%; background: var(--info); transition: width 0.3s ease; border-radius: 3px; }
.global-progress-bar-fill.complete { background: var(--success); }
.global-progress-bar-current { font-size: 0.75rem; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.global-progress-bar-close { background: none; border: none; font-size: 1.2rem; cursor: pointer; color: var(--muted); padding: 0; margin-left: 0.5rem; }
.global-progress-bar-close:hover { color: var(--text); }

/* 汇总面板 */
.summary-panel { background: linear-gradient(135deg, var(--card) 0%, var(--bg) 100%); border: 1px solid var(--border); border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; }
.summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 1rem; margin-bottom: 1rem; }
.summary-item { text-align: center; }
.summary-value { font-size: 1.75rem; font-weight: 700; }
.summary-label { font-size: 0.75rem; color: var(--muted); }
.summary-item.success .summary-value { color: var(--success); }
.summary-item.warning .summary-value { color: var(--warn); }
.summary-item.error .summary-value { color: var(--error); }
.summary-quota { margin: 1rem 0; }
.summary-info { display: flex; gap: 2rem; flex-wrap: wrap; font-size: 0.875rem; color: var(--muted); }
.summary-actions { margin-top: 1rem; display: flex; gap: 0.5rem; }
'''

CSS_STYLES = CSS_BASE + CSS_LAYOUT + CSS_COMPONENTS + CSS_FORMS + CSS_ACCOUNTS + CSS_API + CSS_DOCS + CSS_UI_COMPONENTS


# ==================== HTML 模板 ====================
# 全局进度条容器 - 显示在页面顶部
HTML_GLOBAL_PROGRESS = '''
<!-- 全局进度条 - 批量刷新操作进度显示 -->
<div class="global-progress-bar" id="globalProgressBar">
  <div class="global-progress-bar-inner">
    <div class="global-progress-bar-header">
      <div class="global-progress-bar-title">
        <span class="spinner"></span>
        <span id="globalProgressTitle">正在刷新额度...</span>
      </div>
      <div class="global-progress-bar-stats">
        <span>完成: <strong id="globalProgressCompleted">0</strong>/<strong id="globalProgressTotal">0</strong></span>
        <span class="success">成功: <strong id="globalProgressSuccess">0</strong></span>
        <span class="error">失败: <strong id="globalProgressFailed">0</strong></span>
        <button class="global-progress-bar-close" id="globalProgressClose" onclick="GlobalProgressBar.hide()" style="display:none">&times;</button>
      </div>
    </div>
    <div class="global-progress-bar-track">
      <div class="global-progress-bar-fill" id="globalProgressFill" style="width:0%"></div>
    </div>
    <div class="global-progress-bar-current" id="globalProgressCurrent">准备中...</div>
  </div>
</div>
'''

HTML_HEADER = '''
<header>
  <h1><img src="/assets/icon.svg" alt="Kiro">Kiro API Proxy</h1>
  <div class="status">
    <span class="status-dot" id="statusDot"></span>
    <span id="statusText">检查中...</span>
    <span id="uptime"></span>
  </div>
</header>

<div class="tabs">
  <div class="tab active" data-tab="help">帮助</div>
  <div class="tab" data-tab="flows">流量</div>
  <div class="tab" data-tab="monitor">监控</div>
  <div class="tab" data-tab="accounts">账号</div>
  <div class="tab" data-tab="logs">日志</div>
  <div class="tab" data-tab="api">API</div>
  <div class="tab" data-tab="settings">设置</div>
</div>
'''

HTML_HELP = '''
<div class="panel active" id="help">
  <div class="card" style="padding:1rem">
    <div class="docs-container">
      <nav class="docs-nav" id="docsNav"></nav>
      <div class="docs-content" id="docsContent">
        <p style="color:var(--muted)">加载中...</p>
      </div>
    </div>
  </div>
</div>
'''

HTML_FLOWS = '''
<div class="panel" id="flows">
  <div class="card">
    <h3>Flow 统计 <button class="secondary small" onclick="loadFlowStats()">刷新</button></h3>
    <div class="stats-grid" id="flowStatsGrid"></div>
  </div>
  <div class="card">
    <h3>流量监控</h3>
    <div style="display:flex;gap:0.5rem;margin-bottom:1rem;flex-wrap:wrap">
      <select id="flowProtocol" onchange="loadFlows()">
        <option value="">全部协议</option>
        <option value="anthropic">Anthropic</option>
        <option value="openai">OpenAI</option>
        <option value="gemini">Gemini</option>
      </select>
      <select id="flowState" onchange="loadFlows()">
        <option value="">全部状态</option>
        <option value="completed">完成</option>
        <option value="error">错误</option>
        <option value="streaming">流式中</option>
        <option value="pending">等待中</option>
      </select>
      <input type="text" id="flowSearch" placeholder="搜索内容..." style="flex:1;min-width:150px" onkeydown="if(event.key==='Enter')loadFlows()">
      <button class="secondary" onclick="loadFlows()">搜索</button>
      <button class="secondary" onclick="exportFlows()">导出</button>
    </div>
    <div id="flowList"></div>
  </div>
  <div class="card" id="flowDetail" style="display:none">
    <h3>Flow 详情 <button class="secondary small" onclick="$('#flowDetail').style.display='none'">关闭</button></h3>
    <div id="flowDetailContent"></div>
  </div>
</div>
'''

HTML_MONITOR = '''
<div class="panel" id="monitor">
  <div class="card">
    <h3>服务状态 <button class="secondary small" onclick="loadStats()">刷新</button></h3>
    <div class="stats-grid" id="statsGrid"></div>
  </div>
  <div class="card">
    <h3>配额状态</h3>
    <div id="quotaStatus"></div>
  </div>
  <div class="card">
    <h3>速度测试</h3>
    <button onclick="runSpeedtest()" id="speedtestBtn">开始测试</button>
    <span id="speedtestResult" style="margin-left:1rem"></span>
  </div>
</div>
'''


HTML_ACCOUNTS = '''
<div class="panel" id="accounts">
  <!-- 紧凑的工具栏 + 汇总面板 -->
  <div class="card" style="padding:1rem">
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.75rem;margin-bottom:1rem">
      <h3 style="margin:0;font-size:1.1rem">账号管理</h3>
      <div style="display:flex;gap:0.5rem;flex-wrap:wrap">
        <button class="small" onclick="showLoginOptions()">+ 添加</button>
        <button class="secondary small" onclick="scanTokens()">扫描</button>
        <button class="secondary small" onclick="showImportExportMenu(this)">导入/导出 ▼</button>
        <button class="secondary small" onclick="refreshAllQuotas()">刷新额度</button>
      </div>
    </div>
    <!-- 内嵌汇总统计 -->
    <div id="accountsSummaryCompact"></div>
  </div>
  
  <!-- 账号网格列表 -->
  <div id="accountsGrid" class="accounts-grid"></div>
  
  <!-- 隐藏的弹出面板 -->
  <div class="card" id="loginOptions" style="display:none">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
      <h3 style="margin:0">添加账号</h3>
      <button class="secondary small" onclick="$('#loginOptions').style.display='none'">✕</button>
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem">
      <!-- 在线登录 -->
      <div style="border:1px solid var(--border);border-radius:8px;padding:1rem">
        <h4 style="margin-bottom:0.75rem;font-size:0.9rem">🌐 在线登录</h4>
        <div style="display:flex;flex-direction:column;gap:0.5rem">
          <button class="secondary small" onclick="startSocialLogin('google')" style="justify-content:flex-start;gap:0.5rem">
            <svg width="16" height="16" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
            Google
          </button>
          <button class="secondary small" onclick="startSocialLogin('github')" style="justify-content:flex-start;gap:0.5rem">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>
            GitHub
          </button>
          <button class="secondary small" onclick="startAwsLogin()" style="justify-content:flex-start;gap:0.5rem">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="#FF9900"><path d="M21.698 16.207c-2.626 1.94-6.442 2.969-9.722 2.969-4.598 0-8.74-1.7-11.87-4.526-.247-.223-.024-.527.27-.351 3.384 1.963 7.559 3.153 11.877 3.153 2.914 0 6.114-.607 9.06-1.852.439-.2.814.287.385.607z"/></svg>
            AWS Builder ID
          </button>
        </div>
      </div>
      <!-- 其他方式 -->
      <div style="border:1px solid var(--border);border-radius:8px;padding:1rem">
        <h4 style="margin-bottom:0.75rem;font-size:0.9rem">📋 其他方式</h4>
        <div style="display:flex;flex-direction:column;gap:0.5rem">
          <button class="secondary small" onclick="createRemoteLogin()">🔗 远程登录链接</button>
          <button class="secondary small" onclick="showManualAdd()">✏️ 手动添加 Token</button>
        </div>
      </div>
    </div>
    <div style="margin-top:0.75rem">
      <label style="display:flex;align-items:center;gap:0.5rem;cursor:pointer;font-size:0.85rem;color:var(--muted)">
        <input type="checkbox" id="incognitoMode"> 无痕模式打开浏览器
      </label>
    </div>
  </div>
  
  <div class="card" id="loginPanel" style="display:none">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
      <h3 style="margin:0">在线登录</h3>
      <button class="secondary small" onclick="cancelKiroLogin()">✕</button>
    </div>
    <div id="loginContent"></div>
  </div>
  
  <div class="card" id="remoteLoginPanel" style="display:none">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
      <h3 style="margin:0">远程登录链接</h3>
      <button class="secondary small" onclick="$('#remoteLoginPanel').style.display='none'">✕</button>
    </div>
    <div id="remoteLoginContent"></div>
  </div>
  
  <div class="card" id="manualAddPanel" style="display:none">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
      <h3 style="margin:0">手动添加 Token</h3>
      <button class="secondary small" onclick="$('#manualAddPanel').style.display='none'">✕</button>
    </div>
    <div style="display:grid;gap:0.75rem">
      <div>
        <label style="display:block;font-size:0.8rem;color:var(--muted);margin-bottom:0.25rem">账号名称</label>
        <input type="text" id="manualName" placeholder="我的账号" style="width:100%;padding:0.5rem;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text)">
      </div>
      <div>
        <label style="display:block;font-size:0.8rem;color:var(--muted);margin-bottom:0.25rem">Access Token *</label>
        <textarea id="manualAccessToken" placeholder="粘贴 accessToken..." style="width:100%;height:60px;padding:0.5rem;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text);font-family:monospace;font-size:0.75rem"></textarea>
      </div>
      <div>
        <label style="display:block;font-size:0.8rem;color:var(--muted);margin-bottom:0.25rem">Refresh Token（可选）</label>
        <textarea id="manualRefreshToken" placeholder="粘贴 refreshToken..." style="width:100%;height:60px;padding:0.5rem;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text);font-family:monospace;font-size:0.75rem"></textarea>
      </div>
      <button onclick="submitManualToken()">添加账号</button>
    </div>
  </div>
  
  <div class="card" id="scanResults" style="display:none">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
      <h3 style="margin:0">扫描结果</h3>
      <button class="secondary small" onclick="$('#scanResults').style.display='none'">✕</button>
    </div>
    <div id="scanList"></div>
  </div>
</div>
'''

HTML_LOGS = '''
<div class="panel" id="logs">
  <div class="card">
    <h3>请求日志 <button class="secondary small" onclick="loadLogs()">刷新</button></h3>
    <table>
      <thead><tr><th>时间</th><th>路径</th><th>模型</th><th>账号</th><th>状态</th><th>耗时</th></tr></thead>
      <tbody id="logTable"></tbody>
    </table>
  </div>
</div>
'''

HTML_API = '''
<div class="panel" id="api">
  <div class="card">
    <h3>API 端点</h3>
    <p style="color:var(--muted);font-size:0.875rem;margin-bottom:1rem">支持 OpenAI、Anthropic、Gemini 三种协议</p>
    <h4 style="color:var(--muted);margin-bottom:0.5rem">OpenAI 协议</h4>
    <div class="endpoint"><span class="method post">POST</span><code>/v1/chat/completions</code></div>
    <div class="endpoint"><span class="method get">GET</span><code>/v1/models</code></div>
    <h4 style="color:var(--muted);margin-top:1rem;margin-bottom:0.5rem">Anthropic 协议</h4>
    <div class="endpoint"><span class="method post">POST</span><code>/v1/messages</code></div>
    <div class="endpoint"><span class="method post">POST</span><code>/v1/messages/count_tokens</code></div>
    <h4 style="color:var(--muted);margin-top:1rem;margin-bottom:0.5rem">Gemini 协议</h4>
    <div class="endpoint"><span class="method post">POST</span><code>/v1/models/{model}:generateContent</code></div>
    <h4 style="margin-top:1rem;color:var(--muted)">Base URL</h4>
    <pre><code id="baseUrl"></code></pre>
    <button class="copy-btn" onclick="copy(location.origin)" style="margin-top:0.5rem">复制</button>
  </div>
  <div class="card">
    <h3>配置示例</h3>
    <h4 style="color:var(--muted);margin-bottom:0.5rem">Claude Code</h4>
    <pre><code>Base URL: <span class="pyUrl"></span>
API Key: any
模型: claude-sonnet-4</code></pre>
    <h4 style="color:var(--muted);margin-top:1rem;margin-bottom:0.5rem">Codex CLI</h4>
    <pre><code>Endpoint: <span class="pyUrl"></span>/v1
API Key: any
模型: gpt-4o</code></pre>
  </div>
  <div class="card">
    <h3>Claude Code 终端配置</h3>
    <p style="color:var(--muted);font-size:0.875rem;margin-bottom:1rem">Claude Code 终端版需要配置 <code>~/.claude/settings.json</code> 才能跳过登录使用代理</p>
    
    <h4 style="color:var(--muted);margin-bottom:0.5rem">临时生效（当前终端）</h4>
    <pre id="envTempCmd"><code>export ANTHROPIC_BASE_URL="<span class="pyUrl"></span>"
export ANTHROPIC_AUTH_TOKEN="sk-any"
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1</code></pre>
    <button class="copy-btn" onclick="copyEnvTemp()" style="margin-top:0.5rem">复制命令</button>
    
    <h4 style="color:var(--muted);margin-top:1rem;margin-bottom:0.5rem">永久生效（推荐，写入配置文件）</h4>
    <pre id="envPermCmd"><code># 写入 Claude Code 配置文件
mkdir -p ~/.claude
cat > ~/.claude/settings.json << 'EOF'
{
  "env": {
    "ANTHROPIC_BASE_URL": "<span class="pyUrl"></span>",
    "ANTHROPIC_AUTH_TOKEN": "sk-any",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"
  }
}
EOF</code></pre>
    <button class="copy-btn" onclick="copyEnvPerm()" style="margin-top:0.5rem">复制命令</button>
    
    <h4 style="color:var(--muted);margin-top:1rem;margin-bottom:0.5rem">清除配置</h4>
    <pre id="envClearCmd"><code># 删除 Claude Code 配置
rm -f ~/.claude/settings.json
unset ANTHROPIC_BASE_URL ANTHROPIC_AUTH_TOKEN CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC</code></pre>
    <button class="copy-btn" onclick="copyEnvClear()" style="margin-top:0.5rem">复制命令</button>
    
    <p style="color:var(--muted);font-size:0.75rem;margin-top:1rem">
      💡 使用 <code>ANTHROPIC_AUTH_TOKEN</code> + <code>CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1</code> 可跳过登录
    </p>
  </div>
  <div class="card">
    <h3>模型映射</h3>
    <p style="color:var(--muted);font-size:0.875rem;margin-bottom:1rem">支持多种模型名称，自动映射到 Kiro 模型</p>
    <table>
      <thead><tr><th>Kiro 模型</th><th>能力</th><th>可用名称</th></tr></thead>
      <tbody>
        <tr><td><code>claude-sonnet-4</code></td><td>⭐⭐⭐ 推荐</td><td>gpt-4o, gpt-4, claude-3-5-sonnet-*, sonnet</td></tr>
        <tr><td><code>claude-sonnet-4.5</code></td><td>⭐⭐⭐⭐ 更强</td><td>gemini-1.5-pro</td></tr>
        <tr><td><code>claude-haiku-4.5</code></td><td>⚡ 快速</td><td>gpt-4o-mini, gpt-3.5-turbo, haiku</td></tr>
        <tr><td><code>claude-opus-4.5</code></td><td>⭐⭐⭐⭐⭐ 最强</td><td>o1, o1-preview, opus</td></tr>
        <tr><td><code>auto</code></td><td>🤖 自动</td><td>auto</td></tr>
      </tbody>
    </table>
    <p style="color:var(--muted);font-size:0.75rem;margin-top:0.75rem">
      💡 直接使用 Kiro 模型名（如 claude-sonnet-4）或任意映射名称均可
    </p>
  </div>
</div>
'''

HTML_SETTINGS = '''
<div class="panel" id="settings">
  <!-- 刷新配置面板 -->
  <div class="card">
    <h3>刷新配置 
      <button class="secondary small" onclick="loadRefreshConfig()">刷新</button>
      <button class="secondary small" onclick="resetRefreshConfig()">还原默认</button>
    </h3>
    <p style="color:var(--muted);font-size:0.875rem;margin-bottom:1rem">
      配置 Token 刷新和额度刷新的相关参数
    </p>
    
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem;margin-bottom:1rem">
      <div>
        <label style="display:block;font-size:0.875rem;color:var(--muted);margin-bottom:0.25rem">最大重试次数</label>
        <input type="number" id="refreshMaxRetries" value="3" min="1" max="10" style="width:100%;padding:0.5rem;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text)" onchange="saveRefreshConfig()">
        <span style="font-size:0.75rem;color:var(--muted)">刷新失败时的重试次数（1-10）</span>
      </div>
      <div>
        <label style="display:block;font-size:0.875rem;color:var(--muted);margin-bottom:0.25rem">并发数</label>
        <input type="number" id="refreshConcurrency" value="3" min="1" max="10" style="width:100%;padding:0.5rem;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text)" onchange="saveRefreshConfig()">
        <span style="font-size:0.75rem;color:var(--muted)">同时刷新的账号数量（1-10）</span>
      </div>
      <div>
        <label style="display:block;font-size:0.875rem;color:var(--muted);margin-bottom:0.25rem">自动刷新间隔（秒）</label>
        <input type="number" id="refreshAutoInterval" value="60" min="30" max="600" style="width:100%;padding:0.5rem;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text)" onchange="saveRefreshConfig()">
        <span style="font-size:0.75rem;color:var(--muted)">自动检查刷新的间隔（30-600秒）</span>
      </div>
      <div>
        <label style="display:block;font-size:0.875rem;color:var(--muted);margin-bottom:0.25rem">重试基础延迟（秒）</label>
        <input type="number" id="refreshRetryDelay" value="1.0" min="0.5" max="5" step="0.5" style="width:100%;padding:0.5rem;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text)" onchange="saveRefreshConfig()">
        <span style="font-size:0.75rem;color:var(--muted)">重试延迟基数，指数增长（0.5-5秒）</span>
      </div>
      <div>
        <label style="display:block;font-size:0.875rem;color:var(--muted);margin-bottom:0.25rem">Token 提前刷新时间（秒）</label>
        <input type="number" id="refreshBeforeExpiry" value="300" min="60" max="600" style="width:100%;padding:0.5rem;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text)" onchange="saveRefreshConfig()">
        <span style="font-size:0.75rem;color:var(--muted)">Token 过期前多久开始刷新（60-600秒）</span>
      </div>
    </div>
    
    <div id="refreshConfigStatus" style="padding:0.75rem;background:var(--bg);border-radius:6px;font-size:0.875rem"></div>
  </div>

  <div class="card">
    <h3>请求限速 
      <button class="secondary small" onclick="loadRateLimitConfig()">刷新</button>
      <button class="secondary small" onclick="resetRateLimitConfig()">还原默认</button>
    </h3>
    <p style="color:var(--muted);font-size:0.875rem;margin-bottom:1rem">
      启用后会限制请求频率，并在遇到 429 错误时短暂冷却账号
    </p>
    
    <label style="display:flex;align-items:center;gap:0.5rem;margin-bottom:1rem;cursor:pointer">
      <input type="checkbox" id="rateLimitEnabled" onchange="updateRateLimitConfig()">
      <span><strong>启用限速</strong>（关闭时 429 错误不会导致账号冷却）</span>
    </label>
    
    <div id="rateLimitOptions" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem;margin-bottom:1rem">
      <div>
        <label style="display:block;font-size:0.875rem;color:var(--muted);margin-bottom:0.25rem">最小请求间隔（秒）</label>
        <input type="number" id="minRequestInterval" value="0.5" min="0" max="10" step="0.1" style="width:100%;padding:0.5rem;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text)" onchange="updateRateLimitConfig()">
      </div>
      <div>
        <label style="display:block;font-size:0.875rem;color:var(--muted);margin-bottom:0.25rem">每账号每分钟最大请求</label>
        <input type="number" id="maxRequestsPerMinute" value="60" min="1" max="200" style="width:100%;padding:0.5rem;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text)" onchange="updateRateLimitConfig()">
      </div>
      <div>
        <label style="display:block;font-size:0.875rem;color:var(--muted);margin-bottom:0.25rem">全局每分钟最大请求</label>
        <input type="number" id="globalMaxRequestsPerMinute" value="120" min="1" max="300" style="width:100%;padding:0.5rem;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text)" onchange="updateRateLimitConfig()">
      </div>
      <div>
        <label style="display:block;font-size:0.875rem;color:var(--muted);margin-bottom:0.25rem">429 冷却时间（秒）</label>
        <input type="number" id="quotaCooldownSeconds" value="30" min="5" max="300" style="width:100%;padding:0.5rem;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text)" onchange="updateRateLimitConfig()">
      </div>
    </div>
    
    <div id="rateLimitStats" style="padding:0.75rem;background:var(--bg);border-radius:6px;font-size:0.875rem"></div>
  </div>

  <div class="card">
    <h3>历史消息管理 
      <button class="secondary small" onclick="loadHistoryConfig()">刷新</button>
      <button class="secondary small" onclick="resetHistoryConfig()">还原默认</button>
    </h3>
    <p style="color:var(--muted);font-size:0.875rem;margin-bottom:1rem">
      自动处理 Kiro API 的输入长度限制，超限时智能压缩而非强硬截断
    </p>
    
    <div style="padding:1rem;background:linear-gradient(135deg,rgba(34,197,94,0.1),rgba(59,130,246,0.1));border-radius:8px;margin-bottom:1rem">
      <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.5rem">
        <span style="font-size:1.25rem">🤖</span>
        <strong style="color:var(--success)">智能压缩模式</strong>
        <span style="background:var(--success);color:white;padding:0.125rem 0.5rem;border-radius:4px;font-size:0.75rem">自动</span>
      </div>
      <p style="font-size:0.875rem;color:var(--muted);margin:0">
        当对话历史超过 120K 字符时，自动生成早期对话摘要并保留最近上下文，无需手动配置参数
      </p>
    </div>
    
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem;margin-bottom:1rem">
      <div>
        <label style="display:block;font-size:0.875rem;color:var(--muted);margin-bottom:0.25rem">最大重试次数</label>
        <input type="number" id="maxRetries" value="3" min="1" max="5" style="width:100%;padding:0.5rem;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text)" onchange="updateHistoryConfig()">
        <span style="font-size:0.75rem;color:var(--muted)">超限错误后的重试次数</span>
      </div>
      <div>
        <label style="display:block;font-size:0.875rem;color:var(--muted);margin-bottom:0.25rem">摘要缓存时间（秒）</label>
        <input type="number" id="summaryCacheMaxAge" value="300" min="60" max="600" step="30" style="width:100%;padding:0.5rem;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text)" onchange="updateHistoryConfig()">
        <span style="font-size:0.75rem;color:var(--muted)">相同上下文复用摘要</span>
      </div>
    </div>
    
    <label style="display:flex;align-items:center;gap:0.5rem;cursor:pointer;margin-bottom:1rem">
      <input type="checkbox" id="addWarningHeader" onchange="updateHistoryConfig()">
      <span>压缩时在日志中显示信息</span>
    </label>
    
    <div style="padding:1rem;background:var(--bg);border-radius:6px">
      <p style="font-size:0.875rem;color:var(--muted);margin:0">
        <strong>工作原理：</strong><br>
        1. 发送前自动检测历史消息大小<br>
        2. 超过阈值时，用 AI 生成早期对话摘要<br>
        3. 保留最近 6-20 条完整消息 + 摘要<br>
        4. 收到超限错误时自动压缩并重试<br>
        <br>
        <span style="color:var(--success)">✓ 保留关键上下文</span> &nbsp;
        <span style="color:var(--success)">✓ 自动管理无需配置</span> &nbsp;
        <span style="color:var(--success)">✓ 智能缓存避免重复调用</span>
      </p>
    </div>
  </div>
</div>
'''

HTML_BODY = HTML_GLOBAL_PROGRESS + HTML_HEADER + HTML_HELP + HTML_FLOWS + HTML_MONITOR + HTML_ACCOUNTS + HTML_LOGS + HTML_API + HTML_SETTINGS


# ==================== JavaScript ====================
JS_UTILS = '''
const $=s=>document.querySelector(s);
const $$=s=>document.querySelectorAll(s);

function copy(text){
  navigator.clipboard.writeText(text).then(()=>{
    const toast=document.createElement('div');
    toast.textContent='已复制';
    toast.style.cssText='position:fixed;bottom:2rem;left:50%;transform:translateX(-50%);background:var(--accent);color:var(--bg);padding:0.5rem 1rem;border-radius:6px;font-size:0.875rem;z-index:1000';
    document.body.appendChild(toast);
    setTimeout(()=>toast.remove(),1500);
  });
}

function copyEnvTemp(){
  const url=location.origin;
  copy(`export ANTHROPIC_BASE_URL="${url}"
export ANTHROPIC_AUTH_TOKEN="sk-any"
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`);
}

function copyEnvPerm(){
  const url=location.origin;
  copy(`# 写入 Claude Code 配置文件（推荐）
mkdir -p ~/.claude
cat > ~/.claude/settings.json << 'EOF'
{
  "env": {
    "ANTHROPIC_BASE_URL": "${url}",
    "ANTHROPIC_AUTH_TOKEN": "sk-any",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"
  }
}
EOF
echo "配置完成，请重新打开终端运行 claude"`);
}

function copyEnvClear(){
  copy(`# 删除 Claude Code 配置
rm -f ~/.claude/settings.json
unset ANTHROPIC_BASE_URL ANTHROPIC_AUTH_TOKEN CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC
echo "配置已清除"`);
}

function formatUptime(s){
  if(s<60)return s+'秒';
  if(s<3600)return Math.floor(s/60)+'分钟';
  return Math.floor(s/3600)+'小时'+Math.floor((s%3600)/60)+'分钟';
}

function escapeHtml(text){
  const div=document.createElement('div');
  div.textContent=text;
  return div.innerHTML;
}
'''

JS_TABS = '''
// Tabs
$$('.tab').forEach(t=>t.onclick=()=>{
  $$('.tab').forEach(x=>x.classList.remove('active'));
  $$('.panel').forEach(x=>x.classList.remove('active'));
  t.classList.add('active');
  $('#'+t.dataset.tab).classList.add('active');
  if(t.dataset.tab==='monitor'){loadStats();loadQuota();}
  if(t.dataset.tab==='logs')loadLogs();
  if(t.dataset.tab==='accounts'){loadAccounts();loadAccountsEnhanced();}
  if(t.dataset.tab==='flows'){loadFlowStats();loadFlows();}
});
'''

JS_STATUS = '''
// Status
async function checkStatus(){
  try{
    const r=await fetch('/api/status');
    const d=await r.json();
    $('#statusDot').className='status-dot '+(d.ok?'ok':'err');
    $('#statusText').textContent=d.ok?'已连接':'未连接';
    if(d.stats)$('#uptime').textContent='运行 '+formatUptime(d.stats.uptime_seconds);
  }catch(e){
    $('#statusDot').className='status-dot err';
    $('#statusText').textContent='连接失败';
  }
}
checkStatus();
setInterval(checkStatus,30000);

// URLs
$('#baseUrl').textContent=location.origin;
$$('.pyUrl').forEach(e=>e.textContent=location.origin);
'''

JS_DOCS = '''
// 文档浏览
let docsData = [];
let currentDoc = null;

// 简单的 Markdown 渲染
function renderMarkdown(text) {
  return text
    .replace(/```(\\w*)\\n([\\s\\S]*?)```/g, '<pre><code class="lang-$1">$2</code></pre>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^#### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>')
    .replace(/\\*(.+?)\\*/g, '<em>$1</em>')
    .replace(/\\[([^\\]]+)\\]\\(([^)]+)\\)/g, '<a href="$2" target="_blank">$1</a>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\\/li>\\n?)+/g, '<ul>$&</ul>')
    .replace(/^\\d+\\. (.+)$/gm, '<li>$1</li>')
    .replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
    .replace(/^---$/gm, '<hr>')
    .replace(/\\|(.+)\\|/g, function(match) {
      const cells = match.split('|').filter(c => c.trim());
      if (cells.every(c => /^[\\s-:]+$/.test(c))) return '';
      const tag = match.includes('---') ? 'th' : 'td';
      return '<tr>' + cells.map(c => '<' + tag + '>' + c.trim() + '</' + tag + '>').join('') + '</tr>';
    })
    .replace(/(<tr>.*<\\/tr>\\n?)+/g, '<table>$&</table>')
    .replace(/\\n\\n/g, '</p><p>')
    .replace(/\\n/g, '<br>');
}

async function loadDocs() {
  try {
    const r = await fetch('/api/docs');
    const d = await r.json();
    docsData = d.docs || [];
    
    // 渲染导航
    $('#docsNav').innerHTML = docsData.map((doc, i) => 
      '<a class="docs-nav-item' + (i === 0 ? ' active' : '') + '" data-id="' + doc.id + '" onclick="showDoc(\\'' + doc.id + '\\')">' + doc.title + '</a>'
    ).join('');
    
    // 显示第一个文档
    if (docsData.length > 0) {
      showDoc(docsData[0].id);
    }
  } catch (e) {
    $('#docsContent').innerHTML = '<p style="color:var(--error)">加载文档失败</p>';
  }
}

async function showDoc(id) {
  // 更新导航状态
  $$('.docs-nav-item').forEach(item => {
    item.classList.toggle('active', item.dataset.id === id);
  });
  
  // 获取文档内容
  try {
    const r = await fetch('/api/docs/' + id);
    const d = await r.json();
    currentDoc = d;
    $('#docsContent').innerHTML = renderMarkdown(d.content);
  } catch (e) {
    $('#docsContent').innerHTML = '<p style="color:var(--error)">加载文档失败</p>';
  }
}

// 页面加载时加载文档
loadDocs();
'''

JS_STATS = '''
// Stats
async function loadStats(){
  try{
    const r=await fetch('/api/stats');
    const d=await r.json();
    $('#statsGrid').innerHTML=`
      <div class="stat-item"><div class="stat-value">${d.total_requests}</div><div class="stat-label">总请求</div></div>
      <div class="stat-item"><div class="stat-value">${d.total_errors}</div><div class="stat-label">错误数</div></div>
      <div class="stat-item"><div class="stat-value">${d.error_rate}</div><div class="stat-label">错误率</div></div>
      <div class="stat-item"><div class="stat-value">${d.accounts_available}/${d.accounts_total}</div><div class="stat-label">可用账号</div></div>
      <div class="stat-item"><div class="stat-value">${d.accounts_cooldown||0}</div><div class="stat-label">冷却中</div></div>
    `;
  }catch(e){console.error(e)}
}

// Quota
async function loadQuota(){
  try{
    const r=await fetch('/api/quota');
    const d=await r.json();
    if(d.exceeded_credentials&&d.exceeded_credentials.length>0){
      $('#quotaStatus').innerHTML=d.exceeded_credentials.map(c=>`
        <div style="display:flex;justify-content:space-between;align-items:center;padding:0.5rem;background:var(--bg);border-radius:4px;margin-bottom:0.5rem">
          <span><span class="badge warn">冷却中</span> ${c.credential_id}</span>
          <span style="color:var(--muted);font-size:0.8rem">剩余 ${c.remaining_seconds}秒</span>
          <button class="secondary small" onclick="restoreAccount('${c.credential_id}')">恢复</button>
        </div>
      `).join('');
    }else{
      $('#quotaStatus').innerHTML='<p style="color:var(--muted)">无冷却中的账号</p>';
    }
  }catch(e){console.error(e)}
}

// Speedtest
async function runSpeedtest(){
  $('#speedtestBtn').disabled=true;
  $('#speedtestResult').textContent='测试中...';
  try{
    const r=await fetch('/api/speedtest',{method:'POST'});
    const d=await r.json();
    $('#speedtestResult').textContent=d.ok?`延迟: ${d.latency_ms.toFixed(0)}ms (${d.account_id})`:'测试失败: '+d.error;
  }catch(e){$('#speedtestResult').textContent='测试失败'}
  $('#speedtestBtn').disabled=false;
}
'''

JS_LOGS = '''
// Logs
async function loadLogs(){
  try{
    const r=await fetch('/api/logs?limit=50');
    const d=await r.json();
    $('#logTable').innerHTML=(d.logs||[]).map(l=>`
      <tr>
        <td>${new Date(l.timestamp*1000).toLocaleTimeString()}</td>
        <td>${l.path}</td>
        <td>${l.model||'-'}</td>
        <td>${l.account_id||'-'}</td>
        <td><span class="badge ${l.status<400?'success':l.status<500?'warn':'error'}">${l.status}</span></td>
        <td>${l.duration_ms.toFixed(0)}ms</td>
      </tr>
    `).join('');
  }catch(e){console.error(e)}
}
'''


JS_ACCOUNTS = '''
// Accounts
async function loadAccounts(){
  try{
    const r=await fetch('/api/accounts');
    const d=await r.json();
    if(!d.accounts||d.accounts.length===0){
      $('#accountList').innerHTML='<p style="color:var(--muted)">暂无账号，请点击"扫描 Token"</p>';
      return;
    }
    $('#accountList').innerHTML=d.accounts.map(a=>{
      const statusBadge=a.status==='active'?'success':a.status==='cooldown'?'warn':a.status==='suspended'?'error':'error';
      const statusText={active:'可用',cooldown:'冷却中',unhealthy:'不健康',disabled:'已禁用',suspended:'已封禁'}[a.status]||a.status;
      const authBadge=a.auth_method==='idc'?'info':'success';
      const authText=a.auth_method==='idc'?'IdC':'Social';
      return `
        <div class="account-card">
          <div class="account-header">
            <div class="account-name">
              <span class="badge ${statusBadge}">${statusText}</span>
              <span class="badge ${authBadge}">${authText}</span>
              <span>${a.name}</span>
            </div>
            <span style="color:var(--muted);font-size:0.75rem">${a.id}</span>
          </div>
          <div class="account-meta">
            <div class="account-meta-item"><span>请求数</span><span>${a.request_count}</span></div>
            <div class="account-meta-item"><span>错误数</span><span>${a.error_count}</span></div>
            <div class="account-meta-item"><span>Token</span><span class="badge ${a.token_expired?'error':a.token_expiring_soon?'warn':'success'}">${a.token_expired?'已过期':a.token_expiring_soon?'即将过期':'有效'}</span></div>
            ${a.cooldown_remaining?`<div class="account-meta-item"><span>冷却剩余</span><span>${a.cooldown_remaining}秒</span></div>`:''}
          </div>
          <div id="usage-${a.id}" class="account-usage" style="display:none;margin-top:0.75rem;padding:0.75rem;background:var(--bg);border-radius:6px"></div>
          <div class="account-actions">
            <button class="secondary small" onclick="queryUsage('${a.id}')">查询用量</button>
            <button class="secondary small" onclick="refreshToken('${a.id}')">刷新 Token</button>
            <button class="secondary small" onclick="viewAccountDetail('${a.id}')">详情</button>
            ${a.status==='cooldown'?`<button class="secondary small" onclick="restoreAccount('${a.id}')">恢复</button>`:''}
            <button class="secondary small" onclick="toggleAccount('${a.id}')">${a.enabled?'禁用':'启用'}</button>
            <button class="secondary small" onclick="deleteAccount('${a.id}')" style="color:var(--error)">删除</button>
          </div>
        </div>
      `;
    }).join('');
  }catch(e){console.error(e)}
}

async function queryUsage(id){
  const usageDiv=$('#usage-'+id);
  usageDiv.style.display='block';
  usageDiv.innerHTML='<span style="color:var(--muted)">查询中...</span>';
  try{
    const r=await fetch('/api/accounts/'+id+'/usage');
    const d=await r.json();
    if(d.ok){
      const u=d.usage;
      const pct=u.usage_limit>0?((u.current_usage/u.usage_limit)*100).toFixed(1):0;
      const barColor=u.is_low_balance?'var(--error)':'var(--success)';
      usageDiv.innerHTML=`
        <div style="display:flex;justify-content:space-between;margin-bottom:0.5rem">
          <span style="font-weight:500">${u.subscription_title}</span>
          <span class="badge ${u.is_low_balance?'error':'success'}">${u.is_low_balance?'余额不足':'正常'}</span>
        </div>
        <div style="background:var(--border);border-radius:4px;height:8px;margin-bottom:0.5rem;overflow:hidden">
          <div style="background:${barColor};height:100%;width:${pct}%;transition:width 0.3s"></div>
        </div>
        <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:0.5rem;font-size:0.8rem">
          <div><span style="color:var(--muted)">已用/总额:</span> ${u.current_usage.toFixed(2)} / ${u.usage_limit.toFixed(2)}</div>
          <div><span style="color:var(--muted)">使用率:</span> ${pct}%</div>
        </div>
      `;
    }else{
      usageDiv.innerHTML=`<span style="color:var(--error)">查询失败: ${d.error}</span>`;
    }
  }catch(e){
    usageDiv.innerHTML=`<span style="color:var(--error)">查询失败: ${e.message}</span>`;
  }
}

async function refreshToken(id){
  try{
    const r=await fetch('/api/accounts/'+id+'/refresh',{method:'POST'});
    const d=await r.json();
    alert(d.ok?'刷新成功':'刷新失败: '+d.message);
    loadAccounts();
  }catch(e){alert('刷新失败: '+e.message)}
}

async function refreshAllTokens(){
  try{
    const r=await fetch('/api/accounts/refresh-all',{method:'POST'});
    const d=await r.json();
    alert(`刷新完成: ${d.refreshed} 个账号`);
    loadAccounts();
  }catch(e){alert('刷新失败: '+e.message)}
}

async function restoreAccount(id){
  try{
    await fetch('/api/accounts/'+id+'/restore',{method:'POST'});
    loadAccounts();
    loadQuota();
  }catch(e){alert('恢复失败: '+e.message)}
}

async function viewAccountDetail(id){
  try{
    const r=await fetch('/api/accounts/'+id);
    const d=await r.json();
    alert(`账号: ${d.name}\\nID: ${d.id}\\n状态: ${d.status}\\n请求数: ${d.request_count}\\n错误数: ${d.error_count}`);
  }catch(e){alert('获取详情失败: '+e.message)}
}

async function toggleAccount(id){
  await fetch('/api/accounts/'+id+'/toggle',{method:'POST'});
  loadAccounts();
}

async function deleteAccount(id){
  if(confirm('确定删除此账号?')){
    await fetch('/api/accounts/'+id,{method:'DELETE'});
    loadAccounts();
  }
}

function showAddAccount(){
  const path=prompt('输入 Token 文件路径:');
  if(path){
    const name=prompt('账号名称:','账号');
    fetch('/api/accounts',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name,token_path:path})
    }).then(r=>r.json()).then(d=>{
      if(d.ok)loadAccounts();
      else alert(d.detail||'添加失败');
    });
  }
}

async function scanTokens(){
  try{
    const r=await fetch('/api/token/scan');
    const d=await r.json();
    const panel=$('#scanResults');
    const list=$('#scanList');
    if(d.tokens&&d.tokens.length>0){
      panel.style.display='block';
      list.innerHTML=d.tokens.map(t=>{
        const path=encodeURIComponent(t.path||'');
        const name=encodeURIComponent(t.name||'');
        return `
        <div style="display:flex;justify-content:space-between;align-items:center;padding:0.75rem;border:1px solid var(--border);border-radius:6px;margin-bottom:0.5rem">
          <div>
            <div>${t.name}</div>
            <div style="color:var(--muted);font-size:0.75rem">${t.path}</div>
          </div>
          ${t.already_added?'<span class="badge info">已添加</span>':`<button class="secondary small" data-path="${path}" data-name="${name}" onclick="addFromScan(decodeURIComponent(this.dataset.path),decodeURIComponent(this.dataset.name))">添加</button>`}
        </div>
        `;
      }).join('');
    }else{
      alert('未找到 Token 文件');
    }
  }catch(e){alert('扫描失败: '+e.message)}
}

async function addFromScan(path,name){
  try{
    const r=await fetch('/api/token/add-from-scan',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({path,name})
    });
    const d=await r.json();
    if(d.ok){
      loadAccounts();
      scanTokens();
    }else{
      alert(d.detail||'添加失败');
    }
  }catch(e){alert('添加失败: '+e.message)}
}

async function checkTokens(){
  try{
    const r=await fetch('/api/token/refresh-check',{method:'POST'});
    const d=await r.json();
    let msg='Token 状态:\\n\\n';
    (d.accounts||[]).forEach(a=>{
      const status=a.valid?'✅ 有效':'❌ 无效';
      msg+=`${a.name}: ${status}\\n`;
    });
    alert(msg);
  }catch(e){alert('检查失败: '+e.message)}
}

// 远程登录链接
let remoteLoginPollTimer=null;

async function createRemoteLogin(){
  try{
    const r=await fetch('/api/remote-login/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})});
    const d=await r.json();
    if(!d.ok){alert('创建失败: '+d.error);return;}
    $('#remoteLoginPanel').style.display='block';
    $('#remoteLoginContent').innerHTML=`
      <div style="text-align:center;padding:1rem">
        <p style="margin-bottom:1rem">将此链接发送到有浏览器的机器上完成登录：</p>
        <div style="background:var(--bg);padding:1rem;border-radius:8px;margin-bottom:1rem;word-break:break-all;font-family:monospace;font-size:0.875rem">${d.login_url}</div>
        <button onclick="copy('${d.login_url}')">复制链接</button>
        <p style="color:var(--muted);font-size:0.75rem;margin-top:1rem">链接有效期 10 分钟</p>
        <p style="color:var(--muted);font-size:0.875rem;margin-top:0.5rem" id="remoteLoginStatus">等待登录...</p>
      </div>
    `;
    startRemoteLoginPoll(d.session_id);
  }catch(e){alert('创建失败: '+e.message)}
}

function startRemoteLoginPoll(sessionId){
  if(remoteLoginPollTimer)clearInterval(remoteLoginPollTimer);
  remoteLoginPollTimer=setInterval(async()=>{
    try{
      const r=await fetch('/api/remote-login/'+sessionId+'/status');
      const d=await r.json();
      if(d.status==='completed'){
        $('#remoteLoginStatus').textContent='✅ 登录成功！';
        $('#remoteLoginStatus').style.color='var(--success)';
        clearInterval(remoteLoginPollTimer);
        setTimeout(()=>{$('#remoteLoginPanel').style.display='none';loadAccounts();},1500);
      }else if(d.status==='failed'){
        $('#remoteLoginStatus').textContent='❌ 登录失败';
        $('#remoteLoginStatus').style.color='var(--error)';
        clearInterval(remoteLoginPollTimer);
      }
    }catch(e){}
  },3000);
}

// 手动添加 Token
function showManualAdd(){
  $('#manualAddPanel').style.display='block';
  $('#manualName').value='';
  $('#manualAccessToken').value='';
  $('#manualRefreshToken').value='';
}

async function submitManualToken(){
  const name=$('#manualName').value||'手动添加账号';
  const accessToken=$('#manualAccessToken').value.trim();
  const refreshToken=$('#manualRefreshToken').value.trim();
  
  // 表单验证
  const nameValidation = validateAccountName(name);
  if (!nameValidation.valid) {
    Toast.error(nameValidation.error);
    return;
  }
  
  const tokenValidation = validateToken(accessToken);
  if (!tokenValidation.valid) {
    Toast.error(tokenValidation.error);
    return;
  }
  
  try{
    const r=await fetchWithRetry('/api/accounts/manual',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name: nameValidation.default || name, access_token:accessToken,refresh_token:refreshToken})
    });
    const d=await r.json();
    if(d.ok){
      Toast.success('添加成功');
      $('#manualAddPanel').style.display='none';
      loadAccounts();
      loadAccountsEnhanced();
    }else{
      Toast.error(d.detail||'添加失败');
    }
  }catch(e){Toast.error('添加失败: '+e.message)}
}

// 导出账号
async function exportAccounts(){
  try{
    const r=await fetch('/api/accounts/export');
    const d=await r.json();
    if(!d.ok){alert('导出失败');return;}
    const blob=new Blob([JSON.stringify(d,null,2)],{type:'application/json'});
    const url=URL.createObjectURL(blob);
    const a=document.createElement('a');
    a.href=url;
    a.download='kiro-accounts-'+new Date().toISOString().slice(0,10)+'.json';
    a.click();
  }catch(e){alert('导出失败: '+e.message)}
}

// 导入账号
function importAccounts(){
  const input=document.createElement('input');
  input.type='file';
  input.accept='.json';
  input.onchange=async(e)=>{
    const file=e.target.files[0];
    if(!file)return;
    try{
      const text=await file.text();
      const data=JSON.parse(text);
      const r=await fetch('/api/accounts/import',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify(data)
      });
      const d=await r.json();
      if(d.ok){
        alert(`导入成功: ${d.imported} 个账号`+(d.errors?.length?`\\n错误: ${d.errors.join(', ')}`:''));
        loadAccounts();
      }else{
        alert('导入失败');
      }
    }catch(e){alert('导入失败: '+e.message)}
  };
  input.click();
}
'''

JS_LOGIN = '''
// Kiro 在线登录
let loginPollTimer=null;
let selectedBrowser='default';

async function showLoginOptions(){
  try{
    const r=await fetch('/api/browsers');
    const d=await r.json();
    const browsers=d.browsers||[];
    if(browsers.length>0){
      $('#browserList').innerHTML=browsers.map(b=>`
        <button class="${b.id==='default'?'':'secondary'} small" onclick="selectBrowser('${b.id}',this)" data-browser="${b.id}">${b.name}</button>
      `).join('');
    }
    selectedBrowser='default';
    $('#loginOptions').style.display='block';
  }catch(e){
    $('#loginOptions').style.display='block';
  }
}

function selectBrowser(id,btn){
  selectedBrowser=id;
  $$('#browserList button').forEach(b=>b.classList.add('secondary'));
  btn.classList.remove('secondary');
}

async function startSocialLogin(provider){
  const incognito=$('#incognitoMode')?.checked||false;
  $('#loginOptions').style.display='none';
  try{
    const r=await fetch('/api/kiro/social/start',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({provider,browser:selectedBrowser,incognito})
    });
    const d=await r.json();
    if(!d.ok){alert('启动登录失败: '+d.error);return;}
    showSocialLoginPanel(d.provider);
  }catch(e){alert('启动登录失败: '+e.message)}
}

function showSocialLoginPanel(provider){
  $('#loginPanel').style.display='block';
  $('#loginContent').innerHTML=`
    <div style="text-align:center;padding:1rem">
      <p style="margin-bottom:1rem">正在使用 ${provider} 登录...</p>
      <p style="color:var(--muted);font-size:0.875rem">请在浏览器中完成授权</p>
      <p style="color:var(--muted);font-size:0.875rem;margin-top:1rem">授权完成后，请将浏览器地址栏中的完整 URL 粘贴到下方：</p>
      <input type="text" id="callbackUrl" placeholder="粘贴回调 URL..." style="width:100%;margin-top:0.5rem">
      <button onclick="handleSocialCallback()" style="margin-top:0.5rem">提交</button>
      <p style="color:var(--muted);font-size:0.75rem;margin-top:0.5rem" id="loginStatus"></p>
    </div>
  `;
}

async function handleSocialCallback(){
  const url=$('#callbackUrl').value;
  if(!url){alert('请粘贴回调 URL');return;}
  try{
    const urlObj=new URL(url);
    const code=urlObj.searchParams.get('code');
    const state=urlObj.searchParams.get('state');
    if(!code||!state){alert('无效的回调 URL');return;}
    $('#loginStatus').textContent='正在交换 Token...';
    const r=await fetch('/api/kiro/social/exchange',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({code,state})
    });
    const d=await r.json();
    if(d.ok&&d.completed){
      $('#loginStatus').textContent='✅ '+d.message;
      $('#loginStatus').style.color='var(--success)';
      setTimeout(()=>{$('#loginPanel').style.display='none';loadAccounts();},1500);
    }else{
      $('#loginStatus').textContent='❌ '+(d.error||'登录失败');
      $('#loginStatus').style.color='var(--error)';
    }
  }catch(e){alert('处理回调失败: '+e.message)}
}

async function startAwsLogin(){
  $('#loginOptions').style.display='none';
  startKiroLogin(selectedBrowser);
}

async function startKiroLogin(browser='default'){
  const incognito=$('#incognitoMode')?.checked||false;
  try{
    const r=await fetch('/api/kiro/login/start',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({browser,incognito})
    });
    const d=await r.json();
    if(!d.ok){alert('启动登录失败: '+d.error);return;}
    showLoginPanel(d);
    startLoginPoll();
  }catch(e){alert('启动登录失败: '+e.message)}
}

function showLoginPanel(data){
  $('#loginPanel').style.display='block';
  $('#loginContent').innerHTML=`
    <div style="text-align:center;padding:1rem">
      <p style="margin-bottom:1rem">请在浏览器中完成 AWS Builder ID 授权：</p>
      <div style="font-size:2rem;font-weight:bold;letter-spacing:0.5rem;padding:1rem;background:var(--bg);border-radius:8px;margin-bottom:1rem">${data.user_code}</div>
      <p style="margin-bottom:1rem">
        <a href="${data.verification_uri}" target="_blank" style="color:var(--info);text-decoration:underline">点击打开授权页面</a>
        <button class="secondary small" style="margin-left:0.5rem" onclick="copy('${data.verification_uri}')">复制链接</button>
      </p>
      <p style="color:var(--muted);font-size:0.875rem">授权码有效期: ${Math.floor(data.expires_in/60)} 分钟</p>
      <p style="color:var(--muted);font-size:0.875rem;margin-top:0.5rem" id="loginStatus">等待授权...</p>
    </div>
  `;
}

function startLoginPoll(){
  if(loginPollTimer)clearInterval(loginPollTimer);
  loginPollTimer=setInterval(pollLogin,3000);
}

async function pollLogin(){
  try{
    const r=await fetch('/api/kiro/login/poll');
    const d=await r.json();
    if(!d.ok){$('#loginStatus').textContent='错误: '+d.error;stopLoginPoll();return;}
    if(d.completed){
      $('#loginStatus').textContent='✅ 登录成功！';
      $('#loginStatus').style.color='var(--success)';
      stopLoginPoll();
      setTimeout(()=>{$('#loginPanel').style.display='none';loadAccounts();},1500);
    }
  }catch(e){$('#loginStatus').textContent='轮询失败: '+e.message}
}

function stopLoginPoll(){
  if(loginPollTimer){clearInterval(loginPollTimer);loginPollTimer=null;}
}

async function cancelKiroLogin(){
  stopLoginPoll();
  await fetch('/api/kiro/login/cancel',{method:'POST'});
  $('#loginPanel').style.display='none';
}
'''


JS_FLOWS = '''
// Flow Monitor
async function loadFlowStats(){
  try{
    const r=await fetch('/api/flows/stats');
    const d=await r.json();
    $('#flowStatsGrid').innerHTML=`
      <div class="stat-item"><div class="stat-value">${d.total_flows}</div><div class="stat-label">总请求</div></div>
      <div class="stat-item"><div class="stat-value">${d.completed}</div><div class="stat-label">完成</div></div>
      <div class="stat-item"><div class="stat-value">${d.errors}</div><div class="stat-label">错误</div></div>
      <div class="stat-item"><div class="stat-value">${d.error_rate}</div><div class="stat-label">错误率</div></div>
      <div class="stat-item"><div class="stat-value">${d.avg_duration_ms.toFixed(0)}ms</div><div class="stat-label">平均延迟</div></div>
      <div class="stat-item"><div class="stat-value">${d.total_tokens_in}</div><div class="stat-label">输入Token</div></div>
      <div class="stat-item"><div class="stat-value">${d.total_tokens_out}</div><div class="stat-label">输出Token</div></div>
    `;
  }catch(e){console.error(e)}
}

async function loadFlows(){
  try{
    const protocol=$('#flowProtocol').value;
    const state=$('#flowState').value;
    const search=$('#flowSearch').value;
    let url='/api/flows?limit=50';
    if(protocol)url+=`&protocol=${protocol}`;
    if(state)url+=`&state=${state}`;
    if(search)url+=`&search=${encodeURIComponent(search)}`;
    const r=await fetch(url);
    const d=await r.json();
    if(!d.flows||d.flows.length===0){
      $('#flowList').innerHTML='<p style="color:var(--muted)">暂无请求记录</p>';
      return;
    }
    $('#flowList').innerHTML=d.flows.map(f=>{
      const stateBadge={completed:'success',error:'error',streaming:'info',pending:'warn'}[f.state]||'info';
      const stateText={completed:'完成',error:'错误',streaming:'流式中',pending:'等待中'}[f.state]||f.state;
      const time=new Date(f.timing.created_at*1000).toLocaleTimeString();
      const duration=f.timing.duration_ms?f.timing.duration_ms.toFixed(0)+'ms':'-';
      const model=f.request?.model||'-';
      const tokens=f.response?.usage?(f.response.usage.input_tokens+'/'+f.response.usage.output_tokens):'-';
      return `
        <div style="display:flex;justify-content:space-between;align-items:center;padding:0.75rem;border:1px solid var(--border);border-radius:6px;margin-bottom:0.5rem;cursor:pointer" onclick="viewFlow('${f.id}')">
          <div style="flex:1">
            <div style="display:flex;align-items:center;gap:0.5rem">
              <span class="badge ${stateBadge}">${stateText}</span>
              <span style="font-weight:500">${model}</span>
              ${f.bookmarked?'<span style="color:var(--warn)">★</span>':''}
            </div>
            <div style="color:var(--muted);font-size:0.75rem;margin-top:0.25rem">
              ${time} · ${duration} · ${tokens} tokens · ${f.protocol}
            </div>
          </div>
          <button class="secondary small" onclick="event.stopPropagation();toggleBookmark('${f.id}',${!f.bookmarked})">${f.bookmarked?'取消':'收藏'}</button>
        </div>
      `;
    }).join('');
  }catch(e){console.error(e)}
}

async function viewFlow(id){
  try{
    const r=await fetch('/api/flows/'+id);
    const f=await r.json();
    let html=`<div style="margin-bottom:1rem"><strong>ID:</strong> ${f.id}<br><strong>协议:</strong> ${f.protocol}<br><strong>状态:</strong> ${f.state}<br><strong>时间:</strong> ${new Date(f.timing.created_at*1000).toLocaleString()}<br><strong>延迟:</strong> ${f.timing.duration_ms?f.timing.duration_ms.toFixed(0)+'ms':'N/A'}</div>`;
    if(f.request){
      html+=`<h4 style="margin-bottom:0.5rem">请求</h4><div style="margin-bottom:1rem"><strong>模型:</strong> ${f.request.model}<br><strong>流式:</strong> ${f.request.stream?'是':'否'}</div>`;
    }
    if(f.response){
      html+=`<h4 style="margin-top:1rem;margin-bottom:0.5rem">响应</h4><div><strong>状态码:</strong> ${f.response.status_code}<br><strong>Token:</strong> ${f.response.usage?.input_tokens||0} in / ${f.response.usage?.output_tokens||0} out</div>`;
    }
    if(f.error){
      html+=`<h4 style="margin-top:1rem;margin-bottom:0.5rem;color:var(--error)">错误</h4><div><strong>类型:</strong> ${f.error.type}<br><strong>消息:</strong> ${f.error.message}</div>`;
    }
    $('#flowDetailContent').innerHTML=html;
    $('#flowDetail').style.display='block';
  }catch(e){alert('获取详情失败: '+e.message)}
}

async function toggleBookmark(id,bookmarked){
  await fetch('/api/flows/'+id+'/bookmark',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({bookmarked})});
  loadFlows();
}

async function exportFlows(){
  try{
    const r=await fetch('/api/flows/export',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({format:'json'})});
    const d=await r.json();
    const blob=new Blob([d.content],{type:'application/json'});
    const url=URL.createObjectURL(blob);
    const a=document.createElement('a');
    a.href=url;
    a.download='flows_'+new Date().toISOString().slice(0,10)+'.json';
    a.click();
  }catch(e){alert('导出失败: '+e.message)}
}
'''

JS_SETTINGS = '''
// 设置页面
// 历史消息管理（简化版，自动管理）

async function loadHistoryConfig(){
  try{
    const r=await fetch('/api/settings/history');
    const d=await r.json();
    $('#maxRetries').value=d.max_retries||3;
    $('#summaryCacheMaxAge').value=d.summary_cache_max_age_seconds||300;
    $('#addWarningHeader').checked=d.add_warning_header!==false;
  }catch(e){console.error('加载配置失败:',e)}
}

async function updateHistoryConfig(){
  const config={
    strategies:['error_retry'],  // 固定使用错误重试策略
    max_retries:parseInt($('#maxRetries').value)||3,
    summary_cache_enabled:true,
    summary_cache_max_age_seconds:parseInt($('#summaryCacheMaxAge').value)||300,
    add_warning_header:$('#addWarningHeader').checked
  };
  try{
    await fetch('/api/settings/history',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(config)});
  }catch(e){console.error('保存配置失败:',e)}
}

// 刷新配置
async function loadRefreshConfig(){
  try{
    const r=await fetch('/api/refresh/config');
    const d=await r.json();
    if(d.ok && d.config){
      const c=d.config;
      $('#refreshMaxRetries').value=c.max_retries||3;
      $('#refreshConcurrency').value=c.concurrency||3;
      $('#refreshAutoInterval').value=c.auto_refresh_interval||60;
      $('#refreshRetryDelay').value=c.retry_base_delay||1.0;
      $('#refreshBeforeExpiry').value=c.token_refresh_before_expiry||300;
      // 更新状态显示
      $('#refreshConfigStatus').innerHTML=`
        <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:0.5rem">
          <span>最大重试: <strong>${c.max_retries||3}</strong> 次</span>
          <span>并发数: <strong>${c.concurrency||3}</strong></span>
          <span>自动刷新间隔: <strong>${c.auto_refresh_interval||60}</strong> 秒</span>
          <span>提前刷新: <strong>${c.token_refresh_before_expiry||300}</strong> 秒</span>
        </div>
      `;
    }
  }catch(e){console.error('加载刷新配置失败:',e)}
}

async function saveRefreshConfig(){
  const config={
    max_retries:parseInt($('#refreshMaxRetries').value)||3,
    concurrency:parseInt($('#refreshConcurrency').value)||3,
    auto_refresh_interval:parseInt($('#refreshAutoInterval').value)||60,
    retry_base_delay:parseFloat($('#refreshRetryDelay').value)||1.0,
    token_refresh_before_expiry:parseInt($('#refreshBeforeExpiry').value)||300
  };
  try{
    const r=await fetch('/api/refresh/config',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(config)});
    const d=await r.json();
    if(d.ok){
      Toast.success('刷新配置保存成功');
      loadRefreshConfig();
    }else{
      Toast.error(d.error||'保存失败');
    }
  }catch(e){
    console.error('保存刷新配置失败:',e);
    Toast.error('保存刷新配置失败');
  }
}

// 限速配置
async function loadRateLimitConfig(){
  try{
    const r=await fetch('/api/settings/rate-limit');
    const d=await r.json();
    $('#rateLimitEnabled').checked=d.enabled;
    $('#minRequestInterval').value=d.min_request_interval||0.5;
    $('#maxRequestsPerMinute').value=d.max_requests_per_minute||60;
    $('#globalMaxRequestsPerMinute').value=d.global_max_requests_per_minute||120;
    $('#quotaCooldownSeconds').value=d.quota_cooldown_seconds||30;
    // 更新统计
    const stats=d.stats||{};
    $('#rateLimitStats').innerHTML=`
      <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:0.5rem">
        <span>状态: <span class="badge ${d.enabled?'success':'warn'}">${d.enabled?'已启用':'已禁用'}</span></span>
        <span>全局 RPM: ${stats.global_rpm||0}</span>
        <span>429 冷却: ${d.enabled?(d.quota_cooldown_seconds||30)+'秒':'禁用'}</span>
      </div>
    `;
  }catch(e){console.error('加载限速配置失败:',e)}
}

async function updateRateLimitConfig(){
  const config={
    enabled:$('#rateLimitEnabled').checked,
    min_request_interval:parseFloat($('#minRequestInterval').value)||0.5,
    max_requests_per_minute:parseInt($('#maxRequestsPerMinute').value)||60,
    global_max_requests_per_minute:parseInt($('#globalMaxRequestsPerMinute').value)||120,
    quota_cooldown_seconds:parseInt($('#quotaCooldownSeconds').value)||30
  };
  try{
    await fetch('/api/settings/rate-limit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(config)});
    loadRateLimitConfig();
  }catch(e){console.error('保存限速配置失败:',e)}
}

// 还原默认配置函数
async function resetRefreshConfig(){
  if(!confirm('确定要还原刷新配置为默认值吗？')) return;
  const defaultConfig={
    max_retries:3,
    concurrency:3,
    auto_refresh_interval:60,
    retry_base_delay:1.0,
    token_refresh_before_expiry:300
  };
  try{
    const r=await fetch('/api/refresh/config',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(defaultConfig)});
    const d=await r.json();
    if(d.ok){
      Toast.success('已还原为默认配置');
      loadRefreshConfig();
    }else{
      Toast.error(d.error||'还原失败');
    }
  }catch(e){
    Toast.error('还原配置失败');
  }
}

async function resetRateLimitConfig(){
  if(!confirm('确定要还原限速配置为默认值吗？')) return;
  const defaultConfig={
    enabled:false,
    min_request_interval:0.5,
    max_requests_per_minute:60,
    global_max_requests_per_minute:120,
    quota_cooldown_seconds:30
  };
  try{
    await fetch('/api/settings/rate-limit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(defaultConfig)});
    Toast.success('已还原为默认配置');
    loadRateLimitConfig();
  }catch(e){
    Toast.error('还原配置失败');
  }
}

async function resetHistoryConfig(){
  if(!confirm('确定要还原历史消息配置为默认值吗？')) return;
  const defaultConfig={
    strategies:['error_retry'],
    max_retries:3,
    summary_cache_enabled:true,
    summary_cache_max_age_seconds:300,
    add_warning_header:true
  };
  try{
    await fetch('/api/settings/history',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(defaultConfig)});
    Toast.success('已还原为默认配置');
    loadHistoryConfig();
  }catch(e){
    Toast.error('还原配置失败');
  }
}

// 页面加载时加载设置
loadHistoryConfig();
loadRateLimitConfig();
loadRefreshConfig();
'''

# ==================== UI 组件库 JavaScript ====================
JS_UI_COMPONENTS = '''
// ==================== Modal 模态框组件 ====================
class Modal {
  constructor(options = {}) {
    this.title = options.title || '';
    this.content = options.content || '';
    this.type = options.type || 'default';
    this.confirmText = options.confirmText || '确认';
    this.cancelText = options.cancelText || '取消';
    this.onConfirm = options.onConfirm;
    this.onCancel = options.onCancel;
    this.showCancel = options.showCancel !== false;
    this.element = null;
  }
  
  show() {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
      <div class="modal ${this.type}">
        <div class="modal-header">
          <h3>${this.title}</h3>
          <button class="modal-close" onclick="this.closest('.modal-overlay').modal.hide()">&times;</button>
        </div>
        <div class="modal-body">${this.content}</div>
        <div class="modal-footer">
          ${this.showCancel ? `<button class="secondary" onclick="this.closest('.modal-overlay').modal.cancel()">${this.cancelText}</button>` : ''}
          <button onclick="this.closest('.modal-overlay').modal.confirm()">${this.confirmText}</button>
        </div>
      </div>
    `;
    overlay.modal = this;
    this.element = overlay;
    document.body.appendChild(overlay);
    
    // 键盘事件
    this.keyHandler = (e) => {
      if (e.key === 'Escape') this.hide();
      if (e.key === 'Enter' && !e.target.matches('textarea')) this.confirm();
    };
    document.addEventListener('keydown', this.keyHandler);
    
    // 点击遮罩关闭
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) this.hide();
    });
    
    requestAnimationFrame(() => overlay.classList.add('active'));
    return this;
  }
  
  hide() {
    if (this.element) {
      this.element.classList.remove('active');
      document.removeEventListener('keydown', this.keyHandler);
      setTimeout(() => this.element.remove(), 200);
    }
  }
  
  confirm() {
    if (this.onConfirm) this.onConfirm();
    this.hide();
  }
  
  cancel() {
    if (this.onCancel) this.onCancel();
    this.hide();
  }
  
  setLoading(loading) {
    const btn = this.element?.querySelector('.modal-footer button:last-child');
    if (btn) {
      btn.disabled = loading;
      btn.textContent = loading ? '处理中...' : this.confirmText;
    }
  }
  
  static confirm(title, message, onConfirm) {
    return new Modal({ title, content: `<p>${message}</p>`, onConfirm }).show();
  }
  
  static alert(title, message) {
    return new Modal({ title, content: `<p>${message}</p>`, showCancel: false }).show();
  }
  
  static danger(title, message, onConfirm) {
    return new Modal({ title, content: `<p>${message}</p>`, type: 'danger', onConfirm, confirmText: '删除' }).show();
  }
}

// ==================== Toast 通知组件 ====================
class Toast {
  static container = null;
  
  static getContainer() {
    if (!this.container) {
      this.container = document.createElement('div');
      this.container.className = 'toast-container';
      document.body.appendChild(this.container);
    }
    return this.container;
  }
  
  static show(message, type = 'info', duration = 3000) {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
      <span>${message}</span>
      <button class="toast-close" onclick="this.parentElement.remove()">&times;</button>
    `;
    this.getContainer().appendChild(toast);
    
    if (duration > 0) {
      setTimeout(() => toast.remove(), duration);
    }
    return toast;
  }
  
  static success(message, duration) { return this.show(message, 'success', duration); }
  static error(message, duration) { return this.show(message, 'error', duration); }
  static warning(message, duration) { return this.show(message, 'warning', duration); }
  static info(message, duration) { return this.show(message, 'info', duration); }
}

// ==================== Dropdown 下拉菜单组件 ====================
class Dropdown {
  constructor(trigger, items) {
    this.trigger = trigger;
    this.items = items;
    this.element = null;
    this.init();
  }
  
  init() {
    const wrapper = document.createElement('div');
    wrapper.className = 'dropdown';
    
    this.trigger.parentNode.insertBefore(wrapper, this.trigger);
    wrapper.appendChild(this.trigger);
    
    const menu = document.createElement('div');
    menu.className = 'dropdown-menu';
    menu.innerHTML = this.items.map(item => {
      if (item.divider) return '<div class="dropdown-divider"></div>';
      return `<div class="dropdown-item ${item.danger ? 'danger' : ''}" data-action="${item.action || ''}">${item.icon || ''}${item.label}</div>`;
    }).join('');
    wrapper.appendChild(menu);
    
    this.element = wrapper;
    
    this.trigger.addEventListener('click', (e) => {
      e.stopPropagation();
      this.toggle();
    });
    
    menu.addEventListener('click', (e) => {
      const item = e.target.closest('.dropdown-item');
      if (item) {
        const action = item.dataset.action;
        const itemConfig = this.items.find(i => i.action === action);
        if (itemConfig?.onClick) itemConfig.onClick();
        this.close();
      }
    });
    
    document.addEventListener('click', () => this.close());
  }
  
  toggle() {
    this.element.classList.toggle('open');
  }
  
  close() {
    this.element.classList.remove('open');
  }
}

// ==================== 进度条渲染函数 ====================
function renderProgressBar(value, max, options = {}) {
  const percent = max > 0 ? (value / max * 100) : 0;
  const color = options.color || (percent > 80 ? 'error' : percent > 60 ? 'warning' : 'success');
  const size = options.size || '';
  const showLabel = options.showLabel !== false;
  
  return `
    <div class="progress-bar ${size}">
      <div class="progress-fill ${color}" style="width:${percent}%"></div>
    </div>
    ${showLabel ? `<div class="progress-label"><span>${options.leftLabel || ''}</span><span>${options.rightLabel || Math.round(percent) + '%'}</span></div>` : ''}
  `;
}

// ==================== 账号卡片渲染函数 ====================
function renderAccountCard(account) {
  const quota = account.quota;
  const isPriority = account.is_priority;
  const isActive = account.is_active;
  
  let statusBadge = '';
  if (!account.enabled) statusBadge = '<span class="badge">禁用</span>';
  else if (account.cooldown_remaining > 0) statusBadge = `<span class="badge warn">冷却 ${account.cooldown_remaining}s</span>`;
  else if (account.available) statusBadge = '<span class="badge success">正常</span>';
  else statusBadge = '<span class="badge error">不可用</span>';
  
  let quotaSection = '';
  if (quota && !quota.error) {
    const usedPercent = quota.usage_limit > 0 ? (quota.current_usage / quota.usage_limit * 100) : 0;
    quotaSection = `
      <div class="account-quota-section">
        <div class="quota-header">
          <span>已用/总额</span>
          <span>${quota.current_usage.toFixed(1)} / ${quota.usage_limit.toFixed(1)}</span>
        </div>
        ${renderProgressBar(quota.current_usage, quota.usage_limit, {
          color: quota.is_low_balance ? 'error' : usedPercent > 60 ? 'warning' : 'success',
          rightLabel: usedPercent.toFixed(1) + '%'
        })}
        <div class="quota-detail">
          ${quota.free_trial_limit > 0 ? `<span>试用: ${quota.free_trial_usage.toFixed(0)}/${quota.free_trial_limit.toFixed(0)}</span>` : ''}
          ${quota.bonus_limit > 0 ? `<span>奖励: ${quota.bonus_usage.toFixed(0)}/${quota.bonus_limit.toFixed(0)}</span>` : ''}
          <span>更新: ${quota.updated_at || '未知'}</span>
        </div>
      </div>
    `;
  } else if (quota?.error) {
    quotaSection = `<div class="account-quota-section"><span class="badge error">额度获取失败: ${quota.error}</span></div>`;
  }
  
  return `
    <div class="account-card-enhanced ${isPriority ? 'priority' : ''} ${isActive ? 'active' : ''}" data-id="${account.id}">
      <div class="account-card-header">
        <div class="account-card-title">
          <strong>${account.name}</strong>
          <div class="account-card-badges">
            ${statusBadge}
            ${isPriority ? `<span class="badge info">优先 #${account.priority_order}</span>` : ''}
            ${isActive ? '<span class="badge success">活跃</span>' : ''}
            ${quota?.is_low_balance ? '<span class="badge warn">低额度</span>' : ''}
          </div>
        </div>
        <button class="secondary small" onclick="showAccountMenu('${account.id}', this)">操作 ▼</button>
      </div>
      ${quotaSection}
      <div class="account-stats-grid">
        <div class="account-stat"><div class="account-stat-value">${account.request_count}</div><div class="account-stat-label">请求数</div></div>
        <div class="account-stat"><div class="account-stat-value">${account.error_rate || '0%'}</div><div class="account-stat-label">错误率</div></div>
        <div class="account-stat"><div class="account-stat-value">${account.last_used_ago || '-'}</div><div class="account-stat-label">最后使用</div></div>
        <div class="account-stat"><div class="account-stat-value">${account.auth_method || '-'}</div><div class="account-stat-label">认证方式</div></div>
      </div>
    </div>
  `;
}

// ==================== 汇总面板渲染函数 ====================
function renderSummaryPanel(summary) {
  return `
    <div class="summary-panel">
      <div class="summary-grid">
        <div class="summary-item"><div class="summary-value">${summary.total_accounts}</div><div class="summary-label">总账号</div></div>
        <div class="summary-item success"><div class="summary-value">${summary.available_accounts}</div><div class="summary-label">可用</div></div>
        <div class="summary-item warning"><div class="summary-value">${summary.cooldown_accounts}</div><div class="summary-label">冷却中</div></div>
        <div class="summary-item error"><div class="summary-value">${summary.unhealthy_accounts + summary.disabled_accounts}</div><div class="summary-label">不可用</div></div>
      </div>
      <div class="summary-quota">
        <div class="quota-header">
          <span>总剩余额度</span>
          <span style="font-weight:600">${summary.total_balance.toFixed(1)}</span>
        </div>
        ${renderProgressBar(summary.total_usage, summary.total_limit, {
          size: 'large',
          leftLabel: `已用 ${summary.total_usage.toFixed(0)}`,
          rightLabel: `总计 ${summary.total_limit.toFixed(0)}`
        })}
      </div>
      <div class="summary-info">
        <span>选择策略: ${summary.strategy === 'lowest_balance' ? '剩余额度最少优先' : summary.strategy}</span>
        <span>优先账号: ${summary.priority_accounts.length > 0 ? summary.priority_accounts.join(', ') : '无'}</span>
        <span>最后刷新: ${summary.last_refresh || '未刷新'}</span>
      </div>
      <div class="summary-actions">
        <button onclick="refreshAllQuotas()">刷新全部额度</button>
        <button class="secondary" onclick="loadAccountsEnhanced()">刷新列表</button>
      </div>
    </div>
  `;
}

// ==================== 账号操作菜单 ====================
let currentAccountMenu = null;

function showAccountMenu(accountId, btn) {
  if (currentAccountMenu) {
    currentAccountMenu.remove();
    currentAccountMenu = null;
  }
  
  const menu = document.createElement('div');
  menu.className = 'dropdown-menu';
  menu.style.cssText = 'display:block;position:absolute;z-index:100;';
  menu.innerHTML = `
    <div class="dropdown-item" onclick="refreshAccountQuota('${accountId}')">🔄 刷新额度</div>
    <div class="dropdown-item" onclick="togglePriority('${accountId}')">⭐ 设为优先</div>
    <div class="dropdown-item" onclick="toggleAccount('${accountId}')">🔒 启用/禁用</div>
    <div class="dropdown-divider"></div>
    <div class="dropdown-item danger" onclick="confirmDeleteAccount('${accountId}')">🗑️ 删除账号</div>
  `;
  
  const rect = btn.getBoundingClientRect();
  menu.style.top = (rect.bottom + window.scrollY) + 'px';
  menu.style.left = (rect.left + window.scrollX - 100) + 'px';
  
  document.body.appendChild(menu);
  currentAccountMenu = menu;
  
  setTimeout(() => {
    document.addEventListener('click', function closeMenu() {
      if (currentAccountMenu) {
        currentAccountMenu.remove();
        currentAccountMenu = null;
      }
      document.removeEventListener('click', closeMenu);
    }, { once: true });
  }, 0);
}

// ==================== 额度管理 API 调用 ====================
async function loadAccountsEnhanced() {
  showLoading('#accountsGrid', '加载账号列表...');
  try {
    const r = await fetchWithRetry('/api/accounts/status');
    const d = await r.json();
    if (d.ok) {
      $('#accountsSummaryCompact').innerHTML = renderSummaryCompact(d.summary);
      $('#accountsGrid').innerHTML = d.accounts.map(renderAccountCardCompact).join('');
    } else {
      $('#accountsGrid').innerHTML = `<p style="color:var(--error);text-align:center;padding:2rem">加载失败: ${d.error || '未知错误'}</p>`;
    }
  } catch(e) {
    $('#accountsGrid').innerHTML = `<p style="color:var(--error);text-align:center;padding:2rem">网络错误，<a href="#" onclick="loadAccountsEnhanced();return false">点击重试</a></p>`;
    Toast.error('加载账号列表失败');
  }
}

// ==================== 紧凑汇总面板 ====================
function renderSummaryCompact(summary) {
  const usedPercent = summary.total_limit > 0 ? (summary.total_usage / summary.total_limit * 100) : 0;
  const barColor = usedPercent > 80 ? 'var(--error)' : usedPercent > 60 ? 'var(--warn)' : 'var(--success)';
  return `
    <div class="summary-compact">
      <div class="summary-compact-item">
        <span class="summary-compact-value">${summary.total_accounts}</span>
        <span class="summary-compact-label">总账号</span>
      </div>
      <div class="summary-compact-item">
        <span class="summary-compact-value" style="color:var(--success)">${summary.available_accounts}</span>
        <span class="summary-compact-label">可用</span>
      </div>
      <div class="summary-compact-item">
        <span class="summary-compact-value" style="color:var(--warn)">${summary.cooldown_accounts}</span>
        <span class="summary-compact-label">冷却</span>
      </div>
      <div class="summary-compact-divider"></div>
      <div class="summary-quota-bar">
        <div style="display:flex;justify-content:space-between;font-size:0.75rem;margin-bottom:0.25rem">
          <span>总额度</span>
          <span>${summary.total_balance.toFixed(0)} / ${summary.total_limit.toFixed(0)}</span>
        </div>
        <div style="height:6px;background:var(--bg);border-radius:3px;overflow:hidden">
          <div style="height:100%;width:${usedPercent}%;background:${barColor}"></div>
        </div>
      </div>
      <div class="summary-compact-item" style="margin-left:auto">
        <span class="summary-compact-label">${summary.last_refresh || '未刷新'}</span>
      </div>
    </div>
  `;
}

// ==================== 紧凑账号卡片 ====================
function renderAccountCardCompact(account) {
  const quota = account.quota;
  const isPriority = account.is_priority;
  const isLowBalance = quota?.is_low_balance;
  const isExhausted = quota?.is_exhausted || (quota && quota.balance <= 0);  // 额度耗尽
  const isUnavailable = !account.available;
  
  let cardClass = 'account-card-compact';
  if (isPriority) cardClass += ' priority';
  if (isExhausted) cardClass += ' exhausted';  // 无额度状态
  else if (isLowBalance) cardClass += ' low-balance';
  if (isUnavailable) cardClass += ' unavailable';
  
  // 状态徽章
  let statusBadges = '';
  if (!account.enabled) statusBadges += '<span class="badge">禁用</span>';
  else if (account.cooldown_remaining > 0) statusBadges += `<span class="badge warn">冷却</span>`;
  else if (account.available) statusBadges += '<span class="badge success">正常</span>';
  else statusBadges += '<span class="badge error">异常</span>';
  
  if (isPriority) statusBadges += `<span class="badge info">#${account.priority_order}</span>`;
  // 额度状态徽章：无额度（红色）> 低额度（黄色）
  if (isExhausted) statusBadges += '<span class="badge error">无额度</span>';
  else if (isLowBalance) statusBadges += '<span class="badge warn">低额度</span>';
  
  // Token 过期状态徽章
  if (account.token_expired) statusBadges += '<span class="badge error">Token过期</span>';
  else if (account.token_expiring_soon) statusBadges += '<span class="badge warn">Token即将过期</span>';
  
  // 额度条 - 根据状态显示不同颜色
  let quotaBar = '';
  if (quota && !quota.error) {
    const usedPercent = quota.usage_limit > 0 ? (quota.current_usage / quota.usage_limit * 100) : 0;
    // 颜色逻辑：无额度(红色) > 低额度(黄色) > 正常(绿色)
    let barColor = 'var(--success)';
    if (isExhausted) barColor = 'var(--error)';
    else if (isLowBalance) barColor = 'var(--warn)';
    else if (usedPercent > 60) barColor = 'var(--warn)';
    
    quotaBar = `
      <div class="account-card-quota">
        <div class="account-card-quota-bar">
          <div class="account-card-quota-fill" style="width:${usedPercent}%;background:${barColor}"></div>
        </div>
        <div class="account-card-quota-text">
          <span>剩余 ${quota.balance.toFixed(1)}</span>
          <span>${usedPercent.toFixed(0)}%</span>
        </div>
      </div>
    `;
  } else if (quota?.error) {
    // 额度获取失败时显示重试按钮
    quotaBar = `
      <div class="account-card-quota">
        <span style="font-size:0.7rem;color:var(--error)">额度获取失败: ${quota.error}</span>
        <button class="secondary small" style="margin-left:0.5rem;padding:0.15rem 0.4rem;font-size:0.65rem" onclick="event.stopPropagation();refreshSingleAccountQuota('${account.id}')">重试</button>
      </div>
    `;
  } else {
    // 未查询额度时显示查询按钮
    quotaBar = `
      <div class="account-card-quota">
        <span style="font-size:0.7rem;color:var(--muted)">额度未查询</span>
        <button class="secondary small" style="margin-left:0.5rem;padding:0.15rem 0.4rem;font-size:0.65rem" onclick="event.stopPropagation();refreshSingleAccountQuota('${account.id}')">查询</button>
      </div>
    `;
  }
  
  // Token 过期时间显示
  let tokenExpireInfo = '';
  if (account.token_expires_at) {
    // expires_at 可能是 ISO 字符串或时间戳
    let expireDate;
    if (typeof account.token_expires_at === 'string') {
      // ISO 格式字符串
      expireDate = new Date(account.token_expires_at);
    } else if (account.token_expires_at > 1000000000000) {
      // 毫秒时间戳
      expireDate = new Date(account.token_expires_at);
    } else {
      // 秒时间戳
      expireDate = new Date(account.token_expires_at * 1000);
    }
    
    const now = new Date();
    const diffMs = expireDate - now;
    
    // 检查是否为有效日期
    if (!isNaN(expireDate.getTime()) && !isNaN(diffMs)) {
      const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
      const diffDays = Math.floor(diffHours / 24);
      
      let expireText = '';
      if (diffMs < 0) {
        expireText = '已过期';
      } else if (diffDays > 0) {
        expireText = `${diffDays}天`;
      } else if (diffHours > 0) {
        expireText = `${diffHours}时`;
      } else {
        const diffMins = Math.floor(diffMs / (1000 * 60));
        expireText = diffMins > 0 ? `${diffMins}分` : '即将过期';
      }
      tokenExpireInfo = `<span title="Token过期: ${expireDate.toLocaleString()}">Token ${expireText}</span>`;
    }
  }
  
  return `
    <div class="${cardClass}" data-id="${account.id}" id="account-card-${account.id.replace(/[^a-zA-Z0-9]/g, '_')}">
      <div class="account-card-top">
        <div class="account-card-info">
          <div class="account-card-name">${account.name}</div>
          <div class="account-card-email">${account.id}</div>
        </div>
        <div class="account-card-status">${statusBadges}</div>
      </div>
      ${quotaBar}
      <div class="account-card-stats">
        <span>请求: ${account.request_count}</span>
        <span>错误: ${account.error_count}</span>
        ${tokenExpireInfo}
      </div>
      <div class="account-card-actions">
        <button class="secondary small" onclick="refreshSingleAccountQuota('${account.id}')">刷新</button>
        <button class="secondary small" onclick="togglePriority('${account.id}')">${isPriority ? '取消优先' : '优先'}</button>
        <button class="secondary small" onclick="toggleAccount('${account.id}')">${account.enabled ? '禁用' : '启用'}</button>
        <button class="secondary small" style="color:var(--error)" onclick="confirmDeleteAccount('${account.id}')">删除</button>
      </div>
    </div>
  `;
}

// ==================== 导入导出菜单 ====================
let importExportMenu = null;

function showImportExportMenu(btn) {
  if (importExportMenu) {
    importExportMenu.remove();
    importExportMenu = null;
    return;
  }
  
  const menu = document.createElement('div');
  menu.className = 'dropdown-menu';
  menu.style.cssText = 'display:block;position:absolute;z-index:100;min-width:140px;';
  menu.innerHTML = `
    <div class="dropdown-item" onclick="exportAccounts()">📤 导出账号</div>
    <div class="dropdown-item" onclick="importAccounts()">📥 导入账号</div>
    <div class="dropdown-divider"></div>
    <div class="dropdown-item" onclick="refreshAllTokens()">🔄 刷新 Token</div>
  `;
  
  const rect = btn.getBoundingClientRect();
  menu.style.top = (rect.bottom + window.scrollY + 4) + 'px';
  menu.style.left = (rect.left + window.scrollX) + 'px';
  
  document.body.appendChild(menu);
  importExportMenu = menu;
  
  setTimeout(() => {
    document.addEventListener('click', function closeMenu(e) {
      if (importExportMenu && !importExportMenu.contains(e.target)) {
        importExportMenu.remove();
        importExportMenu = null;
      }
      document.removeEventListener('click', closeMenu);
    }, { once: true });
  }, 10);
}

async function refreshAllQuotas() {
  // 检查是否正在刷新中
  if (GlobalProgressBar.isRefreshing) {
    Toast.warning('正在刷新中，请稍候...');
    return;
  }
  
  try {
    // 先获取账号数量用于显示
    const statusR = await fetch('/api/accounts/status');
    const statusD = await statusR.json();
    const total = statusD.ok ? statusD.accounts?.length || 0 : 0;
    
    // 显示进度条
    GlobalProgressBar.show(total);
    
    // 调用新的批量刷新 API
    const r = await fetch('/api/refresh/all', { method: 'POST' });
    const d = await r.json();
    
    if (d.ok) {
      // 开始轮询进度
      GlobalProgressBar.startPolling();
    } else {
      GlobalProgressBar.hide();
      Toast.error('启动刷新失败: ' + (d.error || '未知错误'));
    }
  } catch(e) {
    GlobalProgressBar.hide();
    Toast.error('刷新失败: ' + e.message);
  }
}

async function refreshAccountQuota(accountId) {
  Toast.info('正在刷新额度...');
  try {
    const r = await fetch(`/api/accounts/${accountId}/refresh-quota`, { method: 'POST' });
    const d = await r.json();
    if (d.ok) {
      Toast.success('额度刷新成功');
      loadAccountsEnhanced();
    } else {
      Toast.error(d.error || '刷新失败');
    }
  } catch(e) {
    Toast.error('刷新失败: ' + e.message);
  }
}

// ==================== 单账号额度查询 (任务 19.2) ====================
async function refreshSingleAccountQuota(accountId) {
  // 获取按钮元素，显示加载状态
  const safeId = accountId.replace(/[^a-zA-Z0-9]/g, '_');
  const btn = document.getElementById('quota-btn-' + safeId);
  const card = document.getElementById('account-card-' + safeId);
  
  if (btn) {
    btn.disabled = true;
    btn.dataset.originalText = btn.textContent;
    btn.textContent = '查询中...';
  }
  
  try {
    const r = await fetch(`/api/accounts/${accountId}/refresh-quota`, { method: 'POST' });
    const d = await r.json();
    
    if (d.ok) {
      Toast.success('额度查询成功');
      // 刷新整个账号列表以更新显示
      loadAccountsEnhanced();
    } else {
      // 失败时显示错误信息和重试按钮
      Toast.error(d.error || '额度查询失败');
      if (btn) {
        btn.textContent = '重试';
        btn.disabled = false;
        btn.classList.add('error-state');
      }
      // 在卡片上显示错误状态
      if (card) {
        const quotaDiv = card.querySelector('.account-card-quota');
        if (quotaDiv) {
          quotaDiv.innerHTML = `
            <span style="font-size:0.7rem;color:var(--error)">查询失败: ${d.error || '未知错误'}</span>
            <button class="secondary small" style="margin-left:0.5rem;padding:0.15rem 0.4rem;font-size:0.65rem" onclick="event.stopPropagation();refreshSingleAccountQuota('${accountId}')">重试</button>
          `;
        }
      }
    }
  } catch(e) {
    Toast.error('网络错误: ' + e.message);
    if (btn) {
      btn.textContent = '重试';
      btn.disabled = false;
    }
  } finally {
    // 恢复按钮状态（如果没有错误）
    if (btn && !btn.classList.contains('error-state')) {
      btn.disabled = false;
      if (btn.dataset.originalText) {
        btn.textContent = btn.dataset.originalText;
      }
    }
    if (btn) {
      btn.classList.remove('error-state');
    }
  }
}

// ==================== 单账号 Token 刷新 (任务 19.2) ====================
async function refreshSingleAccountToken(accountId) {
  // 获取按钮元素，显示加载状态
  const safeId = accountId.replace(/[^a-zA-Z0-9]/g, '_');
  const btn = document.getElementById('token-btn-' + safeId);
  
  if (btn) {
    btn.disabled = true;
    btn.dataset.originalText = btn.textContent;
    btn.textContent = '刷新中...';
  }
  
  try {
    const r = await fetch(`/api/accounts/${accountId}/refresh`, { method: 'POST' });
    const d = await r.json();
    
    if (d.ok) {
      Toast.success('Token 刷新成功');
      // 刷新整个账号列表以更新显示
      loadAccountsEnhanced();
    } else {
      // 失败时显示错误信息
      Toast.error(d.message || d.error || 'Token 刷新失败');
      if (btn) {
        btn.textContent = '重试';
        btn.disabled = false;
      }
    }
  } catch(e) {
    Toast.error('网络错误: ' + e.message);
    if (btn) {
      btn.textContent = '重试';
      btn.disabled = false;
    }
  } finally {
    // 恢复按钮状态
    if (btn && btn.textContent !== '重试') {
      btn.disabled = false;
      if (btn.dataset.originalText) {
        btn.textContent = btn.dataset.originalText;
      }
    }
  }
}

async function togglePriority(accountId) {
  try {
    // 先检查是否已是优先账号
    const r1 = await fetch('/api/priority');
    const d1 = await r1.json();
    const isPriority = d1.priority_accounts?.some(a => a.id === accountId);
    
    if (isPriority) {
      const r = await fetch(`/api/priority/${accountId}`, { method: 'DELETE' });
      const d = await r.json();
      Toast.show(d.message, d.ok ? 'success' : 'error');
    } else {
      const r = await fetch(`/api/priority/${accountId}`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}' });
      const d = await r.json();
      Toast.show(d.message, d.ok ? 'success' : 'error');
    }
    loadAccountsEnhanced();
  } catch(e) {
    Toast.error('操作失败: ' + e.message);
  }
}

function confirmDeleteAccount(accountId) {
  Modal.danger('删除账号', `确定要删除账号 ${accountId} 吗？此操作不可恢复。`, async () => {
    try {
      const r = await fetch(`/api/accounts/${accountId}`, { method: 'DELETE' });
      const d = await r.json();
      if (d.ok) {
        Toast.success('账号已删除');
        loadAccountsEnhanced();
      } else {
        Toast.error('删除失败');
      }
    } catch(e) {
      Toast.error('删除失败: ' + e.message);
    }
  });
}

// ==================== 自动刷新功能 (任务 10.2) ====================
let autoRefreshTimer = null;
const AUTO_REFRESH_INTERVAL = 60000; // 60秒

function startAutoRefresh() {
  if (autoRefreshTimer) clearInterval(autoRefreshTimer);
  autoRefreshTimer = setInterval(() => {
    const accountsTab = document.querySelector('.tab[data-tab="accounts"]');
    if (accountsTab && accountsTab.classList.contains('active')) {
      loadAccountsEnhanced();
    }
  }, AUTO_REFRESH_INTERVAL);
}

function stopAutoRefresh() {
  if (autoRefreshTimer) {
    clearInterval(autoRefreshTimer);
    autoRefreshTimer = null;
  }
}

// 页面加载时启动自动刷新
startAutoRefresh();

// ==================== 加载状态指示器 (任务 10.1) ====================
function showLoading(container, message = '加载中...') {
  const el = typeof container === 'string' ? document.querySelector(container) : container;
  if (el) {
    el.innerHTML = `<div style="text-align:center;padding:2rem;color:var(--muted)">
      <div style="display:inline-block;width:20px;height:20px;border:2px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin 1s linear infinite"></div>
      <p style="margin-top:0.5rem">${message}</p>
    </div>`;
  }
}

// 添加旋转动画
if (!document.querySelector('#spinKeyframes')) {
  const style = document.createElement('style');
  style.id = 'spinKeyframes';
  style.textContent = '@keyframes spin { to { transform: rotate(360deg); } }';
  document.head.appendChild(style);
}

// ==================== 表单验证 (任务 10.3) ====================
function validateToken(token) {
  if (!token || token.trim().length === 0) {
    return { valid: false, error: 'Token 不能为空' };
  }
  if (token.trim().length < 20) {
    return { valid: false, error: 'Token 格式不正确，长度过短' };
  }
  return { valid: true };
}

function validateAccountName(name) {
  if (!name || name.trim().length === 0) {
    return { valid: true, default: '手动添加账号' }; // 名称可选
  }
  if (name.length > 50) {
    return { valid: false, error: '账号名称不能超过50个字符' };
  }
  return { valid: true };
}

// ==================== 网络错误处理 (任务 10.1) ====================
async function fetchWithRetry(url, options = {}, retries = 2) {
  for (let i = 0; i <= retries; i++) {
    try {
      const r = await fetch(url, options);
      if (!r.ok && r.status >= 500 && i < retries) {
        await new Promise(resolve => setTimeout(resolve, 1000 * (i + 1)));
        continue;
      }
      return r;
    } catch (e) {
      if (i === retries) throw e;
      await new Promise(resolve => setTimeout(resolve, 1000 * (i + 1)));
    }
  }
}

// ==================== 全局进度条组件 (任务 18.1) ====================
const GlobalProgressBar = {
  pollTimer: null,
  isRefreshing: false,
  
  // 显示进度条
  show(total) {
    this.isRefreshing = true;
    const bar = $('#globalProgressBar');
    if (bar) {
      bar.classList.add('active');
      // 重置显示
      $('#globalProgressTitle').textContent = '正在刷新额度...';
      $('#globalProgressCompleted').textContent = '0';
      $('#globalProgressTotal').textContent = total || '0';
      $('#globalProgressSuccess').textContent = '0';
      $('#globalProgressFailed').textContent = '0';
      $('#globalProgressFill').style.width = '0%';
      $('#globalProgressFill').classList.remove('complete');
      $('#globalProgressCurrent').textContent = '准备中...';
      $('#globalProgressClose').style.display = 'none';
      // 显示 spinner
      const spinner = bar.querySelector('.spinner');
      if (spinner) spinner.style.display = 'inline-block';
    }
    // 禁用刷新按钮
    this.updateRefreshButton(true);
  },
  
  // 更新进度
  update(progress) {
    if (!progress) return;
    
    const completed = progress.completed || 0;
    const total = progress.total || 0;
    const success = progress.success || 0;
    const failed = progress.failed || 0;
    const current = progress.current_account || '';
    const isComplete = progress.status === 'completed' || progress.status === 'idle';
    
    // 更新数字
    $('#globalProgressCompleted').textContent = completed;
    $('#globalProgressTotal').textContent = total;
    $('#globalProgressSuccess').textContent = success;
    $('#globalProgressFailed').textContent = failed;
    
    // 更新进度条
    const percent = total > 0 ? (completed / total * 100) : 0;
    const fill = $('#globalProgressFill');
    if (fill) {
      fill.style.width = percent + '%';
      if (isComplete) {
        fill.classList.add('complete');
      }
    }
    
    // 更新当前处理的账号
    if (current) {
      $('#globalProgressCurrent').textContent = '正在处理: ' + current;
    } else if (isComplete) {
      $('#globalProgressCurrent').textContent = `刷新完成: 成功 ${success} 个, 失败 ${failed} 个`;
    }
    
    // 完成后的处理
    if (isComplete) {
      this.isRefreshing = false;
      $('#globalProgressTitle').textContent = '刷新完成';
      $('#globalProgressClose').style.display = 'inline-block';
      // 隐藏 spinner
      const spinner = $('#globalProgressBar')?.querySelector('.spinner');
      if (spinner) spinner.style.display = 'none';
      // 恢复刷新按钮
      this.updateRefreshButton(false);
      // 刷新账号列表
      loadAccountsEnhanced();
      // 显示完成通知
      if (failed > 0) {
        Toast.warning(`刷新完成: 成功 ${success} 个, 失败 ${failed} 个`);
      } else {
        Toast.success(`刷新完成: 成功 ${success} 个`);
      }
      // 5秒后自动关闭进度条
      setTimeout(() => this.hide(), 5000);
    }
  },
  
  // 隐藏进度条
  hide() {
    const bar = $('#globalProgressBar');
    if (bar) {
      bar.classList.remove('active');
    }
    this.isRefreshing = false;
    this.stopPolling();
    this.updateRefreshButton(false);
  },
  
  // 开始轮询进度
  startPolling() {
    this.stopPolling();
    this.pollTimer = setInterval(() => this.pollProgress(), 500);
  },
  
  // 停止轮询
  stopPolling() {
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
  },
  
  // 轮询进度 API
  async pollProgress() {
    try {
      const r = await fetch('/api/refresh/progress');
      const d = await r.json();
      if (d.ok) {
        // 传入 progress 对象，如果没有则传入整个响应（兼容）
        const progress = d.progress || d;
        // 添加 status 字段用于判断完成状态
        if (!d.is_refreshing && !progress.status) {
          progress.status = 'completed';
        }
        this.update(progress);
        // 如果完成则停止轮询
        if (!d.is_refreshing || progress.status === 'completed' || progress.status === 'idle') {
          this.stopPolling();
        }
      }
    } catch (e) {
      console.error('轮询进度失败:', e);
    }
  },
  
  // 更新刷新按钮状态
  updateRefreshButton(disabled) {
    // 查找所有刷新额度按钮
    const buttons = document.querySelectorAll('button');
    buttons.forEach(btn => {
      const text = btn.textContent;
      const originalText = btn.dataset.originalText;
      // 匹配"刷新额度"、"刷新全部额度"或已经变成"刷新中..."的按钮
      if (text.includes('刷新额度') || text.includes('刷新全部额度') || 
          text === '刷新中...' || 
          (originalText && (originalText.includes('刷新额度') || originalText.includes('刷新全部额度')))) {
        btn.disabled = disabled;
        if (disabled) {
          if (!btn.dataset.originalText) {
            btn.dataset.originalText = text;
          }
          btn.textContent = '刷新中...';
        } else if (btn.dataset.originalText) {
          btn.textContent = btn.dataset.originalText;
          delete btn.dataset.originalText;
        }
      }
    });
  }
};

// ==================== 进度轮询函数 (任务 18.2) ====================
async function pollRefreshProgress() {
  return GlobalProgressBar.pollProgress();
}
'''

JS_SCRIPTS = JS_UTILS + JS_TABS + JS_STATUS + JS_DOCS + JS_STATS + JS_LOGS + JS_ACCOUNTS + JS_LOGIN + JS_FLOWS + JS_SETTINGS + JS_UI_COMPONENTS


# ==================== 组装最终 HTML ====================
HTML_PAGE = f'''<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Kiro API</title>
<link rel="icon" type="image/svg+xml" href="/assets/icon.svg">
<style>
{CSS_STYLES}
</style>
</head>
<body>
<div class="container">
{HTML_BODY}
<div class="footer">Kiro API Proxy v1.7.1 - Codex 工具调用 | 环境变量配置 | 限速开关修复</div>
</div>
<script>
{JS_SCRIPTS}
</script>
</body>
</html>'''
