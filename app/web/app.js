/* ==========================================================================
   Σuler.SC 2.1 — логика интерфейса.

   ГЛАВНОЕ ПРО МОСТ (почему раньше было "api[method] is not a function"):
   pywebview создаёт window.pywebview.api НЕ сразу и наполняет его методами
   асинхронно через _createApi(). Мой прошлый код резолвил промис на объекте
   api, который в тот момент был ещё пустым {}. Теперь ждём не объект,
   а конкретный метод — и проверяем его наличие перед каждым вызовом.

   ГЛАВНОЕ ПРО ВВОД ФОРМУЛ:
   В прошлой версии клавиши имели data-insert="\\sin(" — двойной слеш.
   HTML не обрабатывает JS-экранирование, MathLive получал два символа "\"
   и показывал их на экране. Теперь весь LaTeX живёт только в этом файле,
   где '\sin(' — один слеш. Плейсхолдер (#?) превращается в слот,
   каретка встаёт внутрь скобок, "#" на экране не появляется.
   ========================================================================== */
'use strict';

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

const state = {
  unit: 'deg',
  inverse: false,
  ans: '',
  model: '',
  busy: false,
  history: [],
  pendingImage: null,
  fnMarked: 0,
  series: [],
  theme: 'auto',
  lastSolution: null,
  // ALT history: the computed form and whether an alternative is showing
  formAltActive: false,
  formPrimaryLatex: null,
  formPrimaryKey: null,
  hardwareProfile: null,
  view: { xMin: -5, xMax: 5, yMin: -10, yMax: 10 },
  series: [],
  warm: false,
  lastMatrixResult: null,
  eqCount: 1,
};


/** Status bar text. Stored as a key and translated on every call, so language
    switches and I18n.apply() never leave a stale string behind. */
function setStatus(keyOrText, tone = 'info', raw = false) {
  const el = $('#status-text');
  const dot = $('#status-dot');
  if (!el) return;
  el.removeAttribute('data-i18n');
  el.dataset.statusKey = raw ? '' : keyOrText;
  el.textContent = raw ? keyOrText : t(keyOrText);
  if (dot) dot.className = 'dot' + (tone === 'err' ? ' off' : tone === 'busy' ? ' busy' : '');
}

/** Re-translate the status line after a language switch. */
function refreshStatus() {
  const el = $('#status-text');
  if (el && el.dataset.statusKey) el.textContent = t(el.dataset.statusKey);
}

/**
 * Attach a listener without aborting the caller when the node is missing.
 *
 * Binding fifty handlers with bare ``$('#id').addEventListener`` means one
 * renamed id throws on the first line and every later handler is never
 * attached — that is how the interface ended up inert. This helper logs the
 * miss and returns null instead of throwing.
 */
function on(selector, event, handler, options) {
  const node = typeof selector === 'string' ? $(selector) : selector;
  if (!node) {
    console.warn('missing element:', selector);
    return null;
  }
  node.addEventListener(event, handler, options);
  return node;
}

/* ============================================================ TRANSPORT */

/**
 * Access token issued per launch and handed to the page in the URL.
 *
 * The engine listens on 127.0.0.1 only and rejects any request without this
 * value, so another local process cannot drive the calculator. The token is
 * generated with ``secrets.token_urlsafe`` and never written to disk.
 */
const API_TOKEN = new URLSearchParams(location.search).get('token') || '';

/**
 * Positional parameter names for every exported method.
 *
 * The transport takes keyword arguments, so ``py('solve', '2+2')`` becomes
 * ``{"expression": "2+2"}``. Keeping the mapping here lets call sites stay
 * positional and readable.
 */
const PARAMS = {
  solve: ['expression', 'matrices'],
  solve_equation: ['equation', 'matrices'],
  solve_system: ['equations'],
  steps: ['expression', 'kind', 'extra'],
  calculus: ['kind', 'expression', 'a', 'b', 'direction'],
  analyze: ['expression', 'interval'],
  limit: ['expression', 'point', 'direction'],
  plot: ['equations', 'x_min', 'x_max', 'points'],
  matrix_op: ['operation', 'first', 'second', 'extra'],
  matrix_save: ['name', 'grid'],
  matrix_delete: ['name'],
  matrix_get: ['name'],
  cycle_form: ['expression', 'current'],
  hardware: ['force'],
  settings_set: ['patch'],
  ollama_pull: ['model'],
  ollama_delete: ['model'],
  setup_all: ['model'],
  open_models_dir: [],
  ai_ask: ['task', 'image_b64', 'model'],
  export_pdf: ['kind', 'payload', 'filename'],
  export_latex: ['kind', 'payload', 'filename'],
  export_graph_pdf: ['payload', 'filename'],
  open_exports_dir: [],
  ollama_cancel: [],
  reference: ['query', 'area', 'level'],
};

/** Turn positional arguments into the keyword object the transport expects. */
function toPayload(method, args) {
  const names = PARAMS[method];
  if (!names) return {};
  const payload = {};
  args.forEach((value, index) => {
    const key = names[index];
    if (key !== undefined && value !== undefined) payload[key] = value;
  });
  return payload;
}

/**
 * Replace the Ans token with the previous answer.
 *
 * The interface shows ``Ans`` and the engine must receive the number. Doing the
 * substitution here keeps the visible formula intact while the computation
 * stays exact.
 */
function resolveAns(expression) {
  const text = String(expression || '');
  if (!text) return text;
  if (!/Ans/.test(text)) return text;

  if (!state.ans) return text;
  return text.replace(/Ans/g, `(${state.ans})`);
}

/**
 * Plural form of a counted noun.
 *
 * Russian, Ukrainian and Belarusian need three forms: 1 модель, 2 модели,
 * 5 моделей. English and Romance languages need two. The count decides.
 */
function pluralCount(count, key) {
  const n = Math.abs(Number(count) || 0);
  const language = I18n.get();

  if (['ru', 'uk', 'be'].includes(language)) {
    const tens = n % 100;
    const units = n % 10;
    if (tens >= 11 && tens <= 14) return t(`${key}.many`);
    if (units === 1) return t(`${key}.one`);
    if (units >= 2 && units <= 4) return t(`${key}.few`);
    return t(`${key}.many`);
  }

  if (language === 'fr') {
    return n <= 1 ? t(`${key}.one`) : t(`${key}.many`);
  }

  return n === 1 ? t(`${key}.one`) : t(`${key}.many`);
}

