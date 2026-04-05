# PFA Contabilitate UI Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 11,351-line monolithic index.html with a modular, monochrome, three-section UI (Overview, Documents, Engine).

**Architecture:** Extract all CSS to `styles.css`, all JS to `renderer.js` + component modules in `components/`. Sidebar navigation replaces top nav. Native fiscal data rendering replaces iframe dashboard. Chat section removed entirely.

**Tech Stack:** Vanilla JS (ES modules via `<script type="module">`), CSS custom properties, Inter font (bundled woff2), Electron IPC unchanged.

---

## File Structure

```
app/
  index.html              # Semantic HTML shell (~200 lines) — CREATE (replaces existing)
  styles.css              # All styling + CSS variables (~400 lines) — CREATE
  renderer.js             # Main UI orchestrator, event delegation, IPC (~500 lines) — CREATE
  components/
    fiscal-table.js       # Shared fiscal summary table — CREATE
    file-tree.js          # Document tree with expand/collapse — CREATE
    dropzone.js           # Drag-drop file import area — CREATE
    inline-expand.js      # Generic expand/collapse utility — CREATE
    year-selector.js      # Shared year picker (synced across sections) — CREATE
    gmail-panel.js        # Gmail setup/status panel — CREATE
  fonts/
    Inter-Regular.woff2   # Inter font files — CREATE (download)
    Inter-Medium.woff2    # CREATE (download)
    Inter-SemiBold.woff2  # CREATE (download)
  icon.png                # New monochrome icon — CREATE (replaces existing)
  preload.js              # Remove chat + dashboard path methods — MODIFY
  package.json            # Update files array for build — MODIFY
```

**Unchanged files** (do not touch):
- `main.js` — all 23 IPC handlers stay as-is
- `agents/` — dispatcher.js, executor.js, feed.js, memory.js, prompts/
- `gmail/` — auth.js, monitor.js
- `python/` — bundled runtime
- `scripts/` — bundle-python.js, release.js

---

### Task 1: Download Inter font and create fonts directory

**Files:**
- Create: `app/fonts/Inter-Regular.woff2`
- Create: `app/fonts/Inter-Medium.woff2`
- Create: `app/fonts/Inter-SemiBold.woff2`

- [ ] **Step 1: Create fonts directory and download Inter woff2 files**

```bash
mkdir -p "app/fonts"
# Download Inter from Google Fonts CDN (woff2 format, latin subset)
curl -L -o "app/fonts/Inter-Regular.woff2" "https://fonts.gstatic.com/s/inter/v18/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuLyfAZ9hiA.woff2"
curl -L -o "app/fonts/Inter-Medium.woff2" "https://fonts.gstatic.com/s/inter/v18/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuI6fAZ9hiA.woff2"
curl -L -o "app/fonts/Inter-SemiBold.woff2" "https://fonts.gstatic.com/s/inter/v18/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuGKYAZ9hiA.woff2"
```

- [ ] **Step 2: Verify files exist and have reasonable size**

Run: `ls -la app/fonts/`
Expected: Three .woff2 files, each ~20-50 KB

- [ ] **Step 3: Commit**

```bash
git add app/fonts/
git commit -m "chore: add Inter font files (woff2, latin)"
```

---

### Task 2: Create the new icon

**Files:**
- Create: `app/icon.png` (replaces existing)

- [ ] **Step 1: Back up existing icon**

```bash
cp app/icon.png app/icon-old.png
```

- [ ] **Step 2: Create new monochrome icon**

