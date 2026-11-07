# Changelog

All notable changes to Σuler.SC. Versions follow `MAJOR.MINOR.PATCH`; the
project does not promise backwards compatibility for `settings.json` between
major versions.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

The project has two repositories. The first, [SmartCalculator], covers versions
1.0.0 through 1.3.0 and is kept for the record. From 2.0.0 onward the code
lives here, after a rewrite that replaced the Tkinter interface with a native
window and a WebView.

[SmartCalculator]: https://github.com/M1kLuXamAkLay/SmartCalculator

## [Unreleased]

Nothing yet.

---

## [5.1.17] — 2026-11-06

A pass over the settings screen; the same four fixes as 5.1.16, plus a layout
guard for narrow windows.

### Changed

- **Technical specifications now read like the first-run window:** the same
  key/value rows, the same accent-coloured values and the same pixel font
  (Handjet, 18 px). Before, the profile printed in the monospace result face on
  one colon-separated line, which made the two screens look like different
  applications.
- **A state pill sits beside the heading**, as in the wizard: "Определяю
  конфигурацию…" while the probe runs, "Конфигурация определена" on success,
  "Не удалось определить конфигурацию" if it fails. Re-probing returns it to
  detecting, and a language switch redraws it in the new language.
- **"Запустить сервер" is now "Запустить сервис"** in all seven languages.
- **"Авто следует за системой"** starts with a capital letter, and so do the
  other six language versions of that note.

### Fixed

- **The cancel button only appeared for "Скачать всё".** The busy state was set
  inside that one click handler, so installing the service, starting it and
  pulling a model all ran with no way to stop them. It now lives in
  `startSetup`, the one entry point every download uses.
- **The pill could be pushed out of the card on a narrow window.** The card head
  now wraps, and the pill keeps its place at the right edge at 900 px.

### Verified

- In headless Chromium at 1276 and 900 px: four rows in Handjet at 18 px, the
  pill visible and right-aligned in the card head, its colour following the
  theme (accent when done, error when failed). A language switch keeps both.
- Cancel appears for install, start, pull and setup-all; a cancelled download
  and a failed one both restore the buttons and report the outcome.
- 76 unit tests, 126 scenarios through the public `Api`.

### Known limitations

- While the probe runs the spec block shows "…" rather than skeleton rows; the
  pill carries the state and the rows follow.
- The screenshot in the report shows the previous build: the profile there is
  still one colon-separated line with no pill.

---

## [5.1.16] — 2026-11-06

Settings polish: the hardware card matches the first-run window, and the cancel
button works for every download.

### Changed

- **Technical specifications read like the first-run window.** The profile is
  drawn with the same key/value rows, the same accent-coloured values and the
  same pixel font (Handjet, 18 px). It used to print in the monospace result
  face, so the two screens looked like different applications.
- **A state pill sits beside the heading**, as in the wizard: "Определяю
  конфигурацию…" while the probe runs, "Конфигурация определена" when it
  returns, "Не удалось определить конфигурацию" if it fails. Re-probing sets it
  back to detecting.
- **"Запустить сервер" is now "Запустить сервис"** in all seven languages —
  the button starts the Ollama service, not a bare server process.
- **"Авто следует за системой"** starts with a capital letter, and so do the
  five other language versions of that note.

### Fixed

- **The cancel button only appeared for "Скачать всё".** The busy state was set
  inside that one click handler, so installing the service, starting it and
  downloading a single model all ran with no way to stop them. It now lives in
  `startSetup`, the single entry point every install and download goes through:
  measured in the browser, all four actions show the button.

### Verified

- In headless Chromium: the profile renders four rows in Handjet at 18 px with
  accent values, in both themes; the pill turns done on success and failed on
  error; the button reads "Запустить сервис"; the note is capitalised.
- Cancel appears for install, start, pull and setup-all; a cancelled download
  and a failed one both restore the buttons and report the outcome.
- 76 unit tests, 126 scenarios through the public `Api`.

### Known limitations

- The empty state while probing still shows a plain "…" in the spec block
  rather than skeleton rows; the pill covers the state, the rows follow.

---

## [5.1.15] — 2026-11-06

The dark keypad is rebuilt for the dark background; the light theme is untouched.

### Fixed

- **Shift / Alt / AC / Del sat 1.12:1 from the function row below them** — two
  nearly identical maroons, one degree apart in hue (349 and 348). That is the
  pair that made the eye work. The modifiers are now a pale slate blue at hue
  224, separated from the functions by 1.65:1 and 109 degrees of hue.
- **The ochre turned brown.** At saturation 0.30 a warm fill at low lightness is
  mud, not gold. The amber is now chroma 0.74 at hue 40.

### Changed

- **A dark palette built for this background** instead of reusing the light
  theme's hues: pale slate blue for modifiers, mauve-wine for functions, rose
  for digits, coral for arithmetic, steel blue for constants and the run key,
  amber for the variable and comparisons, indigo for saved matrices.
- **The slate blue is paler than the previous build's**, as asked: lightness
  0.475 against 0.36 before.
- Every adjacent pair now clears 1.20:1 of luminance or 24 degrees of hue; the
  closest pair on the keypad is 1.07 at 31 degrees (a digit beside a coral
  operator), and those are also divided by the key rim.
- White labels are 5.00:1 or better (was 6.12 minimum, but at the cost of the
  muddy fills), and every key clears the body colour by 1.29:1 or more.

### Verified

- Both dark variable blocks (the `[data-theme="dark"]` one and the
  `prefers-color-scheme` one) carry the same values; the light theme's fills are
  byte-identical to 5.1.14.
- In headless Chromium, dark theme: six fills at saturation 0.18-0.42, plus the
  amber at 0.74; minimum label contrast 5.00.
- 76 unit tests, 126 scenarios through the public `Api`.

### Known limitations

- Judged from contrast ratios and a headless render, not from the Windows
  window. The amber is deliberately more saturated than its neighbours; if it
  still reads too strong, its chroma is the one number to turn down.

---

## [5.1.14] — 2026-11-06

Muted dark keypad; the light theme is unchanged.

### Changed

- **The dark keypad sits in the panel instead of glowing on it.** Saturation
  drops from 0.50-0.70 to 0.17-0.30, and every fill is taken closer to the body
  colour, so the keys read as part of the window.
- **Blue joins the palette.** The constants (π, e, ∞, and the run key) and the
  saved matrices take a desaturated slate blue — hue 204 and 236 at 0.17-0.26
  saturation — the two cool notes in an otherwise rose keypad.
- Fills are spread on a lightness ladder so neighbours still separate: modifiers
  0.33, variable 0.37, functions 0.36, constants 0.37, arithmetic 0.40, digits
  0.43. White labels stay at 6:1 or better; every key clears the body colour by
  at least 1.24, so nothing melts into the background.