/** Call a Python method over the loopback HTTP channel. */
async function py(method, ...args) {
  const response = await fetch(`api/${method}?token=${API_TOKEN}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(toPayload(method, args)),
  });

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      if (body && body.error) detail = body.error;
    } catch { /* non-JSON error page */ }
    throw new Error(detail);
  }
  return response.json();
}

/**
 * Subscribe to engine-initiated events: download progress and AI tokens.
 * Server-Sent Events avoid polling and survive long generations.
 */
function connectEvents() {
  if (!API_TOKEN || typeof EventSource === 'undefined') return null;

  const source = new EventSource(`events?token=${API_TOKEN}`);
  const handlers = window.Euler || {};
  for (const name of Object.keys(handlers)) {
    source.addEventListener(name, (event) => {
      try {
        handlers[name](JSON.parse(event.data));
      } catch (err) {
        console.error('event', name, err);
      }
    });
  }
  // The stream reconnects automatically when the engine restarts
  window.__events = source;
  return source;
}

/* ============================================================ INPUT VALIDATION */

/** Show error in specific output field, without crashing UI. */
function showError(selector, message) {
  const el = $(selector);
  if (!el) return;
  el.classList.add('error');
  el.textContent = message;
}

function showResult(selector, text, html = null) {
  const el = $(selector);
  if (!el) return;
  el.classList.remove('error');
  if (html !== null) el.innerHTML = html;
  else el.textContent = text;
}

/** Wrapper over any async action: catches all throwable errors. */
async function guarded(selector, action) {
  try {
    await action();
  } catch (err) {
    const detail = err && err.message ? message(err.message) : String(err);
    if (selector) showError(selector, `${t('common.error')}: ${detail}`);
    else console.error(err);
  }
}

/* ============================================================ LaTeX PROCESSING */

/** Convert LaTeX from MathLive to string understood by Python. No backslashes in output. */
/**
 * Convert MathLive LaTeX into the plain expression the engine parses.
 *
 * Three things go wrong if this is done naively:
 *
 *  1. MathLive emits a SINGLE backslash (`\frac`, `\times`). Every macro in
 *     the tables below therefore needs one backslash in source — writing two
 *     means the replacement never matches and a stray `\` reaches the parser,
 *     which reports "syntax error".
 *  2. A digit directly before `\frac` is a mixed number: `9\frac{9}{8}` means
 *     9 + 9/8. Treating it as juxtaposition silently computes 9 * 9/8.
 *  3. Spacing macros (`~`, `\,`, `\;`, `\quad`) carry no arithmetic meaning and
 *     must disappear, or they break every expression typed with the keypad.
 */
/**
 * Rewrite ``\log_{b}(x)`` and ``\lg_{b}(x)`` as ``(log(x)/log(b))``.
 *
 * The argument is scanned with bracket counting, not a regular expression: the
 * base can sit on a nested call such as ``\log_{2}(\sin(x)+1)``, which a
 * single-level pattern would cut in half.
 */
function expandLogBases(input) {
  // \log and \lg are already plain here: the named-macro pass runs first.
  // MathLive writes the base either braced (\log_{9}) or bare (\log_9), and a
  // bare one used to survive into "log_9(9)", which the engine rejects as an
  // unknown name. Both forms are accepted.
  const macro = /(?:^|[^a-zA-Z\\])(log10|log|lg)\s*_/g;
  let out = '';
  let rest = input;

  for (;;) {
    macro.lastIndex = 0;
    const match = macro.exec(rest);
    if (!match) return out + rest;

    const nameEnd = match.index + match[0].length;
    let base;
    let cursor;

    if (rest[nameEnd] === '{') {
      let depth = 0;
      let i = nameEnd;
      let baseEnd = -1;
      for (; i < rest.length; i += 1) {
        if (rest[i] === '{') depth += 1;
        else if (rest[i] === '}') {
          depth -= 1;
          if (depth === 0) { baseEnd = i; break; }
        }
      }
      if (baseEnd < 0) return out + rest;
      base = rest.slice(nameEnd + 1, baseEnd);
      cursor = baseEnd + 1;
    } else {
      // a bare base: a number, a single letter, or one macro such as \pi
      const bare = /^(?:\\[a-zA-Z]+|\d+(?:\.\d+)?|[a-zA-Z])/.exec(rest.slice(nameEnd));
      if (!bare) return out + rest;
      base = bare[0];
      cursor = nameEnd + base.length;
    }

    while (rest[cursor] === ' ') cursor += 1;

    let argument;
    let after;
    if (rest[cursor] === '(') {
      let parens = 0;
      let j = cursor;
      for (; j < rest.length; j += 1) {
        if (rest[j] === '(') parens += 1;
        else if (rest[j] === ')') {
          parens -= 1;
          if (parens === 0) { j += 1; break; }
        }
      }
      argument = rest.slice(cursor + 1, j - 1);
      after = j;
    } else {
      const token = /^-?\d+(?:\.\d+)?|^[a-zA-Z\\]+/.exec(rest.slice(cursor));
      if (!token) return out + rest;
      argument = token[0];
      after = cursor + argument.length;
    }

    out += rest.slice(0, match.index) + match[0].slice(0, match[0].indexOf(match[1]));
    out += `(log(${argument})/log(${base}))`;
    rest = rest.slice(after);
  }
}


function latexToPlain(latex) {
  if (!latex) return '';
  let s = String(latex);

  // --- invisible markup -----------------------------------------------------
  s = s.replace(/\\placeholder\{\}/g, '');
  s = s.replace(/\\left|\\right/g, '');
  s = s.replace(/\\[lLrR]?vert/g, '|');
  s = s.replace(/\\\\/g, '\\');           // collapsed doubled backslashes

  // --- spacing: no arithmetic meaning --------------------------------------
  s = s.replace(/\\[,;:! ]/g, '');
  s = s.replace(/\\(?:quad|qquad)/g, '');
  s = s.replace(/~/g, '');

  // --- mixed numbers: 9\frac{9}{8} -> (9+(9)/(8)) ---------------------------
  // A brace group, optionally nested one level (enough for mixed numbers)
  const GROUP = String.raw`\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}`;
  const MIXED = new RegExp(
    // \s* also absorbs the thin spaces MathLive inserts around the fraction
    String.raw`(^|[^\d.)])(\d+)(?:\s|\\[,;:! ]|~)*\\?(?:d|t)?frac` + GROUP + GROUP,
    'g',
  );
  s = s.replace(MIXED, (_m, lead, whole, numerator, denominator) =>
    `${lead}(${whole}+(${numerator})/(${denominator}))`);

  // --- roots --------------------------------------------------------------
  s = s.replace(/\\sqrt\[([^\]]+)\]\{([^{}]*)\}/g, '(($2)**(1/($1)))');
  s = s.replace(/\\sqrt\{([^{}]*)\}/g, 'sqrt($1)');
  s = s.replace(/\\sqrt\s*(\d+)/g, 'sqrt($1)');

  // --- ordinary fractions (repeat: innermost braces first) -----------------
  let guard = 0;
  while (/(?:d|t)?frac/.test(s) && guard++ < 20) {
    const before = s;
    s = s.replace(/\\(?:d|t)?frac\{([^{}]*)\}\{([^{}]*)\}/g, '(($1)/($2))');
    if (s === before) break;
  }

  // --- named macros -------------------------------------------------------
  const simple = [
    ['\\times', '*'], ['\\cdot', '*'], ['\\div', '/'],
    ['\\pi', 'pi'], ['\\infty', 'oo'], ['\\tau', 'tau'],
    ['\\sin', 'sin'], ['\\cos', 'cos'], ['\\tan', 'tan'],
    ['\\cot', 'cot'], ['\\sec', 'sec'], ['\\csc', 'csc'],
    ['\\arcsin', 'asin'], ['\\arccos', 'acos'], ['\\arctan', 'atan'],
    ['\\sinh', 'sinh'], ['\\cosh', 'cosh'], ['\\tanh', 'tanh'],
    ['\\ln', 'ln'], ['\\log', 'log'], ['\\lg', 'log10'], ['\\exp', 'exp'],
    ['\\det', 'det'], ['\\tr', 'trace'], ['\\operatorname', ''],
    ['\\mathrm', ''], ['\\text', ''], ['\\displaystyle', ''],
    ['\\le', '<='], ['\\leq', '<='], ['\\ge', '>='], ['\\geq', '>='],
    ['\\ne', '!='], ['\\neq', '!='], ['\\approx', '~'],
    ['\\pm', '+'], ['\\mp', '-'], ['\\%', '%'],
    ['\\left', ''], ['\\right', ''],
  ];
  for (const [from, to] of simple) {
    s = s.split(from).join(to);
  }

  // --- logarithms with a base ----------------------------------------------
  // MathLive writes log base 2 as \log_{2}(8). The generic subscript rule further
  // down deletes "_{2}", which turned every logarithm into the natural one. The
  // base becomes a ratio of logarithms: log_2(8) = log(8)/log(2).
  // Runs after \left and \right are gone, so the argument is a plain bracket.
  s = expandLogBases(s);

  // --- function powers ------------------------------------------------------
  // MathLive writes "sin squared" as \sin^{2}(x). The exponent must move onto
  // the call, giving sin(x)^2: left alone it becomes sin^(2)(x), which the
  // parser reads as sin**(2)(x) and rejects.
  s = s.replace(
    /(sin|cos|tan|cot|sec|csc|sinh|cosh|tanh|ln|lg|log|exp|arcsin|arccos|arctan)\s*\^\s*\{?\s*(-?\d+(?:\.\d+)?)\s*\}?\s*\(([^()]*)\)/g,
    (match, name, power, argument) => {
      // sin^{-1}(x) is the inverse function, not a reciprocal
      if (power === '-1') return `arc${name}(${argument})`;
      return `${name}(${argument})^(${power})`;
    },
  );

  // --- powers, subscripts, leftovers --------------------------------------
  s = s.replace(/\^\{([^{}]*)\}/g, '^($1)');
  s = s.replace(/_\{([^{}]*)\}/g, '');
  s = s.replace(/[{}]/g, '');

  // Decimal comma: `1,5` is 1.5 in most of the world, while `f(x, y)` uses the
  // same character. Only a digit-comma-digit pair between non-letters is a
  // decimal: inside a call the comma follows a name or a closing bracket.
  s = s.replace(/(\d),(\d)/g, '$1.$2');

  // Decimal comma: `1,5` is 1.5 across most of the world, and MathLive types
  // the comma key as a literal comma. A digit-comma-digit pair is always a
  // decimal; a comma inside a call is preceded by a name or a bracket.
  s = s.replace(/(\d),(\d)/g, '$1.$2');

  s = s.replace(/\s+/g, ' ').trim();

  // MathLive closes brackets on its own: pressing an operator key after "rank("
  // can leave "rank(F))". Drop surplus closers and pad missing ones so the
  // engine receives a balanced expression instead of a syntax error.
  let depth = 0;
  let balanced = '';
  for (const ch of s) {
    if (ch === '(') { depth += 1; balanced += ch; }
    else if (ch === ')') {
      if (depth > 0) { depth -= 1; balanced += ch; }
      // else: stray closer, drop it
    } else balanced += ch;
  }
  balanced += ')'.repeat(depth);

  return balanced;
}

/** Read MathLive field and return string for Python. */
function readField(selector) {
  const el = $(selector);
  if (!el) return '';
  let latex = '';
  try {
    latex = el.getValue ? el.getValue() : el.value || '';
  } catch {
    latex = el.value || '';
  }
  return latexToPlain(latex);
}

/** Set value in MathLive field from LaTeX. */
function setField(selector, latex) {
  const el = $(selector);
  if (!el) return;
  try {
    el.value = latex;
  } catch {
    el.setAttribute('value', latex);
  }
}

/** Проверка field not empty with error message, not silent ignore. */
function requireField(selector, message) {
  const value = readField(selector);
  if (!value || !value.trim()) {
    throw new Error(message || t('err.empty'));
  }
  return value;
}

/* ============================================================ CALCULATOR LCD */

const lcdInput = $('#lcd-input');
const lcdOut = $('#lcd-out');

/**
 * Paint the calculator display.
 *
 * ``latex`` is preferred: the answer is typeset exactly like the input, so a
 * limit or an integral looks the same whether it is being typed or shown.
 * Plain text is used only for messages and as a fallback.
 */
function setLcd(text, { error = false, ms = null, latex = null } = {}) {
  lcdOut.className = 'lcd-out' + (error ? ' error' : '');
  lcdOut.innerHTML = '';

  if (!error && latex) {
    const holder = document.createElement('span');
    holder.className = 'lcd-tex';
    try {
      holder.innerHTML = window.MathLive.convertLatexToMarkup(latex, { displayMode: false });
    } catch {
      holder.textContent = text;
    }
    lcdOut.appendChild(holder);
  } else {
    lcdOut.appendChild(document.createTextNode(text));
  }

  if (ms !== null && !error) {
    const span = document.createElement('span');
    span.className = 'ms';
    span.textContent = `  · ${ms} ms`;
    lcdOut.appendChild(span);
  }
}

function setLcdLatex(latex) {
  setLcd('', { latex });
}

/* ============================================================ KEYBOARD
   Keys are reused во ВСЕХ вкладках: кнопка «открыть клавиатуру»
   вставляет тот же компонент под нужное поле. Раньше во вкладках был
   обычный input, и формулы приходилось печатать вручную. */

/**
 * Direct and inverse functions for the SHIFT key.
 *
 * Pressing SHIFT swaps the label and the inserted LaTeX, so `sin` becomes
 * `sin⁻¹`. `ln` maps to `eˣ` and `log` to `10ˣ`: those are the operations a
 * calculator pairs, and both are useful when solving equations.
 */
const FUNCS = {
  sin: { tex: '\\sin(#?)',  inv: '\\arcsin(#?)',  label: 'sin', invLabel: 'sin\u207b\u00b9' },
  cos: { tex: '\\cos(#?)',  inv: '\\arccos(#?)',  label: 'cos', invLabel: 'cos\u207b\u00b9' },
  tan: { tex: '\\tan(#?)',  inv: '\\arctan(#?)',  label: 'tan', invLabel: 'tan\u207b\u00b9' },
  ln:  { tex: '\\ln(#?)',   inv: 'e^{#?}',        label: 'ln',  invLabel: 'e\u02e3' },
  log: { tex: '\\log_{#?}(#?)', inv: '10^{#?}',    label: 'log', invLabel: '10\u02e3' },
};

/* Layout: [label, action, class]. No small labels above buttons. */
/**
 * Keypad.
 *
 * One base grid is shared by every tab, so a key never moves when the user
 * switches views — that inconsistency was the main complaint about the old
 * per-tab layouts. Tabs append their own final row:
 *
 *   calculator   base only
 *   equations / analysis / calculus   base + variables (x, y, relations)
 *   matrices     base + matrix functions and saved-matrix letters
 *
 * Layout: [label, action, class]
 */
const BASE_LAYOUT = [
  ['SHIFT', 'cmd:shift', 'k-ac'], ['ALT', 'cmd:alt', 'k-ac'],
  ['AC', 'cmd:ac', 'k-ac'], ['DEL', 'cmd:del', 'k-ac'],
  ['%', 'tex:\\%', 'k-op'], ['html:<span class="kfrac"><i>1</i><i>x</i></span>', 'tex:\\frac{1}{#?}', 'k-fn'],

  ['x\u00b2', 'tex:^{2}', 'k-fn'], ['x\u02b8', 'tex:^{#?}', 'k-fn'],
  ['\u221a', 'tex:\\sqrt{#?}', 'k-fn'], ['\u221b', 'tex:\\sqrt[3]{#?}', 'k-fn'],
  ['html:<span class="kfrac"><i>a</i><i>b</i></span>', 'tex:\\frac{#?}{#?}', 'k-fn'], ['n!', 'tex:!', 'k-fn'],

  ['sin', 'func:sin', 'k-fn'], ['cos', 'func:cos', 'k-fn'], ['tan', 'func:tan', 'k-fn'],
  ['ln', 'func:ln', 'k-fn'], ['log', 'func:log', 'k-fn'],
  ['\u222b', 'tex:\\int_{#?}^{#?}', 'k-fn'],

  ['(', 'tex:(', 'k-fn'], [')', 'tex:)', 'k-fn'], ['\u03c0', 'tex:\\pi', 'k-const'],
  ['e', 'tex:e', 'k-const'], ['\u221e', 'tex:\\infty', 'k-const'],
  ['\u00d710\u207f', 'tex:\\times10^{#?}', 'k-fn'],

  ['7', 'num:7', 'k-num'], ['8', 'num:8', 'k-num'], ['9', 'num:9', 'k-num'],
  ['\u00d7', 'tex:\\times', 'k-op k-sym'], ['\u00f7', 'tex:\\div', 'k-op k-sym'],
  [',', 'tex:,', 'k-num k-sym'],

  ['4', 'num:4', 'k-num'], ['5', 'num:5', 'k-num'], ['6', 'num:6', 'k-num'],
  ['\u2212', 'tex:-', 'k-op k-sym'], ['+', 'tex:+', 'k-op k-sym'],
  ['Ans', 'cmd:ans', 'k-fn'],

  ['1', 'num:1', 'k-num'], ['2', 'num:2', 'k-num'], ['3', 'num:3', 'k-num'],
  ['0', 'num:0', 'k-num'], ['.', 'tex:.', 'k-num'],
  ['=', 'cmd:eq', 'k-eq'],

  ['x', 'tex:x', 'k-var'], ['<', 'tex:<', 'k-var k-sym'], ['>', 'tex:>', 'k-var k-sym'],
  ['\u2264', 'tex:\\le', 'k-var k-sym'], ['\u2265', 'tex:\\ge', 'k-var k-sym'],
  ['|x|', 'tex:\\left|#?\\right|', 'k-fn'],
];

/** Matrix operations and the saved-matrix letters A..H. */
const MATRIX_ROWS = [
  ['A', 'tex:A', 'k-mx'], ['B', 'tex:B', 'k-mx'], ['C', 'tex:C', 'k-mx'],
  ['D', 'tex:D', 'k-mx'], ['E', 'tex:E', 'k-mx'], ['F', 'tex:F', 'k-mx'],

  ['G', 'tex:G', 'k-mx'], ['H', 'tex:H', 'k-mx'],
  ['det(', 'tex:\\det(', 'k-mx'], ['rank(', 'tex:\\operatorname{rank}(', 'k-mx'],
  ['inv(', 'tex:\\operatorname{inv}(', 'k-mx'], ['trace(', 'tex:\\operatorname{tr}(', 'k-mx'],
];

/**
 * The matrix keypad: the numeric and function rows of the base layout with the
 * variable row folded in, so every row still holds six keys.
 *
 * Filtering keys out of the base layout left short rows (the comma and the
 * whole comparison row disappeared), and the grid pulled the next row's keys up
 * into the gap: "7 8 9 × ÷ 4" ended up sharing one line. Explicit rows keep the
 * digit block, the operator column and the function block aligned exactly as on
 * the other tabs.
 */
function matrixLayout() {
  // Built from the base layout by position, not by action string: the actions
  // contain LaTeX ("tex:\\times") and comparing them by hand is error-prone.
  const at = (index) => BASE_LAYOUT[index];
  const row = (from, to) => BASE_LAYOUT.slice(from, to);

  return [
    ...row(0, 6),                                     // modifiers, %, 1/x
    ...row(6, 12),                                    // powers, roots, fractions
    ...row(12, 18),                                   // trigonometry, ln, log, integral
    ...row(18, 24),                                   // brackets, constants, x10^n
    // 7 8 9 x / Ans, 4 5 6 - + |x|, 1 2 3 0 . =
    at(24), at(25), at(26), at(27), at(28), at(35),
    at(30), at(31), at(32), at(33), at(34), at(47),
    at(36), at(37), at(38), at(39), at(40), at(41),
    ...MATRIX_ROWS.slice(0, 6),                       // saved matrices A..F
    ...MATRIX_ROWS.slice(6),                          // G, H, det, rank, inv, trace
  ];
}

/**
 * Layout for a keypad host.
 *
 * The matrix tab gets its own keyboard containing the letters of every saved
 * matrix, so a calculation can be written with the mouse alone.
 */
function layoutFor(hostSelector) {
  // The matrix tab is the only extra: it appends the saved-matrix letters.
  // Every other tab shares one grid, so no key ever moves between views.
  if (hostSelector === '#mx-keys') {
    return matrixLayout();
  }
  return BASE_LAYOUT;
}

let LAYOUT = BASE_LAYOUT;

/** Build keyboard in container. targetSelector — field to write to. */
function buildKeyboard(hostSelector, targetSelector, layout = null) {
  const host = $(hostSelector);
  if (!host) return;
  host.innerHTML = '';

  const rows = layout || layoutFor(hostSelector);

  for (const [label, action, cls] of rows) {
    const btn = document.createElement('button');
    btn.className = `key ${cls}`;
    btn.type = 'button';
    if (label.startsWith('html:')) btn.innerHTML = label.slice(5);
    else btn.textContent = label;
    btn.dataset.action = action;
    btn.addEventListener('click', () => handleKeyAction(action, targetSelector));
    host.appendChild(btn);
  }
  updateFuncLabels(hostSelector);
}

function updateFuncLabels(hostSelector = '#keys') {
  for (const btn of $$(`${hostSelector} .key[data-action^="func:"]`)) {
    const meta = FUNCS[btn.dataset.action.split(':')[1]];
    if (!meta) continue;
    btn.textContent = state.inverse ? meta.invLabel : meta.label;
    btn.classList.toggle('inverse', state.inverse);
  }
}

function focusField(selector) {
  const el = $(selector);
  if (el && el.focus) el.focus();
}

function insertInto(selector, tex) {
  const el = $(selector);
  if (!el) return;
  try {
    el.insert(tex);
    if (el.focus) el.focus();
  } catch {
    el.value = (el.value || '') + tex;
  }
}

function handleKeyAction(action, targetSelector) {
  if (!action) return;

  if (action.startsWith('num:')) return insertInto(targetSelector, action.slice(4));
  if (action.startsWith('tex:')) return insertInto(targetSelector, action.slice(4));

  if (action.startsWith('func:')) {
    const meta = FUNCS[action.slice(5)];
    if (meta) insertInto(targetSelector, state.inverse ? meta.inv : meta.tex);
    return;
  }

  const cmd = action.startsWith('cmd:') ? action.slice(4) : '';
  const el = $(targetSelector);

  switch (cmd) {
    case 'ac':
      if (el) el.value = '';
      if (targetSelector === '#lcd-input') setLcd('');
      break;
    case 'del':
      if (el && el.executeCommand) el.executeCommand('deleteBackward');
      break;
    case 'shift':
      state.inverse = !state.inverse;
      // Every keypad shows the same function row; refresh all of them, or the
      // analysis tab keeps showing sin while the calculator shows sin-1.
      ['#keys', '#kb-cx', '#kb-an', '#kb-eq', '#mx-keys'].forEach(updateFuncLabels);
      break;
    case 'ans':
      // The token Ans stays on screen so the formula reads as written; the
      // engine receives the previous value. Pasted digits would be mistaken
      // for user input and lost on the next edit.
      if (!state.ans) {
        setStatus('err.no_answer', 'err');
        break;
      }
      insertInto(targetSelector, '\\mathrm{Ans}');
      break;
    case 'alt':
      cycleAnswerForm();
      break;
    case 'eq':
      // The key doubles as "run" on the tabs that have a result display, and as
      // a plain "=" elsewhere: pressing it while writing an equation must not
      // wipe the field by triggering a solve.
      if (targetSelector === '#lcd-input') evaluateCalculator();
      else if (targetSelector === '#mx-input') evaluateMatrixExpression();
      else insertInto(targetSelector, '=');
      break;
  }
}

/* ============================================================ DISPLAY FORMS */

/**
 * ALT key: show the last answer in the next available form.
 *
 * The value is recomputed from the original expression, so switching between
 * 5 1/2, 11/2, 5.5 and 5.5e0 never loses precision.
 */
/**
 * ALT: show an alternative form, then return to the original one.
 *
 * Pressing ALT once shows the next representation; pressing it again puts the
 * answer back exactly as it was computed. A third press moves on to the next
 * alternative, so every available form stays reachable without trapping the
 * user in a cycle that never returns home.
 *
 * The value is recomputed from the original expression each time, so switching
 * between 5½, 11/2 and 5.5 never loses precision.
 */
async function cycleAnswerForm() {
  const expression = state.lastExpression || readField('#lcd-input');
  if (!expression || !expression.trim()) {
    setLcd(t('err.empty'), { error: true });
    return;
  }

/** Localised name of an answer form ("exact", "decimal" ...), or empty. */
function formLabel(key) {
  return key ? t(`form.${key}`) : '';
}

  // Second press: restore the form the engine chose.
  if (state.formAltActive && state.formPrimaryLatex) {
    state.formAltActive = false;
    state.answerForm = state.formPrimaryKey;
    state.answerLatex = state.formPrimaryLatex;
    setLcdLatex(state.formPrimaryLatex);
    const chip = $('#form-chip');
    if (chip) chip.textContent = formLabel(state.formPrimaryKey);
    return;
  }

  try {
    const res = await py('cycle_form', expression, state.answerForm || 'auto');
    if (!res.ok) {
      setLcd(message(res.error), { error: true });
      return;
    }

    // First alternative of this answer: remember what to return to.
    if (!state.formPrimaryLatex) {
      state.formPrimaryLatex = state.answerLatex;
      state.formPrimaryKey = state.answerForm;
    }

    state.formAltActive = true;
    state.answerForm = res.key;
    state.answerLatex = res.latex;
    setLcdLatex(res.latex);
    const chip = $('#form-chip');
    if (chip) chip.textContent = formLabel(res.key);
  } catch (err) {
    setLcd(message(err.message), { error: true });
  }
}


/**
 * Show friendly guidance when the user makes a common mistake.
 * Called from every input handler before sending the request to Python.
 */
function validateInput(value, context) {
  value = (value || '').trim();

  if (!value) {
    if (context === 'calc') return { ok: false, guide: 'err.empty' };
    if (context === 'analysis') return { ok: false, guide: 'guide.function_required' };
    if (context === 'calculus') return { ok: false, guide: 'guide.function_required' };
    return { ok: false, guide: 'err.empty' };
  }

  return { ok: true };
}

function showGuide(selector, key) {
  const el = $(selector);
  if (!el) return;
  el.innerHTML = `<p style="color:var(--note)">${escapeHtml(t(key))}</p>`;
}

/* ============================================================ CALCULATOR */

async function evaluateCalculator() {
  const latex = lcdInput.getValue();
  const expr = resolveAns(latexToPlain(latex || ''));

  const check = validateInput(expr, 'calc');
  if (!check.ok) {
    setLcd(t(check.guide), { error: true });
    return;
  }

  try {
    const res = await py('solve', expr);
    if (res.ok) {
      state.ans = res.ans || res.plain || res.text;   // parser-readable, not LaTeX
      state.lastExpression = expr;
      state.answerForm = res.form_key || 'exact';
      state.answerLatex = res.latex || res.result;
      // A new computation starts a new form history
      state.formAltActive = false;
      state.formPrimaryLatex = null;
      state.formPrimaryKey = null;
      setLcd(res.result, { ms: res.elapsed_ms, latex: res.latex });
      state.history.unshift({ expr, result: res.result });
      if (state.history.length > 40) state.history.pop();
      const chip = $('#form-chip');
      if (chip) chip.textContent = state.answerForm;
    } else {
      setLcd(message(res.error) || t('common.error'), { error: true });
    }
  } catch (err) {
    setLcd(message(err.message) || String(err), { error: true });
  }
}

/* ============================================================ LIMITS AND INTEGRALS */

async function runCalculus(kind, direction = 'both') {
  const out = '#cx-out';
  await guarded(out, async () => {
    const fn = resolveAns(requireField('#cx-fn', t('err.empty')));
    let a = '', b = '';

    if (kind === 'limit') a = readField('#cx-point');
    if (kind === 'definite') {
      a = readField('#cx-lower');
      b = readField('#cx-upper');
      if (!a || !b) throw new Error(t('err.empty'));
    }

    showResult(out, '…');
    const res = await py('calculus', kind, fn, a, b, direction);
    if (!res.ok) return showError(out, message(res.error) || t('common.error'));

    showResult(out, '', renderTitle(res.title) + renderLines(res.lines));
  });
}

/* ============================================================ FUNCTION ANALYSIS */

async function runAnalysis() {
  const out = '#analysis-out';
  await guarded(out, async () => {
    const fn = resolveAns(markedFunction());
    if (!fn) throw new Error(t('err.empty'));

    const raw = readField('#an-interval');
    let interval = null;
    if (raw) {
      const parts = raw.split(/[;,]/).map((s) => parseFloat(s.replace(',', '.')));
      if (parts.length === 2 && parts.every((v) => Number.isFinite(v))) {
        interval = parts;
      } else {
        throw new Error(t('analysis.interval') + ': -2; 2');
      }
    }

    showResult(out, '…');
    const res = await py('analyze', fn, interval);
    if (!res.ok) return showError(out, message(res.error) || t('common.error'));

    const blocks = [`<h4>${renderInlineMath(res.function_latex || res.function)}</h4>`];
    for (const section of res.sections) {
      blocks.push(`<h4>${escapeHtml(message(section.title))}</h4>`);
      blocks.push(renderLines(section.lines));
    }
    showResult(out, '', blocks.join(''));
    await drawGraph();
  });
}

/* ============================================================ FUNCTIONS (up to four) */

const FN_COLORS = ['#8f4c56', '#2b5fa8', '#2f7d5a', '#c7741b'];
const FN_LIMIT = FN_COLORS.length;
let fnSeq = 0;

function fnRows() {
  return $$('#fn-list .fn-row');
}

function readFunctions() {
  return fnRows().map((row) => readField(`#${row.dataset.field}`));
}

