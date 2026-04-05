# PFA Contabilitate — Complete UI Redesign

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Date:** 2026-04-05
**Status:** Design approved

---

## Goal

Complete UI redesign of the PFA Contabilitate Electron app. Replace the current 11,351-line monolithic index.html with a clean, modular, monochrome interface. Consolidate 6 tabs into 3 sections. Remove Chat. Remove iframe dashboard. Google-level minimalism.

## Architecture

Three-section layout (Overview, Documents, Engine) with a narrow icon-only left sidebar. All CSS extracted to a dedicated file. All JS extracted to a renderer module with component files. Native HTML rendering replaces the dashboard iframe. Inline expansion pattern replaces all modals, prompts, and alerts.

## Tech Stack

- Vanilla JS (no framework — matches existing codebase)
- CSS custom properties for theming
- Inter font (bundled locally)
- Electron IPC unchanged (preload.js surface stays the same)

---

## 1. Global Shell & Navigation

### Layout
- Native OS window chrome (no custom titlebar)
- Left sidebar: 56px wide, icon-only, fixed full-height
- Content area fills remaining width and full height
- Bottom status bar: 28px

### Sidebar
- Three section icons stacked vertically at top (Overview: bar-chart-2, Documents: folder, Engine: play-circle — all Lucide-style stroke icons)
- Active indicator: 3px white vertical bar on left edge of active icon
- Icons: monochrome, 20px, stroke style (not filled)
- Hover: icon area gets `#18181b` background
- No text labels

### Status Bar
- Bottom strip, 28px height, `#111113` background
- Content: data folder path (truncated from left with ellipsis), engine status ("Ready" / "Running..."), last audit timestamp
- Text: `#52525b` (zinc-500), 12px
- Only informational — no interactive elements

### Color System
```
--bg:              #09090b     /* app background */
--surface:         #111113     /* cards, panels, sidebar */
--surface-hover:   #18181b     /* hover states, active panels */
--border:          #27272a     /* all borders, dividers */
--text:            #fafafa     /* primary text */
--text-secondary:  #a1a1aa     /* secondary text, labels */
--text-muted:      #52525b     /* tertiary text, disabled, captions */
--accent:          #ffffff     /* primary actions, active indicators */
--destructive:     #ef4444     /* errors only */
--warning:         #f59e0b     /* deadline urgency only */
```

No green anywhere. Monochrome UI. Success states use a checkmark icon, not a color.

### Typography
```
--font-sans:   'Inter', system-ui, -apple-system, sans-serif
--font-mono:   'JetBrains Mono', 'Cascadia Code', 'Fira Code', monospace

--text-xs:     12px    /* captions, status bar */
--text-sm:     13px    /* body text */
--text-base:   14px    /* subheadings, labels */
--text-lg:     18px    /* section headings */
--text-xl:     24px    /* display numbers (fiscal summary values) */

--weight-normal:  400
--weight-medium:  500
--weight-bold:    600
```

Inter font bundled with the app in `app/fonts/`. Loaded via `@font-face` in CSS. No CDN.

### Animations
- All transitions: `150ms ease` (matches current)
- Expand/collapse: `200ms ease` height transition
- Spinner: CSS keyframe rotation, 16px, 2px white border with transparent top
- No pulse, no glow, no bounce

---

## 2. Overview Section

**Purpose:** At-a-glance financial status. Open the app, see everything without clicking.

**Layout:** Single scrollable column, max-width 720px, horizontally centered in content area. Vertical padding 32px top, 24px between sections.

### 2.1 Fiscal Summary

- **Year selector:** Inline. Current year displayed as `--text-lg` heading. Left/right chevron buttons flanking it. Clicking chevrons changes year and refreshes data. Buttons are `--text-muted`, hover to `--text`.
- **Data table:** Two columns — label left-aligned, value right-aligned. Rows separated by 1px `--border` bottom line. Row height 40px. Label in `--text-secondary` at `--text-sm`. Value in `--text` at `--text-base`, `--weight-medium`.
- **Rows displayed:**
  - Venit brut
  - Cheltuieli deductibile
  - Venit net
  - CAS
  - CASS
  - Impozit pe venit
  - Net dupa taxe (this row: `--weight-bold`, slightly larger)