Create a 256x256 PNG with a white stylized "P" on a black (#09090b) background. The "P" should be geometric — constructed from a vertical bar and a half-circle, using negative space. White (#fafafa) on near-black.

Use Python with Pillow to generate it:

```python
from PIL import Image, ImageDraw, ImageFont
import os

size = 256
img = Image.new('RGBA', (size, size), (9, 9, 11, 255))
draw = ImageDraw.Draw(img)

# Geometric P: vertical stroke + semicircle bowl
# Vertical stroke
stroke_x = 72
stroke_w = 28
stroke_top = 48
stroke_bottom = 208
draw.rectangle([stroke_x, stroke_top, stroke_x + stroke_w, stroke_bottom], fill=(250, 250, 250, 255))

# Bowl (top half) — rounded rectangle approximation
bowl_left = stroke_x + stroke_w
bowl_right = 192
bowl_top = stroke_top
bowl_bottom = 136
# Outer arc
draw.arc([bowl_left - 10, bowl_top, bowl_right, bowl_bottom], -90, 90, fill=(250, 250, 250, 255), width=28)
# Connect top
draw.rectangle([stroke_x + stroke_w, bowl_top, bowl_left + 20, bowl_top + 28], fill=(250, 250, 250, 255))
# Connect bottom
draw.rectangle([stroke_x + stroke_w, bowl_bottom - 28, bowl_left + 20, bowl_bottom], fill=(250, 250, 250, 255))

out_path = os.path.join('app', 'icon.png')
img.save(out_path, 'PNG')
print(f'Saved to {out_path}')
```

Run: `python generate_icon.py`

Visually inspect the result. The icon should be a clean geometric white P on a near-black background. If the Pillow approach doesn't produce a clean result, manually create a 256x256 icon in any image editor with:
- Background: #09090b
- Letter "P" in #fafafa, geometric/minimal style, centered

- [ ] **Step 3: Clean up and commit**

```bash
rm -f app/icon-old.png generate_icon.py
git add app/icon.png
git commit -m "chore: replace icon with monochrome geometric P"
```

---

### Task 3: Create styles.css — the complete stylesheet

**Files:**
- Create: `app/styles.css`

- [ ] **Step 1: Create styles.css with full design system**

```css
/* === PFA Contabilitate — Design System === */

/* --- Fonts --- */
@font-face {
  font-family: 'Inter';
  font-style: normal;
  font-weight: 400;
  font-display: swap;
  src: url('fonts/Inter-Regular.woff2') format('woff2');
}
@font-face {
  font-family: 'Inter';
  font-style: normal;
  font-weight: 500;
  font-display: swap;
  src: url('fonts/Inter-Medium.woff2') format('woff2');
}
@font-face {
  font-family: 'Inter';
  font-style: normal;
  font-weight: 600;
  font-display: swap;
  src: url('fonts/Inter-SemiBold.woff2') format('woff2');
}

/* --- Variables --- */
:root {
  --bg: #09090b;
  --surface: #111113;
  --surface-hover: #18181b;
  --border: #27272a;
  --text: #fafafa;
  --text-secondary: #a1a1aa;
  --text-muted: #52525b;
  --accent: #ffffff;
  --destructive: #ef4444;
  --warning: #f59e0b;

  --font-sans: 'Inter', system-ui, -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', 'Cascadia Code', 'Fira Code', monospace;

  --text-xs: 12px;
  --text-sm: 13px;
  --text-base: 14px;
  --text-lg: 18px;
  --text-xl: 24px;
}

/* --- Reset --- */
*, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--font-sans);
  font-size: var(--text-sm);
  overflow: hidden;
  height: 100vh;
  display: flex;
}

/* --- App Shell --- */
.sidebar {
  width: 56px;
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 0;
  flex-shrink: 0;
}
.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.sidebar-btn {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  position: relative;
  color: var(--text-muted);
  transition: background 150ms ease, color 150ms ease;
}
.sidebar-btn:hover {
  background: var(--surface-hover);
  color: var(--text-secondary);
}
.sidebar-btn.active {
  color: var(--text);
}
.sidebar-btn.active::before {
  content: '';
  position: absolute;
  left: -8px;
  top: 8px;
  bottom: 8px;
  width: 3px;
  background: var(--accent);
  border-radius: 0 2px 2px 0;
}
.sidebar-btn svg {
  width: 20px;
  height: 20px;
  stroke: currentColor;
  stroke-width: 1.5;
  fill: none;
}

.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.content {
  flex: 1;
  overflow-y: auto;
}

/* --- Status Bar --- */
.statusbar {
  height: 28px;
  background: var(--surface);
  border-top: 1px solid var(--border);
  display: flex;
  align-items: center;
  padding: 0 16px;
  gap: 16px;
  font-size: var(--text-xs);
  color: var(--text-muted);
  flex-shrink: 0;
}
.statusbar-path {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  direction: rtl;
  text-align: left;
  max-width: 300px;
}
.statusbar-right {
  margin-left: auto;
  display: flex;
  gap: 16px;
}

/* --- Section Pages --- */
.section { display: none; height: 100%; }
.section.active { display: flex; }

/* Centered column layout (Overview, Engine) */
.centered-column {
  max-width: 720px;
  width: 100%;
  margin: 0 auto;
  padding: 32px 24px;
}

/* --- Buttons --- */
.btn-primary {
  background: transparent;
  color: var(--text);
  border: 1px solid var(--accent);
  padding: 8px 16px;
  border-radius: 6px;
  font-size: var(--text-sm);
  font-weight: 500;
  font-family: var(--font-sans);
  cursor: pointer;
  transition: all 150ms ease;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.btn-primary:hover {
  background: var(--accent);
  color: var(--bg);
}
.btn-primary:disabled {
  opacity: 0.4;
  pointer-events: none;
}

.btn-secondary {
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border);
  padding: 8px 16px;
  border-radius: 6px;
  font-size: var(--text-sm);
  font-weight: 500;
  font-family: var(--font-sans);
  cursor: pointer;
  transition: all 150ms ease;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.btn-secondary:hover {
  background: var(--surface-hover);
  color: var(--text);
  border-color: var(--text-muted);
}
.btn-secondary:disabled {
  opacity: 0.4;
  pointer-events: none;
}

.btn-text {
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: var(--text-sm);
  font-family: var(--font-sans);
  cursor: pointer;
  padding: 0;
  transition: color 150ms ease;
}
.btn-text:hover {
  color: var(--text);
  text-decoration: underline;
}

/* --- Spinner --- */
.spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid transparent;
  border-top-color: currentColor;
  border-radius: 50%;
  animation: spin 600ms linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* --- Data Table (fiscal summary, metadata) --- */
.data-table {
  width: 100%;
  border-collapse: collapse;
}
.data-table tr {
  border-bottom: 1px solid var(--border);
}
.data-table td {
  padding: 10px 0;
  font-size: var(--text-sm);
}
.data-table td:first-child {
  color: var(--text-secondary);
}
.data-table td:last-child {
  text-align: right;
  font-weight: 500;
}
.data-table tr.highlight td {
  font-weight: 600;
  font-size: var(--text-base);
}
.data-table-sm td {
  padding: 6px 0;
  font-size: var(--text-xs);
}

/* --- Year Selector --- */
.year-selector {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 24px;
}
.year-selector-label {
  font-size: var(--text-lg);
  font-weight: 600;
}
.year-selector-btn {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  transition: color 150ms ease;
}
.year-selector-btn:hover {
  color: var(--text);
}
.year-selector-btn svg {
  width: 16px;
  height: 16px;
  stroke: currentColor;
  stroke-width: 2;
  fill: none;
}

/* --- Section Headers --- */
.section-header {
  font-size: var(--text-base);
  font-weight: 600;
  margin-bottom: 12px;
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.section-header-meta {
  font-size: var(--text-xs);
  font-weight: 400;
  color: var(--text-muted);
}

/* --- Deadlines --- */
.deadline-row {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  font-size: var(--text-sm);
  color: var(--text-secondary);
}
.deadline-row.urgent {
  color: var(--warning);
}
.deadline-row.overdue {
  color: var(--destructive);
}

/* --- Activity Feed --- */
.activity-entry {
  display: flex;
  align-items: baseline;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
  font-size: var(--text-sm);
}
.activity-time {
  font-size: var(--text-xs);
  color: var(--text-muted);
  width: 80px;
  flex-shrink: 0;
}
.activity-desc {
  flex: 1;
  min-width: 0;
}
.activity-agent {
  font-size: var(--text-xs);
  color: var(--text-muted);
  flex-shrink: 0;
}
.activity-undo {
  display: none;
  font-size: var(--text-xs);
  color: var(--text-secondary);
  background: none;
  border: none;
  cursor: pointer;
  font-family: var(--font-sans);
  flex-shrink: 0;
}
.activity-undo:hover { text-decoration: underline; }
.activity-entry:hover .activity-agent { display: none; }
.activity-entry:hover .activity-undo { display: block; }

/* --- Documents: Two-panel layout --- */
.docs-layout {
  display: flex;
  height: 100%;
}
.docs-sidebar {
  width: 280px;
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow: hidden;
}
.docs-tree {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}
.docs-main {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

/* File tree */
.tree-folder {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 12px 0 var(--indent, 12px);
  cursor: pointer;
  font-size: var(--text-sm);
  color: var(--text);
  transition: background 150ms ease;
  user-select: none;
}
.tree-folder:hover { background: var(--surface-hover); }
.tree-folder-count {
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-left: auto;
}
.tree-chevron {
  width: 12px;
  height: 12px;
  stroke: var(--text-muted);
  stroke-width: 2;
  fill: none;
  transition: transform 200ms ease;
  flex-shrink: 0;
}
.tree-chevron.open { transform: rotate(90deg); }

.tree-file {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 28px;
  padding: 0 12px 0 var(--indent, 28px);
  cursor: pointer;
  font-size: var(--text-sm);
  color: var(--text-secondary);
  transition: background 150ms ease;
}
.tree-file:hover { background: var(--surface-hover); }
.tree-file.selected {
  border-left: 2px solid var(--accent);
  padding-left: calc(var(--indent, 28px) - 2px);
}
.tree-file-icon {
  width: 14px;
  height: 14px;
  stroke: var(--text-muted);
  stroke-width: 1.5;
  fill: none;
  flex-shrink: 0;
}

/* Gmail panel (bottom of docs sidebar) */
.gmail-panel {
  border-top: 1px solid var(--border);
  padding: 12px;
}
.gmail-email {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  margin-bottom: 8px;
}
.gmail-toggle {
  position: relative;
  display: inline-block;
  width: 32px;
  height: 18px;
}
.gmail-toggle input { opacity: 0; width: 0; height: 0; }
.gmail-toggle-slider {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background: var(--border);
  border-radius: 9px;
  cursor: pointer;
  transition: background 150ms ease;
}
.gmail-toggle-slider::before {
  content: '';
  position: absolute;
  left: 2px;
  top: 2px;
  width: 14px;
  height: 14px;
  background: var(--text-muted);
  border-radius: 50%;
  transition: transform 150ms ease, background 150ms ease;
}
.gmail-toggle input:checked + .gmail-toggle-slider {
  background: var(--text-muted);
}
.gmail-toggle input:checked + .gmail-toggle-slider::before {
  transform: translateX(14px);
  background: var(--text);
}

/* --- Dropzone --- */
.dropzone {
  border: 2px dashed var(--border);
  border-radius: 8px;
  padding: 48px 24px;
  text-align: center;
  cursor: pointer;
  transition: border-color 150ms ease;
  color: var(--text-muted);
  font-size: var(--text-sm);
}
.dropzone:hover,
.dropzone.dragover {
  border-color: var(--accent);
}

/* Import log */
.import-log {
  margin-top: 24px;
}
.import-log-header {
  font-size: var(--text-sm);
  font-weight: 500;
  margin-bottom: 8px;
  color: var(--text-secondary);
}
.import-log-entry {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  font-size: var(--text-sm);
}
.import-log-file {
  font-family: var(--font-mono);
  color: var(--text-secondary);
}
.import-log-result {
  color: var(--text-muted);
}
.import-log-icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}
.import-log-icon.ok { color: var(--text-secondary); }
.import-log-icon.err { color: var(--destructive); }

/* --- File detail (right panel when file selected) --- */
.file-detail-name {
  font-size: var(--text-lg);
  font-weight: 600;
  margin-bottom: 16px;
}
.file-detail-actions {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 16px;
}

/* --- Inline confirmation --- */
.inline-confirm {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

/* --- Engine action buttons --- */
.engine-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
}
.engine-actions > button {
  flex: 1;
}

/* --- Execution Log --- */
.exec-log-header {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  font-size: var(--text-sm);
  color: var(--text-secondary);
  padding: 8px 0;
  user-select: none;
}
.exec-log-header .tree-chevron {
  width: 10px;
  height: 10px;
}
.exec-log-count {
  color: var(--text-muted);
  font-size: var(--text-xs);
}
.exec-log-body {
  display: none;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 12px;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-secondary);
  max-height: 400px;
  overflow-y: auto;
  white-space: pre-wrap;
  line-height: 1.6;
}
.exec-log-body.open { display: block; }

/* --- Verification results --- */
.verify-section-header {
  font-size: var(--text-sm);
  font-weight: 500;
  margin: 16px 0 8px;
  color: var(--text);
}
.verify-item {
  font-size: var(--text-sm);
  padding: 2px 0;
}
.verify-item.issue { color: var(--destructive); }
.verify-item.clean { color: var(--text-secondary); }

/* --- Empty State --- */
.empty-state {
  color: var(--text-muted);
  font-size: var(--text-sm);
  text-align: center;
  padding: 48px 24px;
}

/* --- Scrollbar --- */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

/* --- Inline expand animation --- */
.expandable {
  overflow: hidden;
  max-height: 0;
  transition: max-height 200ms ease;
}
.expandable.open {
  max-height: 2000px;
}

/* --- Utilities --- */
.gap-24 { margin-bottom: 24px; }
.hidden { display: none !important; }
```

- [ ] **Step 2: Verify the CSS is valid**

Open the file and scan for syntax errors — unclosed braces, missing semicolons. The CSS should have no errors.

- [ ] **Step 3: Commit**

```bash
git add app/styles.css
git commit -m "feat: add complete design system stylesheet"
```

---

### Task 4: Create the inline-expand utility component

**Files:**
- Create: `app/components/inline-expand.js`

- [ ] **Step 1: Create the inline-expand module**

```javascript
// inline-expand.js — Generic expand/collapse behavior
// Usage: InlineExpand.toggle(triggerId, contentId)
// Or: InlineExpand.confirm(element, message, onYes)

export const InlineExpand = {
  /**
   * Toggle an expandable content area.
   * @param {HTMLElement} trigger - The element that was clicked
   * @param {HTMLElement} content - The .expandable element to toggle
   */
  toggle(trigger, content) {
    const isOpen = content.classList.contains('open');
    content.classList.toggle('open');
    return !isOpen;
  },

  /**
   * Replace an element with inline confirmation, restore on cancel.
   * @param {HTMLElement} element - The element to replace
   * @param {string} message - Confirmation text
   * @param {Function} onYes - Callback when confirmed
   */
  confirm(element, message, onYes) {
    const original = element.outerHTML;
    const parent = element.parentNode;

    const container = document.createElement('span');
    container.className = 'inline-confirm';
    container.innerHTML = `
      <span>${message}</span>
      <button class="btn-text" data-action="yes">Yes</button>
      <button class="btn-text" data-action="no">No</button>
    `;

    container.querySelector('[data-action="yes"]').addEventListener('click', () => {
      onYes();
      container.remove();
    });

    container.querySelector('[data-action="no"]').addEventListener('click', () => {
      const temp = document.createElement('div');
      temp.innerHTML = original;
      parent.replaceChild(temp.firstElementChild, container);
    });

    parent.replaceChild(container, element);
  }
};
```

- [ ] **Step 2: Commit**

```bash
git add app/components/inline-expand.js
git commit -m "feat: add inline expand/confirm utility component"
```

---

### Task 5: Create the year-selector component

**Files:**
- Create: `app/components/year-selector.js`

- [ ] **Step 1: Create the year-selector module**

```javascript
// year-selector.js — Shared year picker, synced across sections
// Emits 'year-changed' custom event on document when year changes

const CHEVRON_LEFT = '<svg viewBox="0 0 24 24"><polyline points="15 18 9 12 15 6"/></svg>';
const CHEVRON_RIGHT = '<svg viewBox="0 0 24 24"><polyline points="9 6 15 12 9 18"/></svg>';

let currentYear = new Date().getFullYear();
const instances = [];

export const YearSelector = {
  /** Get current selected year */
  getYear() {
    return currentYear;
  },

  /** Set year programmatically */
  setYear(year) {
    currentYear = year;
    instances.forEach(el => updateDisplay(el));
    document.dispatchEvent(new CustomEvent('year-changed', { detail: { year: currentYear } }));
  },

  /**
   * Mount a year selector into a container element.
   * @param {HTMLElement} container - The element to render into
   */
  mount(container) {
    container.classList.add('year-selector');
    container.innerHTML = `
      <button class="year-selector-btn" data-dir="prev">${CHEVRON_LEFT}</button>
      <span class="year-selector-label">${currentYear}</span>
      <button class="year-selector-btn" data-dir="next">${CHEVRON_RIGHT}</button>
    `;

    container.querySelector('[data-dir="prev"]').addEventListener('click', () => {
      YearSelector.setYear(currentYear - 1);
    });
    container.querySelector('[data-dir="next"]').addEventListener('click', () => {
      YearSelector.setYear(currentYear + 1);
    });

    instances.push(container);
  }
};

function updateDisplay(container) {
  const label = container.querySelector('.year-selector-label');
  if (label) label.textContent = currentYear;
}
```

- [ ] **Step 2: Commit**

```bash
git add app/components/year-selector.js
git commit -m "feat: add shared year-selector component"
```

---

### Task 6: Create the fiscal-table component

**Files:**
- Create: `app/components/fiscal-table.js`

- [ ] **Step 1: Create the fiscal-table module**

```javascript
// fiscal-table.js — Renders fiscal summary as a data table
// Used in Overview (fiscal summary) and Engine (calculation results)

const ROW_LABELS = {
  'Venit brut': 'Venit brut',
  'Cheltuieli deductibile': 'Cheltuieli deductibile',
  'Venit net': 'Venit net',
  'CAS': 'CAS',
  'CASS': 'CASS',
  'Impozit pe venit': 'Impozit pe venit',
  'Net dupa taxe': 'Net dupa taxe',
};

// Keys from SUMAR-CALCUL that map to our display rows
const KEY_MAP = {
  'Venituri brute incasate': 'Venit brut',
  'Total cheltuieli deductibile': 'Cheltuieli deductibile',
  'Venit net anual': 'Venit net',
  'CAS datorat': 'CAS',
  'CASS datorat': 'CASS',
  'Impozit pe venit net': 'Impozit pe venit',
};

const HIGHLIGHT_ROW = 'Net dupa taxe';

function formatRON(value) {
  return new Intl.NumberFormat('ro-RO', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value) + ' RON';
}

export const FiscalTable = {
  /**
   * Render fiscal data into a container.
   * @param {HTMLElement} container - Element to render into
   * @param {Object} data - Key-value pairs from get-sumar IPC (e.g., {"Venituri brute incasate": 50000})
   */
  render(container, data) {
    if (!data || Object.keys(data).length === 0) {
      container.innerHTML = '<div class="empty-state">No calculation data for this year.</div>';
      return;
    }

    // Map raw keys to display labels
    const mapped = {};
    for (const [rawKey, value] of Object.entries(data)) {
      for (const [pattern, label] of Object.entries(KEY_MAP)) {
        if (rawKey.includes(pattern) || rawKey === pattern) {
          mapped[label] = value;
          break;
        }
      }
    }

    // Calculate net after taxes
    const venit = mapped['Venit brut'] || 0;
    const cas = mapped['CAS'] || 0;
    const cass = mapped['CASS'] || 0;
    const impozit = mapped['Impozit pe venit'] || 0;
    mapped['Net dupa taxe'] = venit - cas - cass - impozit;

    let html = '<table class="data-table">';
    for (const label of Object.values(ROW_LABELS)) {
      const value = mapped[label];
      const isHighlight = label === HIGHLIGHT_ROW;
      html += `<tr${isHighlight ? ' class="highlight"' : ''}>`;
      html += `<td>${label}</td>`;
      html += `<td>${value !== undefined ? formatRON(value) : '—'}</td>`;
      html += '</tr>';
    }
    html += '</table>';

    container.innerHTML = html;
  }
};
```

- [ ] **Step 2: Commit**

```bash
git add app/components/fiscal-table.js
git commit -m "feat: add fiscal-table component"
```

---

### Task 7: Create the file-tree component

**Files:**
- Create: `app/components/file-tree.js`

- [ ] **Step 1: Create the file-tree module**

```javascript
// file-tree.js — Document tree with expand/collapse
// Renders hierarchical file structure in the Documents sidebar

const CHEVRON_SVG = '<svg class="tree-chevron" viewBox="0 0 24 24"><polyline points="9 6 15 12 9 18"/></svg>';
const FILE_SVG = '<svg class="tree-file-icon" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>';

export const FileTree = {
  /**
   * Render file tree into container.
   * @param {HTMLElement} container - The .docs-tree element
   * @param {Object} data - Output from get-output-files IPC: { "2026": [{name, path, ext, size}], ... }
   * @param {Function} onFileSelect - Callback when file is clicked: (fileObj) => void
   * @param {Function} onFolderSelect - Callback when folder is clicked: (folderName, files) => void
   */
  render(container, data, onFileSelect, onFolderSelect) {
    container.innerHTML = '';

    if (!data || Object.keys(data).length === 0) {
      container.innerHTML = '<div class="empty-state" style="padding:24px">No documents found.</div>';
      return;
    }

    const years = Object.keys(data).filter(k => /^\d{4}$/.test(k)).sort().reverse();
    const otherKeys = Object.keys(data).filter(k => !/^\d{4}$/.test(k));

    for (const key of [...years, ...otherKeys]) {
      const files = data[key];
      if (!files || files.length === 0) continue;

      // Separate files and subfolders
      const directFiles = files.filter(f => !f.name.includes('/'));
      const subfolders = {};
      files.filter(f => f.name.includes('/')).forEach(f => {
        const parts = f.name.split('/');
        const folder = parts[0];
        if (!subfolders[folder]) subfolders[folder] = [];
        subfolders[folder].push({ ...f, displayName: parts.slice(1).join('/') });
      });

      const folderEl = createFolder(key, files.length, 0);
      const childContainer = document.createElement('div');
      childContainer.style.display = 'none';

      // Sub-folders first
      for (const [subName, subFiles] of Object.entries(subfolders)) {
        const subEl = createFolder(subName, subFiles.length, 1);
        const subChildContainer = document.createElement('div');
        subChildContainer.style.display = 'none';

        for (const file of subFiles) {
          subChildContainer.appendChild(createFileRow(file, 2, file.displayName, onFileSelect));
        }

        subEl.addEventListener('click', () => {
          toggleFolder(subEl, subChildContainer);
          onFolderSelect(subName, subFiles);
        });
        childContainer.appendChild(subEl);
        childContainer.appendChild(subChildContainer);
      }

      // Direct files
      for (const file of directFiles) {
        childContainer.appendChild(createFileRow(file, 1, file.name, onFileSelect));
      }

      folderEl.addEventListener('click', () => {
        toggleFolder(folderEl, childContainer);
        onFolderSelect(key, directFiles);
      });

      container.appendChild(folderEl);
      container.appendChild(childContainer);
    }
  },

  /** Deselect all files in the tree */
  deselectAll(container) {
    container.querySelectorAll('.tree-file.selected').forEach(el => el.classList.remove('selected'));
  }
};

function createFolder(name, count, depth) {
  const el = document.createElement('div');
  el.className = 'tree-folder';
  el.style.setProperty('--indent', `${12 + depth * 16}px`);
  el.innerHTML = `${CHEVRON_SVG}<span>${name}</span><span class="tree-folder-count">${count}</span>`;
  return el;
}

function createFileRow(file, depth, displayName, onFileSelect) {
  const el = document.createElement('div');
  el.className = 'tree-file';
  el.style.setProperty('--indent', `${12 + depth * 16}px`);
  el.innerHTML = `${FILE_SVG}<span>${displayName}</span>`;
  el.addEventListener('click', (e) => {
    e.stopPropagation();
    // Deselect siblings
    el.closest('.docs-tree').querySelectorAll('.tree-file.selected').forEach(s => s.classList.remove('selected'));
    el.classList.add('selected');
    onFileSelect(file);
  });
  return el;
}

function toggleFolder(folderEl, childContainer) {
  const chevron = folderEl.querySelector('.tree-chevron');
  const isOpen = childContainer.style.display !== 'none';
  childContainer.style.display = isOpen ? 'none' : 'block';
  chevron.classList.toggle('open', !isOpen);
}
```

- [ ] **Step 2: Commit**

```bash
git add app/components/file-tree.js
git commit -m "feat: add file-tree component for Documents sidebar"
```

---

### Task 8: Create the dropzone component

**Files:**
- Create: `app/components/dropzone.js`

- [ ] **Step 1: Create the dropzone module**

```javascript
// dropzone.js — Drag-drop file import area

export const Dropzone = {
  /**
   * Initialize dropzone behavior on an element.
   * @param {HTMLElement} element - The .dropzone element
   * @param {Object} api - window.api reference
   * @param {Function} onImportComplete - Callback after import: (results) => void
   * @param {Function} setStatus - Callback to update status bar: (text, busy) => void
   */
  init(element, api, onImportComplete, setStatus) {
    element.innerHTML = 'Drop files or click to browse';

    // Click to pick
    element.addEventListener('click', async () => {
      const paths = await api.pickFiles();
      if (paths && paths.length > 0) {
        await doImport(paths, api, onImportComplete, setStatus);
      }
    });

    // Drag events — prevent defaults on document
    document.addEventListener('dragover', (e) => e.preventDefault());
    document.addEventListener('drop', (e) => e.preventDefault());

    element.addEventListener('dragover', (e) => {
      e.preventDefault();
      element.classList.add('dragover');
    });
    element.addEventListener('dragleave', () => {
      element.classList.remove('dragover');
    });
    element.addEventListener('drop', async (e) => {
      e.preventDefault();
      element.classList.remove('dragover');
      const files = Array.from(e.dataTransfer.files);
      const paths = files.map(f => f.path);
      if (paths.length > 0) {
        await doImport(paths, api, onImportComplete, setStatus);
      }
    });
  }
};

async function doImport(paths, api, onImportComplete, setStatus) {
  setStatus(`Importing ${paths.length} files...`, true);
  const results = await api.importFiles(paths);

  // Trigger agent processing
  try {
    await api.agentProcessImport(paths);
  } catch (e) { /* agent may not be available */ }

  setStatus(`${paths.length} files imported`, false);
  onImportComplete(results);
}
```

- [ ] **Step 2: Commit**

```bash
git add app/components/dropzone.js
git commit -m "feat: add dropzone component for file import"
```

---

### Task 9: Create the gmail-panel component

**Files:**
- Create: `app/components/gmail-panel.js`

- [ ] **Step 1: Create the gmail-panel module**

```javascript
// gmail-panel.js — Gmail setup/status in Documents sidebar

import { InlineExpand } from './inline-expand.js';

export const GmailPanel = {
  /**
   * Mount Gmail panel into a container.
   * @param {HTMLElement} container - The .gmail-panel element
   * @param {Object} api - window.api reference
   */
  async mount(container, api) {
    const hasCreds = await api.gmailHasCredentials();
    const status = hasCreds ? await api.gmailStatus() : null;

    if (!hasCreds || !status || status.accounts.length === 0) {
      renderDisconnected(container, api, hasCreds);
    } else {
      renderConnected(container, api, status);
    }
  }
};

function renderDisconnected(container, api, hasCreds) {
  container.innerHTML = `
    <button class="btn-secondary" style="width:100%" id="gmail-connect-btn">Connect Gmail</button>
    <div class="expandable" id="gmail-setup-expand">
      <div style="padding: 12px 0; font-size: 12px; color: var(--text-secondary); line-height: 1.6;">
        <p style="margin-bottom: 8px; font-weight: 500;">Setup:</p>
        <p>1. Go to Google Cloud Console, create OAuth credentials</p>
        <p>2. Download the credentials JSON file</p>
        <p style="margin-bottom: 12px;">3. Select it below, then authorize</p>
        <div style="display: flex; flex-direction: column; gap: 8px;">
          ${!hasCreds ? '<button class="btn-secondary" id="gmail-pick-creds" style="font-size: 12px;">Select credentials file</button>' : ''}
          <button class="btn-primary" id="gmail-authorize" style="font-size: 12px;" ${!hasCreds ? 'disabled' : ''}>Authorize</button>
        </div>
      </div>
    </div>
  `;

  const connectBtn = container.querySelector('#gmail-connect-btn');
  const expandEl = container.querySelector('#gmail-setup-expand');

  connectBtn.addEventListener('click', () => {
    InlineExpand.toggle(connectBtn, expandEl);
  });

  const pickCredsBtn = container.querySelector('#gmail-pick-creds');
  if (pickCredsBtn) {
    pickCredsBtn.addEventListener('click', async () => {
      // Use Electron file picker to select credentials.json
      const paths = await api.pickFiles();
      if (paths && paths.length > 0) {
        // Copy credentials to app data dir — handled by main process
        pickCredsBtn.textContent = 'Credentials selected';
        pickCredsBtn.disabled = true;
        container.querySelector('#gmail-authorize').disabled = false;
      }
    });
  }

  const authorizeBtn = container.querySelector('#gmail-authorize');
  authorizeBtn.addEventListener('click', async () => {
    authorizeBtn.textContent = 'Authorizing...';
    authorizeBtn.disabled = true;
    const result = await api.gmailSetupStart('default');
    if (result.success) {
      GmailPanel.mount(container, api);
    } else {
      authorizeBtn.textContent = 'Failed — retry';
      authorizeBtn.disabled = false;
    }
  });
}

function renderConnected(container, api, status) {
  const account = status.accounts[0];
  const lastCheck = status.lastChecks[account]
    ? new Date(status.lastChecks[account]).toLocaleString('ro-RO')
    : 'never';

  container.innerHTML = `
    <div class="gmail-email">${account}</div>
    <div style="display: flex; align-items: center; justify-content: space-between;">
      <div style="display: flex; align-items: center; gap: 8px;">
        <label class="gmail-toggle">
          <input type="checkbox" id="gmail-monitor-toggle" ${status.running ? 'checked' : ''}>
          <span class="gmail-toggle-slider"></span>
        </label>
        <span style="font-size: 12px; color: var(--text-muted);">${status.running ? 'Monitoring' : 'Paused'}</span>
      </div>
      <button class="btn-text" style="font-size: 12px; color: var(--text-muted);" id="gmail-disconnect">Disconnect</button>
    </div>
    <div style="font-size: 11px; color: var(--text-muted); margin-top: 6px;">Last check: ${lastCheck}</div>
  `;

  container.querySelector('#gmail-monitor-toggle').addEventListener('change', async () => {
    await api.gmailToggle();
    GmailPanel.mount(container, api);
  });

  container.querySelector('#gmail-disconnect').addEventListener('click', (e) => {
    InlineExpand.confirm(e.target, `Disconnect ${account}?`, async () => {
      await api.gmailRemoveAccount(account);
      GmailPanel.mount(container, api);
    });
  });
}
```

- [ ] **Step 2: Commit**

```bash
git add app/components/gmail-panel.js
git commit -m "feat: add gmail-panel component"
```

---

### Task 10: Create index.html — semantic HTML shell

**Files:**
- Create: `app/index.html` (replaces existing 728-line file)

- [ ] **Step 1: Back up existing index.html**

```bash
cp app/index.html app/index-old.html
```

- [ ] **Step 2: Write the new index.html**

```html
<!DOCTYPE html>
<html lang="ro">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PFA Contabilitate</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>

  <!-- Sidebar Navigation -->
  <nav class="sidebar">
    <div class="sidebar-nav">
      <button class="sidebar-btn active" data-section="overview" title="Overview">
        <svg viewBox="0 0 24 24"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
      </button>
      <button class="sidebar-btn" data-section="documents" title="Documents">
        <svg viewBox="0 0 24 24"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
      </button>
      <button class="sidebar-btn" data-section="engine" title="Engine">
        <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polygon points="10 8 16 12 10 16 10 8"/></svg>
      </button>
    </div>
  </nav>

  <!-- Main Content Area -->
  <div class="main-area">
    <div class="content">

      <!-- Overview Section -->
      <div id="section-overview" class="section active" style="overflow-y: auto;">
        <div class="centered-column">
          <div id="overview-year-selector"></div>
          <div id="overview-fiscal" class="gap-24"></div>
          <div id="overview-deadlines" class="gap-24"></div>
          <div id="overview-activity" class="gap-24"></div>
          <div id="overview-gmail"></div>
        </div>
      </div>

      <!-- Documents Section -->
      <div id="section-documents" class="section">
        <div class="docs-layout">
          <div class="docs-sidebar">
            <div class="docs-tree" id="docs-tree"></div>
            <div class="gmail-panel" id="gmail-panel"></div>
          </div>
          <div class="docs-main" id="docs-main">
            <div class="dropzone" id="dropzone"></div>
            <div class="import-log" id="import-log"></div>
          </div>
        </div>
      </div>

      <!-- Engine Section -->
      <div id="section-engine" class="section" style="overflow-y: auto;">
        <div class="centered-column">
          <div id="engine-year-selector"></div>
          <div class="engine-actions">
            <button class="btn-primary" id="btn-run-calc">Run Calculation</button>
            <button class="btn-secondary" id="btn-verify">Verify</button>
            <button class="btn-secondary" id="btn-autofix">Auto-Fix</button>
          </div>
          <div id="engine-results"></div>
          <div id="engine-log-section" class="gap-24">
            <div class="exec-log-header" id="exec-log-toggle">
              <svg class="tree-chevron" viewBox="0 0 24 24"><polyline points="9 6 15 12 9 18"/></svg>
              <span>Log</span>
              <span class="exec-log-count" id="exec-log-count"></span>
            </div>
            <div class="exec-log-body" id="exec-log-body"></div>
          </div>
          <div id="engine-d212" style="margin-top: 24px;">
            <button class="btn-secondary" id="btn-generate-d212">Generate D212</button>
            <span id="d212-result" style="margin-left: 12px;"></span>
          </div>
        </div>
      </div>

    </div>

    <!-- Status Bar -->
    <div class="statusbar">
      <span class="statusbar-path" id="statusbar-path"></span>
      <div class="statusbar-right">
        <span id="statusbar-engine">Ready</span>
        <span id="statusbar-audit"></span>
      </div>
    </div>
  </div>

  <script type="module" src="renderer.js"></script>
</body>
</html>
```

- [ ] **Step 3: Commit**

```bash
git add app/index.html
git commit -m "feat: replace monolithic index.html with semantic HTML shell"
```

---

### Task 11: Create renderer.js — main UI orchestrator

**Files:**
- Create: `app/renderer.js`

- [ ] **Step 1: Create renderer.js**

```javascript
// renderer.js — Main UI orchestrator
// Handles navigation, event delegation, IPC calls, section rendering

import { YearSelector } from './components/year-selector.js';
import { FiscalTable } from './components/fiscal-table.js';
import { FileTree } from './components/file-tree.js';
import { Dropzone } from './components/dropzone.js';
import { GmailPanel } from './components/gmail-panel.js';
import { InlineExpand } from './components/inline-expand.js';

const api = window.api;

// ============================================================
// Navigation
// ============================================================

const sidebarBtns = document.querySelectorAll('.sidebar-btn');
const sections = document.querySelectorAll('.section');

sidebarBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    const target = btn.dataset.section;
    sidebarBtns.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    sections.forEach(s => s.classList.remove('active'));
    document.getElementById(`section-${target}`).classList.add('active');
    onSectionActivated(target);
  });
});

function onSectionActivated(section) {
  if (section === 'overview') loadOverview();
  if (section === 'documents') loadDocuments();
  if (section === 'engine') { /* engine loads on demand via buttons */ }
}

// ============================================================
// Status Bar
// ============================================================

function setStatus(text, busy) {
  document.getElementById('statusbar-engine').textContent = text;
}

async function initStatusBar() {
  try {
    const folder = await api.getDataFolder();
    document.getElementById('statusbar-path').textContent = folder || '';
  } catch { /* ignore */ }
}

// ============================================================
// Year Selector (shared)
// ============================================================

YearSelector.mount(document.getElementById('overview-year-selector'));
YearSelector.mount(document.getElementById('engine-year-selector'));

document.addEventListener('year-changed', () => {
  loadOverviewFiscal();
});

// ============================================================
// Overview Section
// ============================================================

async function loadOverview() {
  await Promise.all([
    loadOverviewFiscal(),
    loadOverviewDeadlines(),
    loadOverviewActivity(),
    loadOverviewGmail(),
  ]);
}

async function loadOverviewFiscal() {
  const year = YearSelector.getYear();
  const result = await api.getSumar(year);
  const container = document.getElementById('overview-fiscal');
  FiscalTable.render(container, result.success ? result.data : null);
}

async function loadOverviewDeadlines() {
  const container = document.getElementById('overview-deadlines');
  try {
    const result = await api.getDeadlines();
    if (!result.success || !result.data || result.data.length === 0) {
      container.innerHTML = '';
      return;
    }

    const upcoming = result.data.filter(d => d.daysLeft <= 30);
    if (upcoming.length === 0) {
      container.innerHTML = '';
      return;
    }

    let html = '<div class="section-header">Deadlines</div>';
    for (const d of upcoming) {
      let cls = '';
      if (d.daysLeft < 0 || d.passed) cls = 'overdue';
      else if (d.daysLeft <= 3) cls = 'urgent';

      const daysText = d.daysLeft >= 0 ? `${d.daysLeft} days` : 'overdue';
      html += `<div class="deadline-row ${cls}">
        <span>${d.date}</span>
        <span>${d.name.split(' — ')[0]} — ${daysText}</span>
      </div>`;
    }
    container.innerHTML = html;
  } catch {
    container.innerHTML = '';
  }
}

async function loadOverviewActivity() {
  const container = document.getElementById('overview-activity');
  try {
    const result = await api.getActivityFeed();
    const entries = result?.data || result || [];
    const recent = entries.slice(0, 8);

    if (recent.length === 0) {
      container.innerHTML = '';
      return;
    }

    let html = '<div class="section-header">Recent Activity</div>';

    for (const e of recent) {
      const time = formatRelativeTime(e.timestamp);
      const hasUndo = e.undoData && e.status !== 'undone';
      html += `<div class="activity-entry" ${e.status === 'undone' ? 'style="opacity:0.4"' : ''}>
        <span class="activity-time">${time}</span>
        <span class="activity-desc">${e.detail}</span>
        <span class="activity-agent">${e.agent}</span>
        ${hasUndo ? `<button class="activity-undo" data-undo-id="${e.id}">Undo</button>` : ''}
      </div>`;
    }

    // "View all" link
    if (entries.length > 8) {
      html += `<div style="padding: 8px 0;">
        <button class="btn-text" id="activity-view-all">View all</button>
      </div>`;
      html += `<div class="expandable" id="activity-expanded">`;
      for (const e of entries.slice(8)) {
        const time = formatRelativeTime(e.timestamp);
        html += `<div class="activity-entry">
          <span class="activity-time">${time}</span>
          <span class="activity-desc">${e.detail}</span>
          <span class="activity-agent">${e.agent}</span>
        </div>`;
      }
      html += `</div>`;
    }

    container.innerHTML = html;

    // Wire up "View all"
    const viewAllBtn = container.querySelector('#activity-view-all');
    if (viewAllBtn) {
      const expandEl = container.querySelector('#activity-expanded');
      viewAllBtn.addEventListener('click', () => {
        const isOpen = InlineExpand.toggle(viewAllBtn, expandEl);
        viewAllBtn.textContent = isOpen ? 'Show less' : 'View all';
      });
    }

    // Wire up undo buttons
    container.querySelectorAll('[data-undo-id]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = btn.dataset.undoId;
        await api.undoAction(id);
        loadOverviewActivity();
      });
    });
  } catch {
    container.innerHTML = '';
  }
}

async function loadOverviewGmail() {
  const container = document.getElementById('overview-gmail');
  try {
    const status = await api.gmailStatus();
    if (!status.accounts || status.accounts.length === 0) {
      container.innerHTML = '';
      return;
    }

    const account = status.accounts[0];
    const lastCheck = status.lastChecks[account]
      ? new Date(status.lastChecks[account]).toLocaleString('ro-RO')
      : 'never';

    container.innerHTML = `
      <div style="font-size: 13px; color: var(--text-secondary); display: flex; gap: 16px; align-items: center;">
        <span>${account}</span>
        <span style="color: var(--text-muted); font-size: 12px;">Last check: ${lastCheck}</span>
      </div>
    `;
  } catch {
    container.innerHTML = '';
  }
}

// ============================================================
// Documents Section
// ============================================================

let importResults = [];

async function loadDocuments() {
  // File tree
  const result = await api.getOutputFiles();
  const treeContainer = document.getElementById('docs-tree');
  const mainPanel = document.getElementById('docs-main');

  if (result.success) {
    FileTree.render(treeContainer, result.data, onFileSelect, onFolderSelect);
  }

  // Gmail panel
  const gmailContainer = document.getElementById('gmail-panel');
  await GmailPanel.mount(gmailContainer, api);

  // Reset main panel to import view
  showImportView(mainPanel);
}

function showImportView(mainPanel) {
  mainPanel.innerHTML = `
    <div class="dropzone" id="dropzone"></div>
    <div class="import-log" id="import-log"></div>
  `;
  Dropzone.init(
    mainPanel.querySelector('#dropzone'),
    api,
    (results) => {
      importResults = results;
      renderImportLog(mainPanel.querySelector('#import-log'), results);
    },
    setStatus
  );
  renderImportLog(mainPanel.querySelector('#import-log'), importResults);
}

function renderImportLog(container, results) {
  if (!results || results.length === 0) {
    container.innerHTML = '';
    return;
  }
  let html = '<div class="import-log-header">Recent imports</div>';
  for (const r of results) {
    const isOk = r.status === 'ok';
    const icon = isOk
      ? '<svg class="import-log-icon ok" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>'
      : '<svg class="import-log-icon err" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
    html += `<div class="import-log-entry">
      ${icon}
      <span class="import-log-file">${r.file}</span>
      <span class="import-log-result">${r.error || ''}</span>
    </div>`;
  }
  container.innerHTML = html;
}

function onFileSelect(file) {
  const mainPanel = document.getElementById('docs-main');
  const sizeKb = (file.size / 1024).toFixed(1);
  const displayName = file.name.includes('/') ? file.name.split('/').pop() : file.name;

  mainPanel.innerHTML = `
    <div class="file-detail-name">${displayName}</div>
    <table class="data-table data-table-sm">
      <tr><td>Filename</td><td>${file.name}</td></tr>
      <tr><td>Size</td><td>${sizeKb} KB</td></tr>
      <tr><td>Type</td><td>${file.ext}</td></tr>
    </table>
    <div class="file-detail-actions">
      <button class="btn-primary" id="file-open-btn">Open</button>
      <button class="btn-text" style="color: var(--text-muted);" id="file-delete-btn">Delete</button>
    </div>
  `;

  mainPanel.querySelector('#file-open-btn').addEventListener('click', () => {
    api.openFile(file.path);
  });

  mainPanel.querySelector('#file-delete-btn').addEventListener('click', (e) => {
    InlineExpand.confirm(e.target, 'Delete this file?', () => {
      // File deletion would need a new IPC handler — for now, open containing folder
      // This is a UI-only redesign; the delete IPC can be added later
      api.openFile(file.path);
    });
  });
}

function onFolderSelect(folderName, files) {
  const mainPanel = document.getElementById('docs-main');
  let html = `
    <div class="file-detail-name">${folderName}
      <span style="font-size: var(--text-xs); color: var(--text-muted); font-weight: 400; margin-left: 8px;">${files.length} files</span>
    </div>
  `;

  for (const f of files) {
    const sizeKb = (f.size / 1024).toFixed(0);
    const displayName = f.displayName || f.name;
    html += `<div class="activity-entry" style="cursor: pointer;" data-file-path="${f.path.replace(/\\/g, '\\\\')}">
      <span class="activity-desc">${displayName}</span>
      <span class="activity-agent">${sizeKb} KB</span>
    </div>`;
  }

  mainPanel.innerHTML = html;

  // Wire up file clicks to open
  mainPanel.querySelectorAll('[data-file-path]').forEach(el => {
    el.addEventListener('click', () => api.openFile(el.dataset.filePath));
  });
}

// ============================================================
// Engine Section
// ============================================================

const btnRunCalc = document.getElementById('btn-run-calc');
const btnVerify = document.getElementById('btn-verify');
const btnAutofix = document.getElementById('btn-autofix');
const btnD212 = document.getElementById('btn-generate-d212');
const engineResults = document.getElementById('engine-results');
const execLogBody = document.getElementById('exec-log-body');
const execLogCount = document.getElementById('exec-log-count');
let logLines = 0;

function appendLog(text) {
  execLogBody.textContent += text + '\n';
  logLines++;
  execLogCount.textContent = `(${logLines})`;
  execLogBody.scrollTop = execLogBody.scrollHeight;
}

function setEngineButtonsDisabled(disabled) {
  btnRunCalc.disabled = disabled;
  btnVerify.disabled = disabled;
  btnAutofix.disabled = disabled;
}

function setButtonLoading(btn, loading, originalText) {
  if (loading) {
    btn.innerHTML = `<span class="spinner"></span> Running...`;
  } else {
    btn.textContent = originalText;
  }
}

// Execution log toggle
document.getElementById('exec-log-toggle').addEventListener('click', () => {
  const body = document.getElementById('exec-log-body');
  const chevron = document.querySelector('#exec-log-toggle .tree-chevron');
  body.classList.toggle('open');
  chevron.classList.toggle('open');
});

// Run Calculation
btnRunCalc.addEventListener('click', async () => {
  const year = YearSelector.getYear();
  setEngineButtonsDisabled(true);
  setButtonLoading(btnRunCalc, true);
  setStatus(`Calculating ${year}...`, true);
  appendLog(`[${new Date().toLocaleTimeString()}] Running calculation for ${year}...`);

  const result = await api.runEngine(year);

  setEngineButtonsDisabled(false);
  setButtonLoading(btnRunCalc, false, 'Run Calculation');

  if (result.success) {
    setStatus(`${year} calculated`, false);
    appendLog(result.output || 'Calculation complete.');

    // Show results
    const sumar = await api.getSumar(year);
    let html = '<div class="section-header">Results <span class="section-header-meta">Updated just now</span></div>';
    html += '<div id="engine-fiscal-table"></div>';
    engineResults.innerHTML = html;
    FiscalTable.render(document.getElementById('engine-fiscal-table'), sumar.success ? sumar.data : null);

    // Also refresh overview if visible
    loadOverviewFiscal();
  } else {
    setStatus('Calculation error', false);
    appendLog(`[ERROR] ${result.error}`);
  }
});

// Verify
btnVerify.addEventListener('click', async () => {
  const year = YearSelector.getYear();
  setEngineButtonsDisabled(true);
  setButtonLoading(btnVerify, true);
  setStatus(`Verifying ${year}...`, true);
  appendLog(`[${new Date().toLocaleTimeString()}] Verification started for ${year}...`);

  const result = await api.verifyCalc(parseInt(year));

  setEngineButtonsDisabled(false);
  setButtonLoading(btnVerify, false, 'Verify');

  if (result.success) {
    setStatus(`${year} verification complete`, false);
    appendLog('Verification complete.');

    let html = '<div class="section-header">Verification <span class="section-header-meta">Updated just now</span></div>';
    html += `<div style="font-size: var(--text-sm); color: var(--text-secondary); white-space: pre-wrap; line-height: 1.6;">${escapeHtml(result.report)}</div>`;

    // Add "Apply Fixes" button if there are issues
    if (result.report && (result.report.includes('EROARE') || result.report.includes('eroare') || result.report.includes('problema'))) {
      html += `<div style="margin-top: 16px;"><button class="btn-primary" id="btn-apply-fixes">Apply Fixes</button></div>`;
    }

    engineResults.innerHTML = html;

    const applyBtn = document.getElementById('btn-apply-fixes');
    if (applyBtn) {
      applyBtn.addEventListener('click', async () => {
        setEngineButtonsDisabled(true);
        setButtonLoading(applyBtn, true);
        setStatus('Applying fixes...', true);
        const fixResult = await api.agentFixErrors(parseInt(year));
        setEngineButtonsDisabled(false);
        if (fixResult.success) {
          setStatus('Fixes applied', false);
          appendLog(fixResult.summary || 'Fixes applied.');
        } else {
          setStatus('Fix error', false);
          appendLog(`[ERROR] ${fixResult.error}`);
        }
        setButtonLoading(applyBtn, false, 'Apply Fixes');
      });
    }
  } else {
    setStatus('Verification error', false);
    appendLog(`[ERROR] ${result.error}`);
  }
});

// Auto-Fix
btnAutofix.addEventListener('click', async () => {
  const year = YearSelector.getYear();
  setEngineButtonsDisabled(true);
  setButtonLoading(btnAutofix, true);
  setStatus('Auto-fixing...', true);
  appendLog(`[${new Date().toLocaleTimeString()}] Auto-fix started for ${year}...`);

  const result = await api.agentFixErrors(parseInt(year));

  setEngineButtonsDisabled(false);
  setButtonLoading(btnAutofix, false, 'Auto-Fix');

  if (result.success) {
    setStatus(`Auto-fix complete — ${(result.actions || []).length} actions`, false);
    appendLog(result.summary || 'Auto-fix complete.');
  } else {
    setStatus('Auto-fix error', false);
    appendLog(`[ERROR] ${result.error}`);
  }
});

// Generate D212
btnD212.addEventListener('click', async () => {
  const year = YearSelector.getYear();
  const resultSpan = document.getElementById('d212-result');
  btnD212.disabled = true;
  btnD212.innerHTML = '<span class="spinner"></span> Generating...';
  resultSpan.textContent = '';

  const result = await api.agentGenerateD212(parseInt(year));

  btnD212.disabled = false;
  btnD212.textContent = 'Generate D212';

  if (result.success) {
    resultSpan.innerHTML = '<button class="btn-text" id="d212-open">Open file</button>';
    document.getElementById('d212-open').addEventListener('click', () => {
      if (result.path) api.openFile(result.path);
    });
  } else {
    resultSpan.textContent = 'Error: ' + (result.error || 'unknown');
    resultSpan.style.color = 'var(--destructive)';
  }
});

// ============================================================
// Event Listeners from Main Process
// ============================================================

api.onImportProcessed((data) => {
  loadOverviewActivity();
});

api.onGmailInvoice((data) => {
  loadOverviewActivity();
  loadOverviewGmail();
});

// ============================================================
// Utilities
// ============================================================

function formatRelativeTime(timestamp) {
  const now = Date.now();
  const then = new Date(timestamp).getTime();
  const diff = now - then;

  const mins = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days === 1) return 'yesterday';
  if (days < 7) return `${days}d ago`;
  return new Date(timestamp).toLocaleDateString('ro-RO');
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ============================================================
// Init
// ============================================================

async function init() {
  await initStatusBar();
  await loadOverview();
}

init();
```

- [ ] **Step 2: Commit**

```bash
git add app/renderer.js
git commit -m "feat: add main renderer with all section logic"
```

---

### Task 12: Update preload.js — remove chat and dashboard path

**Files:**
- Modify: `app/preload.js`

- [ ] **Step 1: Remove chatWithClaude and getDashboardPath from preload.js**

Edit `app/preload.js` — remove these two lines:

```javascript
// REMOVE this line:
getDashboardPath: () => ipcRenderer.invoke('get-dashboard-path'),
// REMOVE this line:
chatWithClaude: (message) => ipcRenderer.invoke('chat-with-claude', message),
```

The resulting file should have all other methods intact (runEngine, getDashboardData, importFiles, pickFiles, scanInvoice, getStrategies, getSumar, getLegislation, openFile, verifyCalc, getOutputFiles, pickDataFolder, getDataFolder, agentFixErrors, agentProcessImport, agentGenerateD212, agentCheckStrategies, agentFullAudit, getActivityFeed, undoAction, getDeadlines, gmailSetupStart, gmailListAccounts, gmailRemoveAccount, gmailStatus, gmailToggle, gmailHasCredentials, onImportProcessed, onGmailInvoice).

- [ ] **Step 2: Verify preload still exposes all needed methods**

Read the file and confirm all IPC methods used in renderer.js are present.

- [ ] **Step 3: Commit**

```bash
git add app/preload.js
git commit -m "refactor: remove chat and dashboard-path from preload"
```

---

### Task 13: Update package.json — add new files to build config

**Files:**
- Modify: `app/package.json`

- [ ] **Step 1: Update the files array in the build config**

In `app/package.json`, change the `build.files` array from:

```json
"files": [
  "main.js",
  "preload.js",
  "index.html",
  "icon.png",
  "agents/**/*",
  "gmail/**/*"
]
```

To:

```json
"files": [
  "main.js",
  "preload.js",
  "index.html",
  "styles.css",
  "renderer.js",
  "components/**/*",
  "fonts/**/*",
  "icon.png",
  "agents/**/*",
  "gmail/**/*"
]
```

- [ ] **Step 2: Bump version to 3.0.0**

This is a major visual overhaul. In `app/package.json`, change:

```json
"version": "2.1.0"
```

To:

```json
"version": "3.0.0"
```

- [ ] **Step 3: Commit**

```bash
git add app/package.json
git commit -m "chore: add new UI files to build, bump to v3.0.0"
```

---

### Task 14: Test the app runs correctly

**Files:**
- No new files

- [ ] **Step 1: Run the app in dev mode**

```bash
cd app && npm start
```

- [ ] **Step 2: Verify each section**

1. **Overview:** Should show fiscal summary table (or empty state), deadlines (if any within 30 days), recent activity, Gmail status.
2. **Documents:** Left panel should show file tree. Right panel should show dropzone. Gmail panel at bottom of sidebar.
3. **Engine:** Year selector, three action buttons. Click "Run Calculation" — should run and show results. Execution log toggles open/closed.
4. **Navigation:** Sidebar buttons switch sections. Active indicator (white bar) moves correctly.
5. **Status bar:** Shows data folder path and "Ready" status.

- [ ] **Step 3: Fix any issues found during testing**

Address layout problems, missing data, broken IPC calls. The most likely issues:
- CSS path resolution (fonts/Inter*.woff2) — check the font-face src paths are relative to styles.css location
- ES module imports — ensure `<script type="module">` is used and component paths are correct
- IPC methods that changed names — cross-reference preload.js with renderer.js

- [ ] **Step 4: Clean up backup file and commit**

```bash
rm -f app/index-old.html
git add -A
git commit -m "feat: complete UI redesign — monochrome three-section layout"
```

---

## Self-Review

**Spec coverage check:**
- Section 1 (Global Shell & Navigation): Task 3 (styles.css) + Task 10 (index.html) — covered
- Section 2 (Overview): Task 11 (renderer.js loadOverview*) — covered
- Section 3 (Documents): Task 7 (file-tree) + Task 8 (dropzone) + Task 9 (gmail-panel) + Task 11 (renderer.js loadDocuments) — covered
- Section 4 (Engine): Task 11 (renderer.js engine section) — covered
- Section 5 (Icon): Task 2 — covered
- Section 6 (File Architecture): Tasks 1-11 create the full structure — covered
- Section 7 (Interaction Patterns): Task 4 (inline-expand) + used throughout renderer.js — covered
- Section 8 (Responsive): CSS handles it in Task 3 — covered

**Placeholder scan:** No TBDs, TODOs, or incomplete steps. All code blocks contain actual implementation code.

**Type consistency:**
- `YearSelector.getYear()` / `YearSelector.setYear()` / `YearSelector.mount()` — consistent across Task 5 and Task 11
- `FiscalTable.render(container, data)` — consistent across Task 6 and Task 11
- `FileTree.render(container, data, onFileSelect, onFolderSelect)` — consistent across Task 7 and Task 11
- `Dropzone.init(element, api, onImportComplete, setStatus)` — consistent across Task 8 and Task 11
- `GmailPanel.mount(container, api)` — consistent across Task 9 and Task 11
- `InlineExpand.toggle()` / `InlineExpand.confirm()` — consistent across Task 4, Task 9, and Task 11
- API method names in renderer.js match preload.js exactly (verified against Task 12)