- **The light theme keeps the swatch palette** from 5.1.13 unchanged; only the
  dark blocks were rewritten.

### Verified

- In headless Chromium, dark theme: six fills at saturation 0.17-0.30, minimum
  label contrast 6.12, minimum key-to-body separation 1.24.
- Every adjacent pair separates by 1.09:1 of luminance or 17 degrees of hue; the
  pairs that match in brightness (π beside ×, for example) are 168 degrees apart
  in hue and are also divided by the key rim.
- 76 unit tests, 126 scenarios through the public `Api`.

### Known limitations

- The palette was judged by contrast ratios and a headless render, not in the
  Windows window. The light theme was not changed, so it is unaffected.

---

## [5.1.13] — 2026-11-06

Key palette taken from the supplied swatch.

### Changed

- **The key colours now come from the palette swatch**, sampled from the image:
  pale pink `#F7C3CF`, salmon `#E78B90`, coral `#FB6767`, magenta `#E0187B`,
  deep magenta `#A60169`, on its purple background `#43305E`.
  - *Light theme* uses the pale end — pink digits, salmon arithmetic, a
    lavender-pink function block, a paler magenta for the constants, deeper
    coral for the variable and comparisons, lavender for the saved matrices.
    One dark label, `#43305E` — the swatch's own background — on every key.
  - *Dark theme* uses the same hues at full saturation: magenta digits, wine
    functions, deep coral arithmetic, bright magenta constants and a violet
    accent for the matrices, with one white label on every key.
- Fills were fitted to the pairs that touch on the grid: 1.10:1 apart, or 20
  degrees of hue where lightness is close. The tightest label contrast is 4.54
  in the light theme and 4.95 in the dark.

### Fixed

- **"=" had a white label in the light theme.** Two older rules upstream set a
  fill and a label of their own, so one key broke the single-label rule while
  its neighbours followed it. Both rules now set only the size and weight.

### Verified

- In headless Chromium: one label colour per theme on the calculator and matrix
  keypads, six distinct fills, no label below 4.5:1.
- 76 unit tests, 126 scenarios through the public `Api`.

### Known limitations

- Judged from the contrast numbers and a headless render; the palette has not
  been looked at in the Windows window.

---

## [5.1.12] — 2026-11-06

Parser repairs, one label colour, and a new key palette.

### Fixed

- **`log_9(9)` was rejected as an unknown name.** MathLive writes a base
  without braces (`\log_9`), while the rewrite only looked for `\log_{9}`, so
  the subscript survived into `log_9(9)` and the validator refused it. Bases are
  now read in both forms, in the interface and in the engine, with bracket
  counting so `log_2(sin(x)+1)` works.
- **`log` and `ln` were the same function.** The keypad gives `log` the inverse
  `10^x`, so it is the base-10 key; it parsed as the natural logarithm. `log` is
  now base 10, `ln` stays natural, and `log10` (what the interface sends for
  `lg`) is a known name instead of an unknown one.
- **An equation with no solution answered `ok: true` with the text
  "ExprError.no_solution".** The window printed the raw key. It is now a proper
  error, so the message reads "no real solutions".
- **`x^2 + 1 = 0` reported "not solvable"** instead of the complex pair; an
  invalid `isinstance` against `sp.EmptySet` raised and was swallowed.
- **Matrix operations sent long names** ("determinant", "inverse") reached the
  engine as unknown operations; the keypad sends the short ones. Both now work.

### Changed

- **One label colour on every keypad, in both themes.** Every key fill is dark
  enough for a white label, so the digits, the arithmetic column and the
  function block no longer mix white and dark captions. The earlier rules set a
  dark caption on two groups and left them looking grey.
- **New key palette.** The light theme no longer uses the near-white, grey and
  near-black keys: one rose family carries the structure, with one accent per
  role — pine for constants and the run key, ochre for the variable and
  comparisons, violet for saved matrices, brick for arithmetic. The dark theme
  shifts the operators toward red by changing the colour rather than the
  brightness. Fills were fitted to the pairs that actually touch on the grid:
  1.12:1 apart, or 27 degrees of hue where lightness is close.

### Verified

- **126 scenarios through the public `Api`** — the same layer the window calls:
  calculator, logarithms in five notations, equations, systems, analysis,
  calculus, plotting, matrix operations, saved matrices, display forms, step
  solutions, the reference, and the input guardrails. All pass.
- 76 unit tests. In headless Chromium, both themes: six distinct fills and a
  single white label on the calculator and matrix keypads, no label below 4.5:1.

### Known limitations

- The palettes were judged by contrast ratios and rendered in a headless
  Chromium; nobody has looked at them in the Windows window yet.
- Logarithms with a base arrive as a ratio of natural logarithms, so a solution
  step may show `log(8)/log(2)` rather than `log₂(8)`.
- The graphical parts (installer pages, first-run window) were checked headless.

---

## [5.1.11] — 2026-11-06

Logarithm bases, "=" size and colour.

### Added

- **Logarithms accept a base.** The log key inserts `\log_{⬚}(⬚)` with two
  slots: the base and the argument, shown as log₂(2). Bases can be any
  expression, including a fraction or a nested call. The plain-text form is a
  ratio of natural logarithms, so `log₂(8)` evaluates to `3` and `log₂(1/8)` to
  `−3`; a logarithm written without a base stays natural, as before.
  The base is read with bracket counting, so `\log_{2}(\sin(x)+1)` works. The
  previous generic subscript rule deleted `_{2}` and silently turned every
  logarithm into the natural one.

### Changed

- **The "=" key is smaller:** 34 px instead of 42 (30 px in the equation panel's
  keypad, where the whole pad is scaled down).
- **The "=" key has the same fill as π, e and ∞** in both themes: one constant
  colour, so the keypad no longer has a separate green run key. Its rim is
  lighter than the neighbouring keys', which keeps the run key findable.

### Verified

- In headless Chromium: the log key inserts both slots, `\log_{2}(8)` reaches
  the engine as `(log(8)/log(2))` and answers 3; `log₂(1/8)` answers −3; the
  "=" fill equals the π/e/∞ fill on the calculator, matrix and equations
  keypads in both themes, at 34 px (30 px inline).
- Solver tests for the ratio form, and for a logarithm without a base.

### Known limitations

- The nested `\log_{2}(\sin(x)+1)` case was checked through the plain-text
  conversion only, not through the real window on Windows.
- The graphical parts were checked in headless Chromium with a stub engine.

---

## [5.1.10] — 2026-11-06

Keypad grouping and contrast between key families.

### Fixed

- **The matrix keypad slid out of alignment.** Its keys were made by filtering
  the comparison row out of the base layout, so each row lost one key and the
  grid pulled the next row's keys up: `7 8 9 × ÷ 4` shared one line. The matrix
  keypad is now built as explicit rows of six, the same way as every other tab
  (54 keys, nine rows). The decimal point also left the arithmetic group and
  belongs to the digits, where it is used.