/** Functions with a non-empty formula, each with the colour of its row. */
function activeFunctions() {
  return readFunctions()
    .map((expr, index) => ({ expr: expr.trim(), index, color: FN_COLORS[index] }))
    .filter((fn) => fn.expr);
}

function markedFunction() {
  const row = fnRows()[state.fnMarked] || fnRows()[0];
  return row ? readField(`#${row.dataset.field}`) : '';
}

function setActiveFnRow(row) {
  fnRows().forEach((r) => r.classList.toggle('is-active', r === row));
}

let graphTimer = null;
let graphSeq = 0;

function scheduleGraph() {
  clearTimeout(graphTimer);
  graphTimer = setTimeout(drawGraph, 180);
}

function syncFnControls() {
  const rows = fnRows();
  const add = $('#btn-add-fn');
  if (add) add.disabled = rows.length >= FN_LIMIT;
  rows.forEach((row, index) => {
    row.querySelector('.fn-remove').disabled = rows.length === 1 && !readField(`#${row.dataset.field}`);
    const mark = row.querySelector('.fn-mark');
    const marked = index === state.fnMarked;
    mark.setAttribute('aria-pressed', String(marked));
    mark.classList.toggle('on', marked);
    row.querySelector('.fn-swatch').style.background = FN_COLORS[index];
  });
  renderLegend();
  scheduleGraph();
}

function buildFnRow(value, index) {
  const row = document.createElement('div');
  row.className = 'fn-row';
  row.dataset.index = String(index);
  row.dataset.field = `an-fn-${++fnSeq}`;

  const swatch = document.createElement('span');
  swatch.className = 'fn-swatch';

  const field = document.createElement('math-field');
  field.className = 'mf-input';
  field.id = row.dataset.field;

  const mark = document.createElement('button');
  mark.type = 'button';
  mark.className = 'fn-mark';
  mark.title = t('analysis.mark_full');
  mark.setAttribute('aria-label', t('analysis.mark_full'));
  mark.textContent = '\u25C9';

  const remove = document.createElement('button');
  remove.type = 'button';
  remove.className = 'fn-remove';
  remove.title = t('analysis.remove_fn');
  remove.setAttribute('aria-label', t('analysis.remove_fn'));
  remove.textContent = '\u00D7';

  row.append(swatch, field, mark, remove);

  field.addEventListener('focusin', () => setActiveFnRow(row));
  field.addEventListener('input', syncFnControls);
  mark.addEventListener('click', () => {
    state.fnMarked = Number(row.dataset.index);
    syncFnControls();
  });
  remove.addEventListener('click', () => removeFunction(row));
  return { row, field, value };
}

function renderFnList(values, marked = 0) {
  const list = $('#fn-list');
  if (!list) return;
  const items = values.length ? values : [''];
  list.innerHTML = '';
  items.forEach((value, index) => {
    const { row, field } = buildFnRow(value, index);
    list.appendChild(row);
    setField(`#${row.dataset.field}`, value);
  });
  state.fnMarked = Math.min(Math.max(marked, 0), items.length - 1);
  setActiveFnRow(fnRows()[0]);
  syncFnControls();
}

function addFunction() {
  const values = readFunctions();
  if (values.length >= FN_LIMIT) return;
  values.push('');
  renderFnList(values, state.fnMarked);
  const last = fnRows()[fnRows().length - 1];
  setActiveFnRow(last);
  const field = document.getElementById(last.dataset.field);
  if (field && field.focus) field.focus();
}

function removeFunction(row) {
  const values = readFunctions();
  const index = Number(row.dataset.index);
  if (values.length === 1) {
    values[0] = '';
  } else {
    values.splice(index, 1);
  }
  let marked = state.fnMarked;
  if (index === marked) marked = 0;
  else if (index < marked) marked -= 1;
  renderFnList(values, marked);
}

function formulaMarkup(latex) {
  try {
    return window.MathLive.convertLatexToMarkup(latex, { displayMode: false });
  } catch {
    return escapeHtml(latex);
  }
}

function renderLegend() {
  const fns = activeFunctions();
  for (const legend of $$('.fn-legend')) {
    legend.innerHTML = '';
    for (const fn of fns) {
      const chip = document.createElement('span');
      chip.className = 'fn-chip';
      const stripe = document.createElement('i');
      stripe.className = 'fn-stripe';
      stripe.style.background = fn.color;
      const formula = document.createElement('span');
      formula.className = 'fn-tex';
      formula.style.color = fn.color;
      formula.innerHTML = formulaMarkup(`y_{${fn.index + 1}} = ${plainToLatex(fn.expr)}`);
      chip.append(stripe, formula);
      legend.appendChild(chip);
    }
  }
}

/* ============================================================ GRAPH */

const graphCanvas = $('#graph-canvas');
const graphCtx = graphCanvas ? graphCanvas.getContext('2d') : null;

async function drawGraph() {
  if (!graphCanvas || !graphCtx) return;
  if (!$('#view-analysis').classList.contains('active')) return;
  // A hidden card has zero size; measuring now would draw nothing
  if (!graphCanvas.getBoundingClientRect().width) return;

  const fns = activeFunctions();
  renderLegend();
  if (!fns.length) {
    state.series = [];
    renderCanvas();
    return;
  }

  const seq = ++graphSeq;
  try {
    // Sampling density is what keeps a curve smooth: 2400 points across the
    // visible span, so a wiggly function does not turn into a polygon.
    const res = await py('plot', fns.map((fn) => fn.expr), state.view.xMin, state.view.xMax, 2400);
    if (seq !== graphSeq) return;
    if (res.ok && res.series) {
      state.series = res.series.flatMap((s, i) =>
        s.segments.map((segment) => ({ segment, color: fns[i] ? fns[i].color : FN_COLORS[0] })));
    }
  } catch {
    // Graph non-critical: if core is busy, keep previous
  }
  renderCanvas();
}

/**
 * Draw the plot on any canvas.
 *
 * @param {HTMLCanvasElement} canvas target surface (inline or fullscreen)
 * @param {CanvasRenderingContext2D} ctx its 2D context
 * @param {boolean} detailed draw grid labels, axis names and the function title
 *
 * Grid steps are chosen from a 1/2/5 sequence so the labels stay readable at
 * any zoom level instead of degrading into values like 0.3333.
 */
function renderGraph(canvas, ctx, detailed = false) {
  if (!canvas || !ctx) return;

  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  if (!rect.width || !rect.height) return;

  // Backing store in device pixels, drawing in CSS pixels: the plot then fills
  // the element exactly, with no letterboxing at any zoom or window size.
  canvas.width = Math.round(rect.width * dpr);
  canvas.height = Math.round(rect.height * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  const w = rect.width;
  const h = rect.height;

  // One unit is the same length on both axes, so a circle looks like a circle
  // and the curve is not stretched by the shape of the card.
  const view = { ...state.view };
  const spanX = view.xMax - view.xMin;
  const spanY = view.yMax - view.yMin;
  const targetRatio = h / w;
  const currentRatio = spanY / spanX;

  if (Number.isFinite(targetRatio) && Number.isFinite(currentRatio) && currentRatio > 0) {
    if (currentRatio < targetRatio) {
      const extra = (spanX * targetRatio - spanY) / 2;
      view.yMin -= extra;
      view.yMax += extra;
    } else {
      const extra = (spanY / targetRatio - spanX) / 2;
      view.xMin -= extra;
      view.xMax += extra;
    }
  }

  const { xMin, xMax, yMin, yMax } = view;

  const toX = (x) => ((x - xMin) / (xMax - xMin)) * w;
  const toY = (y) => h - ((y - yMin) / (yMax - yMin)) * h;

  ctx.fillStyle = '#f6e7ea';
  ctx.fillRect(0, 0, w, h);

  // One step for both axes.
  //
  // Units per pixel are identical on both axes (see the aspect correction
  // above), so different steps made the grid cells rectangular and the plot
  // looked stretched even though the scale was correct.
  // Aim for 8-10 cells across the wider axis. Dividing the SHORTER span by a
  // fixed number made the cells tiny whenever the window was wide: at 21 units
  // per side the step came out at 0.2 and the labels overlapped into a smear.
  const step = niceStep(Math.max(xMax - xMin, yMax - yMin) / 9);
  const stepX = step;
  const stepY = step;

  // Minor grid
  ctx.strokeStyle = '#e6d2d8';
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (let x = Math.ceil(xMin / stepX) * stepX; x <= xMax; x += stepX) {
    const px = Math.round(toX(x)) + 0.5;
    ctx.moveTo(px, 0);
    ctx.lineTo(px, h);
  }
  for (let y = Math.ceil(yMin / stepY) * stepY; y <= yMax; y += stepY) {
    const py = Math.round(toY(y)) + 0.5;
    ctx.moveTo(0, py);
    ctx.lineTo(w, py);
  }
  ctx.stroke();

  // Axes
  const zeroX = toX(0);
  const zeroY = toY(0);
  const axisY = Math.min(Math.max(zeroY, 0), h);
  const axisX = Math.min(Math.max(zeroX, 0), w);

  ctx.strokeStyle = '#6d4f56';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(0, Math.round(axisY) + 0.5);
  ctx.lineTo(w, Math.round(axisY) + 0.5);
  ctx.moveTo(Math.round(axisX) + 0.5, 0);
  ctx.lineTo(Math.round(axisX) + 0.5, h);
  ctx.stroke();

  // Curve.
  //
  // Off-screen points are CLIPPED, not dropped. Dropping them reset the
  // polyline, which is why a steep curve appeared as a few disconnected
  // dashes instead of a line. A break is only inserted for a genuine
  // discontinuity: a jump larger than the whole canvas height, which is what
  // an asymptote produces and a steep-but-continuous curve never does.
  if (state.series.length) {
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, w, h);
    ctx.clip();

    state.series.forEach(({ segment, color }) => {
      if (!segment || segment.length < 2) return;

      ctx.strokeStyle = color;
      ctx.lineWidth = 2.4;
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';
      ctx.beginPath();

      let started = false;
      let previous = null;

      for (const [x, y] of segment) {
        const px = toX(x);
        const py = toY(y);

        if (!Number.isFinite(py)) {
          started = false;
          previous = null;
          continue;
        }

        const jump = previous !== null && Math.abs(py - previous) > h * 4;
        if (jump) {
          ctx.stroke();
          ctx.beginPath();
          started = false;
        }

        if (!started) {
          ctx.moveTo(px, py);
          started = true;
        } else {
          ctx.lineTo(px, py);
        }
        previous = py;
      }
      ctx.stroke();
    });

    ctx.restore();
  }

  if (!detailed) return;

  // ---- labels
  const font = getComputedStyle(document.body).fontFamily;
  ctx.font = `12px ${font}`;
  ctx.fillStyle = '#2e1c20';

  const decimals = Math.max(0, -Math.floor(Math.log10(stepX)));
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';

  // Label every Nth grid line, with N fixed by the pixel width of one step.
  // The old rule skipped a tick whenever it sat closer than 46px to the last
  // labelled one, so which ticks got labels depended on where they landed
  // during a drag: the same axis read every 1 unit at one pixel and every 2
  // at the next. N comes from the step alone, so a drag cannot change it.
  const labelEvery = labelMultiple(stepX, toX(stepX) - toX(0), 46);

  for (let k = Math.ceil(xMin / stepX); k * stepX <= xMax; k++) {
    if (k % labelEvery !== 0) continue;
    const x = k * stepX;
    if (Math.abs(x) < stepX / 100) continue;
    const px = toX(x);
    if (px < 16 || px > w - 16) continue;
    ctx.fillText(x.toFixed(decimals), px, axisY + 5);
    ctx.beginPath();
    ctx.strokeStyle = '#6d4f56';
    ctx.lineWidth = 1;
    ctx.moveTo(Math.round(px) + 0.5, axisY - 3);
    ctx.lineTo(Math.round(px) + 0.5, axisY + 3);
    ctx.stroke();
  }

  const decimalsY = Math.max(0, -Math.floor(Math.log10(stepY)));
  ctx.textAlign = 'right';
  ctx.textBaseline = 'middle';
  const labelEveryY = labelMultiple(stepY, toY(0) - toY(stepY), 22);

  for (let k = Math.ceil(yMin / stepY); k * stepY <= yMax; k++) {
    if (k % labelEveryY !== 0) continue;
    const y = k * stepY;
    if (Math.abs(y) < stepY / 100) continue;
    const py = toY(y);
    if (py < 12 || py > h - 12) continue;
    ctx.fillText(y.toFixed(decimalsY), axisX - 6, py);
    ctx.beginPath();
    ctx.strokeStyle = '#6d4f56';
    ctx.lineWidth = 1;
    ctx.moveTo(axisX - 3, Math.round(py) + 0.5);
    ctx.lineTo(axisX + 3, Math.round(py) + 0.5);
    ctx.stroke();
  }

  // Axis names, pinned to the canvas edges so they never scroll away
  ctx.font = `italic 14px ${font}`;
  ctx.fillStyle = '#6d4f56';
  ctx.textAlign = 'right';
  ctx.textBaseline = 'bottom';
  ctx.fillText('x', w - 6, axisY - 6);


}

