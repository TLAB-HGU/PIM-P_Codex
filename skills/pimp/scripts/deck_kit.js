/**
 * deck_kit.js — 논문 리뷰 세미나용 슬라이드 아키타입 라이브러리 (pptxgenjs)
 *
 * 사용법:
 *   const kit = require('/path/to/deck_kit.js')({ theme: 'teal', short: 'TSMixer' });
 *   kit.titleSlide({...}); kit.tldrSlide({...}); ...
 *   await kit.save('/home/claude/review/deck.pptx');
 *
 * 캔버스: LAYOUT_WIDE (13.333" x 7.5"). 모든 함수는 notes(발표자 노트)를 받는다.
 * pptxgenjs 함정 준수: '#' 없는 6자리 hex, 옵션 객체 공유 금지, isTextBox:true, margin:0.
 */
const fs = require('fs');
const pptxgen = require('pptxgenjs');

const THEMES = {
  // dark: 표지·간지·결론 배경 / primary: 강조 도형·표 헤더 / accent: 포인트 컬러(소량)
  teal:     { dark: '0B3B3C', primary: '0F6466', accent: 'E8A33D', surface: 'EEF5F4', highlight: 'FCF1DE' },
  graphite: { dark: '1F2328', primary: '3A4750', accent: 'E07A2E', surface: 'F3F4F6', highlight: 'FDEBDD' },
  plum:     { dark: '2B1B34', primary: '5B3A6E', accent: 'E4572E', surface: 'F5F1F7', highlight: 'FCE6DF' },
  forest:   { dark: '1C3326', primary: '2C5F2D', accent: 'D9A13B', surface: 'F0F5EE', highlight: 'FAF0D9' },
  navy:     { dark: '111D35', primary: '24467F', accent: 'F25C54', surface: 'EEF2F8', highlight: 'FDE4E2' },
  crimson:  { dark: '2A1215', primary: '8C1C2B', accent: '2F6F8F', surface: 'F7F0F0', highlight: 'E3EFF5' },
};
const BASE = {
  ink: '1F2933',       // 본문 텍스트
  muted: '6B7280',     // 캡션·보조
  border: 'D9DEE3',
  white: 'FFFFFF',
  onDark: 'FFFFFF',
  onDarkMuted: 'B8C2CC',
};

const W = 13.333, H = 7.5, MX = 0.6;
const CONTENT_TOP = 1.85, CONTENT_BOTTOM = 6.75;

function pngSize(file) {
  const b = fs.readFileSync(file);
  if (b.toString('ascii', 1, 4) === 'PNG') return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
  // JPEG: SOF 마커 탐색
  let i = 2;
  while (i < b.length) {
    if (b[i] !== 0xff) { i++; continue; }
    const m = b[i + 1];
    if (m >= 0xc0 && m <= 0xcf && ![0xc4, 0xc8, 0xcc].includes(m)) return { h: b.readUInt16BE(i + 5), w: b.readUInt16BE(i + 7) };
    i += 2 + b.readUInt16BE(i + 2);
  }
  throw new Error('Unsupported image: ' + file);
}

/** box 안에 비율 유지로 맞춘 좌표 (align: 'center' | 'left' | 'top') */
function fit(file, box, align = 'center') {
  const s = pngSize(file);
  const r = Math.min(box.w / s.w, box.h / s.h);
  const w = s.w * r, h = s.h * r;
  let x = box.x + (box.w - w) / 2, y = box.y + (box.h - h) / 2;
  if (align === 'left') x = box.x;
  if (align === 'top') y = box.y;
  return { x, y, w, h };
}