### Changed

- **Each key family has its own fill** in both themes: modifiers, digits,
  arithmetic, functions, constants, variable and comparisons, saved matrices,
  and the run key. Fills were picked with a contrast study against the pairs
  that actually touch on the grid — every adjacent pair is at least 1.9:1, or
  at least 25 degrees of hue apart where lightness alone was not enough.
- **A 1 px rim** in the page colour separates neighbouring keys where two fills
  are close in lightness (the decimal point next to the run key, for example).
- **Constant keys** (π, e, ∞) are a deeper teal; they sit directly above the
  pale arithmetic row and previously merged with it.

### Verified

- Measured in headless Chromium, light and dark themes: 48 keys in eight rows
  on the calculator and 54 in nine on the matrix tab, every row exactly six
  keys; seven distinct fills per keypad; label contrast 4.6:1 or better on every
  group.

### Known limitations

- The strongest measured contrast between two adjacent fills is 1.7:1 for the
  decimal point beside the run key; the rim, not the fill, does the separating
  there. Judging that in the real window still needs a look on Windows.
- The graphical parts were checked in headless Chromium with a stub engine, not
  on Windows.
- Export files go straight to the exports folder; there is no save dialog.

---

## [5.1.9] — 2026-11-06

Result height, the delete-model button, first-run alignment, and a verified
installer build.

### Changed

- **Graph tab: the Result card is 10 px lower.** Its top edge sits at 570 px
  instead of 561 px in a 905 px window, and the card is 300 px high instead of
  310 px; the cards above take the difference.
- **First-run window:** both underlined lines are 15 px (were 13 px). The note
  and the buttons share one row: the note is vertically centred with the
  buttons (measured offset 0 px) via a footer wrapper, and the window is 282 px
  high instead of 303 px.
- **Delete model runs as a background job.** It shows the same busy state as a
  download, blocks a second click, reports progress in the status line and
  starts the service first when it is stopped.

### Fixed

- **"Delete model" answered "no models installed"** when the installed list was
  populated but nothing was selected. The first installed model is preselected,
  and a single installed model is used even if the selection was cleared. A
  genuinely empty list still says "no models installed"; a non-empty one with
  several models now says "pick a model from the list" in all seven languages.
- **The finished deletion was invisible:** the button waited for a synchronous
  answer while the backend reports through `onDeleteDone`. It now listens for
  that event, clears the busy state, shows the model name and applies the
  active-model fallback.

### Verified

- **The installer builds.** `makensis build/installer.nsi` finishes with exit
  code 0 and produces a valid NSIS self-extracting PE32 executable (6 languages,
  4 sections, 193 KB with a stub bundle). The build was made on Linux against a
  stub application directory, so it checks the script, not a real install.

### Known limitations

- The installer was not run on Windows, and was built against a stub bundle
  rather than a PyInstaller output; a real `build.bat` run is still needed.
- Model deletion was exercised against a stub bridge; a real multi-gigabyte
  delete was not performed.
- The two other graphical points from the previous round remain unverified on
  Windows: the `=` key shape and the matrix input frame.
- Export files are not offered in a dialog any more; users find them in the
  exports folder.
- The dark theme keeps its previous key colours; the contrast change is for the
  light theme only.
- Inequalities with two or more unknowns are not solved step by step.
- The installer offers six languages; Bengali is available in the application
  only.

---

## [5.1.8] — 2026-11-06

Layout fixes, lighter comparison signs, one cancel for downloads, and a
clean stop on exit.

### Added

- **One cancel button for every download in Settings.** It appears while the
  service or a model is being installed or downloaded. Cancelling stops the
  transfer, removes an incomplete installer file, rolls back a half-written
  service install, and leaves no partial model under its name. The other
  download buttons are disabled while a job runs.
- **Safe stop on exit.** Closing the window cancels any running download or
  install, then stops the Ollama service the application started. A service that
  was already running before the window opened is left alone.

### Changed

- **Graph tab: the Result card height follows the green line** on the reference
  screenshot: the lower part of the pane, below the graph, with the cards above
  it taking the rest.
- **Comparison signs** (`< > ≤ ≥`) use a lighter font weight (500) and the
  system symbol face, so they no longer look like solid blocks next to `=`.
- **First-run window:** the note reads "Определяется при первом запуске" and sits
  on the same row as the buttons, so the window is shorter.
- **Keypad symbols** are a little larger on all keypads.
- **Matrix keypad:** the comma key is removed (with `x`, `<`, `>`, `≤`, `≥`).

### Fixed

- **The matrix input field** is drawn with its own border and background, so it
  fills the frame in the matrix tab as in the reference screenshot.

### Known limitations

- The cancel button and the exit stop were checked by the backend tests and in
  headless Chromium with a stub engine; a real download was not cancelled on
  Windows.
- The graphical parts (installer pages, first-run window, graph tab, keypads)
  were checked in headless Chromium, not on Windows.
- Export files are not offered in a dialog any more; users find them in the
  exports folder.
- The dark theme keeps its previous key colours; the contrast change is for the
  light theme only.
- Inequalities with two or more unknowns are not solved step by step.
- Matrices are not drawn with round brackets and column alignment yet.
- The installer offers six languages; Bengali is available in the application
  only.
- The Bengali texts need review by a native speaker.

---

## [5.1.7] — 2026-11-06

Result card height and trigonometric equations.

### Changed

- **Graph tab: the Result card is proportional again**, and shorter than in 5.1.5.
  It keeps about 28 % of the pane height (235 px at 905 px window height, 193 px
  at 760 px) instead of the fixed 298 px of 5.1.6. The cards above take the rest.

### Fixed

- **Trigonometric equations were reported as "cannot parse the expression".**
  `sin^2(x) - 5sin(x) + 6 = 0` and similar are now solved by substitution:
  `t = sin(x)`, solve the quadratic, then return to `x`. A root outside [-1; 1]
  gives **no solution** instead of `asin(2)` presented as an answer.
  `sin^2(x) - 3sin(x) + 2 = 0` returns `x = π/2 + 2πk`.
- **`solveset` raising an exception** on an unusual relation no longer surfaces as
  a parse error; the substitution path is tried first.

### Known limitations

- The equation panel was exercised through the real browser pipeline
  (MathLive → plain text → solver) for the cases above; other unusual notations
  may still reach the parser unchanged.
- The graphical parts (installer pages, first-run window, graph tab, keyboard
  sizes and colours) were checked in a headless Chromium with a stub engine, not
  on Windows.
- Export files are not offered in a dialog any more; users find them in the
  exports folder.
- The dark theme keeps its previous key colours; the contrast change is for the
  light theme only.