function renderCanvas() {
  // Labels in the small card too: without them the preview is a bare curve
  renderGraph(graphCanvas, graphCtx, true);
}
/**
 * A grid step from the 1 / 2 / 5 sequence.
 *
 * The sequence keeps labels round: 1, 2, 5, 10, 20, 50 … instead of 3.7.
 * ``span`` is the width the step has to divide; the caller decides how many
 * cells it wants and passes the already-divided value.
 */
/* Smallest integer N (1, 2, 5, 10, ...) such that labels N steps apart are at
   least minPx apart. Computed once per redraw from the pixel size of one grid
   step, so the set of labelled ticks is a property of the zoom, not of where
   the ticks happen to sit. */
function labelMultiple(stepUnits, pxPerStep, minPx) {
  if (!Number.isFinite(pxPerStep) || pxPerStep <= 0) return 1;
  for (const n of [1, 2, 5, 10, 20, 50, 100]) {
    if (n * Math.abs(pxPerStep) >= minPx) return n;
  }
  return 100;
}

function niceStep(span) {
  const raw = Math.abs(span) || 1;
  const power = Math.pow(10, Math.floor(Math.log10(raw)));
  const normalized = raw / power;

  let step = power;
  if (normalized >= 5) step = power * 5;
  else if (normalized >= 2) step = power * 2;

  // Guard: a degenerate view must still produce a usable step
  if (!Number.isFinite(step) || step <= 0) return 1;
  return step;
}



/* ============================================================ FULLSCREEN GRAPH */

let graphFullscreenCanvas = null;
let graphFullscreenCtx = null;

/**
 * Open the plot full screen.
 *
 * The canvas is sized from its own layout box, not from window guesses: with
 * `position:absolute; inset:0` the CSS size already fills the dialog, so only
 * the backing store needs scaling by devicePixelRatio. The title is typeset
 * through MathLive — a header reading `y = x^3-3x` in ASCII was the complaint.
 */
async function openFullscreenGraph() {
  const overlay = $('#graph-fullscreen');
  const canvas = $('#graph-canvas-fs');
  if (!overlay || !canvas) return;

  const title = $('#graph-title-fs');
  if (title) title.textContent = t('analysis.graph');

  overlay.hidden = false;
  graphFullscreenCanvas = canvas;
  graphFullscreenCtx = canvas.getContext('2d');

  // Give the dialog a frame to lay out before measuring
  await new Promise((resolve) => requestAnimationFrame(resolve));

  renderGraph(canvas, graphFullscreenCtx, true);
  setupFullscreenControls();

  // Redraw on resize while the overlay is open
  if (window.__fsResize) window.removeEventListener('resize', window.__fsResize);
  window.__fsResize = () => {
    if (!overlay.hidden && graphFullscreenCtx) {
      renderGraph(canvas, graphFullscreenCtx, true);
    }
  };
  window.addEventListener('resize', window.__fsResize);
}

/**
 * A plain expression into LaTeX for the plot title: `x^3-3x` -> `x^{3}-3x`.
 *
 * Only the pieces a plot title needs: powers, multiplication signs and the
 * constants the keypad inserts.
 */
function plainToLatex(expression) {
  let text = String(expression || '').trim();
  if (!text) return '';

  // already LaTeX
  if (text.includes('\\')) return text;

  text = text.replace(/\*\*/g, '^');
  text = text.replace(/\^\(([^)]*)\)/g, '^{$1}');
  text = text.replace(/\^(-?\d+(?:\.\d+)?)/g, '^{$1}');
  text = text.replace(/\bpi\b/g, '\\pi');
  text = text.replace(/\binfty\b|\boo\b/g, '\\infty');
  text = text.replace(/\bsqrt\(([^)]*)\)/g, '\\sqrt{$1}');
  text = text.replace(/\b(sin|cos|tan|cot|ln|log|exp|arcsin|arccos|arctan)\b/g, '\\$1');
  text = text.replace(/(\d)\s*\*\s*/g, '$1 \\cdot ').replace(/\*/g, ' \\cdot ');
  text = text.replace(/(\d)\s*([a-zA-Z\\])/g, '$1 $2');
  return text;
}

function setupFullscreenControls() {
  const canvas = graphFullscreenCanvas;
  if (!canvas) return;

  let drag = null;

  const point = (event) => {
    const rect = canvas.getBoundingClientRect();
    return { x: event.clientX - rect.left, y: event.clientY - rect.top };
  };

  const mousedown = (event) => {
    if (event.button !== 0) return;
    drag = { ...point(event), view: { ...state.view } };
    canvas.style.cursor = 'grabbing';
    event.preventDefault();
  };

  let fsPending = 0;
  const fsDraw = () => {
    if (fsPending) return;
    fsPending = requestAnimationFrame(() => {
      fsPending = 0;
      renderGraph(canvas, graphFullscreenCtx, true);
    });
  };

  const mousemove = (event) => {
    if (!drag) return;
    const rect = canvas.getBoundingClientRect();
    const here = point(event);
    const dx = (here.x - drag.x) / rect.width;
    const dy = (here.y - drag.y) / rect.height;
    const spanX = drag.view.xMax - drag.view.xMin;
    const spanY = drag.view.yMax - drag.view.yMin;

    state.view = {
      xMin: drag.view.xMin - dx * spanX,
      xMax: drag.view.xMax - dx * spanX,
      yMin: drag.view.yMin + dy * spanY,
      yMax: drag.view.yMax + dy * spanY,
    };
    fsDraw();
  };

  const mouseup = () => {
    if (!drag) return;
    drag = null;
    canvas.style.cursor = 'crosshair';
    // The inline plot is refreshed once the gesture ends; refetching mid-drag
    // is what made it stutter.
    renderCanvas();
  };

  const wheel = (event) => {
    event.preventDefault();
    const factor = event.deltaY < 0 ? 0.88 : 1.14;
    const rect = canvas.getBoundingClientRect();
    const here = point(event);
    // Zoom about the cursor, not the centre: otherwise the point under the
    // mouse slides away and the plot feels wrong to navigate.
    const fx = here.x / rect.width;
    const fy = 1 - here.y / rect.height;
    const { xMin, xMax, yMin, yMax } = state.view;
    const cx = xMin + fx * (xMax - xMin);
    const cy = yMin + fy * (yMax - yMin);

    state.view = {
      xMin: cx + (xMin - cx) * factor,
      xMax: cx + (xMax - cx) * factor,
      yMin: cy + (yMin - cy) * factor,
      yMax: cy + (yMax - cy) * factor,
    };
    fsDraw();
  };

  canvas.onmousedown = mousedown;
  canvas.onmousemove = mousemove;
  canvas.onmouseup = mouseup;
  canvas.onmouseleave = mouseup;
  canvas.onwheel = wheel;

  const close = () => {
    const overlay = $('#graph-fullscreen');
    if (overlay) overlay.hidden = true;
    canvas.onmousedown = null;
    canvas.onmousemove = null;
    canvas.onmouseup = null;
    canvas.onmouseleave = null;
    canvas.onwheel = null;
    if (window.__fsResize) {
      window.removeEventListener('resize', window.__fsResize);
      window.__fsResize = null;
    }
    graphFullscreenCanvas = null;
    graphFullscreenCtx = null;
    drawGraph();
  };

  const closeButton = $('#btn-close-graph');
  if (closeButton) closeButton.onclick = close;

  // Escape closes the overlay: a fullscreen view with only a small X is a trap
  document.addEventListener('keydown', function onEscape(event) {
    if (event.key !== 'Escape') return;
    const overlay = $('#graph-fullscreen');
    if (overlay && !overlay.hidden) {
      close();
      document.removeEventListener('keydown', onEscape);
    }
  });

  const reset = $('#btn-fs-reset');
  if (reset) reset.onclick = () => {
    state.view = { xMin: -10, xMax: 10, yMin: -10, yMax: 10 };
    renderGraph(canvas, graphFullscreenCtx, true);
  };

}

/* Pan and zoom */
// Redraw the inline plot when its card changes size (window resize, tab switch)
if (graphCanvas && typeof ResizeObserver !== 'undefined') {
  let pending = null;
  new ResizeObserver(() => {
    if (pending) cancelAnimationFrame(pending);
    pending = requestAnimationFrame(() => {
      if ($('#view-analysis').classList.contains('active')) {
        renderGraph(graphCanvas, graphCtx, true);
      }
    });
  }).observe(graphCanvas.parentElement || graphCanvas);
}

let drag = null;
if (graphCanvas) {
  /*
   * Pan and zoom.
   *
   * The drag delta is measured from a cached rect, and the redraw is batched
   * into one animation frame: pointer events arrive far faster than the screen
   * refreshes, and repainting on every one of them made the plot trail behind
   * the cursor.
   *
   * On release the curve is NOT refetched. Refetching used to re-fit the view,
   * which silently undid the drag — the plot snapped back to where it was.
   */
  let dragState = null;
  let pendingFrame = 0;

  const scheduleDraw = () => {
    if (pendingFrame) return;
    pendingFrame = requestAnimationFrame(() => {
      pendingFrame = 0;
      renderCanvas();
    });
  };

  graphCanvas.addEventListener('mousedown', (e) => {
    if (e.button !== 0) return;
    const rect = graphCanvas.getBoundingClientRect();
    dragState = {
      startX: e.clientX,
      startY: e.clientY,
      width: rect.width || 1,
      height: rect.height || 1,
      view: { ...state.view },
    };
    graphCanvas.style.cursor = 'grabbing';
    e.preventDefault();
  });

  window.addEventListener('mousemove', (e) => {
    if (!dragState) return;

    const dx = (e.clientX - dragState.startX) / dragState.width;
    const dy = (e.clientY - dragState.startY) / dragState.height;
    const spanX = dragState.view.xMax - dragState.view.xMin;
    const spanY = dragState.view.yMax - dragState.view.yMin;

    state.view = {
      xMin: dragState.view.xMin - dx * spanX,
      xMax: dragState.view.xMax - dx * spanX,
      yMin: dragState.view.yMin + dy * spanY,
      yMax: dragState.view.yMax + dy * spanY,
    };
    scheduleDraw();
  });

  const endDrag = () => {
    if (!dragState) return;
    dragState = null;
    graphCanvas.style.cursor = 'crosshair';
  };

  window.addEventListener('mouseup', endDrag);
  window.addEventListener('blur', endDrag);

  graphCanvas.addEventListener('wheel', (e) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 0.88 : 1.14;
    const rect = graphCanvas.getBoundingClientRect();
    const fx = (e.clientX - rect.left) / rect.width;
    const fy = 1 - (e.clientY - rect.top) / rect.height;
    const { xMin, xMax, yMin, yMax } = state.view;
    const cx = xMin + fx * (xMax - xMin);
    const cy = yMin + fy * (yMax - yMin);

    state.view = {
      xMin: cx + (xMin - cx) * factor,
      xMax: cx + (xMax - cx) * factor,
      yMin: cy + (yMin - cy) * factor,
      yMax: cy + (yMax - cy) * factor,
    };
    scheduleDraw();
  }, { passive: false });

  new ResizeObserver(() => {
    if ($('#view-analysis').classList.contains('active')) scheduleDraw();
  }).observe(graphCanvas);
}

/* ============================================================ MATRICES
   Input into ready grid ячеек, как в шаблоне. No "1 2; 3 4" notation.
   Каждая ячейка проверяется на корректность при вводе.
   Результат можно применить к A и продолжить цепочку вычислений. */

const matrixA = { rows: 3, cols: 3, cells: [] };

function makeMatrixStore(store, rows, cols, fill = '') {
  store.rows = rows;
  store.cols = cols;
  store.cells = Array.from({ length: rows }, () => Array(cols).fill(fill));
}

/** Rebuild grid ячеек. Сохраняет уже введённые значения. */
function renderMatrixGrid(which) {
  const store = matrixA;
  const host = $('#grid-a');
  if (!host) return;

  host.style.gridTemplateColumns = `repeat(${store.cols}, auto)`;
  host.innerHTML = '';

  for (let r = 0; r < store.rows; r++) {
    for (let c = 0; c < store.cols; c++) {
      const input = document.createElement('input');
      input.type = 'text';
      input.value = store.cells[r][c] ?? '';
      input.dataset.r = String(r);
      input.dataset.c = String(c);
      input.setAttribute('aria-label', `${which.toUpperCase()}[${r + 1}][${c + 1}]`);

      input.addEventListener('input', () => {
        store.cells[r][c] = input.value;
        validateCell(input);
      });

      // Enter и стрелки ведут себя как в таблице — это заметно удобнее мыши
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === 'ArrowDown') {
          e.preventDefault();
          focusCell(which, r + 1, c);
        } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          focusCell(which, r - 1, c);
        } else if (e.key === 'ArrowRight' && input.selectionStart === input.value.length) {
          e.preventDefault();
          focusCell(which, r, c + 1);
        } else if (e.key === 'ArrowLeft' && input.selectionStart === 0) {
          e.preventDefault();
          focusCell(which, r, c - 1);
        }
      });

      input.addEventListener('focus', () => input.select());
      host.appendChild(input);
    }
  }
}

function focusCell(which, r, c) {
  if (r < 0 || c < 0) return;
  const host = $('#grid-a');
  const target = host.querySelector(`input[data-r="${r}"][data-c="${c}"]`);
  if (target) {
    target.focus();
    target.select();
  }
}

/** Immediate validation ячейки: видно сразу, а не после нажатия кнопки. */
function validateCell(input) {
  const value = input.value.trim();
  if (!value) {
    input.classList.remove('invalid');
    return;
  }
  // Допускаем числа, дроби вида 3/4, pi, e, корни и простые выражения
  const ok = /^[-+*/^(). 0-9a-zA-Z\u03c0\u221a]+$/.test(value);
  input.classList.toggle('invalid', !ok);
}

/** Collect matrix в строку для Python. Check all cells filled. */
/** Write matrix из ответа Python в ячейки. */
function writeMatrix(which, grid) {
  const store = matrixA;
  if (!Array.isArray(grid) || !grid.length) return;

  const rows = grid.length;
  const cols = grid[0].length;
  makeMatrixStore(store, rows, cols);
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      store.cells[r][c] = String(grid[r][c] ?? '');
    }
  }
  renderMatrixGrid(which);
}

function resizeMatrix(which, dRow, dCol) {
  const store = matrixA;
  const rows = Math.min(8, Math.max(1, store.rows + dRow));
  const cols = Math.min(8, Math.max(1, store.cols + dCol));

  const cells = Array.from({ length: rows }, (_, r) =>
    Array.from({ length: cols }, (_, c) => store.cells[r]?.[c] ?? ''));

  store.rows = rows;
  store.cols = cols;
  store.cells = cells;
  renderMatrixGrid(which);

  // keep the "rows x cols" readout in step with the grid
  if (which === 'a') updateCarouselLabel();
}