- **Empty state:** If no data for selected year, show "No calculation data for {year}" in `--text-muted`, centered.
- **Data source:** Parsed from SUMAR-CALCUL-{year}.txt via the existing `get-sumar` IPC handler.

### 2.2 Deadlines

- **Visibility:** Only rendered if any deadline is within 30 days. If none, this entire section is absent from the DOM (not hidden — not rendered).
- **Header:** "Deadlines" in `--text-base`, `--weight-bold`.
- **List:** Compact rows. Date on left (`--text-sm`), obligation name on right (`--text-sm`).
  - Within 3 days: both date and name in `--warning`
  - Past due: both in `--destructive`
  - Otherwise: default `--text-secondary`
- **No icons, no badges.** Color shift is the only signal.
- **Data source:** Existing `get-deadlines` IPC handler.

### 2.3 Recent Activity

- **Header:** "Recent Activity" in `--text-base`, `--weight-bold`.
- **List:** Last 8 entries from activity feed.
- **Entry layout:** Single row per entry.
  - Left: relative timestamp ("2h ago", "yesterday") in `--text-muted`, `--text-xs`, fixed 80px width.
  - Middle: one-line description in `--text-sm`.
  - Right: agent name in `--text-muted`, `--text-xs`.
- **Undo:** On hover, a small "Undo" text link appears at right edge (replacing agent name) for reversible actions. `--text-secondary`, underline on hover.
- **Expand:** "View all" link at bottom in `--text-secondary`. Clicking it expands the list inline to show full history (scrollable, max-height 500px). Link text changes to "Show less".
- **Data source:** Existing `get-activity-feed` IPC handler.

### 2.4 Gmail Status

- **Visibility:** Only rendered if at least one Gmail account is connected (check via `gmail-status` IPC). If not connected, this section is absent.
- **Layout:** Single line. Account email in `--text-sm`, last check time in `--text-muted`, invoice count today in `--text-secondary`.
- **No controls here.** Gmail management lives in Documents section.

---

## 3. Documents Section

**Purpose:** Import files, browse documents, manage Gmail connection.

**Layout:** Two-panel horizontal split. Left panel 280px fixed width, `--surface` background. Right panel fills remaining width.

### 3.1 Left Panel — File Tree

- **Structure:** Hierarchical, mirroring Output directory.
  - Year folders at top level (2026, 2025, ...)
  - Inside each year: Facturi, Declaratii
  - Legislatie folder at same level as years (not per-year)
- **Expand/collapse:** Chevron icon rotates 90deg on open (`200ms ease`). Indentation: 16px per level.
- **Folder row:** Chevron + folder name + file count in `--text-muted` (e.g., "Facturi  12"). Height 32px. Hover: `--surface-hover` background.
- **File row:** File icon (tiny, generic document icon) + filename. Height 28px. Hover: `--surface-hover`. Click: selects file, highlights row with left 2px `--accent` border.
- **Data source:** Existing `get-output-files` IPC handler.

### 3.2 Right Panel — Import (default state)

When no file or folder is selected, the right panel shows the import area.

- **Dropzone:** Full panel width, dashed 2px `--border` border, `--text-muted` text centered: "Drop files or click to browse". Drag state: border becomes `--accent` (white). Click triggers `pick-files` IPC.
- **Import log:** Below the dropzone, separated by 24px. Header "Recent imports" in `--text-sm`, `--weight-medium`. Last 10 processed files:
  - Each row: status icon (checkmark or x, 14px), filename in `--text-sm`, result summary in `--text-muted`. Monospace font for filenames.
- **Data source:** `import-files` and `pick-files` IPC handlers. Import events via `onImportProcessed` listener.

### 3.3 Right Panel — File Selected

When a file is clicked in the tree:

- **Filename** as `--text-lg` heading.
- **Metadata table:** label-value rows (same style as fiscal summary but smaller, `--text-xs`).
  - Date imported
  - File size
  - Source (Manual / Gmail)
  - Processing result (if applicable)
- **Actions:**
  - "Open" button — primary style (white border/text). Calls `open-file` IPC.
  - "Delete" text link in `--text-muted`. Click replaces it inline with "Delete this file? Yes / No" — Yes calls delete, No restores the link. No modal, no confirm().

### 3.4 Right Panel — Folder Selected

When a folder is clicked in the tree:

- **Folder name** as `--text-lg` heading, file count beside it in `--text-muted`.
- **File list:** Same rows as the tree but in the right panel with more detail — filename, date, size. Clickable to select individual files.

### 3.5 Gmail Setup (bottom of left panel)

Persistent area pinned to bottom of the left panel.

**Not connected state:**
- "Connect Gmail" button, secondary style, full width of left panel (minus padding).
- Click expands inline below the button (pushes content up if needed):
  - Step 1: "Go to Google Cloud Console, create OAuth credentials"
  - Step 2: "Download credentials.json"
  - Step 3: "Click Authorize below"
  - "Select credentials file" button → file picker for credentials.json (copies to app data dir)
  - "Authorize" button → triggers `gmail-setup-start` IPC → opens browser for OAuth
  - Collapse after successful connection.

**Connected state:**
- Email address in `--text-sm`
- Toggle switch (custom CSS, monochrome) for monitoring on/off. Calls `gmail-toggle` IPC.
- "Disconnect" text link in `--text-muted`. Click → inline confirmation same as file delete.

---

## 4. Engine Section

**Purpose:** Run calculations, verify, fix errors, generate declarations.

**Layout:** Single scrollable column, max-width 720px, horizontally centered (same as Overview).

### 4.1 Controls

- **Year selector:** Same shared component as Overview. Stays in sync — changing year in one section changes it everywhere.
- **Action buttons:** Horizontal row, three buttons, equal width, separated by 8px gap.
  - "Run Calculation" — primary: `--accent` border, `--text` text, transparent bg, hover fills `--accent` bg with `--bg` text.
  - "Verify" — secondary: `--border` border, `--text-secondary` text, same hover pattern but fills `--surface-hover`.
  - "Auto-Fix" — secondary (same as Verify).
- **Running state:** Button text changes to "Running..." with CSS spinner next to it. All three buttons disabled (opacity 0.4, pointer-events none).
- **IPC:** "Run Calculation" → `run-engine`, "Verify" → `verify-calc`, "Auto-Fix" → `agent-fix-errors`.

### 4.2 Results

Not rendered until an action produces output. Appears below controls with 24px gap.

**After calculation:**
- Section header "Results" in `--text-base`, `--weight-bold`, with "Updated just now" timestamp in `--text-muted` to the right.
- Fiscal data table (same component as Overview fiscal summary — shared rendering).

**After verification:**
- Section header "Verification" with timestamp.
- Structured output:
  - Each check area as a sub-header in `--text-sm`, `--weight-medium`.
  - Findings as compact list items. Issues: `--destructive` text. Clean items: `--text-secondary`.
- "Apply Fixes" button appears below only if actionable issues exist. Primary button style. Calls `agent-fix-errors` IPC.

### 4.3 Execution Log

- **Collapsed by default.** Header: "Log" with entry count in `--text-muted`. Chevron expands.
- **Expanded:** Monospace text, `--text-xs`, `--surface` background, 1px `--border` border. Max-height 400px, overflow-y scroll. Auto-scrolls to bottom on new output.
- **Content:** Raw stdout from Python engine and agent processes.

### 4.4 Declaration Generation

- Below the log section, 24px gap.
- "Generate D212" button, secondary style. Calls `agent-generate-d212` IPC.
- Running state: same pattern as control buttons.
- Complete state: inline "Open file" link appears next to the button.

---

## 5. Icon