- Inequalities with two or more unknowns are not solved step by step.
- Matrices are not drawn with round brackets and column alignment yet.
- The installer offers six languages; Bengali is available in the application
  only.
- The Bengali texts need review by a native speaker.

---

## [5.1.6] — 2026-11-06

Graph tab height, arithmetic key size and the matrix input.

### Changed

- **Graph tab: the Result card is 298 px high** (was 306 px), a quarter of the
  height of the **Keyboard** button (31 px) less. The space goes to the input and
  graph cards above it.
- **Arithmetic symbols are smaller on every keyboard:** `+ − × ÷ , .` are 30 px
  (main keypad), `< > ≤ ≥` 22 px. The inline keypad and the matrix keypad are
  scaled the same way. The **=** key is unchanged.

### Fixed

- **The matrix tab input moved out of its frame.** The input now sets its own
  border, outline and background, so it no longer depends on the default look of
  the editor's shadow element, which differs between engines.

### Known limitations

- The matrix input fix was checked by geometry and computed styles in headless
  Chromium; the look in the Windows WebView2 window was not checked.
- The graphical parts (installer pages, first-run window, graph tab, keyboard
  sizes and colours, Enter in the calculator) were checked in a headless
  Chromium with a stub engine, not on Windows.
- Export files are not offered in a dialog any more; users find them in the
  exports folder or via the **Open export folder** button.
- The dark theme keeps its previous key colours; the contrast change is for the
  light theme only.
- Inequalities with two or more unknowns are not solved step by step.
- Matrices are not drawn with round brackets and column alignment yet.
- Curve labels on the graph itself are not drawn; only the legend is.
- The installer offers six languages (Russian, English, Simplified Chinese,
  Spanish, French, Portuguese). NSIS has no Bengali language file, so Bengali is
  available in the application only.
- The Bengali texts are new translations and need review by a native speaker.
- The first solution PDF export takes a second or two longer while matplotlib
  builds its font cache.

---

## [5.1.5] — 2026-11-06

First-run hand-over to Settings.

### Changed

- **Install and start** closes the first-run window, opens the **Settings** tab
  and starts the download of the Ollama service and the recommended model there.
  Progress, cancel and errors appear in the Settings card, the same as when the
  download is started from Settings.

### Known limitations

- The graphical parts (installer pages, first-run window, graph tab, keyboard
  sizes and colours, Enter in the calculator) were checked in a headless
  Chromium with a stub engine, not on Windows.
- Export files are not offered in a dialog any more; users find them in the
  exports folder or via the **Open export folder** button.
- The dark theme keeps its previous key colours; the contrast change is for the
  light theme only.
- Inequalities with two or more unknowns are not solved step by step.
- Matrices are not drawn with round brackets and column alignment yet.
- Curve labels on the graph itself are not drawn; only the legend is.
- The installer offers six languages (Russian, English, Simplified Chinese,
  Spanish, French, Portuguese). NSIS has no Bengali language file, so Bengali is
  available in the application only.
- The Bengali texts are new translations and need review by a native speaker.
- The first solution PDF export takes a second or two longer while matplotlib
  builds its font cache.

---

## [5.1.4] — 2026-11-06

First-run window and exports.

### Changed

- **Exports go straight to the exports folder.** Solution PDF, LaTeX and graph
  PDF are written to the `exports` folder in the application data directory,
  with no save dialog. Each file gets a time stamp, so earlier exports are kept.
  The status line shows the full path, and **Open export folder** opens it.
- **First-run window is more compact.** The empty space between the hardware
  box and the buttons is gone, and the window is 440 px wide (was 470 px).
- **The note "determined once at first launch"** moved from the Technical
  specifications card in Settings into the first-run window, under the box.

### Fixed

- **The Settings hardware card showed the note as a placeholder** while the
  hardware was being detected; it shows "loading" now.

### Known limitations

- The graphical parts (installer pages, first-run window, graph tab, keyboard
  sizes and colours, Enter in the calculator) were checked in a headless
  Chromium with a stub engine, not on Windows.
- Export files are not offered in a dialog any more; users find them in the
  exports folder or via the **Open export folder** button.
- The dark theme keeps its previous key colours; the contrast change is for the
  light theme only.
- Inequalities with two or more unknowns are not solved step by step.
- Matrices are not drawn with round brackets and column alignment yet.
- Curve labels on the graph itself are not drawn; only the legend is.
- The installer offers six languages (Russian, English, Simplified Chinese,
  Spanish, French, Portuguese). NSIS has no Bengali language file, so Bengali is
  available in the application only.
- The Bengali texts are new translations and need review by a native speaker.
- The first solution PDF export takes a second or two longer while matplotlib
  builds its font cache.

---

## [5.1.3] — 2026-11-06

Step-solver for inequalities, localised step captions, keyboard symbols and
contrast, and a shorter result card on the graph tab.

### Added

- **Inequalities in the step-solver.** `<`, `>`, `≤`, `≥` are solved step by
  step: the standard form, the critical points, the sign of the function on each
  interval, and the solution set (`x ∈ (−∞; −2) ∪ [1; +∞)`). Up to ten
  intervals get a sign line; more intervals skip the table and show the answer.
- **Numbered roots.** Equations with several roots list them as `x_1 = …,
  x_2 = …` in one step. An equation with no real roots shows `∅`.

### Changed

- **Graph tab.** The result card is about 16 px shorter; the height goes to the
  input and graph cards above it. The legend under the small graph is removed;
  the fullscreen graph keeps its legend with the coloured formulas.
- **Keyboard symbols are larger:** `+ − × ÷ < > ≤ ≥ , .` are 34–38 px (26 px in
  the small inline keypad). The **=** key is 44 px and white in every theme.
- **Coloured keys have more contrast** in the light theme: function keys are a
  darker burgundy with white text, operator keys are a lighter pink with dark
  text. The Shift-related keys (SHIFT, ALT, AC, DEL and the inverse labels) are
  unchanged.
- **The server button** reports **«Сервер уже запущен»** (Server is already
  running) when Ollama is running, and **«Сервер запущен»** after a start. It
  showed `ok` before.
- **PDF formulas** use `\dfrac` (full-size fractions) and `\leq`/`\geq`, so
  inequality formulas are typeset instead of falling back to plain text.

### Fixed

- **Step captions shown in English in every language:** "Solve for the variable",
  "The unknown is in the exponent…", "is outside [-1; 1]" and "Back-substitute"
  are translated.
- **An empty root list** showed the raw key `step.cap.solve_variable`.
- **Inequalities** typed in the step-solver were treated as equations (or as an
  error), so `x^2-4<=0` failed with a syntax error.

### Known limitations

- The graphical parts (installer pages, first-run window, graph tab, keyboard
  sizes and colours, Enter in the calculator) were checked in a headless
  Chromium with a stub engine, not on Windows. The screenshots were not reviewed
  by eye.