function fillMatrix(which, kind) {
  const store = matrixA;

  if (kind === 'identity') {
    makeMatrixStore(store, store.rows, store.cols, '0');
    for (let i = 0; i < Math.min(store.rows, store.cols); i++) {
      store.cells[i][i] = '1';
    }
  } else if (kind === 'clear') {
    makeMatrixStore(store, store.rows, store.cols, '');
  } else {
    // A fixed 3x3 was useless after the first look: every press produced the
    // same grid. Random entries make it a real exercise.
    const low = -9;
    const high = 9;
    store.cells = Array.from({ length: store.rows }, () =>
      Array.from({ length: store.cols }, () =>
        String(Math.floor(Math.random() * (high - low + 1)) + low)));
  }

  renderMatrixGrid(which);
}





/* ============================================================ THEME */

/**
 * Apply a colour scheme.
 *
 * ``auto`` follows the operating system through ``prefers-color-scheme``;
 * ``light`` and ``dark`` pin it. The choice is stored in settings so the window
 * opens in the same scheme next time.
 */
function applyTheme(choice) {
  const root = document.documentElement;
  if (choice === 'auto') root.removeAttribute('data-theme');
  else root.setAttribute('data-theme', choice);

  $$('[data-theme-choice]').forEach((btn) => {
    btn.setAttribute('aria-pressed', String(btn.dataset.themeChoice === choice));
  });
  state.theme = choice;
}

async function chooseTheme(choice) {
  applyTheme(choice);
  try {
    await py('settings_set', { theme: choice });
  } catch { /* engine not ready: the choice still applies this session */ }
}


/**
 * Render a title sent as ``[key, arg]``.
 *
 * Python returns a tuple instead of a sentence so the heading can be localised:
 * `("calculus.title.limit", "0")` becomes "Предел в точке 0" or "Limit at 0".
 */
function titleText(title) {
  if (Array.isArray(title)) {
    const [key, arg] = title;
    return `${message(key)}${arg ? ' ' + String(arg) : ''}`;
  }
  if (typeof title === 'string' && title.includes('.')) return message(title);
  return String(title || '');
}

function renderTitle(title) {
  return `<h4>${escapeHtml(titleText(title))}</h4>`;
}

/* ============================================================ STEPS + EXPORT */

state.lastSolution = null;

/**
 * Render the worked solution for the current equation.
 *
 * Steps arrive as ``{n, text, latex}``. LaTeX is typeset so the working looks
 * like the input, and the whole payload is kept for PDF/LaTeX export.
 */
async function showSteps() {
  const out = '#eq-out';
  await guarded(out, async () => {
    const equations = collectEquations().map(resolveAns);
    const expression = equations[0];
    showResult(out, '\u2026');

    // Two or more equations: ask for the elimination, not two answers
    const res = equations.length > 1
      ? await py('steps', expression, 'system', equations.slice(1))
      : await py('steps', expression, 'auto');
    if (!res.ok) return showError(out, message(res.error));

    // The last step carries the answer; keep its LaTeX for export rather than
    // scraping the rendered DOM, which would glue all steps together.
    const finalStep = res.steps.length ? res.steps[res.steps.length - 1] : null;
    state.lastSolution = {
      title: res.title,
      steps: res.steps,
      answer: finalStep ? (finalStep.latex || finalStep.text || '') : '',
    };

    const blocks = [renderTitle(res.title), '<div class="steps">'];
    for (const step of res.steps) {
      const body = step.latex && step.latex !== step.text
        ? renderInlineMath(step.latex)
        : escapeHtml(message(step.text));
      const caption = step.text && step.latex !== step.text
        ? `<div class="step-caption">${escapeHtml(message(step.text))}</div>`
        : '';
      blocks.push(`<div class="step"><span class="step-n">${step.n}</span>` +
                  `<div class="step-body">${caption}${body}</div></div>`);
    }
    blocks.push('</div>');
    showResult(out, '', blocks.join(''));
  });
}

/** Collect the answer text for the export payload. */
function currentAnswerText() {
  const el = $('#eq-out');
  return el ? el.textContent.trim().slice(0, 400) : '';
}

async function exportSolution(kind) {
  const status = '#export-status';
  await guarded(status, async () => {
    const solution = state.lastSolution;
    if (!solution) throw new Error(t('steps.show_first'));

    const payload = {
      title: titleText(solution.title),
      steps: solution.steps.map((step) => ({ ...step, text: step.text ? message(step.text) : step.text })),
      answer: solution.answer || currentAnswerText(),
      language: I18n.get(),
    };

    const method = kind === 'pdf' ? 'export_pdf' : 'export_latex';
    const res = await py(method, 'solution', payload, '');
    if (!res.ok) return showError(status, message(res.error));

    $(status).textContent = `${t('export.saved')}: ${res.path}`;
  });
}



/** Status line under the matrix editor: saves, loads, deletes. */
function showMatrixStatus(text, isError = false) {
  const el = $('#mx-status');
  if (!el) return;
  el.textContent = text;
  el.style.color = isError ? 'var(--err)' : 'var(--note)';
}

/* ============================================================ MATRIX TAB */

/**
 * Evaluate whatever is typed in the matrix calculator.
 *
 * Saved matrices are already visible to ``solve`` server-side, so `rank(F)` and
 * `A*B` work as soon as the letter exists in the carousel.
 */
async function evaluateMatrixExpression() {
  const field = $('#mx-input');
  if (!field || typeof field.getValue !== 'function') return;

  const expr = resolveAns(latexToPlain(field.getValue()));
  if (!expr.trim()) return;

  const out = $('#mx-out');
  const form = $('#mx-form');
  out.className = 'lcd-out';
  out.textContent = '\u2026';

  try {
    const res = await py('solve', expr);
    if (!res.ok) {
      out.className = 'lcd-out error';
      out.textContent = message(res.error) || t('common.error');
      return;
    }
    state.lastExpression = expr;
    state.answerLatex = res.latex || res.result;
    state.answerForm = res.form_key || 'exact';
    // No mode label here: the field already says what tab this is, and a
    // "3 × 3" tag next to a result read as if it belonged to the answer.
    if (form) form.textContent = '';

    out.innerHTML = '';
    if (res.latex) {
      try {
        out.innerHTML = window.MathLive.convertLatexToMarkup(res.latex, { displayMode: false });
      } catch {
        out.textContent = res.result;
      }
    } else {
      out.textContent = res.result;
    }
  } catch (err) {
    out.className = 'lcd-out error';
    out.textContent = message(err.message) || String(err);
  }
}

/* ============================================================ MATRIX CAROUSEL */

state.savedMatrices = [];
state.carouselIndex = 0;
state.currentLetter = 'A';

/**
 * Reload the list of saved matrices and point the carousel at a letter.
 * Called after saving, deleting and on startup.
 */
async function refreshCarousel(selectLetter = null) {
  try {
    const res = await py('matrix_list');
    if (!res.ok) return;

    state.savedMatrices = res.items || [];
    if (selectLetter) {
      const index = state.savedMatrices.findIndex((m) => m.name === selectLetter);
      state.carouselIndex = index >= 0 ? index : 0;
    }
    updateCarouselLabel();
  } catch {
    // The carousel is a convenience: failure must not block the tab
  }
}

/**
 * Refresh the letter and size shown above the grid.
 *
 * The size must come from the GRID being edited, not from the saved record:
 * after +row the grid is 3x4 while the stored copy is still 3x3, so reading
 * the record showed a stale "3 x 3" next to a 3x4 grid.
 */
function updateCarouselLabel() {
  const total = state.savedMatrices.length;
  const label = $('#mx-name');
  const size = $('#mx-size');
  if (!label) return;

  const letterInput = $('#mx-letter');
  const editing = (letterInput && letterInput.value || '').trim().toUpperCase();

  if (!total) {
    label.textContent = editing || '—';
    if (size) size.textContent = `${matrixA.rows} × ${matrixA.cols}`;
    return;
  }

  const item = state.savedMatrices[state.carouselIndex % total];
  state.currentLetter = item.name;
  label.textContent = item.name;

  // Size of the grid on screen, which is what the user is looking at
  if (size) size.textContent = `${matrixA.rows} × ${matrixA.cols}`;
  if (letterInput) letterInput.value = item.name;
}

/** Load a saved matrix into the editable grid. */
async function loadMatrixIntoGrid(name) {
  try {
    const res = await py('matrix_get', name);
    if (!res.ok) return showMatrixStatus(message(res.error), true);

    writeMatrix('a', res.grid);
    updateCarouselLabel();
    showMatrixStatus(`${name} · ${res.grid.length} × ${res.grid[0].length}`);
  } catch (err) {
    showMatrixStatus(message(err.message), true);
  }
}

function carouselStep(delta) {
  const total = state.savedMatrices.length;
  if (!total) return;
  state.carouselIndex = (state.carouselIndex + delta + total) % total;
  updateCarouselLabel();
  loadMatrixIntoGrid(state.savedMatrices[state.carouselIndex].name);
}

/** Save the current grid under the letter typed in the field. */
async function saveCurrentMatrix() {
  await guarded('#mx-out', async () => {
    const letter = ($('#mx-letter').value || '').trim().toUpperCase();
    if (!/^[A-H]$/.test(letter)) {
      throw new Error(t('matrix.need_letter'));
    }

    const grid = matrixA.cells.map((row) => row.map((cell) => String(cell ?? '').trim()));
    for (const row of grid) {
      for (const cell of row) {
        if (!cell) throw new Error(t('matrix.fill_cells'));
      }
    }

    const res = await py('matrix_save', letter, grid);
    if (!res.ok) return showMatrixStatus(message(res.error), true);

    await refreshCarousel(letter);
    showMatrixStatus(`${letter} · ${res.rows} × ${res.cols} ✓`);
  });
}

async function deleteCurrentMatrix() {
  await guarded('#mx-out', async () => {
    const letter = ($('#mx-letter').value || '').trim().toUpperCase();
    const res = await py('matrix_delete', letter);
    if (!res.ok) return showMatrixStatus(message(res.error), true);
    await refreshCarousel();

    showMatrixStatus(`${letter} —`);
  });
}

/* ============================================================ EQUATIONS
   Input via MathLive — тот же редактор, что в калькуляторе. */

function addEquationsRow(latex = '') {
  const host = $('#eq-rows');
  if (!host) return;

  state.eqCount += 1;

  const row = document.createElement('div');
  row.className = 'eq-row';

  const field = document.createElement('math-field');
  field.className = 'mf-input';
  field.setAttribute('aria-label', `equation ${state.eqCount}`);
  field.value = latex;

  const del = document.createElement('button');
  del.className = 'del';
  del.textContent = '×';
  del.title = t('eq.remove');
  del.addEventListener('click', () => {
    // Keep at least one row: пустой список выглядит как поломка
    if ($$('#eq-rows .eq-row').length <= 1) return;
    row.remove();
  });

  row.append(field, del);
  host.appendChild(row);
  field.focus();
}

function collectEquations() {
  const values = $$('#eq-rows math-field')
    .map((field) => latexToPlain(field.getValue ? field.getValue() : field.value || ''))
    .map((s) => s.trim())
    .filter(Boolean);

  if (!values.length) throw new Error(t('err.empty'));
  return values;
}

async function solveEquations() {
  const out = '#eq-out';
  await guarded(out, async () => {
    const equations = collectEquations();

    showResult(out, '\u2026');

    if (equations.length > 1) {
      const res = await py('solve_system', equations);
      if (!res.ok) return showError(out, message(res.error) || t('common.error'));
      // The engine answers with {text, latex}; "result" was never one of them,
      // so every solution rendered as "undefined".
      return renderSolution(out, res);
    }

    const res = await py('solve_equation', equations[0]);
    if (!res.ok) return showError(out, message(res.error) || t('common.error'));
    renderSolution(out, res);
  });
}

/** Show a solution: typeset when LaTeX is present, plain text otherwise. */
function renderSolution(selector, res) {
  if (res.latex) {
    // A caveat such as "roots are complex" prevents asin(2) from being read as
    // a real answer to sin(x) = 2.
    const note = res.note ? `<div class="solution-note">${escapeHtml(message(res.note))}</div>` : '';
    showResult(selector, '', `<div class="solution">${renderInlineMath(res.latex)}</div>${note}`);
    return;
  }
  // Messages such as ExprError.no_solution arrive in "text"
  const text = message(res.text || '');
  showResult(selector, text);
}


/* ============================================================ AI */

const chatEl = $('#chat');

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

/* Markdown + formulas.
 *
 * Formulas are extracted BEFORE marked, otherwise it eats the underscores and
 * asterisks inside them ($a_1$ becomes italic "a" plus a literal "1").
 *
 * Four delimiters are recognised. Local models are inconsistent: the same model
 * emits $...$ in one answer and \[...\] in the next, and the prompt asks for
 * $ but does not always win. Handling only $ left raw LaTeX on screen — that is
 * exactly what "Теорема Лагранжа: \[ \lim..." in the screenshot was.
 *
 *   \[ ... \]  display
 *   $$ ... $$  display
 *   \( ... \)  inline
 *   $ ... $    inline
 */
const MATH_TOKEN =
  /\\\[([\s\S]+?)\\\]|\\\(([\s\S]+?)\\\)|\$\$([\s\S]+?)\$\$|\$([^$\n]+?)\$/g;

/**
 * Close any delimiter left open by a half-streamed answer.
 *
 * While text streams in, the model sends "\[ \lim_{x \to" long before the
 * closing bracket arrives. Without balancing, MathLive receives a broken string
 * and the formula flashes as raw text until the end of the answer.
 */
function balanceMath(text) {
  let out = String(text || '');

  const pairs = [
    ['\\[', '\\]'],
    ['\\(', '\\)'],
    ['$$', '$$'],
  ];

  for (const [open, close] of pairs) {
    // Only count delimiters outside of the other kinds to avoid false pairs
    const opened = (out.match(new RegExp(open.replace(/[\\^$.*+?()[\]{}|]/g, '\\$&'), 'g')) || []).length;
    const closed = (out.match(new RegExp(close.replace(/[\\^$.*+?()[\]{}|]/g, '\\$&'), 'g')) || []).length;
    if (opened > closed) {
      out += close.repeat(opened - closed);
    }
  }

  // A lone trailing $ opens an inline formula
  const dollars = (out.match(/\$/g) || []).length;
  if (dollars % 2 === 1) out += '$';

  return out;
}

function renderMarkdown(src) {
  if (!src) return '';
  const store = [];

  const withoutMath = balanceMath(src).replace(MATH_TOKEN, (_, blockA, inlineA, blockB, inlineB) => {
    const latex = blockA || inlineA || blockB || inlineB || '';
    const display = Boolean(blockA || blockB);
    store.push({ latex: latex.trim(), display });
    return `\uE000${store.length - 1}\uE001`;
  });

  let html = marked.parse(withoutMath);

  html = html.replace(/\uE000(\d+)\uE001/g, (_, i) => {
    const item = store[Number(i)];
    if (!item) return '';
    try {
      return window.MathLive.convertLatexToMarkup(item.latex, { displayMode: item.display });
    } catch {
      return `<code>${escapeHtml(item.latex)}</code>`;
    }
  });

  return html;
}

function setAiBusy(busy) {
  state.busy = busy;
  $('#btn-send').disabled = busy;
  $('#btn-stop').disabled = !busy;
  $('#status-dot').className = 'dot' + (busy ? ' busy' : '');
}

/** Check environment перед отправкой. Better to notify upfront, чем ждать ошибку. */
async function ensureAiReady() {
  const settings = await py('settings_get');
  const model = settings.model || '';

  if (!model) {
    throw new Error(t('ai.need_model'));
  }

  const status = await py('ollama_status');
  if (!status.installed) throw new Error(t('ai.no_ollama'));
  if (!status.running) throw new Error(t('ai.no_ollama'));

  const installed = (status.models || []).some((m) => m.name === model);
  if (!installed) {
    throw new Error(`${t('ai.need_model')} (${model})`);
  }
  return model;
}

/* ============================================================ CONVERSATIONS */