module.exports = function createKit(opts = {}) {
  const T = Object.assign({}, BASE, THEMES[opts.theme || 'teal'] || THEMES.teal, opts.colors || {});
  // 밝은 accent(노랑 계열)는 흰 배경 글자색으로 대비가 약하므로 강조 글자색은 primary로
  const lum = (hex) => { const n = parseInt(hex, 16); return (0.299 * (n >> 16) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255)) / 255; };
  T.bestText = lum(T.accent) > 0.6 ? T.primary : T.accent;
  const FONT_HEAD = opts.fontHead || 'Malgun Gothic';
  const FONT_BODY = opts.fontBody || 'Malgun Gothic';
  const SHORT = opts.short || '';           // 푸터에 들어갈 논문 약칭
  const pres = new pptxgen();
  pres.layout = 'LAYOUT_WIDE';
  pres.title = opts.title || 'Paper Review';
  let pageNo = 0;

  // ---------- primitives ----------
  const text = (slide, value, o) => slide.addText(value, Object.assign({
    isTextBox: true, fontFace: FONT_BODY, color: T.ink, fontSize: 15, margin: 0, valign: 'top',
  }, o));

  const card = (slide, x, y, w, h, fill = T.surface, line = null) => slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h, rectRadius: 0.08, fill: { color: fill }, line: line ? { color: line, width: 1 } : { type: 'none' },
  });

  const badge = (slide, x, y, label, fill = T.primary, size = 0.42, fontSize = 13) => {
    slide.addShape(pres.shapes.OVAL, { x, y, w: size, h: size, fill: { color: fill }, line: { type: 'none' } });
    text(slide, String(label), { x, y, w: size, h: size, align: 'center', valign: 'middle', bold: true, color: T.white, fontSize, fontFace: FONT_HEAD });
  };

  const chip = (slide, x, y, label, fill = T.primary, color = T.white, w = null) => {
    const cw = w || Math.max(1.0, 0.16 * label.length + 0.4);
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: cw, h: 0.34, rectRadius: 0.17, fill: { color: fill }, line: { type: 'none' } });
    text(slide, label, { x, y, w: cw, h: 0.34, align: 'center', valign: 'middle', bold: true, color, fontSize: 11, fontFace: FONT_HEAD });
    return cw;
  };

  const notes = (slide, n) => { if (n) slide.addNotes(n); };

  /** 일반 본문 슬라이드 뼈대: eyebrow + 액션 타이틀 + 푸터 */
  function contentSlide({ eyebrow, title }) {
    const s = pres.addSlide();
    pageNo += 1;
    s.background = { color: T.white };
    if (eyebrow) text(s, eyebrow.toUpperCase(), { x: MX, y: 0.42, w: W - 2 * MX, h: 0.3, fontSize: 11, bold: true, color: T.primary, charSpacing: 2, fontFace: FONT_HEAD });
    text(s, title, { x: MX, y: 0.72, w: W - 2 * MX, h: 0.95, fontSize: 26, bold: true, color: T.ink, fontFace: FONT_HEAD, valign: 'middle', fit: 'shrink' });
    text(s, SHORT, { x: MX, y: 7.02, w: 6, h: 0.28, fontSize: 10, color: T.muted });
    text(s, String(pageNo), { x: W - MX - 1, y: 7.02, w: 1, h: 0.28, fontSize: 10, color: T.muted, align: 'right' });
    return s;
  }

  function darkSlide() {
    const s = pres.addSlide();
    pageNo += 1;
    s.background = { color: T.dark };
    return s;
  }

  /** bullet 목록 → pptxgenjs text runs. items: string | {text, sub:[...]} */
  function bulletRuns(items, fontSize = 15, color = T.ink) {
    const runs = [];
    items.forEach((it, i) => {
      const main = typeof it === 'string' ? it : it.text;
      const subs = typeof it === 'string' ? [] : (it.sub || []);  // 주의: String.prototype.sub가 존재함
      const last = i === items.length - 1 && !subs.length;
      runs.push({ text: main, options: { bullet: { indent: 16 }, fontSize, color, paraSpaceAfter: 6, breakLine: !last } });
      subs.forEach((sub, j) => {
        const lastSub = i === items.length - 1 && j === subs.length - 1;
        runs.push({ text: sub, options: { bullet: { indent: 16 }, indentLevel: 1, fontSize: fontSize - 2, color: T.muted, paraSpaceAfter: 4, breakLine: !lastSub } });
      });
    });
    return runs;
  }

  // ---------- archetypes ----------

  /** 표지. title(원제), subtitle(한국어 의역/한 줄 소개), authors, venue, presenter, date */
  function titleSlide({ title, subtitle, authors, venue, presenter, date, label = 'PAPER REVIEW SEMINAR', notes: n }) {
    const s = pres.addSlide();
    s.background = { color: T.dark };
    // 모티프: 우측 동심원 (장식, 텍스트와 겹치지 않는 영역)
    [3.6, 2.6, 1.6].forEach((d, i) => s.addShape(pres.shapes.OVAL, {
      x: W - 1.2 - d / 2 - 0.6, y: 1.2 + (3.6 - d) / 2, w: d, h: d,
      fill: { color: i === 2 ? T.accent : T.primary, transparency: i === 2 ? 0 : 55 + i * 10 }, line: { type: 'none' },
    }));
    chip(s, MX, 1.0, label, T.accent, T.dark);
    text(s, title, { x: MX, y: 1.6, w: 8.6, h: 2.3, fontSize: 32, bold: true, color: T.onDark, fontFace: FONT_HEAD, valign: 'bottom', fit: 'shrink' });
    if (subtitle) text(s, subtitle, { x: MX, y: 4.05, w: 8.6, h: 0.8, fontSize: 17, color: T.onDarkMuted });
    const meta = [authors, venue].filter(Boolean).join('   |   ');
    if (meta) text(s, meta, { x: MX, y: 5.2, w: 11.5, h: 0.4, fontSize: 13, color: T.onDarkMuted });
    const who = [presenter, date].filter(Boolean).join('   ·   ');
    if (who) text(s, who, { x: MX, y: 6.4, w: 11.5, h: 0.4, fontSize: 14, bold: true, color: T.onDark });
    notes(s, n);
    return s;
  }

  /** 목차. items: string[]; current: 0-based 강조 인덱스(선택) */
  function agendaSlide({ title = '목차', items, current = -1, notes: n }) {
    const s = contentSlide({ eyebrow: 'Outline', title });
    const twoCol = items.length > 5;
    const perCol = twoCol ? Math.ceil(items.length / 2) : items.length;
    const colW = twoCol ? 5.7 : 11.5;
    const rowH = Math.min(0.85, (CONTENT_BOTTOM - CONTENT_TOP) / perCol);
    items.forEach((it, i) => {
      const col = twoCol && i >= perCol ? 1 : 0;
      const row = col ? i - perCol : i;
      const x = MX + col * (colW + 0.5), y = CONTENT_TOP + 0.1 + row * rowH;
      const active = current < 0 || i === current;
      badge(s, x, y + (rowH - 0.5) / 2, String(i + 1).padStart(2, '0'), active ? T.primary : T.border, 0.5, 13);
      text(s, it, { x: x + 0.7, y, w: colW - 0.8, h: rowH, valign: 'middle', fontSize: 18, bold: i === current, color: active ? T.ink : T.muted });
    });
    notes(s, n);
    return s;
  }

  /** 간지. num: '02' 등, title, subtitle */
  function sectionSlide({ num, title, subtitle, notes: n }) {
    const s = darkSlide();
    if (num !== undefined) text(s, String(num).padStart(2, '0'), { x: MX + 0.2, y: 2.0, w: 3, h: 1.3, fontSize: 64, bold: true, color: T.accent, fontFace: FONT_HEAD });
    text(s, title, { x: MX + 0.2, y: 3.35, w: 11, h: 1.0, fontSize: 36, bold: true, color: T.onDark, fontFace: FONT_HEAD, valign: 'middle' });
    if (subtitle) text(s, subtitle, { x: MX + 0.2, y: 4.4, w: 10, h: 0.8, fontSize: 17, color: T.onDarkMuted });
    notes(s, n);
    return s;
  }

  /** TL;DR 3칸. oneLiner(선택), problem, idea, result */
  function tldrSlide({ title = '한 장 요약', oneLiner, problem, idea, result, notes: n }) {
    const s = contentSlide({ eyebrow: 'TL;DR', title });
    let top = CONTENT_TOP;
    if (oneLiner) {
      text(s, oneLiner, { x: MX, y: top, w: W - 2 * MX, h: 0.8, fontSize: 18, italic: true, color: T.primary, valign: 'middle' });
      top += 1.0;
    }
    const cols = [['PROBLEM', problem, T.muted], ['KEY IDEA', idea, T.primary], ['RESULT', result, T.accent]];
    const gap = 0.35, cw = (W - 2 * MX - 2 * gap) / 3, ch = CONTENT_BOTTOM - top;
    cols.forEach(([lab, body, c], i) => {
      const x = MX + i * (cw + gap);
      card(s, x, top, cw, ch, i === 1 ? T.surface : 'F7F8F9');
      chip(s, x + 0.3, top + 0.3, lab, c, T.white);
      text(s, body, { x: x + 0.3, y: top + 0.95, w: cw - 0.6, h: ch - 1.25, fontSize: 18, lineSpacingMultiple: 1.25, fit: 'shrink' });
    });
    notes(s, n);
    return s;
  }

  /**
   * 번호형 요점 슬라이드. points: [{head, body}] (2–5개)
   * image(선택): 오른쪽에 그림, caption
   */
  function pointsSlide({ eyebrow, title, points, image, caption, numbered = true, notes: n }) {
    const s = contentSlide({ eyebrow, title });
    const textW = image ? 5.9 : W - 2 * MX;
    const rowH = (CONTENT_BOTTOM - CONTENT_TOP) / Math.max(points.length, 3);
    points.forEach((p, i) => {
      const y = CONTENT_TOP + i * rowH;
      const bx = MX;
      if (numbered) badge(s, bx, y + 0.05, i + 1);
      const tx = numbered ? bx + 0.65 : bx;
      text(s, p.head, { x: tx, y, w: textW - (tx - MX), h: 0.5, fontSize: 18, bold: true, fontFace: FONT_HEAD, valign: 'middle' });
      if (p.body) text(s, p.body, { x: tx, y: y + 0.52, w: textW - (tx - MX), h: rowH - 0.6, fontSize: 14, color: T.muted, lineSpacingMultiple: 1.15, fit: 'shrink' });
    });
    if (image) {
      const box = { x: MX + textW + 0.4, y: CONTENT_TOP, w: W - MX - (MX + textW + 0.4), h: CONTENT_BOTTOM - CONTENT_TOP - (caption ? 0.45 : 0) };
      card(s, box.x, box.y, box.w, box.h, 'FFFFFF', T.border);
      const f = fit(image, { x: box.x + 0.15, y: box.y + 0.15, w: box.w - 0.3, h: box.h - 0.3 });
      s.addImage(Object.assign({ path: image }, f));
      if (caption) text(s, caption, { x: box.x, y: box.y + box.h + 0.08, w: box.w, h: 0.35, fontSize: 10, color: T.muted });
    }
    notes(s, n);
    return s;
  }

  /**
   * 논문 Figure 슬라이드.
   * layout 'side'(기본): 그림 왼쪽 ~62%, 요점 오른쪽 / 'full': 그림 크게 + 하단 takeaway
   */
  function figureSlide({ eyebrow, title, image, caption, points = [], takeaway, layout = 'side', notes: n }) {
    const s = contentSlide({ eyebrow, title });
    if (layout === 'full') {
      const bottomReserve = (takeaway ? 0.75 : 0) + (caption ? 0.4 : 0);
      const box = { x: MX, y: CONTENT_TOP, w: W - 2 * MX, h: CONTENT_BOTTOM - CONTENT_TOP - bottomReserve };
      const f = fit(image, box);
      s.addImage(Object.assign({ path: image }, f));
      let y = f.y + f.h + 0.08;
      if (caption) { text(s, caption, { x: MX, y, w: W - 2 * MX, h: 0.32, fontSize: 10, color: T.muted, align: 'center' }); y += 0.4; }
      if (takeaway) {
        card(s, MX, y, W - 2 * MX, 0.6, T.highlight);
        text(s, takeaway, { x: MX + 0.3, y, w: W - 2 * MX - 0.6, h: 0.6, fontSize: 15, bold: true, valign: 'middle' });
      }
    } else {
      const imgW = 7.6;
      const box = { x: MX, y: CONTENT_TOP, w: imgW, h: CONTENT_BOTTOM - CONTENT_TOP - (caption ? 0.45 : 0) };
      card(s, box.x, box.y, box.w, box.h, 'FFFFFF', T.border);
      const f = fit(image, { x: box.x + 0.15, y: box.y + 0.15, w: box.w - 0.3, h: box.h - 0.3 });
      s.addImage(Object.assign({ path: image }, f));
      if (caption) text(s, caption, { x: box.x, y: box.y + box.h + 0.08, w: box.w, h: 0.35, fontSize: 10, color: T.muted });
      const rx = MX + imgW + 0.45, rw = W - MX - rx;
      const tkH = takeaway ? 1.3 : 0;
      if (points.length) s.addText(bulletRuns(points, 15), { x: rx, y: CONTENT_TOP, w: rw, h: CONTENT_BOTTOM - CONTENT_TOP - tkH - 0.2, isTextBox: true, fontFace: FONT_BODY, color: T.ink, margin: 0, valign: 'top', fit: 'shrink' });
      if (takeaway) {
        card(s, rx, CONTENT_BOTTOM - tkH, rw, tkH, T.highlight);
        text(s, takeaway, { x: rx + 0.25, y: CONTENT_BOTTOM - tkH + 0.15, w: rw - 0.5, h: tkH - 0.3, fontSize: 14, bold: true, valign: 'middle', fit: 'shrink' });
      }
    }
    notes(s, n);
    return s;
  }

  /**
   * 수식 슬라이드. eqImages: PNG 경로 배열(1–2개, render_equation.py 출력)
   * symbols: [{sym, desc}] — sym은 유니코드 텍스트(예: 'Q, K, V'), intuition: 직관적 해석
   */
  function equationSlide({ eyebrow, title, eqImages, eqLabels = [], symbols = [], intuition, notes: n }) {
    const s = contentSlide({ eyebrow, title });
    const eqH = eqImages.length > 1 ? 2.1 : 1.6;
    card(s, MX, CONTENT_TOP, W - 2 * MX, eqH, T.surface);
    const slotH = (eqH - 0.3) / eqImages.length;
    eqImages.forEach((img, i) => {
      const f = fit(img, { x: MX + 1.4, y: CONTENT_TOP + 0.15 + i * slotH, w: W - 2 * MX - 2.8, h: slotH - 0.1 });
      s.addImage(Object.assign({ path: img }, f));
      if (eqLabels[i]) text(s, eqLabels[i], { x: W - MX - 1.3, y: CONTENT_TOP + 0.15 + i * slotH, w: 1.1, h: slotH - 0.1, fontSize: 12, color: T.muted, align: 'right', valign: 'middle' });
    });
    const top = CONTENT_TOP + eqH + 0.35, h = CONTENT_BOTTOM - top;
    const leftW = intuition ? 6.2 : W - 2 * MX;
    if (symbols.length) {
      const rows = symbols.map((r) => [
        { text: r.sym, options: { bold: true, italic: true, color: T.primary, fontFace: 'Cambria' } },
        { text: r.desc, options: { color: T.ink } },
      ]);
      s.addTable(rows, { x: MX, y: top, w: leftW, colW: [1.5, leftW - 1.5], fontSize: 13, fontFace: FONT_BODY, border: { type: 'solid', color: T.border, pt: 0.75 }, valign: 'middle', rowH: Math.min(0.45, h / symbols.length), margin: 0.06 });
    }
    if (intuition) {
      const x = MX + leftW + 0.4, w = W - MX - x;
      card(s, x, top, w, h, T.highlight);
      chip(s, x + 0.3, top + 0.25, '직관적 해석', T.accent, T.white);
      text(s, intuition, { x: x + 0.3, y: top + 0.8, w: w - 0.6, h: h - 1.0, fontSize: 15, lineSpacingMultiple: 1.2, fit: 'shrink' });
    }
    notes(s, n);
    return s;
  }

  /** 좌우 비교. left/right: {label, points[]}, verdict(선택): 하단 결론 */
  function compareSlide({ eyebrow, title, left, right, verdict, notes: n }) {
    const s = contentSlide({ eyebrow, title });
    const gap = 0.5, cw = (W - 2 * MX - gap) / 2;
    const ch = CONTENT_BOTTOM - CONTENT_TOP - (verdict ? 0.95 : 0);
    [[left, 'F4F5F7', T.muted], [right, T.surface, T.primary]].forEach(([side, fill, c], i) => {
      const x = MX + i * (cw + gap);
      card(s, x, CONTENT_TOP, cw, ch, fill);
      chip(s, x + 0.35, CONTENT_TOP + 0.3, side.label, c, T.white);
      s.addText(bulletRuns(side.points, 15), { x: x + 0.35, y: CONTENT_TOP + 0.95, w: cw - 0.7, h: ch - 1.2, isTextBox: true, fontFace: FONT_BODY, color: T.ink, margin: 0, valign: 'top', fit: 'shrink' });
    });
    // 가운데 화살표 배지
    badge(s, W / 2 - 0.3, CONTENT_TOP + ch / 2 - 0.3, '→', T.accent, 0.6, 18);
    if (verdict) {
      card(s, MX, CONTENT_BOTTOM - 0.75, W - 2 * MX, 0.75, T.highlight);
      text(s, verdict, { x: MX + 0.3, y: CONTENT_BOTTOM - 0.75, w: W - 2 * MX - 0.6, h: 0.75, fontSize: 15, bold: true, valign: 'middle' });
    }
    notes(s, n);
    return s;
  }

  /**
   * 결과 표 (native). header: string[], rows: string[][]
   * highlightRows: [rowIdx] (제안 기법 행), bestCells: [[rowIdx, colIdx]] (굵게+accent)
   * takeaway(선택): 오른쪽 또는 하단 요약, note(선택): 표 아래 출처/지표 설명
   */
  function tableSlide({ eyebrow, title, header, rows, highlightRows = [], bestCells = [], colW, takeaway, note, fontSize, notes: n }) {
    const s = contentSlide({ eyebrow, title });
    const side = takeaway && header.length <= 5;
    const tw = side ? 8.3 : W - 2 * MX;
    const fs = fontSize || (rows.length > 10 ? 11 : 13);
    const best = new Set(bestCells.map(([r, c]) => `${r},${c}`));
    const data = [header.map((h) => ({ text: h, options: { bold: true, color: T.white, fill: { color: T.primary }, align: 'center' } }))];
    rows.forEach((r, ri) => {
      const hl = highlightRows.includes(ri);
      data.push(r.map((cell, ci) => ({
        text: String(cell),
        options: {
          fill: { color: hl ? T.highlight : (ri % 2 ? 'F8F9FA' : T.white) },
          bold: hl || best.has(`${ri},${ci}`),
          color: best.has(`${ri},${ci}`) ? T.bestText : T.ink,
          align: ci === 0 ? 'left' : 'center',
        },
      })));
    });
    const widths = colW || (() => { const first = Math.min(3.0, tw * 0.3); const rest = (tw - first) / (header.length - 1); return [first, ...Array(header.length - 1).fill(rest)]; })();
    const maxH = CONTENT_BOTTOM - CONTENT_TOP - (note ? 0.45 : 0) - (takeaway && !side ? 0.9 : 0);
    const rowH = Math.min(0.48, maxH / data.length);
    s.addTable(data, { x: MX, y: CONTENT_TOP, w: tw, colW: widths, rowH, fontSize: fs, fontFace: FONT_BODY, valign: 'middle', border: { type: 'solid', color: T.border, pt: 0.75 }, margin: 0.05 });
    const tableBottom = CONTENT_TOP + rowH * data.length;
    if (note) text(s, note, { x: MX, y: tableBottom + 0.1, w: tw, h: 0.35, fontSize: 10, color: T.muted });
    if (takeaway) {
      if (side) {
        const x = MX + tw + 0.4, w = W - MX - x;
        card(s, x, CONTENT_TOP, w, CONTENT_BOTTOM - CONTENT_TOP, T.highlight);
        chip(s, x + 0.3, CONTENT_TOP + 0.3, 'TAKEAWAY', T.accent, T.white);
        const tk = Array.isArray(takeaway) ? takeaway : [takeaway];
        s.addText(bulletRuns(tk, 15), { x: x + 0.3, y: CONTENT_TOP + 0.95, w: w - 0.6, h: CONTENT_BOTTOM - CONTENT_TOP - 1.2, isTextBox: true, fontFace: FONT_BODY, color: T.ink, margin: 0, valign: 'top', fit: 'shrink' });
      } else {
        card(s, MX, CONTENT_BOTTOM - 0.75, W - 2 * MX, 0.75, T.highlight);
        text(s, Array.isArray(takeaway) ? takeaway.join('  /  ') : takeaway, { x: MX + 0.3, y: CONTENT_BOTTOM - 0.75, w: W - 2 * MX - 0.6, h: 0.75, fontSize: 15, bold: true, valign: 'middle' });
      }
    }
    notes(s, n);
    return s;
  }

  /** 큰 숫자 강조. stats: [{value, label, sub}] (2–4개), note(선택) */
  function statSlide({ eyebrow, title, stats, note, notes: n }) {
    const s = contentSlide({ eyebrow, title });
    const gap = 0.35, cw = (W - 2 * MX - gap * (stats.length - 1)) / stats.length;
    const ch = 3.6, y = CONTENT_TOP + 0.4;
    stats.forEach((st, i) => {
      const x = MX + i * (cw + gap);
      card(s, x, y, cw, ch, i === 0 ? T.surface : 'F7F8F9');
      text(s, st.value, { x: x + 0.2, y: y + 0.4, w: cw - 0.4, h: 1.4, fontSize: 54, bold: true, color: i === 0 ? T.primary : T.ink, align: 'center', valign: 'middle', fontFace: FONT_HEAD, fit: 'shrink' });
      text(s, st.label, { x: x + 0.2, y: y + 1.95, w: cw - 0.4, h: 0.5, fontSize: 16, bold: true, align: 'center' });
      if (st.sub) text(s, st.sub, { x: x + 0.3, y: y + 2.5, w: cw - 0.6, h: 0.9, fontSize: 12, color: T.muted, align: 'center' });
    });
    if (note) text(s, note, { x: MX, y: y + ch + 0.4, w: W - 2 * MX, h: 0.8, fontSize: 14, color: T.ink });
    notes(s, n);
    return s;
  }

  /**
   * 네이티브 막대/선 차트. labels: string[], series: [{name, values}]
   * highlightIndex: 제안 기법 막대 위치(단일 시리즈일 때 accent 대신 primary로 강조)
   */
  function chartSlide({ eyebrow, title, type = 'bar', labels, series, valTitle, takeaway, note, numFmt = 'General', valMin, valMax, notes: n }) {
    const s = contentSlide({ eyebrow, title });
    const cw = takeaway ? 8.3 : W - 2 * MX;
    const ch = CONTENT_BOTTOM - CONTENT_TOP - (note ? 0.45 : 0);
    const palette = [T.primary, T.accent, '9AA5B1', T.dark, 'C7CDD4'];
    s.addChart(type === 'line' ? pres.charts.LINE : pres.charts.BAR, series.map((sr) => ({ name: sr.name, labels, values: sr.values })), {
      x: MX, y: CONTENT_TOP, w: cw, h: ch, barDir: 'col', chartColors: palette.slice(0, Math.max(series.length, 1)),
      showValue: type === 'bar', dataLabelPosition: 'outEnd', dataLabelFontSize: 10, dataLabelColor: T.ink,
      dataLabelFormatCode: numFmt, valAxisLabelFormatCode: numFmt,
      catAxisLabelColor: T.muted, valAxisLabelColor: T.muted, catAxisLabelFontFace: FONT_BODY, valAxisLabelFontFace: FONT_BODY,
      catAxisLabelFontSize: 11, valAxisLabelFontSize: 10,
      valGridLine: { color: 'E5E7EB', size: 0.5 }, catGridLine: { style: 'none' },
      showLegend: series.length > 1, legendPos: 'b', legendFontSize: 11, legendFontFace: FONT_BODY,
      showValAxisTitle: !!valTitle, valAxisTitle: valTitle || '', valAxisTitleFontSize: 11, valAxisTitleColor: T.muted,
      lineSize: 2.5, lineDataSymbolSize: 7,
      ...(valMin !== undefined ? { valAxisMinVal: valMin } : {}), ...(valMax !== undefined ? { valAxisMaxVal: valMax } : {}),
    });
    if (note) text(s, note, { x: MX, y: CONTENT_TOP + ch + 0.1, w: cw, h: 0.35, fontSize: 10, color: T.muted });
    if (takeaway) {
      const x = MX + cw + 0.4, w = W - MX - x;
      card(s, x, CONTENT_TOP, w, CONTENT_BOTTOM - CONTENT_TOP, T.highlight);
      chip(s, x + 0.3, CONTENT_TOP + 0.3, 'TAKEAWAY', T.accent, T.white);
      const tk = Array.isArray(takeaway) ? takeaway : [takeaway];
      s.addText(bulletRuns(tk, 15), { x: x + 0.3, y: CONTENT_TOP + 0.95, w: w - 0.6, h: CONTENT_BOTTOM - CONTENT_TOP - 1.2, isTextBox: true, fontFace: FONT_BODY, color: T.ink, margin: 0, valign: 'top', fit: 'shrink' });
    }
    notes(s, n);
    return s;
  }

  /** 파이프라인. steps: [{title, desc}] (3–5개) */
  function processSlide({ eyebrow, title, steps, footer, notes: n }) {
    const s = contentSlide({ eyebrow, title });
    const k = steps.length, arrowW = 0.45;
    const bw = (W - 2 * MX - arrowW * (k - 1)) / k;
    const y = CONTENT_TOP + 0.3, bh = footer ? 3.9 : 4.4;
    steps.forEach((st, i) => {
      const x = MX + i * (bw + arrowW);
      card(s, x, y, bw, bh, i === k - 1 ? T.surface : 'F7F8F9');
      badge(s, x + 0.25, y + 0.25, i + 1, T.primary, 0.48, 14);
      text(s, st.title, { x: x + 0.25, y: y + 0.9, w: bw - 0.5, h: 0.9, fontSize: 17, bold: true, fontFace: FONT_HEAD, fit: 'shrink' });
      text(s, st.desc || '', { x: x + 0.25, y: y + 1.85, w: bw - 0.5, h: bh - 2.05, fontSize: 13, color: T.muted, lineSpacingMultiple: 1.15, fit: 'shrink' });
      if (i < k - 1) s.addShape(pres.shapes.LINE, { x: x + bw + 0.07, y: y + bh / 2, w: arrowW - 0.14, h: 0, line: { color: T.accent, width: 2.5, endArrowType: 'triangle' } });
    });
    if (footer) {
      card(s, MX, CONTENT_BOTTOM - 0.65, W - 2 * MX, 0.65, T.highlight);
      text(s, footer, { x: MX + 0.3, y: CONTENT_BOTTOM - 0.65, w: W - 2 * MX - 0.6, h: 0.65, fontSize: 14, bold: true, valign: 'middle' });
    }
    notes(s, n);
    return s;
  }

  /**
   * Critical review. strengths/weaknesses: string[] (각 항목 앞에 '[저자 언급]' 등 라벨 가능)
   * future(선택): string[] 후속 연구 아이디어
   */
  function critiqueSlide({ eyebrow = 'Critical Review', title, strengths, weaknesses, future, notes: n }) {
    const s = contentSlide({ eyebrow, title });
    const gap = 0.4;
    const cols = future && future.length ? 3 : 2;
    const cw = (W - 2 * MX - gap * (cols - 1)) / cols, ch = CONTENT_BOTTOM - CONTENT_TOP;
    const defs = [['+', '강점', strengths, T.primary], ['−', '약점 · 의문', weaknesses, T.accent]];
    if (cols === 3) defs.push(['→', '후속 연구', future, T.muted]);
    defs.forEach(([sym, lab, items, c], i) => {
      const x = MX + i * (cw + gap);
      card(s, x, CONTENT_TOP, cw, ch, i === 0 ? T.surface : 'F7F8F9');
      badge(s, x + 0.3, CONTENT_TOP + 0.3, sym, c, 0.5, 18);
      text(s, lab, { x: x + 0.95, y: CONTENT_TOP + 0.3, w: cw - 1.2, h: 0.5, fontSize: 18, bold: true, valign: 'middle', fontFace: FONT_HEAD });
      s.addText(bulletRuns(items, 15), { x: x + 0.3, y: CONTENT_TOP + 1.05, w: cw - 0.6, h: ch - 1.3, isTextBox: true, fontFace: FONT_BODY, color: T.ink, margin: 0, valign: 'top', fit: 'shrink' });
    });
    notes(s, n);
    return s;
  }

  /** 토론 질문. questions: string[] (3–5) */
  function questionsSlide({ title = '함께 생각해 볼 질문', questions, notes: n }) {
    const s = contentSlide({ eyebrow: 'Discussion', title });
    const rowH = Math.min(1.15, (CONTENT_BOTTOM - CONTENT_TOP) / questions.length);
    questions.forEach((q, i) => {
      const y = CONTENT_TOP + i * rowH;
      card(s, MX, y, W - 2 * MX, rowH - 0.2, i % 2 ? 'F7F8F9' : T.surface);
      text(s, `Q${i + 1}`, { x: MX + 0.3, y, w: 0.8, h: rowH - 0.2, fontSize: 22, bold: true, color: T.accent, valign: 'middle', fontFace: FONT_HEAD });
      text(s, q, { x: MX + 1.2, y, w: W - 2 * MX - 1.5, h: rowH - 0.2, fontSize: 16, valign: 'middle', fit: 'shrink' });
    });
    notes(s, n);
    return s;
  }

  /** 결론. takeaways: string[] (3), closing: 'Q&A' 등 */
  function closingSlide({ title = 'Take-home Messages', takeaways, closing = 'Q & A', notes: n }) {
    const s = darkSlide();
    text(s, 'CONCLUSION', { x: MX, y: 0.6, w: 6, h: 0.3, fontSize: 11, bold: true, color: T.accent, charSpacing: 2, fontFace: FONT_HEAD });
    text(s, title, { x: MX, y: 0.95, w: W - 2 * MX, h: 0.9, fontSize: 32, bold: true, color: T.onDark, fontFace: FONT_HEAD, valign: 'middle' });
    const rowH = 1.15;
    takeaways.forEach((t, i) => {
      const y = 2.2 + i * rowH;
      badge(s, MX, y + 0.2, i + 1, T.accent, 0.55, 16);
      text(s, t, { x: MX + 0.85, y, w: 10.8, h: rowH - 0.1, fontSize: 19, color: T.onDark, valign: 'middle', fit: 'shrink' });
    });
    text(s, closing, { x: MX, y: 6.1, w: W - 2 * MX, h: 0.8, fontSize: 28, bold: true, color: T.accent, align: 'right', fontFace: FONT_HEAD });
    notes(s, n);
    return s;
  }

  /** 참고문헌. refs: string[] */
  function referencesSlide({ title = 'References', refs, notes: n }) {
    const s = contentSlide({ eyebrow: 'Appendix', title });
    s.addText(refs.map((r, i) => ({ text: r, options: { fontSize: 11, color: T.ink, paraSpaceAfter: 6, breakLine: i < refs.length - 1 } })),
      { x: MX, y: CONTENT_TOP, w: W - 2 * MX, h: CONTENT_BOTTOM - CONTENT_TOP, isTextBox: true, fontFace: FONT_BODY, margin: 0, valign: 'top', fit: 'shrink' });
    notes(s, n);
    return s;
  }

  async function save(file) {
    await pres.writeFile({ fileName: file });
    return file;
  }

  return {
    pres, theme: T, fonts: { head: FONT_HEAD, body: FONT_BODY }, W, H, MX, CONTENT_TOP, CONTENT_BOTTOM,
    // primitives (커스텀 레이아웃용)
    text, card, badge, chip, fit, pngSize, bulletRuns, contentSlide,
    // archetypes
    titleSlide, agendaSlide, sectionSlide, tldrSlide, pointsSlide, figureSlide, equationSlide,
    compareSlide, tableSlide, statSlide, chartSlide, processSlide, critiqueSlide, questionsSlide,
    closingSlide, referencesSlide, save,
  };
};
module.exports.THEMES = THEMES;
