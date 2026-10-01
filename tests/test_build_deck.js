'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {createRequire} = require('node:module');
const skill = path.resolve(__dirname, '../skills/pimp');
const requireSkill = createRequire(path.join(skill, 'package.json'));
const JSZip = requireSkill('jszip');
const builder = require('../skills/pimp/scripts/build_deck.js');
const createKit = require('../skills/pimp/scripts/deck_kit.js');
const CLI = path.join(skill, 'scripts/build_deck.js');
const NOTES = '논문의 실험 조건과 평가 지표를 설명하고 수치를 원문 표와 대조합니다.';
const SOURCE = {page: 2, kind: 'paper', label: 'Table 1'};
const PIXEL = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a8skAAAAASUVORK5CYII=', 'base64');

function slide(overrides = {}) {
  return {archetype:'pointsSlide', section:'Method', notes:NOTES, sources:[{...SOURCE}],
    data:{title:'실험 조건', points:[{head:'공통 조건', body:'동일한 지표로 비교합니다.'}]}, ...overrides};
}
function spec(slides = [slide()]) {
  return {schema_version:1, mode:'normal', paper_pages:3, theme:'teal', title:'Synthetic research fixture', slides};
}
function workspace(t) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'pimp-node-test-'));
  t.after(() => fs.rmSync(dir, {recursive:true, force:true}));
  return dir;
}
async function zipFile(file) {
  return JSZip.loadAsync(fs.readFileSync(file), {checkCRC32:true});
}

test('content requires sources while a cover can omit them', () => {
  assert.throws(() => builder.validate(spec([slide({sources:[]})])), /sources/);
  const cover = slide({archetype:'titleSlide', sources:[], data:{title:'Paper'}});
  assert.doesNotThrow(() => builder.validate(spec([cover])));
  for (const bad of [{...SOURCE,page:0}, {...SOURCE,page:4}, {...SOURCE,kind:'made-up'}, {...SOURCE,label:''}]) {
    assert.throws(() => builder.validate(spec([slide({sources:[bad]})])));
  }
});

test('punctuation, empty notes and nested notes do not count as a speaker script', () => {
  for (const notes of ['', '짧은 설명', '................................................', '   '.repeat(20)]) {
    assert.throws(() => builder.validate(spec([slide({notes})])), /notes/);
  }
  assert.throws(() => builder.validate(spec([slide({data:{title:'Problem', notes:NOTES}})])), /notes/);
});

test('malformed plans and invalid page limits fail before writing a presentation', () => {
  for (const bad of [null, {}, {...spec(),schema_version:2}, {...spec(),mode:'casual'}, {...spec(),slides:[]},
    {...spec(),paper_pages:0}, {...spec(),paper_pages:-1}, {...spec(),paper_pages:1.5}, {...spec(),paper_pages:'3'},
    spec([slide({archetype:'unknown'})]), spec([slide({data:[]})]), spec([slide({sources:null})])]) {
    assert.throws(() => builder.validate(bad));
  }
});

test('real PPTX includes Korean notes, page citations, and matching manifest', async t => {
  const dir = workspace(t), out = path.join(dir,'deck.pptx'), manifestPath = path.join(dir,'reports','manifest.json');
  const manifest = await builder.build(spec(), dir, out, manifestPath);
  const zip = await zipFile(out);
  const slideXML = await zip.file('ppt/slides/slide1.xml').async('string');
  const notesXML = await zip.file('ppt/notesSlides/notesSlide1.xml').async('string');
  assert.match(slideXML, /실험 조건/);
  assert.ok(notesXML.includes(NOTES));
  assert.match(notesXML, /Table 1 \(PDF p\.2\)/);
  assert.match(notesXML, /논문/);
  assert.equal(manifest.paper_pages, 3);
  assert.deepEqual(JSON.parse(fs.readFileSync(manifestPath,'utf8')), manifest);
  assert.equal(manifest.slides[0].index,1);
  assert.deepEqual(manifest.slides[0].sources, [SOURCE]);
});