/**
 * Conversation tabs.
 *
 * Each tab is a separate history on the Python side: a follow-up question in
 * one tab must not inherit the context of another. The list lives only in the
 * page — histories are cheap to recreate, and persisting them would need a
 * migration path for every future field.
 */
const chats = {
  items: [],
  active: null,
  seq: 0,
};

function newConversationId() {
  chats.seq += 1;
  return `chat-${Date.now()}-${chats.seq}`;
}

function activeConversation() {
  return chats.active || '';
}

/** Draw the tab strip: title, close button, and a "+" to add one. */
function renderChatTabs() {
  const host = $('#chat-tabs');
  if (!host) return;
  host.innerHTML = '';

  for (const item of chats.items) {
    const tab = document.createElement('div');
    tab.className = 'chat-tab';
    tab.setAttribute('role', 'tab');
    tab.setAttribute('aria-selected', String(item.id === chats.active));

    const label = document.createElement('button');
    label.className = 'chat-tab-label';
    label.type = 'button';
    // The first message becomes the title; an empty tab keeps a number
    label.textContent = item.title || `${t('ai.dialog')} ${item.number}`;
    label.title = label.textContent;
    label.addEventListener('click', () => switchConversation(item.id));

    const close = document.createElement('button');
    close.className = 'chat-tab-close';
    close.type = 'button';
    close.textContent = '\u00d7';
    close.title = t('ai.close_dialog');
    close.addEventListener('click', (event) => {
      event.stopPropagation();
      closeConversation(item.id);
    });

    tab.append(label, close);
    host.appendChild(tab);
  }

  const add = document.createElement('button');
  add.className = 'chat-tab-add';
  add.type = 'button';
  add.textContent = '+';
  add.title = t('ai.new');
  add.addEventListener('click', () => openConversation());
  host.appendChild(add);
}

/** Create a tab and make it the active one. */
function openConversation(id = null) {
  const conversationId = id || newConversationId();
  chats.items.push({
    id: conversationId,
    number: chats.items.length + 1,
    title: '',
    messages: [],
  });
  chats.active = conversationId;
  renderChatTabs();
  renderActiveChat();
  py('ai_new_chat', conversationId).catch(() => {});
  const input = $('#ai-input');
  if (input) input.focus();
  return conversationId;
}

/** Close a tab: drop the history on both sides. */
function closeConversation(conversationId) {
  const index = chats.items.findIndex((item) => item.id === conversationId);
  if (index < 0) return;

  chats.items.splice(index, 1);
  py('ai_drop_chat', conversationId).catch(() => {});

  // Closing the last tab leaves one empty tab: a window with no chat box
  // looks broken, and the user would have to find "+" to type anything.
  if (!chats.items.length) {
    openConversation();
    return;
  }

  if (chats.active === conversationId) {
    const next = chats.items[Math.min(index, chats.items.length - 1)];
    chats.active = next.id;
  }
  renderChatTabs();
  renderActiveChat();
}

function switchConversation(conversationId) {
  if (chats.active === conversationId) return;
  chats.active = conversationId;
  renderChatTabs();
  renderActiveChat();
}

function currentChat() {
  return chats.items.find((item) => item.id === chats.active) || null;
}

/** Repaint the message list from the stored messages of the active tab. */
function renderActiveChat() {
  const chatEl = $('#chat');
  if (!chatEl) return;
  chatEl.innerHTML = '';

  const item = currentChat();
  if (!item) return;

  if (!item.messages.length) {
    chatEl.innerHTML = `<div class="msg ai"><div class="md"><p>${escapeHtml(t('ai.welcome'))}</p></div></div>`;
    return;
  }

  for (const message of item.messages) {
    if (message.role === 'user') {
      const wrap = document.createElement('div');
      wrap.className = 'msg user';
      wrap.innerHTML = escapeHtml(message.text);
      chatEl.appendChild(wrap);
      continue;
    }

    const wrap = document.createElement('div');
    wrap.className = 'msg ai';
    const body = document.createElement('div');
    body.className = 'md';
    body.innerHTML = renderMarkdown(message.text || '');
    wrap.appendChild(body);

    if (message.theory && message.theory.length) {
      wrap.appendChild(buildTheoryBlock(message.theory));
    }
    if (message.looping) {
      const note = document.createElement('div');
      note.className = 'answer-note';
      note.textContent = t('ai.looping');
      wrap.appendChild(note);
    }
    chatEl.appendChild(wrap);
  }

  const scroller = $('#ai-body');
  if (scroller) scroller.scrollTop = scroller.scrollHeight;
}

/**
 * The formulas the answer was grounded on.
 *
 * Shown under the answer, not instead of it: the model writes the reasoning,
 * these cards supply the exact statement. A student can check that the formula
 * in the answer matches the one in the reference.
 */
function buildTheoryBlock(entries) {
  const box = document.createElement('div');
  box.className = 'theory';

  const head = document.createElement('div');
  head.className = 'theory-head';
  head.innerHTML = `<span>${escapeHtml(t('ai.theory'))}</span>`;
  box.appendChild(head);

  for (const entry of entries) {
    const card = document.createElement('div');
    card.className = 'theory-card';

    const title = document.createElement('div');
    title.className = 'theory-title';
    title.textContent = message(entry.title);
    card.appendChild(title);

    const formula = document.createElement('div');
    formula.className = 'theory-formula';
    try {
      formula.innerHTML = window.MathLive.convertLatexToMarkup(entry.latex, { displayMode: true });
    } catch {
      formula.textContent = entry.latex;
    }
    card.appendChild(formula);

    // After layout, let the box grow to the rendered formula's real height.
    // MathLive sets its own height only after fonts load, and without this the
    // card kept a fixed 26 px window and a scrollbar appeared inside it.
    requestAnimationFrame(() => {
      const rendered = formula.firstElementChild;
      if (!rendered) return;
      const height = rendered.getBoundingClientRect().height;
      if (height > 0) formula.style.minHeight = `${Math.ceil(height) + 8}px`;
    });

    if (entry.example) {
      const example = document.createElement('div');
      example.className = 'theory-example';
      try {
        example.innerHTML = window.MathLive.convertLatexToMarkup(entry.example, { displayMode: false });
      } catch {
        example.textContent = entry.example;
      }
      card.appendChild(example);
    }

    box.appendChild(card);
  }

  return box;
}

/* ============================================================ AI REQUESTS */

async function sendAiMessage() {
  if (state.busy) return;

  const input = $('#ai-input');
  const text = (input.value || '').trim();
  const hasImage = Boolean(state.pendingImage);

  if (!text && !hasImage) {
    $('#ai-status').textContent = t('err.empty');
    return;
  }
  if (!chats.active) openConversation();

  const item = currentChat();
  const conversationId = item.id;

  const note = hasImage ? `\n\ud83d\udcce ${t('ai.photo_attached')}` : '';
  item.messages.push({ role: 'user', text: (text || t('ai.photo')) + note });

  // The first message titles the tab, trimmed to something a tab can show
  if (!item.title) {
    item.title = (text || t('ai.photo')).slice(0, 28);
    renderChatTabs();
  }

  input.value = '';
  renderActiveChat();

  const image = state.pendingImage;
  clearAttachment();

  setAiBusy(true);
  $('#ai-status').textContent = t('ai.thinking');

  // Placeholder for the streaming answer
  const message = { role: 'ai', text: '', theory: [] };
  item.messages.push(message);
  const chatEl = $('#chat');
  const wrap = document.createElement('div');
  wrap.className = 'msg ai';
  const body = document.createElement('div');
  body.className = 'md';
  body.innerHTML = '<span class="stream-caret"></span>';
  wrap.appendChild(body);
  chatEl.appendChild(wrap);

  let buffer = '';

  window.__stream = {
    token(piece) {
      // A tab switched mid-answer keeps receiving text: write it to its own
      // message object, not to whatever tab is on screen now.
      buffer += piece;
      message.text = buffer;
      if (chats.active !== conversationId) return;
      body.innerHTML = renderMarkdown(buffer) + '<span class="stream-caret"></span>';
      const scroller = $('#ai-body');
      if (scroller) scroller.scrollTop = scroller.scrollHeight;
    },
    theory(entries) {
      message.theory = entries || [];
      if (chats.active !== conversationId) return;
      const existing = wrap.querySelector('.theory');
      if (existing) existing.remove();
      if (message.theory.length) wrap.appendChild(buildTheoryBlock(message.theory));
    },
    done(meta) {
      /* Three special endings arrive without a streamed answer, so `buffer` is
         empty in all of them: a refusal, a clarification request, and a loop
         cut-off. Each carries a message key in ``meta.answer`` instead. */
      const refused = Boolean(meta && meta.refused);
      const clarify = Boolean(meta && meta.clarify);

      if (clarify) {
        // Nothing was recognised and the model was not sure: ask the user to
        // narrow it down rather than show a card picked at random.
        buffer = `${t('ai.clarify')}\n\n${t('ai.clarify_hint')}`;
        message.theory = [];
      } else if (refused) {
        const key = (meta && meta.answer) || 'guard.weapons';
        // Self-harm gets a supportive message on its own; appending the
        // "I help with mathematics" line to it would be crass.
        const care = Boolean(meta && meta.care);
        buffer = care ? message(key) : `${message(key)}\n\n${t('guard.note')}`;
        message.theory = [];
        message.care = care;
      }

      message.text = buffer;
      message.looping = Boolean(meta && meta.looping);
      message.refused = refused;
      message.clarify = clarify;

      if (chats.active === conversationId) {
        // Drop any theory card drawn before this ending arrived
        const stale = wrap.querySelector('.theory');
        if (stale) stale.remove();

        body.innerHTML = renderMarkdown(buffer);

        if (message.clarify) {
          const note = document.createElement('div');
          note.className = 'answer-note';
          note.textContent = t('ai.clarify_examples');
          wrap.appendChild(note);
        }

        if (message.looping) {
          // Say why the text stopped: a silent cut looks like a crash
          const note = document.createElement('div');
          note.className = 'answer-note';
          note.textContent = t('ai.looping');
          wrap.appendChild(note);
        }
      }
      finishAi(meta);
    },
    error(errorText) {
      message.text = `${t('common.error')}: ${errorText}`;
      message.error = true;
      if (chats.active === conversationId) {
        body.innerHTML =
          `<p style="color:var(--err)"><b>${escapeHtml(t('common.error'))}:</b> ${escapeHtml(errorText)}</p>`;
      }
      finishAi({});
    },
  };

  try {
    await ensureAiReady();
    const bare = image ? image.split(',')[1] : null;
    const res = await py('ai_ask',
      text || '\u0420\u0435\u0448\u0438 \u0437\u0430\u0434\u0430\u0447\u0443 \u043d\u0430 \u0444\u043e\u0442\u043e, \u043e\u0431\u044a\u044f\u0441\u043d\u0438 \u0448\u0430\u0433\u0438.',
      bare, null, conversationId);
    if (!res.ok) {
      const reason = message(res.error);
      message.text = reason;
      body.innerHTML = `<p style="color:var(--err)">${escapeHtml(reason)}</p>`;
      finishAi({});
    }
  } catch (err) {
    const reason = err.message || String(err);
    message.text = reason;
    body.innerHTML = `<p style="color:var(--err)">${escapeHtml(reason)}</p>`;
    finishAi({});
  }
}

function finishAi(meta) {
  setAiBusy(false);
  $('#ai-status').textContent = '';
  if (meta && meta.tokens) {
    $('#ai-stats').textContent =
      `${meta.tokens} tok \u00b7 ${meta.tokens_per_s}/s \u00b7 ${meta.elapsed_s}s`;
  }
  window.__stream = null;
}

/* Event handlers from Python. pywebview calls them через evaluate_js. */
/* The chip beside the AI title shows the model that answers, by name only. */
function renderModelChip(name) {
  const chip = $('#ai-model-chip');
  if (!chip) return;
  chip.textContent = name || '—';
  chip.title = name ? `${t('ai.model')}: ${name}` : '';
}

window.Euler = {
  onAiStart(d) {
    renderModelChip(d.model);
    $('#ai-status').textContent = t('ai.thinking');
    // The reference entries the answer is grounded on, retrieved server-side
    if (window.__stream && window.__stream.theory) {
      window.__stream.theory(d.theory || []);
    }
  },
  onToken(d) {
    if (window.__stream) window.__stream.token(d.text || '');
  },
  onStats(d) {
    $('#ai-stats').textContent = `${d.tokens} tok · ${d.tokens_per_s}/s · ${d.elapsed_s}s`;
  },
  onAiDone(d) {
    if (window.__stream) window.__stream.done(d);
  },
  onAiError(d) {
    if (window.__stream) window.__stream.error(d.error || '');
  },
  onService(d) {
    const line = $('#setup-status');
    const bar = $('#setup-progress');
    const onbBar = $('#onb-progress');
    const onbStatus = $('#onb-status');
    if (d.stage === 'download') {
      const percent = d.percent || 0;
      const gb = d.total_gb ? ` · ${d.completed_gb}/${d.total_gb} GB` : '';
      if (bar) bar.firstElementChild.style.width = `${percent}%`;
      if (onbBar) onbBar.firstElementChild.style.width = `${percent}%`;
      if (line) line.textContent = `${t('setup.ollama_downloading')} · ${percent}%${gb}`;
      if (onbStatus) onbStatus.textContent = `${t('setup.ollama_downloading')} · ${percent}%${gb}`;
      return;
    }
    const label = d.text ? t(d.text) : '';
    if (line) line.textContent = label;
    if (onbStatus) onbStatus.textContent = label;
    if (d.stage === 'install') {
      if (bar) bar.firstElementChild.style.width = '15%';
      if (onbBar) onbBar.firstElementChild.style.width = '15%';
    }
  },
  onServiceDone(d) {
    const line = $('#setup-status');
    if (line) line.textContent = d.cancelled ? t('setup.cancelled') : message(d.text || '');
    showSetupBusy(false);
    loadOllamaStatus();
  },
  onPull(d) {
    const percent = d.percent || 0;
    const gb = d.total_gb ? ` · ${d.completed_gb}/${d.total_gb} GB` : '';

    const bar = $('#setup-progress');
    if (bar) bar.firstElementChild.style.width = `${percent}%`;
    const line = $('#setup-status');
    if (line) line.textContent = `${d.stage || 'download'} · ${percent}%${gb}`;

    const onbBar = $('#onb-progress');
    if (onbBar) onbBar.firstElementChild.style.width = `${percent}%`;
    const onbStatus = $('#onb-status');
    if (onbStatus) onbStatus.textContent = `${percent}%${gb}`;
  },
  onDeleteDone(d) {
    onDeleteFinished(d || {});
  },
  onPullDone(d) {
    const line = $('#setup-status');
    showSetupBusy(false);
    if (line) {
      if (d.cancelled) line.textContent = t('setup.cancelled');
      else line.textContent = d.ok ? 'OK' : `${t('common.error')}: ${message(d.error)}`;
    }
    if (d.ok) {
      loadOllamaStatus();
      const overlay = $('#onboarding');
      if (overlay) overlay.hidden = true;
    }
  },
  onSetupDone(d) {
    const line = $('#setup-status');
    showSetupBusy(false);
    if (line) line.textContent = d.cancelled ? t('setup.cancelled') : (d.ok ? (d.text || '') : message(d.text || d.error || ''));
    if (d.ok) {
      const bar = $('#setup-progress');
      if (bar) bar.firstElementChild.style.width = '100%';
      loadOllamaStatus();
    }
  },
};

/* ---------------------------------------------------------- фото */

function clearAttachment() {
  state.pendingImage = null;
  $('#attach-row').hidden = true;
  $('#thumb-img').src = '';
  $('#thumb-name').textContent = '';
}

/** Resize image до 1024 px: vision models do not need more. */
function prepareImage(source, name) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      const max = 1024;
      let w = img.width;
      let h = img.height;
      if (w > max || h > max) {
        const scale = Math.min(max / w, max / h);
        w = Math.round(w * scale);
        h = Math.round(h * scale);
      }
      const canvas = document.createElement('canvas');
      canvas.width = w;
      canvas.height = h;
      canvas.getContext('2d').drawImage(img, 0, 0, w, h);

      state.pendingImage = canvas.toDataURL('image/jpeg', 0.85);
      $('#thumb-img').src = state.pendingImage;
      $('#thumb-name').textContent = name;
      $('#attach-row').hidden = false;
      resolve(state.pendingImage);
    };
    img.onerror = () => resolve(null);
    img.src = source;
  });
}