- The dark theme keeps its previous key colours; the contrast change is for the
  light theme only.
- Inequalities with two or more unknowns are not solved step by step.
- Matrices are not drawn with round brackets and column alignment yet.
- Curve labels on the graph itself are not drawn; only the legend is.
- The installer offers six languages (Russian, English, Simplified Chinese,
  Spanish, French, Portuguese). NSIS has no Bengali language file, so Bengali is
  available in the application only.
- The Bengali texts are new translations and need review by a native speaker.
- The first solution PDF export takes a second or two longer while matplotlib
  builds its font cache.

---

## [5.1.2] — 2026-11-06

Analysis tab layout, automatic graph redraw, LaTeX legend, and clean formulas
in steps and PDF exports.

### Added

- **Legend with LaTeX formulas under both graphs.** Each function has a colour
  stripe and its formula in the same colour; the fullscreen graph shows the same
  legend. The fullscreen header now shows only the title.
- **Ctrl+Enter runs the full analysis** on the analysis tab.

### Changed

- **Analysis tab layout.** The input card and the graph card are the same height.
  The **Graph** button is removed: the graph redraws about 0.2 s after any change
  to a function. The result card fills the space down to the bottom edge. A long
  list of functions scrolls inside the input card, so the result does not move.
- **1/x is a stacked fraction** on the calculator keypad, like a/b.
- **Unit coefficients are not written.** Steps show `x^{2} - 5x + 6 = 0` instead of
  `1x^{2} + -5x + 6 = 0`, and a leading `-1` shows as a minus sign. Coefficient
  lists such as `a = 1` keep their values, because there they state a number.

### Fixed

- **The PDF title showed the raw key** (for example `step.title.quadratic`). It is
  now the translated title.
- **PDF step captions showed raw keys** (for example `step.cap.coefficients`). They
  are translated, as on screen.
- **A negative-discriminant step in substitution was English in every language.**
  It now uses the translated caption.
- **A slow graph response could replace a newer one.** Only the latest request is
  drawn now.

### Known limitations

- The graphical parts (installer pages, first-run window, graph tab, fullscreen
  legend, stacked fractions on the keys, Enter in the calculator) were checked by
  code review and automated tests only; they have not been run on Windows.
- Matrices are not drawn with round brackets and column alignment yet.
- Curve labels on the graph itself are not drawn; only the legend is.
- Step-by-step wording has been reviewed only in part.
- The installer offers six languages (Russian, English, Simplified Chinese,
  Spanish, French, Portuguese). NSIS has no Bengali language file, so Bengali is
  available in the application only.
- The Bengali first-run text is a new translation and needs review by a native
  speaker.
- The first solution PDF export takes a second or two longer while matplotlib
  builds its font cache.

---

## [5.1.1] — 2026-11-06

Calculator Enter fix, graph layout with a function legend, typeset formulas in
the solution PDF, and first-run wording in the chosen language.

### Added

- **Graph legend.** Under the graph, one row per function: a colour square and
  its formula (y1 = …, y2 = …). The colours match the function rows.
- **Typeset formulas in the solution PDF.** Fractions, roots and powers are drawn
  with matplotlib's math engine, so no LaTeX installation is needed. A formula
  the engine cannot draw is written as plain text. matplotlib is a runtime
  dependency now and is no longer excluded from the packaged build.

### Changed

- **Analysis tab layout.** The analysis input sits on the left and the graph on
  the right, both at the top. The result spans the full width below them. On
  narrow windows (under 900 px) the graph moves under the input.
- **First-run window wording.** The lead line is formal in all seven languages:
  "Detecting system parameters and selecting a suitable language model". The model
  reason is built in the interface from its numbers, so it follows the chosen
  language; before, the English sentence came from the Python side.
- **First-run status badge.** Beside the title: "Detecting configuration…",
  "Configuration determined" or "Could not determine configuration", in all seven
  languages.
- **The a/b key shows a stacked fraction** instead of the text "a/b".
- **Larger text.** Regular buttons 17 px (was 16), small buttons 15 px (was 14).
  Keyboard keys are 2–3 px larger, including the matrix keypad.
- **The matrix name label** ("Name") is 14 px and vertically centred beside the
  buttons.

### Fixed

- **Enter in the calculator** evaluates the expression. The editor took Enter
  first and inserted a line break, and Ctrl+Enter evaluated twice, which produced
  the error "Syntax error in expression".
- **Solution PDF formulas** were plain text in 5.1.0; they are typeset in 5.1.1.

### Known limitations

- The graphical parts (installer pages, first-run window, graph tab, stacked
  fraction on the key, Enter in the calculator) were checked by code review and
  automated tests only; they have not been run on Windows.
- Matrices are not drawn with round brackets and column alignment yet.
- Curve labels on the graph itself are not drawn; only the legend is.
- Step-by-step text has not been reviewed for wording in this release.
- The installer offers six languages (Russian, English, Simplified Chinese,
  Spanish, French, Portuguese). NSIS has no Bengali language file, so Bengali is
  available in the application only.
- The Bengali first-run text is a new translation and needs review by a native
  speaker.
- The first solution PDF export takes a second or two longer while matplotlib
  builds its font cache.

---

## [5.1.0] — 2026-11-05

Installer language, first-run window, Ollama download reliability, PDF export,
and graphs with up to four functions.

### Added

- **Installer languages.** The installer offers Russian, English, Simplified
  Chinese, Spanish, French and Portuguese (Brazil). The chosen language is
  written to `HKCU\Software\EulerSC\Language` and the application uses it on
  first launch. Bengali is available in the application only.
- **Ollama download progress and cancel.** The installer download shows its
  percentage and size in the settings card and in the first-run window. A
  **Cancel** button stops the download or install; a cancelled download keeps
  nothing under the final name, and a cancelled install is rolled back.
- **Resumable, verified downloads** (`euler/core/download.py`). An interrupted
  transfer resumes with an HTTP `Range` request. The final file is checked
  against its size and SHA-256; a corrupt file is removed. Covered by
  `tests/test_download.py` against a local HTTP server that cuts connections,
  ignores `Range` and serves corrupt bytes.
- **Closing the application stops every download.** The window's close handler
  sets the cancel flag, kills the child installer process tree and waits up to
  15 seconds for the worker to finish before stopping Ollama.
- **PDF export of a solution as a worked answer.** Title with a rule, numbered
  steps, each formula on a tinted panel, and the answer in a bordered box, with a
  page footer. Formulas are written as readable plain text, not typeset LaTeX.
- **PDF export of the fullscreen graph.** The graph is saved as an image on a
  page with its caption, through the same save dialog as the solution export.
- **Export folder button.** Opens the folder where exports are saved when no
  save dialog is available.