test('CLI resolves figure files relative to the plan, even from another cwd', async t => {
  const dir = workspace(t), planDir = path.join(dir,'plan'), assets = path.join(planDir,'assets');
  fs.mkdirSync(assets,{recursive:true});
  fs.writeFileSync(path.join(assets,'pixel.png'), PIXEL);
  const input = path.join(planDir,'deck.json'), out = path.join(dir,'output','deck.pptx'), manifest = path.join(dir,'audit','manifest.json');
  fs.writeFileSync(input, JSON.stringify(spec([slide({archetype:'figureSlide', data:{title:'Figure 1', image:'assets/pixel.png', caption:'Synthetic image'}})])));
  const original = fs.readFileSync(input,'utf8');
  const result = spawnSync(process.execPath,[CLI,input,'--out',out,'--manifest',manifest],{cwd:dir,encoding:'utf8'});
  assert.equal(result.status,0,result.stderr);
  assert.equal(fs.readFileSync(input,'utf8'),original);
  const zip = await zipFile(out);
  const media = Object.values(zip.files).filter(item => /^ppt\/media\//.test(item.name) && !item.dir);
  assert.ok(media.length > 0,'figure must be embedded');
  const images = await Promise.all(media.map(item => item.async('nodebuffer')));
  assert.ok(images.some(image => image.equals(PIXEL)),'embedded media matches the relative source');
  assert.equal(JSON.parse(fs.readFileSync(manifest,'utf8')).slides[0].archetype,'figureSlide');
});

test('missing and nonfile image assets fail', t => {
  const dir = workspace(t);
  assert.throws(() => builder.resolveAssets({image:'missing.png'},dir),/missing asset/);
  assert.throws(() => builder.resolveAssets({eqImages:[null]},dir),/asset path/);
  assert.throws(() => builder.resolveAssets({image:dir},dir),/asset|file/);
});

test('bar highlight writes the intended color for each actual OOXML data point', async t => {
  const dir = workspace(t), out = path.join(dir,'chart.pptx');
  await builder.build(spec([slide({archetype:'chartSlide', data:{title:'비교 결과', labels:['A','제안','C'], series:[{name:'Accuracy',values:[0.6,0.8,0.7]}], highlightIndex:1}})]),dir,out,path.join(dir,'manifest.json'));
  const zip = await zipFile(out);
  const xml = await zip.file('ppt/charts/chart1.xml').async('string');
  const points = [...xml.matchAll(/<c:dPt>([\s\S]*?)<\/c:dPt>/g)].map(match => {
    return {index:Number(match[1].match(/<c:idx val="(\d+)"/)[1]), color:match[1].match(/<a:srgbClr val="([A-Fa-f0-9]+)"/)[1]};
  });
  assert.deepEqual(points,[{index:0,color:'9AA5B1'},{index:1,color:'0F6466'},{index:2,color:'9AA5B1'}]);
  assert.ok(Object.keys(zip.files).some(name => /^ppt\/embeddings\/.*\.xlsx$/.test(name)), 'native chart includes editable workbook');
});

test('charts reject inconsistent categories, nonfinite values and invalid highlights', () => {
  const data = {title:'Result',labels:['A','B'],series:[{name:'Metric',values:[1,2]}]};
  for (const overrides of [{type:'pie'}, {series:[{name:'Metric',values:[1]}]}, {series:[{name:'Metric',values:[1,NaN]}]},
    {highlightIndex:2}, {highlightIndex:0.5}, {type:'line',highlightIndex:0},
    {series:[{name:'M',values:[1,2]},{name:'N',values:[3,4]}],highlightIndex:0}]) {
    assert.throws(() => createKit().chartSlide({...data,...overrides}));
  }
});

test('CLI refuses plan/deck/manifest collisions and preserves the plan', t => {
  const dir = workspace(t), input = path.join(dir,'deck.json'), out = path.join(dir,'deck.pptx');
  const original = JSON.stringify(spec());
  fs.writeFileSync(input,original);
  for (const args of [['--out',input],['--out',out,'--manifest',input],['--out',out,'--manifest',out]]) {
    const result = spawnSync(process.execPath,[CLI,input,...args],{encoding:'utf8'});
    assert.equal(result.status,1);
    assert.match(result.stderr,/paths must differ/);
    assert.equal(fs.readFileSync(input,'utf8'),original);
  }
  assert.equal(fs.existsSync(out),false);
});

test('exported build also refuses to overwrite deck with manifest JSON', async t => {
  const dir = workspace(t), same = path.join(dir,'result.pptx');
  await assert.rejects(builder.build(spec(),dir,same,same),/paths must differ/);
  assert.equal(fs.existsSync(same),false);
});

test('explicit fonts are preserved in the deck kit', () => {
  assert.deepEqual(createKit({fontHead:'Heading Font',fontBody:'Body Font'}).fonts,{head:'Heading Font',body:'Body Font'});
});

test('malformed ICNS image parsing terminates instead of blocking the process', () => {
  const script = `
    const {imageSize} = require('image-size');
    const png = Buffer.from('${PIXEL.toString('base64')}', 'base64');
    const size = imageSize(png);
    if (size.width !== 1 || size.height !== 1) process.exit(2);
    const malformed = Buffer.alloc(16);
    malformed.write('icns', 0); malformed.writeUInt32BE(16, 4);
    malformed.write('icp4', 8); malformed.writeUInt32BE(0, 12);
    try { imageSize(malformed); process.exit(3); }
    catch (error) { console.log('invalid image rejected'); }
  `;
  const result = spawnSync(process.execPath, ['-e', script], {cwd:skill, encoding:'utf8', timeout:3000});
  assert.equal(result.status, 0, result.error?.message || result.stderr);
  assert.match(result.stdout, /invalid image rejected/);
});