/* ============================================================ SETTINGS */

const CATALOG = [
  { tag: 'qwen2.5:0.5b', size_gb: 0.4, ram_gb: 2,  desc: 'minimal' },
  { tag: 'qwen2.5:1.5b', size_gb: 1.0, ram_gb: 4,  desc: 'light' },
  { tag: 'qwen2.5:3b',   size_gb: 2.0, ram_gb: 6,  desc: 'balanced' },
  { tag: 'qwen2.5:7b',   size_gb: 4.7, ram_gb: 12, desc: 'accurate' },
  { tag: 'qwen2.5:14b',  size_gb: 9.0, ram_gb: 20, desc: 'pro' },
  { tag: 'llava:7b',     size_gb: 4.7, ram_gb: 12, desc: 'vision' },
  { tag: 'qwen2-vl:7b',  size_gb: 4.9, ram_gb: 12, desc: 'vision+' },
];

async function loadSettings() {
  await guarded('#hw-out', async () => {
    const settings = await py('settings_get');

    // The installer writes the chosen language; trust it over the browser's
    // locale the first time, then the user's own setting wins.
    const fromInstaller = (settings.language || '').trim();
    I18n.set(I18n.detect(fromInstaller || null));
    buildLangGrid();
    I18n.apply();
    applyTheme(settings.theme || 'auto');

    await restoreUserState(settings);

    state.model = settings.model || '';
  renderModelChip(state.model);
    $('#set-temp').value = settings.temperature ?? 0.3;
    $('#temp-val').textContent = Number(settings.temperature ?? 0.3).toFixed(2);

    const hw = settings.hardware;
    if (hw) {
      renderHardware(hw);
    } else {
      // First launch (or an install that skipped the wizard): probe now and
      // persist. Reading only the saved value left the panel empty forever.
      $('#hw-out').textContent = t('common.loading');
      setHwState('detecting');
      py('hardware', false)
        .then((probed) => {
          if (!probed || !probed.ok) {
            setHwState('failed');
            return;
          }
          // The bridge spreads the profile, so the spec lives under "hardware"
          // for the nested fields and at the top level for the rest.
          renderHardware({ ...(probed.hardware || {}), model: probed.model });
        })
        .catch(() => { setHwState('failed'); });
    }
  });

  await loadOllamaStatus();
}

/**
 * Show the machine profile.
 *
 * The bridge returns ``{ok, model, hardware: {cpu, ram_gb, ...}}`` while the
 * saved settings hold the same profile flat. Both shapes reach this function,
 * so the fields are read from either place — otherwise the panel printed
 * "undefined" for a profile that had been detected correctly.
 */
/** Redraw the hardware panel in the current language, if it has data. */
function renderHardwarePanel() {
  if (state.hardwareProfile) renderHardware(state.hardwareProfile);
}

/** Set the pill beside the hardware heading: detecting, done or failed. */
function setHwState(kind) {
  const el = $('#hw-state');
  if (!el) return;
  const key = ONB_STATE_KEYS[kind] || ONB_STATE_KEYS.detecting;
  el.dataset.state = kind;
  el.dataset.i18n = key;
  el.textContent = t(key);
}

function renderHardware(profile) {
  const el = $('#hw-out');
  if (!el) return;
  el.classList.remove('error');

  // Remember the profile: the panel is redrawn on a language switch, and the
  // labels are the only thing that changes.
  if (profile) state.hardwareProfile = profile;
  const source = profile || state.hardwareProfile || {};
  const spec = source.hardware || source;

  const cpu = spec.cpu || spec.cpu_name || EM_DASH;
  const ram = spec.ram_gb ?? spec.total_ram_gb;
  const vram = spec.vram_gb;
  const model = source.model || source.recommended || spec.model || EM_DASH;

  // The same rows as the first-run card, so the machine profile reads the same
  // in both places: key on the left, value in the accent colour.
  const rows = [
    [t('hw.cpu'), cpu],
    [t('hw.ram'), `${ram ?? '?'} ${t('hw.gb')}`],
  ];
  if (vram) rows.push([t('hw.vram'), `${vram} ${t('hw.gb')}`]);
  rows.push([t('hw.recommend'), model]);

  el.innerHTML = rows.map(([key, value]) =>
    '<div class="onb-row"><span class="onb-key">' + escapeHtml(key) + '</span>' +
    '<span class="onb-val">' + escapeHtml(String(value)) + '</span></div>').join('');

  setHwState('done');
}

function buildLangGrid() {
  const host = $('#lang-grid');
  if (!host) return;
  host.innerHTML = '';

  for (const code of I18n.langs) {
    const btn = document.createElement('button');
    btn.className = 'lang-btn';
    btn.type = 'button';
    btn.setAttribute('aria-pressed', String(code === I18n.get()));

    const native = document.createElement('span');
    native.className = 'native';
    native.textContent = I18N[code]['lang.name'];

    const label = document.createElement('span');
    label.className = 'code';
    label.textContent = code.toUpperCase();

    btn.append(native, label);
    btn.addEventListener('click', async () => {
      I18n.set(code);
      buildLangGrid();
      retranslateDynamic();
      refreshStatus();
      await py('settings_set', { language: code });
      // Reference titles come from the bridge as keys: re-render in the new
      // language instead of leaving the old one until the tab is reopened.
    });
    host.appendChild(btn);
  }
}

/**
 * Retranslate all JS-built UI after language switch.
 * Static HTML is handled by I18n.apply(), but keyboards, chart labels, etc.
 * need manual rebuild.
 */
/**
 * Retranslate everything the HTML attributes cannot reach.
 *
 * ``I18n.apply()`` walks ``data-i18n`` attributes, so static markup switches
 * instantly. Text built in JavaScript — the hardware panel, the model list,
 * conversation tab titles — has no attribute to walk and stayed in the old
 * language until the tab was reopened. That lag is what made the switch look
 * half-applied.
 */
function retranslateDynamic() {
  buildKeyboard('#keys', '#lcd-input');
  buildKeyboard('#kb-cx', '#cx-fn');
  buildKeyboard('#kb-an', '#fn-list .fn-row.is-active math-field');
  buildKeyboard('#kb-eq', null);
  buildKeyboard('#mx-keys', '#mx-input');

  // Conversation tabs carry translated labels ("Диалог N", tooltips)
  renderChatTabs();
  renderActiveChat();

  // Chart hint
  const graphCard = document.querySelector('#view-analysis .card-head .card-note');
  if (graphCard) graphCard.textContent = t('analysis.graph_hint');

  // Hardware panel and model names are rendered from data, not markup
  renderHardwarePanel();
  loadOllamaStatus();
  refreshStatus();

  // Matrix status line and the saved-letter chip
  const mxStatus = $('#mx-status');
  if (mxStatus && mxStatus.dataset.key) mxStatus.textContent = t(mxStatus.dataset.key);

  // An answer already on screen keeps its text, but the labels around it move
  const formChip = $('#form-chip');
  if (formChip && formChip.dataset.key) formChip.textContent = t(formChip.dataset.key);
}

async function loadOllamaStatus() {
  try {
    const status = await py('ollama_status');
    if (!status.ok) return;

    const chip = $('#ollama-chip');
    if (!status.installed) {
      chip.textContent = t('settings.not_installed');
      chip.className = 'chip bad';
    } else if (!status.running) {
      chip.textContent = t('settings.not_running');
      chip.className = 'chip warn';
    } else {
      chip.textContent = `${t('settings.running')} · ${status.models.length} ${pluralCount(status.models.length, 'settings.models_count')}`;
      chip.className = 'chip ok';
    }

    const installSelect = $('#set-model');
    installSelect.innerHTML = '';
    for (const m of CATALOG) {
      const opt = document.createElement('option');
      opt.value = m.tag;
      opt.textContent = `${m.tag}  (${m.size_gb} GB · ${m.desc})`;
      installSelect.appendChild(opt);
    }

    const installedSelect = $('#set-model-installed');
    installedSelect.innerHTML = `<option value="">${t('settings.not_selected')}</option>`;
    for (const m of status.models || []) {
      const opt = document.createElement('option');
      opt.value = m.name;
      opt.textContent = `${m.name} (${m.size_gb} GB)`;
      installedSelect.appendChild(opt);
    }
    // A populated list with nothing selected left "Delete model" reporting
    // "no models installed" while a model was shown two centimetres above.
    if (state.model) installedSelect.value = state.model;
    else if (installedSelect.options.length > 1) installedSelect.value = installedSelect.options[1].value;
  } catch {
    /* silently: settings are non-critical для работы калькулятора */
  }
}


/**
 * Persist user state: language, unit mode, last input values.
 * Called on meaningful changes (not every keystroke).
 */
async function saveUserState() {
  try {
    await py('settings_set', {
      language: I18n.get(),
      unit: state.unit,
      last_calc_expr: readField('#lcd-input'),
      graph_functions: readFunctions(),
      graph_marked: state.fnMarked,
      analysis_interval: readField('#an-interval'),
      last_calculus_fn: readField('#cx-fn'),
      graph_view: state.view,
    });
  } catch {
    // Non-critical: state saving should never block UI
  }
}

/**
 * Restore user state from last session.
 */
async function restoreUserState(settings) {
  if (settings.unit && ['deg', 'rad'].includes(settings.unit)) {
    state.unit = settings.unit;
    $$('[data-unit]').forEach((b) =>
      b.setAttribute('aria-pressed', String(b.dataset.unit === state.unit)));
    const label = $('#lcd-unit');
    if (label) label.textContent = state.unit.toUpperCase();
  }

  if (settings.last_calc_expr) {
    setField('#lcd-input', settings.last_calc_expr);
  }
  const savedFunctions = Array.isArray(settings.graph_functions) ? settings.graph_functions : [];
  renderFnList(savedFunctions.length ? savedFunctions.map(String) : ['x^3-3x'],
    Number(settings.graph_marked) || 0);
  if (settings.analysis_interval) {
    setField('#an-interval', settings.analysis_interval);
  }
  if (settings.last_calculus_fn) {
    setField('#cx-fn', settings.last_calculus_fn);
  }
  if (settings.graph_view) {
    state.view = { ...state.view, ...settings.graph_view };
  }
}


/**
 * Render a list of result lines.
 *
 * Python returns ``{text, latex}`` pairs. LaTeX is typeset through MathLive so
 * limits, integrals and fractions look identical to what the user typed.
 */
function renderInlineMath(latex) {
  try {
    return window.MathLive.convertLatexToMarkup(latex, { displayMode: false });
  } catch {
    return escapeHtml(latex);
  }
}

function renderLines(lines) {
  const out = [];

  for (const line of lines) {
    const item = typeof line === 'string' ? { text: line, latex: null, math: false } : line;

    // A monotonicity line carries a translated label plus a separate formula:
    // "Возрастает  (π/2; 3π/2)". Joining them into one LaTeX string made the
    // key appear literally, because no translation can live inside a formula.
    if (item.key && item.range_latex) {
      out.push(
        `<div class="line"><span class="line-label">${escapeHtml(message(item.key))}</span>`
        + renderInlineMath(item.range_latex) + '</div>',
      );
      continue;
    }

    // ``math: false`` means "this is a message key, translate it".
    // ``math: true`` means "typeset the LaTeX exactly as sent".
    if (!item.math) {
      out.push(`<div class="line">${escapeHtml(message(item.text))}</div>`);
      continue;
    }

    try {
      const markup = window.MathLive.convertLatexToMarkup(item.latex, { displayMode: false });
      out.push(`<div class="line">${markup}</div>`);
    } catch {
      out.push(`<div class="line">${escapeHtml(item.text)}</div>`);
    }
  }
  return out.join('');
}

/* ============================================================ TABS */

function switchTab(name) {
  $$('.tab').forEach((t) => t.setAttribute('aria-selected', String(t.dataset.tab === name)));
  $$('.view').forEach((v) => v.classList.toggle('active', v.id === `view-${name}`));

  if (name === 'settings') loadSettings();
  if (name === 'analysis') {
    requestAnimationFrame(() => {
      renderCanvas();
      drawGraph();
    });
  }
  if (name === 'ai') {
    const input = $('#ai-input');
    if (input) input.focus();
  }
  if (name === 'calc') {
    const el = $('#lcd-input');
    if (el && el.focus) el.focus();
  }
  if (name === 'matrix') {
    // The field is empty and ready: put the caret there so a keystroke goes
    // into the expression instead of nowhere.
    const el = $('#mx-input');
    if (el && el.focus) requestAnimationFrame(() => el.focus());
  }
}


/* ============================================================ ONBOARDING */

const EM_DASH = '\u2014';

const ONB_STATE_KEYS = { detecting: 'onb.detecting', done: 'onb.done', failed: 'onb.failed' };

function tf(key, vars) {
  return t(key).replace(/\{(\w+)\}/g, (_, name) => vars[name] ?? '');
}

function reasonText(reason) {
  if (!reason || typeof reason !== 'object') return '';
  if (reason.code === 'vram') return tf('hw.reason_vram', reason);
  if (reason.code === 'ram') return tf('hw.reason_ram', reason);
  if (reason.code === 'low') return tf('hw.reason_low', reason);
  return '';
}

function setOnbState(state) {
  const el = $('#onb-state');
  const key = ONB_STATE_KEYS[state];
  el.dataset.state = state;
  el.dataset.i18n = key;
  el.textContent = t(key);
}

async function checkFirstRun() {
  try {
    const settings = await py('settings_get');
    if (settings.onboarding_done) return;

    const overlay = $('#onboarding');
    overlay.hidden = false;
    setOnbState('detecting');

    // If hardware probing stalls, the user must still be able to leave.
    setTimeout(() => {
      if (!overlay.hidden && $('#onb-spec').dataset.loaded !== '1') {
        setOnbState('failed');
        $('#onb-spec').textContent = t('onb.failed_hint');
        $('#onb-accept').textContent = t('onb.skip');
      }
    }, 6000);

    const hw = await py('hardware', false);
    if (!hw.ok) {
      setOnbState('failed');
      $('#onb-spec').textContent = t('onb.failed_hint');
      $('#onb-accept').textContent = t('onb.skip');
      $('#onb-accept').onclick = async () => {
        await py('settings_set', { onboarding_done: true });
        overlay.hidden = true;
      };
      return;
    }

    const model = hw.model || hw.recommended;
    const meta = CATALOG.find((m) => m.tag === model);
    $('#onb-spec').dataset.loaded = '1';
    setOnbState('done');
    const rows = [
      [t('hw.cpu'), hw.hardware?.cpu || '\u2014'],
      [t('hw.ram'), `${hw.hardware?.ram_gb ?? '?'} ${t('hw.gb')}`],
    ];
    if (hw.hardware?.vram_gb) rows.push([t('hw.vram'), `${hw.hardware.vram_gb} ${t('hw.gb')}`]);
    rows.push([t('hw.recommend'), model + (meta ? ` (${meta.size_gb} ${t('hw.gb')})` : '')]);
    $('#onb-spec').innerHTML =
      rows.map(([key, value]) =>
        `<div class="onb-row"><span class="onb-key">${escapeHtml(key)}</span>` +
        `<span class="onb-val">${escapeHtml(value)}</span></div>`).join('') +
      (reasonText(hw.reason) ? `<p class="onb-reason">${escapeHtml(reasonText(hw.reason))}</p>` : '');

    $('#onb-accept').onclick = async () => {
      overlay.hidden = true;
      switchTab('settings');
      showSetupBusy(true);
      await startSetup('setup_all', [model]);
      await py('settings_set', { onboarding_done: true, model });
    };
  } catch {
    /* Onboarding should not мешать запуску */
  }
}