- **Style:** Monochrome geometric typographic mark.
- **Design:** Stylized "P" in white on black, constructed from clean geometric shapes. Negative-space approach — the letter form emerges from the background rather than sitting on top of it.
- **Sizes:** 256x256 PNG (source), ICO (generated for Windows).
- **Usage:** Window icon, taskbar, tray, NSIS installer.

---

## 6. File Architecture

### Current (to be replaced)
```
app/
  index.html     # 11,351 lines — HTML + CSS + JS, all inline
```

### New structure
```
app/
  index.html           # Semantic HTML only (~200 lines)
  styles.css           # All styling, CSS variables (~400 lines)
  renderer.js          # Main UI logic, event listeners, IPC calls (~600 lines)
  components/
    fiscal-table.js    # Shared fiscal summary table renderer
    file-tree.js       # Document tree with expand/collapse
    dropzone.js        # Drag-drop file import
    inline-expand.js   # Generic expand/collapse behavior
    year-selector.js   # Shared year picker component
    gmail-panel.js     # Gmail setup/status in Documents sidebar
  fonts/
    Inter-Regular.woff2
    Inter-Medium.woff2
    Inter-SemiBold.woff2
  icon.png             # New monochrome icon
```

### What stays unchanged
- `main.js` — all IPC handlers stay as-is
- `preload.js` — IPC surface stays as-is (minus chat methods)
- `agents/` — dispatcher, executor, feed, memory
- `gmail/` — auth.js, monitor.js
- `python/` — bundled runtime
- `scripts/` — bundle-python.js, release.js

### What gets removed
- Chat section (all HTML, all JS functions: `sendChat`, `appendChatMessage`, etc.)
- Dashboard iframe loading and `get-dashboard-path` usage
- All `prompt()`, `alert()`, `confirm()` calls
- All emoji icons used as UI elements
- All inline `onclick="..."` handlers
- All inline `style="..."` attributes
- All `<script>` content from index.html (moves to renderer.js + components/)
- All `<style>` content from index.html (moves to styles.css)

### What gets added
- Inter font files (woff2, bundled)
- `styles.css` external stylesheet
- `renderer.js` entry point
- `components/` directory with 6 modules
- Updated `icon.png`

### Preload.js changes
- Remove: `chatWithClaude` method
- Remove: `getDashboardPath` method (no longer needed — data parsed natively)
- Everything else stays.

### Build config changes
- `package.json` files array: add `styles.css`, `renderer.js`, `components/**/*`, `fonts/**/*`
- Remove chat-related entries if any

---

## 7. Interaction Patterns

### Inline Expansion
All secondary actions use inline expand/collapse instead of modals or system dialogs.

**Pattern:**
1. User clicks trigger element (button or link)
2. Content area expands below the trigger with `200ms ease` height animation
3. Trigger text may change (e.g., "View all" → "Show less")
4. Clicking trigger again or clicking a "Cancel"/"Close" element collapses
5. Only one expansion active per context (opening a new one closes the previous)

**Used for:**
- Activity feed "View all"
- File delete confirmation
- Gmail setup wizard
- Gmail disconnect confirmation
- Execution log

### Inline Confirmation
For destructive actions (delete file, disconnect Gmail):
1. Original element (button/link) is replaced in-place by confirmation text + Yes/No
2. "Yes" executes action and restores original element (or removes the item)
3. "No" restores original element
4. No backdrop, no overlay, no focus trap

### Loading States
- Button text changes to "Running..." + CSS spinner
- All related buttons disable (opacity 0.4)
- Status bar updates with current operation
- On completion: result renders inline, buttons re-enable

### Empty States
- No placeholder boxes or skeleton screens
- Sections that have no data simply don't render
- First-run experience: Overview shows "No calculation data for {year}" in muted text. Documents shows the dropzone. Engine shows controls only.

---

## 8. Responsive Behavior

- **Minimum window:** 900x600 (unchanged from current)
- **Sidebar:** Always 56px, never collapses further
- **Documents left panel:** 280px fixed, does not resize
- **Content max-width:** 720px in Overview and Engine, fluid in Documents right panel
- **No breakpoints needed** — Electron window, not a web page. Fixed minimum handles the constraints.