- **Up to four functions on one graph.** Each function has its own colour
  (burgundy, blue, green, orange) and a legend under the graph header. The
  full analysis runs on the function marked with the circle (◉).
- **Localised strings** for the new controls, for the engine errors
  `ExprError.ai_looping`, `ExprError.comma_outside_call` and
  `ExprError.not_a_function`, for the answer-form labels (exact, decimal,
  scientific, mixed, radical) and for the looping notice.

### Changed

- **Analysis tab layout.** The analysis card is a vertical stack: the function
  rows, the extremum interval and the buttons. The graph sits directly below it
  and the result under the graph.
- **First-run window** is a card in the same style as the settings cards, about
  470 px wide. Hardware details are laid out as aligned rows. The hard-coded
  light box that stood out in dark themes is removed.
- **The graph has no Y-axis caption and no "Fit Y" buttons** (inline or
  fullscreen). The auto-scale routine was removed.
- **The installer no longer offers "Show README"** on the finish page.
- **The licence text lists bundled components** with the licence type first,
  aligned to the left edge.
- **Settings:** the "Hardware" card is titled "Technical specifications" in all
  seven interface languages.
- **The answer-form chip** shows a localised name instead of the engine key.
### Fixed

- **The installer language was ignored.** The default language in settings was
  `ru`, so the first launch never used the installer's choice.
- **`setup_all` called `pull` with an argument it does not accept**, so a model
  download would have failed with a `TypeError`.
- **A cancel flag stayed set after a cancel**, so the next Ollama action was
  cancelled at once. The flag is now cleared at the start of every job.
- **The Ollama installer stage showed a raw key** ("installing") instead of text.
- **The Ollama download showed no progress** because only the model download
  reported it.
- **Ollama and graph export methods were missing from the bridge allow-list**,
  so the new buttons would have been refused.

### Known limitations

- The graphical parts (installer pages, first-run window, graph tab, stacked
  fraction on the key, Enter in the calculator) were checked by code review and
  automated tests only; they have not been run on Windows.
- The Ollama installer is run with `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART
  /SP-`. These are Inno Setup switches; `/S` is an NSIS switch and does not
  suppress the Ollama installer window.
- The solution PDF uses matplotlib, so the first export in a session takes a
  second or two longer while its font cache is built.
- The installer offers six languages (Russian, English, Simplified Chinese,
  Spanish, French, Portuguese). NSIS has no Bengali language file, so Bengali is
  available in the application only.
- Matrices are not drawn with round brackets and column alignment yet.
- Step-by-step text has not been reviewed for wording in this release.
- The Bengali first-run text is a new translation and needs review by a native
  speaker.

---

## [5.0.3] — 2026-11-04

AI panel layout.

### Changed

- **The model name shows in the AI card header.** The chip beside "Решение с
  ИИ" used to read "—" until an answer had started, and then "Модель: …". It now
  shows the model name alone, set from the saved settings on startup and updated
  when the model changes, when an answer starts, and after a deletion falls back
  to another model. The full label is kept as a tooltip.
- **The input panel sits at the bottom of the card.** An empty status line
  reserved 16 px plus a gap beneath the buttons, which read as dead space. The
  status line is hidden while it is empty, so Photo, New dialog, Stop and Send
  sit at the bottom edge.

---

## [5.0.2] — 2026-11-04

Graph fixes from testing the small card and the fullscreen view.

### Fixed

- **Axis labels changed density while dragging on the small graph.** The
  x-axis label rule skipped any tick closer than 46 px to the previously
  labelled one, so which ticks were labelled depended on where they sat at that
  exact frame. The same axis read every 1 unit at one pixel position and every 2
  at the next, and the labelled set flickered as the mouse moved. The label
  multiple is now chosen once per redraw from the pixel width of one grid step,
  and labels are placed on whole multiples of it. The y-axis had the same rule
  (22 px) and gets the same fix. The label set is now a property of the zoom
  level, not of the drag.
- **Stray element beside the close button in the fullscreen header.** The
  function-title strip used `overflow-x: auto`, which draws a scrollbar whenever
  the typeset formula is wider than its box. It now uses hidden overflow with
  an ellipsis.

### Changed

- **Fullscreen graph uses the whole screen.** The dialog was 96×94 vh with a
  2 px rounded border; it is now 100×100 vh, borderless. The header and the
  control strip lost most of their padding, and the title dropped from 20 px to
  18 px to fit.

### Removed

- Two stale helpers from an intermediate attempt at the label fix. A
  hysteresis-based grid step was tried first; measurement showed the span does
  not change during a pan, so it was removed rather than kept as dead code.

---

## [5.0.1] — 2026-11-04

### Fixed

- **Deleting a model failed** with `ollama_delete() missing 1 required positional
  argument`. The bridge passes arguments by name, and the method was missing from
  the table that maps positional arguments to names, so the model never reached
  the engine.
- A service-status line showed the raw key `settings.running` instead of a
  translation. The engine's message keys are now translated on that path too.

### Changed

- **"Только сервис" renamed to "Скачать сервис".** The button installs the Ollama
  service only, not a model; the old label suggested it did something else.
- **New "Открыть папку моделей" button** next to "Открыть папку данных". It opens
  the folder Ollama stores models in: `OLLAMA_MODELS` if set, otherwise
  `~/.ollama/models`. The folder is created if missing, so it works before the
  first download.

---

## [5.0.0] — 2026-11-04

A rename, and one migration to go with it.

### Changed

- **Package `suler` → `euler`.** The product name keeps the sigma, Σuler.SC, but
  a Greek letter in an import path breaks on case-insensitive filesystems,
  cannot be typed easily, and ends up mangled in URLs. The import name is now
  plain ASCII. This is why the major version moved: anyone importing the old
  name gets an ImportError, and that is better than a silent half-rename.
- **Data directory `SulerSC` → `EulerSC`.** Moved automatically on first launch,
  once. Without it the rename would have quietly reset everyone's language,
  theme and saved matrices.
- **Executable `SulerSC.exe` → `EulerSC.exe`**, publisher `Euler Project`.

### Unchanged

- The interface wordmark stays **Σuler.SC**. That is the brand, and it renders
  fine where a filesystem path would not.
- `settings.json` keeps its format; the file moves, its contents do not change.

---

## [4.8.0] — 2026-11-04

Hardening pass after a real failure: the assistant answered a request for
instructions on killing someone.

### Added

- **Self-harm and violence rules in the guard.** The filter covered weapons,
  drugs and cyber-attacks but had no rule for violence against a person, so
  "как убить" reached the model untouched.
- **Supportive reply for self-harm.** Someone typing "не хочу жить" now gets a
  helpline message in their own language, not a flat refusal with a maths
  advertisement attached.
- **Profanity masking.** Obscenities in a reply are masked (`х***я`), not
  refused: the user came for mathematics. Masked twice — per streamed chunk for
  display, and over the finished text for history, because a word can be split
  between two chunks.