/**
 * Remove a downloaded model.
 *
 * Deletes from the INSTALLED list: the catalogue on the left may name a model
 * that was never downloaded, and asking Ollama to delete that returns an error
 * about a missing manifest.
 *
 * If the deleted model was the active one, the backend switches to whatever
 * remains, so the assistant does not end up pointing at nothing.
 */
async function deleteSelectedModel() {
  const select = $('#set-model-installed');
  const model = select ? select.value : '';
  const status = $('#setup-status');

  if (!model) {
    // Exactly one installed model and nothing selected: treat it as selected.
    // Only a genuinely empty list is "no models installed".
    const available = select ? Array.from(select.options).filter((o) => o.value) : [];
    if (available.length === 1) {
      if (select) select.value = available[0].value;
      return deleteSelectedModel();
    }
    if (status) status.textContent = available.length ? t('settings.pick_model') : t('settings.no_models');
    return;
  }

  // Models are gigabytes; re-downloading is slow enough to warrant a question
  const question = t('settings.delete_confirm').replace('{0}', model);
  if (!window.confirm(question)) return;

  if (status) status.textContent = '\u2026';
  showSetupBusy(true);
  try {
    const res = await py('ollama_delete', model);
    if (!res.ok) {
      showSetupBusy(false);
      if (status) status.textContent = `${t('common.error')}: ${message(res.error)}`;
      return;
    }
    // The job answers on 'onDeleteDone': deleting a multi-gigabyte model takes
    // seconds, and a synchronous call would freeze the busy state on screen.
    state.deletingModel = model;
  } catch (err) {
    showSetupBusy(false);
    if (status) status.textContent = `${t('common.error')}: ${err.message}`;
  }
}

/** Completion of the model deletion, including the active-model fallback. */
async function onDeleteFinished(d) {
  const status = $('#setup-status');
  showSetupBusy(false);
  const model = state.deletingModel || '';
  state.deletingModel = '';

  if (!d.ok) {
    if (status) status.textContent = `${t('common.error')}: ${message(d.error || d.text || '')}`;
    return;
  }

  let note = `${t('settings.deleted')}: ${model}`;
  if (d.fallback_model) {
    note += ` \u00b7 ${t('settings.fallback')} ${d.fallback_model}`;
    state.model = d.fallback_model;
    renderModelChip(d.fallback_model);
  }
  if (status) status.textContent = note;
  await loadOllamaStatus();
}

/* ============================================================ EVENT BINDING */

function bindEvents() {
  /* Калькулятор */
  buildKeyboard('#keys', '#lcd-input');

  // Capture phase: MathLive would otherwise insert a line break on Enter first.
  // Enter and Ctrl+Enter both evaluate here; Shift+Enter is left alone.
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter' || e.shiftKey) return;
    if (document.activeElement?.id !== 'lcd-input') return;
    e.preventDefault();
    e.stopImmediatePropagation();
    evaluateCalculator();
  }, true);

  $$('.tab').forEach((tab) => {
    tab.addEventListener('click', () => switchTab(tab.dataset.tab));
  });

  /* DEG / RAD */
  $$('[data-unit]').forEach((btn) => {
    btn.addEventListener('click', () => {
      state.unit = btn.dataset.unit;
      $$('[data-unit]').forEach((b) =>
        b.setAttribute('aria-pressed', String(b === btn)));
      const label = $('#lcd-unit');
      if (label) label.textContent = state.unit.toUpperCase();
      saveUserState();
    });
  });

  /* Ctrl+Enter — evaluate in active field */
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      const active = document.activeElement;
      if (active && active.id === 'ai-input') sendAiMessage();
      else if ($('#view-analysis').classList.contains('active')) runAnalysis();
      else if ($('#view-calculus').classList.contains('active')) runCalculus('limit');
      else if ($('#view-equations').classList.contains('active')) solveEquations();
    }
  });

  /* Клавиатуры во вкладках: раскрываются по кнопке, пишут в активное поле */
  const kbMap = [
    ['#btn-kb-cx', '#kb-cx', '#cx-fn'],
    ['#btn-kb-an', '#kb-an', '#fn-list .fn-row.is-active math-field'],
    ['#btn-kb-eq', '#kb-eq', null],   // для уравнений — в последнее поле
  ];

  for (const [btnSel, hostSel, fieldSel] of kbMap) {
    const btn = $(btnSel);
    const host = $(hostSel);
    if (!btn || !host) continue;

    // Строим клавиатуру сразу, но скрытую: раскрытие мгновенное
    const target = fieldSel
      || `#eq-rows .eq-row:last-child math-field`;
    buildKeyboard(hostSel, target);

    btn.addEventListener('click', () => {
      const willShow = host.hidden;
      host.hidden = !willShow;
      btn.setAttribute('aria-pressed', String(willShow));
      if (willShow) {
        // Перестраиваем на актуальное поле: строки уравнений могли добавиться
        const actual = fieldSel || '#eq-rows .eq-row:last-child math-field';
        buildKeyboard(hostSel, actual);
        focusField(actual);
      }
    });
  }

  /* Пределы */
  $$('[data-cx]').forEach((btn) => {
    btn.addEventListener('click', () => runCalculus(btn.dataset.cx, btn.dataset.dir || 'both'));
  });

  /* Анализ */
  on('#btn-analyze', 'click', runAnalysis);
  on('#btn-add-fn', 'click', addFunction);
  on('#btn-open-exports', 'click', async () => {
    const res = await py('open_exports_dir');
    $('#export-status').textContent = res.ok ? res.path : `${t('common.error')}: ${res.error}`;
  });
  on('#btn-fs-pdf', 'click', exportGraphPdf);
  on('#btn-graph-fullscreen', 'click', openFullscreenGraph);
  on('#btn-clear-analysis', 'click', () => {
    renderFnList([''], 0);
    showResult('#analysis-out', '');
    state.series = [];
    renderCanvas();
  });

  /* Матрицы */
  $$('[data-mrow]').forEach((btn) =>
    btn.addEventListener('click', () => resizeMatrix('a', btn.dataset.mrow === '+' ? 1 : -1, 0)));
  $$('[data-mcol]').forEach((btn) =>
    btn.addEventListener('click', () => resizeMatrix('a', 0, btn.dataset.mcol === '+' ? 1 : -1)));
  $$('[data-mfill]').forEach((btn) =>
    btn.addEventListener('click', () => fillMatrix('a', btn.dataset.mfill)));

  /* Theme */
  $$('[data-theme-choice]').forEach((btn) => {
    btn.addEventListener('click', () => chooseTheme(btn.dataset.themeChoice));
  });

  /* Steps and export */
  const stepsBtn = $('#btn-steps');
  if (stepsBtn) stepsBtn.addEventListener('click', showSteps);
  const pdfBtn = $('#btn-export-pdf');
  if (pdfBtn) pdfBtn.addEventListener('click', () => exportSolution('pdf'));
  const texBtn = $('#btn-export-tex');
  if (texBtn) texBtn.addEventListener('click', () => exportSolution('latex'));

  buildKeyboard('#mx-keys', '#mx-input');

  // Ctrl+Enter evaluates from anywhere in the matrix tab
  on('#mx-input', 'keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      evaluateMatrixExpression();
    }
  });

  on('#mx-prev', 'click', () => carouselStep(-1));
  on('#mx-next', 'click', () => carouselStep(1));
  on('#mx-save', 'click', saveCurrentMatrix);
  on('#mx-delete', 'click', deleteCurrentMatrix);

  /* Equations: auto-detect system by line count */
  on('#btn-eq-add', 'click', () => addEquationsRow());
  on('#btn-eq-solve', 'click', () => solveEquations());
  on('#btn-eq-clear', 'click', () => {
    const host = $('#eq-rows');
    host.innerHTML = '';
    addEquationsRow();
    showResult('#eq-out', '');
  });

  /* ИИ */
  if (!chats.items.length) openConversation();
  on('#btn-send', 'click', sendAiMessage);
  on('#ai-input', 'keydown', (e) => {
    // Enter sends, Shift+Enter inserts a line break: the behaviour every chat
    // box has, and the one the hint at the bottom of the window promises.
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendAiMessage();
    }
  });
  on('#btn-stop', 'click', () => py('ai_stop'));
  on('#btn-newdialog', 'click', () => openConversation());

  on('#btn-photo', 'click', async () => {
    try {
      const res = await py('pick_image');
      if (res.ok && res.path) {
        await prepareImage(`file:///${res.path.replace(/\\/g, '/')}`,
                           res.path.split(/[\\/]/).pop());
      }
    } catch (err) {
      $('#ai-status').textContent = err.message;
    }
  });
  on('#btn-unattach', 'click', clearAttachment);

  /* Ctrl+V — фото из буфера */
  document.addEventListener('paste', async (e) => {
    if (!$('#view-ai').classList.contains('active')) return;
    const items = e.clipboardData?.items;
    if (!items) return;

    for (const item of items) {
      if (item.type.startsWith('image/')) {
        const file = item.getAsFile();
        const reader = new FileReader();
        reader.onload = (ev) => prepareImage(ev.target.result, file.name || 'clipboard');
        reader.readAsDataURL(file);
        e.preventDefault();
        return;
      }
    }
  });

  /* Настройки */
  on('#set-temp', 'input', (e) => {
    $('#temp-val').textContent = Number(e.target.value).toFixed(2);
  });
  on('#set-temp', 'change', (e) => {
    py('settings_set', { temperature: Number(e.target.value) });
  });

  on('#set-model-installed', 'change', async (e) => {
    state.model = e.target.value;
    await py('settings_set', { model: e.target.value });
    renderModelChip(e.target.value);
  });

  on('#btn-hw-rescan', 'click', async () => {
    await guarded('#hw-out', async () => {
      $('#hw-out').textContent = '…';
      setHwState('detecting');
      const res = await py('hardware', true);
      if (!res.ok) {
        setHwState('failed');
        return showError('#hw-out', message(res.error));
      }
      renderHardware(res.hardware ? { ...res.hardware, model: res.model } : res);
    });
  });

  on('#btn-setup-all', 'click', () => startSetup('setup_all', [$('#set-model').value]));
  on('#btn-setup-cancel', 'click', () => py('ollama_cancel'));
  on('#onb-cancel', 'click', () => py('ollama_cancel'));
  on('#btn-install-ollama', 'click', () => startSetup('ollama_install'));
  on('#btn-start-ollama', 'click', () => startSetup('ollama_start'));
  on('#btn-pull-model', 'click', () => startSetup('ollama_pull', [$('#set-model').value]));
  on('#btn-delete-model', 'click', deleteSelectedModel);

  on('#btn-open-models', 'click', async () => {
    try {
      const res = await py('open_models_dir');
      if (res.ok) $('#data-path').textContent = res.path;
      else $('#data-path').textContent = message(res.error);
    } catch (err) {
      $('#data-path').textContent = err.message;
    }
  });

  on('#btn-open-data', 'click', async () => {
    try {
      const res = await py('open_data_dir');
      if (res.ok) $('#data-path').textContent = res.path;
    } catch (err) {
      $('#data-path').textContent = err.message;
    }
  });

  /* Onboarding must never trap the user: Escape, backdrop click and the
     explicit button all dismiss it, and the choice is remembered. */
  const closeOnboarding = () => {
    const overlay = $('#onboarding');
    if (overlay && !overlay.hidden) {
      overlay.hidden = true;
      py('settings_set', { onboarding_done: true }).catch(() => {});
    }
  };

  on('#onb-later', 'click', closeOnboarding);

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeOnboarding();
  });

  on('#onboarding', 'mousedown', (e) => {
    if (e.target === $('#onboarding')) closeOnboarding();
  });
}

/** Pixels of a canvas as base64 RGB, the form the engine packs into a PDF image. */
function canvasRgbBase64(canvas) {
  const ctx = canvas.getContext('2d');
  const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
  const rgb = new Uint8Array((data.length / 4) * 3);
  for (let i = 0, j = 0; i < data.length; i += 4, j += 3) {
    rgb[j] = data[i];
    rgb[j + 1] = data[i + 1];
    rgb[j + 2] = data[i + 2];
  }
  let binary = '';
  const chunk = 0x8000;
  for (let k = 0; k < rgb.length; k += chunk) {
    binary += String.fromCharCode.apply(null, rgb.subarray(k, k + chunk));
  }
  return btoa(binary);
}

async function exportGraphPdf() {
  const canvas = $('#graph-canvas-fs');
  const status = $('#graph-fs-status');
  if (!canvas || !canvas.width || !status) return;
  status.textContent = '\u2026';
  const payload = {
    width: canvas.width,
    height: canvas.height,
    rgb: canvasRgbBase64(canvas),
    title: activeFunctions().map((fn) => `y = ${fn.expr}`).join(', '),
    language: I18n.get(),
  };
  const res = await py('export_graph_pdf', payload, 'graph');
  if (!res.ok) status.textContent = `${t('common.error')}: ${message(res.error)}`;
  else status.textContent = `${t('export.saved')}: ${res.path}`;
}

/** Show the cancel button while an Ollama download or install runs. */
function showSetupBusy(busy) {
  for (const id of ['#btn-setup-cancel', '#onb-cancel']) {
    const el = $(id);
    if (el) el.hidden = !busy;
  }
  // Every download and install in Settings is covered by the one cancel button
  for (const id of ['#btn-setup-all', '#btn-install-ollama', '#btn-start-ollama', '#btn-pull-model', '#btn-delete-model']) {
    const el = $(id);
    if (el) el.disabled = busy;
  }
}

async function startSetup(method, args = []) {
  const line = '#setup-status';
  // Every install and download goes through here, so the Cancel button and the
  // disabled action buttons are set in one place. Before this only the
  // "Скачать всё" handler turned them on, and every other download ran with no
  // way to stop it.
  showSetupBusy(true);
  try {
    if (method === 'setup_all' || method === 'ollama_pull') {
      if (!args[0]) {
        throw new Error(t('err.no_model'));
      }
      $('#setup-progress').firstElementChild.style.width = '0%';
    }
    $(line).textContent = '…';
    const res = await py(method, ...args);
    if (res && res.ok === false) {
      showSetupBusy(false);
      $(line).textContent = res.error || t('common.error');
    }
  } catch (err) {
    $(line).textContent = err.message;
  }
}

/* ============================================================ INITIALIZATION */

async function init() {
  // 0) Keypad and event wiring first: they depend only on the DOM.
  //    A failure anywhere else must not leave the interface inert.
  try {
    buildKeyboard('#keys', '#lcd-input');
  } catch (err) {
    console.error('keypad failed', err);
  }

  try {
    bindEvents();
  } catch (err) {
    console.error('event binding failed', err);
    setStatus(String(err && err.message ? err.message : err), 'err', true);
  }

  // 1) Language before any text is shown
  try {
    I18n.set(I18n.detect(null));
    I18n.apply();
  } catch (err) {
    console.error('i18n failed', err);
  }

  // 2) Matrix grids and the first equation row
  try {
    makeMatrixStore(matrixA, 3, 3, '');
    fillMatrix('a', 'example');
    renderMatrixGrid('a');
    addEquationsRow('x^2-5q+6=0'.replace('q', 'x'));
  } catch (err) {
    console.error('matrix init failed', err);
  }

  // 3) Chat greeting
  try {
  } catch (err) {
    console.error('chat init failed', err);
  }

  // 4) Engine: the page is served over loopback HTTP, so readiness is a fetch
  connectEvents();
  setStatus('common.loading', 'busy');

  const bootStarted = Date.now();
  const poll = setInterval(async () => {
    try {
      const r = await py('ready');
      if (r && r.error) {
        clearInterval(poll);
        setStatus(r.error, 'err', true);
        return;
      }
      if (r && r.warm) {
        clearInterval(poll);
        state.warm = true;
        await loadSettings();
        await refreshCarousel();
        await checkFirstRun();
        setStatus('common.ready', 'ok');
      }
    } catch (err) {
      const seconds = Math.round((Date.now() - bootStarted) / 1000);
      setStatus(`${t('common.loading')} ${seconds}s`, 'busy');
    }
  }, 300);

  const lcd = $('#lcd-input');
  if (lcd && lcd.focus) lcd.focus();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}