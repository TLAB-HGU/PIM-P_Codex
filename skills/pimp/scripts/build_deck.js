#!/usr/bin/env node
/** Build a source-linked deck from a Codex-authored deck.json. No LLM API calls. */
'use strict';
const fs = require('fs');
const path = require('path');
const createKit = require('./deck_kit.js');
const ARCHETYPES = ['titleSlide', 'agendaSlide', 'sectionSlide', 'tldrSlide', 'pointsSlide',
  'figureSlide', 'equationSlide', 'compareSlide', 'processSlide', 'tableSlide', 'statSlide',
  'chartSlide', 'critiqueSlide', 'questionsSlide', 'closingSlide', 'referencesSlide'];
const EXEMPT = new Set(['titleSlide', 'agendaSlide', 'sectionSlide', 'referencesSlide']);

function validate(spec) {
  if (spec.schema_version !== 1) throw new Error('schema_version must be 1');
  if (!['normal', 'easy'].includes(spec.mode)) throw new Error('mode must be normal or easy');
  if (spec.paper_pages !== undefined && (!Number.isInteger(spec.paper_pages) || spec.paper_pages < 1)) throw new Error('paper_pages must be a positive integer');
  if (spec.duration_minutes !== undefined && (!Number.isFinite(spec.duration_minutes) || spec.duration_minutes <= 0)) throw new Error('duration_minutes must be positive');
  if (!Array.isArray(spec.slides) || !spec.slides.length) throw new Error('slides must be a nonempty array');
  spec.slides.forEach((s, i) => {
    const prefix = `slide ${i + 1}: `;
    if (!ARCHETYPES.includes(s.archetype)) throw new Error(prefix + 'unsupported archetype');
    if (!s.data || typeof s.data !== 'object' || Array.isArray(s.data)) throw new Error(prefix + 'data must be an object');
    if (typeof s.section !== 'string' || !s.section.trim()) throw new Error(prefix + 'section must be nonempty');
    if (typeof s.notes !== 'string' || (s.notes.match(/[\p{L}\p{N}]/gu) || []).length < 20) throw new Error(prefix + 'substantive speaker notes are required (20+ letters/digits)');
    if (!Array.isArray(s.sources)) throw new Error(prefix + 'sources must be an array');
    if (!EXEMPT.has(s.archetype) && !s.sources.length) throw new Error(prefix + 'content slides require paper/reviewer sources');
    s.sources.forEach(src => {
      if (!Number.isInteger(src.page) || src.page < 1 || !['paper','reviewer'].includes(src.kind) || typeof src.label !== 'string' || !src.label.trim()) {
        throw new Error(prefix + 'each source needs page >= 1, kind paper/reviewer, and label');
      }
    });
    if (spec.paper_pages && s.sources.some(src => src.page > spec.paper_pages)) throw new Error(prefix + 'source page exceeds paper_pages');
    if (s.data.notes !== undefined) throw new Error(prefix + 'put notes at slide level, not inside data');
  });
}

function resolveAssets(data, base) {
  const d = {...data};
  for (const key of ['image', 'eqImages']) {
    if (d[key] === undefined) continue;
    const resolveOne = name => {
      if (typeof name !== 'string') throw new Error('asset path must be a string');
      const f = path.resolve(base, name);
      if (!fs.existsSync(f) || !fs.statSync(f).isFile()) throw new Error('missing asset file: ' + f);
      return f;
    };
    d[key] = Array.isArray(d[key]) ? d[key].map(resolveOne) : resolveOne(d[key]);
  }
  return d;
}

async function build(spec, base, out, manifestPath) {
  out = path.resolve(out);
  manifestPath = path.resolve(manifestPath);
  if (out === manifestPath) throw new Error('deck and manifest paths must differ');
  validate(spec);
  const kit = createKit({theme:spec.theme, title:spec.title, short:spec.short,
    fontHead:spec.font_head, fontBody:spec.font_body, colors:spec.colors});
  const manifest = {version:1, mode:spec.mode, title:spec.title || 'Paper Review',
    input_pdf:spec.input_pdf || null, paper_brief:spec.paper_brief || null, paper_pages:spec.paper_pages || null,
    duration_minutes:spec.duration_minutes || 30, fonts:kit.fonts, slides:[]};
  spec.slides.forEach((s, i) => {
    const citations = s.sources.map(src => `[${src.kind === 'reviewer' ? '리뷰어 관점' : '논문'}] ${src.label} (PDF p.${src.page})`).join('\n');
    const notes = s.notes.trim() + (citations ? '\n\n출처:\n' + citations : '');
    const data = resolveAssets(s.data, base);
    try { kit[s.archetype]({...data, notes}); }
    catch (e) { throw new Error(`slide ${i + 1} (${s.archetype}): ${e.message}`); }
    manifest.slides.push({index:i + 1, title:data.title || data.oneLiner || s.section || s.archetype,
      archetype:s.archetype, section:s.section || '', appendix:!!s.appendix,
      notes, sources:s.sources});
  });
  fs.mkdirSync(path.dirname(out), {recursive:true});
  await kit.save(out);
  fs.mkdirSync(path.dirname(manifestPath), {recursive:true});
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n');
  return manifest;
}

async function main(args) {
  if (args.includes('--help') || !args.length) {
    console.log('Usage: node build_deck.js deck.json --out deck.pptx [--manifest deck_manifest.json]');
    return;
  }
  const input = path.resolve(args[0]);
  let out, manifest;
  for (let i = 1; i < args.length; i++) {
    if (args[i] === '--out') out = args[++i];
    else if (args[i] === '--manifest') manifest = args[++i];
    else throw new Error('unknown argument: ' + args[i]);
  }
  if (!out) throw new Error('--out is required');
  out = path.resolve(out);
  manifest = path.resolve(manifest || path.join(path.dirname(out), 'deck_manifest.json'));
  if (out === input || manifest === input || manifest === out) throw new Error('input, deck and manifest paths must differ');
  const result = await build(JSON.parse(fs.readFileSync(input,'utf8')), path.dirname(input), out, manifest);
  console.log(JSON.stringify({deck:out, manifest, slides:result.slides.length, mode:result.mode}));
}
if (require.main === module) main(process.argv.slice(2)).catch(e => {console.error(e.message);process.exitCode = 1;});
module.exports = {build, validate, resolveAssets, ARCHETYPES};