- **Explicit violence prohibition in the system prompt.** The previous wording
  ("help with real-world harm") was too abstract for a 0.5B model, which
  reformatted the request into "questions to consider" with methods inside.

### Fixed

- Idiom `убить время` ("to pass the time") is not a threat and passes through.
- Self-harm rules require the reflexive pronoun, so `как убить` is classified
  as violence rather than a cry for help.

### Metrics

`blocked 17/17`, `allowed 12/12`, `sweep 199 checks`.

---

## [4.7.0] — 2026-10-29

The reference learned to read descriptions, and to admit when it does not know.

### Added

- **`euler/core/intent.py`** — three-layer resolution of what the user wants:
  lexical phrases (7 ms) → model classifier (~2 s) → ask the user.
- **59 description phrases** in `reference.PHRASES`: "квадрат гипотенузы" →
  `pythagoras`, "вероятность ровно k успехов" → `bernoulli`. A description is
  as strong a signal as the theorem's name.
- **JSON-mode classifier.** The model chooses from a shortlist of 14 real ids
  and returns `{intent, theorem, confidence}`. Two safeguards make a 0.5B model
  usable: an id outside the shortlist is dropped, and confidence below 0.55
  turns a verdict into a question.
- **Clarification instead of guessing.** When nothing is certain the interface
  asks the user to rephrase and shows two examples of the shape that works.
- **Intent-specific answer structure.** A theorem gets statement → when it
  applies → example; an exercise gets given → solution → answer.
- **`llm.classify()`** — a separate non-streaming call in JSON mode. Kept apart
  from `chat_stream` so a classification failure can never break an answer.

### Fixed

- Shortlist ranked by raw hit count, so "квадрат" (three occurrences, half of
  algebra) buried "гипотенуз" (one occurrence, one theorem). Now weighted by
  inverse document frequency.

---

## [4.6.0] — 2026-10-24

### Added

- **`euler/core/guard.py`** — a local check for requests the assistant must
  decline: sexual content involving minors, weapons, explosives, drug
  synthesis, attacks on systems the user does not own. Runs before generation,
  so a small model is never asked to refuse on its own judgement.
- **Model deletion** in Settings, with confirmation and automatic fallback to a
  remaining model when the active one is removed.
- **`balanceMath()`** — unclosed delimiters are closed before rendering, so a
  formula streams as a formula instead of flashing as raw LaTeX.

### Fixed

- **Theory attached to any question.** "как дела" returned the one-sided limit
  theorem, because "дела" is a substring of "слева". Ranking now requires exact
  stems, has a score floor, and penalises low coverage.
- Off-topic messages produce no theory card at all.
- Four LaTeX delimiters recognised: `\[...\]`, `$$...$$`, `\(...\)`, `$...$`.
  Only `$` was handled, and the model prefers brackets.
- Scrollbar inside theory cards replaced by a frame that grows to fit.

---

## [4.5.0] — 2026-10-19

### Fixed

- Brand and logo were painted with `--accent-ink`, the colour of text *on* an
  accent fill, which is near-black in the dark theme. A separate `--brand-ink`
  keeps the wordmark visible.
- Dark palette restored to the saturated rose of earlier builds; the keys had
  been desaturated to grey-mauve.
- **Localisation lag.** Three keyboard buttons had no `data-i18n` attribute, and
  the hardware panel is rendered from data with no attribute to walk. Both
  update the moment the language changes now.
- **Graph.** `fitViewToSeries` ran on mouse release and silently undid the
  drag, which is why panning felt like fighting the plot. Removed; pan and zoom
  are pure drawing.
- Equal axis scaling forced the x-range to ±140 for `x³−3x`, collapsing the
  curve into a stripe. Reverted to per-axis fit.

---

## [4.4.0] — 2026-10-12

### Added

- Five analysis theorems lost in the 4.2 rewrite restored: Lagrange, Rolle,
  Cauchy, Fermat, Lipschitz. The reference is now 145 entries (94 school,
  51 university).

### Fixed

- **Fuzzy matching.** Levenshtein distance with radius 1–2 by word length, so
  `пифогор`, `логранжа` and `обьем` find their entries instead of returning
  nothing.
- **Infinite generation.** A small model could latch onto one line and stream
  it forever. Three defences: `num_predict: 900`, `repeat_penalty: 1.18`, and a
  repeat detector that cuts the answer after the third identical line and says
  why.
- Model output was not capped, so a loop ran for minutes.

---

## [4.3.0] — 2026-10-03

### Added

- Reference expanded to 140 entries across 10 areas: algebra, trigonometry,
  plane geometry, solid geometry, limits, derivatives, integrals, series,
  probability, complex numbers. 94 school, 46 university.
- Formula-shape recognition: a bare `x^2-5x+6=0` is recognised as a quadratic
  with no words to match.

---

## [4.2.0] — 2026-09-19

### Added

- **Conversation tabs** in the AI view, each with an independent history on the
  Python side and a close button. Closing the last tab creates a fresh one.
- The theorem reference is attached to the answer that used it, rendered from
  LaTeX under the response.
- 595 translations: 80 theorem titles plus interface strings.

### Removed

- The separate "Справочник" tab. A card index nobody browses is worse than
  theory placed where it is needed.

---

## [4.1.0] — 2026-08-28

### Added

- Ollama is stopped when the window closes — but only a server this app
  started. A service the user was already running is left alone.
- `Enter` sends in the AI box (`Shift+Enter` for a newline) and evaluates in
  both calculators.
- Installer rewritten: language page, licence page, components page, per-user
  install without UAC, and an uninstaller that stops processes *before*
  deleting files, removes app data, and offers to remove Ollama with its
  models.

### Fixed

- The dark theme ignored the calculator body and the language buttons, which
  kept fixed pastels.
- Matrix placeholder `rank(F)` removed; the field takes focus on tab switch.

---

## [4.0.0] — 2026-08-06

### Added

- **Theorem reference** — 60 entries with statement, worked example and
  keywords. Retrieval by relevance, injected into the model prompt as
  authoritative grounding: a small model quotes a supplied formula correctly
  and invents one badly.
- IDF-weighted ranking. Without it "теорема" outweighed "Пифагора" and a
  question about right triangles was answered with the law of sines.

---

## [3.9.0] — 2026-07-14

### Fixed

- Grid step came out at 0.2 on a 21-unit view, turning labels into a smear.
  Step is now derived from the wider span with a 1/2/5 sequence.
- Graph canvas fills its element exactly at any window size, with no
  letterboxing at high DPI.

---

## [3.0.0] — 2026-06-02

### Added

- Function analysis: domain, range, asymptotes, extrema, monotonicity.
- Export to PDF (with embedded Cyrillic-capable font) and to `.tex`.

---

## [2.2.0] — 2026-05-08

### Added

- Seven interface languages with a full translation table.
- Light, dark and auto themes.

---

## [2.0.0] — 2026-04-14

First release with a native window. A rewrite: the Tkinter interface, Matplotlib
canvas and `pix2text` OCR were dropped in favour of a native window around the
system WebView.

### Added

- SymPy-backed calculator with exact arithmetic and five output forms.
- Limits, derivatives, integrals, matrices by name (A–H), equation solving.
- Local AI assistant through Ollama.

### Removed

- Tkinter interface — replaced by pywebview.
- Matplotlib plotting — replaced by a canvas renderer with its own sampler.
- `pix2text` OCR and its PyTorch dependency, roughly 2 GB of wheels. Photographs
  of tasks are handled by a vision model through Ollama instead, which needs no
  separate stack.


---

## Version history at a glance

| Version | Date | Headline |
|---|---|---|
| 5.0.3 | 2026-11-04 | AI panel: model name in the header, input panel at the bottom |
| 5.0.2 | 2026-11-04 | Stable axis labels while dragging, fullscreen uses the whole screen |
| 5.0.1 | 2026-11-04 | Model deletion fixed, service button renamed, models folder button |
| 5.0.0 | 2026-11-04 | Rename: package `euler`, data directory migrated |
| 4.8.0 | 2026-11-04 | Violence and self-harm rules, profanity masking |
| 4.7.0 | 2026-10-29 | Description phrases, LLM classifier, clarify instead of guessing |
| 4.6.0 | 2026-10-24 | Request guard, model deletion, LaTeX streaming |
| 4.5.0 | 2026-10-19 | Brand colour, localisation lag, graph pan |
| 4.4.0 | 2026-10-12 | Fuzzy matching, loop detection, lost theorems |
| 4.3.0 | 2026-10-03 | Reference to 140 entries, formula-shape recognition |
| 4.2.0 | 2026-09-19 | Conversation tabs, theory under answers |
| 4.1.0 | 2026-08-28 | Ollama shutdown, installer rewrite, Enter key |
| 4.0.0 | 2026-08-06 | Theorem reference with retrieval |
| 3.9.0 | 2026-07-14 | Graph grid and canvas sizing |
| 3.0.0 | 2026-06-02 | Function analysis, PDF and TeX export |
| 2.2.0 | 2026-05-08 | Localisation and themes |
| 2.0.0 | 2026-04-14 | Rewrite: native window, WebView, no OCR stack |
| 1.3.0 | 2026-04-05 | Config file, automatic Ollama install · *legacy repo* |
| 1.2.3 | 2026-04-03 | Photograph input through Pix2Text · *legacy repo* |
| 1.2.1 | 2026-03-29 | Function analysis · *legacy repo* |
| 1.0.0 | 2026-03-09 | First calculator: expressions, equations, plots · *legacy repo* |

## Prehistory — SmartCalculator 1.0.0 … 1.3.0

Before the rewrite the project lived in
[M1kLuXamAkLay/SmartCalculator](https://github.com/M1kLuXamAkLay/SmartCalculator).
Sixteen commits between March and April 2026. Dates are commit dates, not
release dates: there were no tagged releases, only a `Setup/` folder holding the
installer script.

The stack at that time: **Tkinter** for the interface, **Matplotlib** for plots,
**SymPy 1.13** for algebra, **Pix2Text** (and through it, PyTorch) for
recognising formulas in photographs, **Ollama** for the assistant, on
**Python 3.12**. Configuration sat in a `config.txt` beside the executable:
model name, temperature, graph window, and two absolute paths the user had to
edit by hand — the source of most installation failures.

| Version | Date | What it was |
|---|---|---|
| 1.0.0 | 2026-03-09 | First working calculator: expressions, equations, systems of up to four, Matplotlib plots with zoom and pan |
| 1.2.0 | 2026-03-29 | Function analysis — derivative, integral, extrema, behaviour. Reverted the same day, then re-landed |
| 1.2.1 | 2026-03-29 | Re-landed 1.2.0 without the regression that forced the revert |
| 1.2.3 | 2026-04-03 | Photograph input through Pix2Text, routing simple tasks to SymPy and hard ones to the model |
| 1.3.0 | 2026-04-05 | Config file, model choice with a RAM estimate, automatic Ollama install and model pull on first launch |
| — | 2026-04-06 | Installer fix: the one that finally produced a working `Setup.exe` |

### A note on the record

This changelog was introduced at 4.0.0. Earlier work is reconstructed from the
build archives rather than written at the time, and intermediate builds —
2.1, 2.3, 3.1 through 3.8 — exist as installers with no separate entry here.
They are marked in the table above only where something notable shipped. The
archives themselves are the accurate record.

### Why it was rewritten

Three problems could not be fixed in place:

1. **Tkinter could not render the mathematics.** Results were plain text;
   fractions, integrals and matrices never looked like mathematics. LaTeX
   rendering was the reason the project existed.
2. **`pix2text` cost 2 GB and worked badly on photographs of handwriting.** A
   vision model behind Ollama does the same job with no extra dependency.
3. **The interface could not be tested.** A Tkinter widget tree needs a display
   and a live event loop. Serving the interface over loopback HTTP means every
   screen opens in a plain browser, which is why the release sweep exists today.

The rename from SmartCalculator to Σuler.SC and then to the package name
`euler` reflects the same thing: the application became one program with a
computational core, not a script with a window on top.

---

[Unreleased]: https://github.com/euler-project/euler/compare/v4.8.0...HEAD
[4.8.0]: https://github.com/euler-project/euler/compare/v4.7.0...v4.8.0
[4.7.0]: https://github.com/euler-project/euler/compare/v4.6.0...v4.7.0
[4.6.0]: https://github.com/euler-project/euler/compare/v4.5.0...v4.6.0
[4.5.0]: https://github.com/euler-project/euler/compare/v4.4.0...v4.5.0
[4.4.0]: https://github.com/euler-project/euler/compare/v4.3.0...v4.4.0
[4.3.0]: https://github.com/euler-project/euler/compare/v4.2.0...v4.3.0
[4.2.0]: https://github.com/euler-project/euler/compare/v4.1.0...v4.2.0
[4.1.0]: https://github.com/euler-project/euler/compare/v4.0.0...v4.1.0
[4.0.0]: https://github.com/euler-project/euler/compare/v3.9.0...v4.0.0
[3.9.0]: https://github.com/euler-project/euler/compare/v3.0.0...v3.9.0
[3.0.0]: https://github.com/euler-project/euler/compare/v2.2.0...v3.0.0
[2.2.0]: https://github.com/euler-project/euler/compare/v2.0.0...v2.2.0
[2.0.0]: https://github.com/euler-project/euler/releases/tag/v2.0.0
