#!/usr/bin/env node
import { chromium } from 'playwright';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';
import readline from 'node:readline/promises';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const AUTH_FILE = path.join(__dirname, 'auth.json');
const EXPORT_ROOT = path.join(__dirname, 'export');
const LS_BASE = 'https://noraweweler.learningsuite.io';

async function promptEnter(message) {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  await rl.question(message);
  rl.close();
}

async function login() {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(`${LS_BASE}/admin/courses`);

  console.log('\n→ Im Browser einloggen. Wenn du die Kurs-Übersicht siehst:');
  await promptEnter('  Hier Enter drücken um Session zu speichern… ');

  await context.storageState({ path: AUTH_FILE });
  await browser.close();
  console.log(`✓ Session gespeichert: ${AUTH_FILE}`);
}

async function triggerVideoDownload(page) {
  // Wait for video element, then also wait until video is actually loaded (readyState >= 2 = HAVE_CURRENT_DATA)
  await page.locator('video').first().waitFor({ state: 'attached', timeout: 60_000 });
  await page.waitForFunction(() => {
    const v = document.querySelector('video');
    return v && (v.readyState >= 1 || v.duration > 0);
  }, { timeout: 60_000 }).catch(() => {});

  // Open the video context menu (purple button overlay)
  await page.locator('.MuiButtonBase-root.MuiButton-root.MuiButton-text').first().click({ timeout: 30_000 });

  // Wait for "Video herunterladen" button to exist AND be enabled
  const dlBtn = page.getByRole('button', { name: 'Video herunterladen' });
  await dlBtn.waitFor({ state: 'visible', timeout: 30_000 });
  await page.waitForFunction(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const b = btns.find((x) => x.textContent?.trim() === 'Video herunterladen');
    return b && !b.disabled && b.getAttribute('aria-disabled') !== 'true';
  }, { timeout: 60_000 });
  await dlBtn.click({ timeout: 15_000 });

  // Submenu: Original (also wait for enabled)
  const origItem = page.getByRole('menuitem', { name: 'Original' });
  await origItem.waitFor({ state: 'visible', timeout: 30_000 });
  const downloadPromise = page.waitForEvent('download', { timeout: 60_000 });
  // Safety net: suppress unhandled rejection if click below throws
  downloadPromise.catch(() => {});
  await origItem.click({ timeout: 15_000 });
  return downloadPromise;
}

async function triggerVideoDownloadWithRetry(page, lessonUrl, maxAttempts = 3) {
  let lastErr;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      if (attempt > 1) {
        await page.goto(lessonUrl, { waitUntil: 'domcontentloaded', timeout: 45_000 });
        await page.waitForTimeout(2000 * attempt);
      }
      return await triggerVideoDownload(page);
    } catch (e) {
      lastErr = e;
      if (attempt < maxAttempts) {
        await page.waitForTimeout(3000 * attempt);
      }
    }
  }
  throw lastErr;
}

async function download(lessonUrl, outDir, { manual = false } = {}) {
  if (!fs.existsSync(AUTH_FILE)) {
    console.error('✗ Keine Session. Zuerst: node ls-export.mjs login');
    process.exit(1);
  }
  const targetDir = outDir || path.join(EXPORT_ROOT, 'poc');
  fs.mkdirSync(targetDir, { recursive: true });

  const browser = await chromium.launch({ headless: !manual });
  const context = await browser.newContext({
    storageState: AUTH_FILE,
    acceptDownloads: true,
  });
  const page = await context.newPage();

  console.log(`→ Öffne Lektion: ${lessonUrl}`);
  await page.goto(lessonUrl, { waitUntil: 'domcontentloaded' });

  let dl;
  if (manual) {
    console.log('→ Klick manuell im Browser: Menü → "Video herunterladen" → "Original"…');
    dl = await page.waitForEvent('download', { timeout: 5 * 60 * 1000 });
  } else {
    console.log('→ Auto-Klick: Menü → "Video herunterladen" → "Original"…');
    dl = await triggerVideoDownload(page);
  }

  const suggested = dl.suggestedFilename();
  const filepath = path.join(targetDir, suggested);
  await dl.saveAs(filepath);
  const size = fs.statSync(filepath).size;
  console.log(`✓ Gespeichert: ${filepath} (${(size / 1024 / 1024).toFixed(1)} MB)`);

  await browser.close();
}

const TENANT_ID = 'clw9mtobn1aze9wppi06umx8l';
const GRAPHQL_URL = `https://api.learningsuite.io/${TENANT_ID}/graphql`;
const QUERY_HASHES = {
  AuthoredCourses:          'a70e28d2b8370d93ce039c75abe29c0ed646259d799d1522bf31e0c22b813c0b',
  CoursePaths:              'dcb1132ae4701875b7ce74fc38afd5ae97ea08df83c06959bff99f3ebe28227b',
  TopicQuery:               'b44496383040234ea01b5031834480ab3aa50435f4aa2f5ef8fa6f63ee7d285c',
  SitemapLessonQuery:       '61b50b92ccc934c236e989cabd9305720ed56446309f1f30c195baffc653628c',
  StepFileTranscriptQuery:  '495c0bb2ce8e62b76037c7db669e3ba5c6bd5716dd7c6f5d7d2f1344689d2b6d',
};

function msToVTT(ms) {
  const h = Math.floor(ms / 3600000);
  const m = Math.floor((ms % 3600000) / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  const msR = ms % 1000;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${String(msR).padStart(3, '0')}`;
}

function transcriptToVTT(transcript) {
  if (!transcript?.translations?.length) return null;
  const tr = transcript.translations.find((t) => t.lang === transcript.sourceLanguage) || transcript.translations[0];
  if (!tr?.text?.length) return null;
  let vtt = 'WEBVTT\n\n';
  tr.text.forEach((seg, i) => {
    vtt += `${i + 1}\n${msToVTT(seg.from)} --> ${msToVTT(seg.to)}\n${seg.text}\n\n`;
  });
  return vtt;
}

async function captureToken(page) {
  let token = null;
  page.on('request', (req) => {
    if (!req.url().includes('/graphql')) return;
    const auth = req.headers()['authorization'];
    if (auth?.startsWith('Bearer ')) token = auth;
  });
  await page.goto(`${LS_BASE}/admin/courses`);
  await page.waitForResponse((r) => r.url().includes('/graphql') && r.status() === 200, { timeout: 30_000 });
  await page.waitForTimeout(1000);
  if (!token) throw new Error('Konnte Bearer-Token nicht aus Requests extrahieren.');
  return token;
}

async function gql(page, token, opName, vars) {
  const hash = QUERY_HASHES[opName];
  if (!hash) throw new Error(`Unbekannte Operation: ${opName}`);
  const res = await page.request.post(GRAPHQL_URL, {
    headers: {
      Authorization: token,
      Origin: LS_BASE,
      'Content-Type': 'application/json',
    },
    data: {
      operationName: opName,
      extensions: { persistedQuery: { version: 1, sha256Hash: hash } },
      variables: vars,
    },
  });
  if (!res.ok()) throw new Error(`GraphQL ${opName} → HTTP ${res.status()}: ${await res.text()}`);
  const body = await res.json();
  if (body.errors) throw new Error(`GraphQL ${opName} errors: ${JSON.stringify(body.errors)}`);
  return body.data;
}

async function enumerate(outFile) {
  if (!fs.existsSync(AUTH_FILE)) {
    console.error('✗ Keine Session. Zuerst: node ls-export.mjs login');
    process.exit(1);
  }
  const target = outFile || path.join(__dirname, 'work-list.json');

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ storageState: AUTH_FILE });
  const page = await context.newPage();

  console.log('→ Session prüfen, Bearer-Token extrahieren…');
  const token = await captureToken(page);
  console.log('  ✓ Token OK');

  console.log('→ Kurse laden…');
  const { courses } = await gql(page, token, 'AuthoredCourses', {});
  console.log(`  ✓ ${courses.length} Kurse`);

  const workList = [];
  let totalVideos = 0;

  for (const course of courses) {
    console.log(`→ Kurs: ${course.name} (${course.sid})`);
    const cp = await gql(page, token, 'CoursePaths', { courseSid: course.sid });
    const modules = cp.course.modules.map((mc) => mc.module);
    console.log(`  ${modules.length} Module`);

    for (const mod of modules) {
      const tq = await gql(page, token, 'TopicQuery', { topicSid: mod.sid, courseSid: course.sid });
      for (const section of tq.topic.sections || []) {
        for (const lesson of section.lessons || []) {
          const sl = await gql(page, token, 'SitemapLessonQuery', {
            lessonSid: lesson.sid,
            topicSid: mod.sid,
          });
          for (const step of sl.lesson.steps || []) {
            const hasVideo = (step.mediaDuration || 0) > 0;
            if (!hasVideo) continue;
            totalVideos++;
            workList.push({
              courseSid: course.sid,
              courseName: course.name,
              moduleSid: mod.sid,
              moduleName: mod.name,
              sectionName: section.name,
              lessonSid: lesson.sid,
              lessonName: lesson.name,
              stepSid: step.sid,
              stepName: step.name,
              mediaDuration: step.mediaDuration,
              lessonUrl: `${LS_BASE}/admin/editor/${course.sid}/${mod.sid}/${lesson.sid}/${step.sid}`,
            });
          }
        }
      }
    }
    console.log(`  ⇒ bisher ${totalVideos} Videos`);
  }

  fs.writeFileSync(target, JSON.stringify(workList, null, 2));
  console.log(`\n✓ ${totalVideos} Videos gefunden → ${target}`);
  await browser.close();
}

async function transcripts(workListFile, outRoot) {
  if (!fs.existsSync(AUTH_FILE)) {
    console.error('✗ Keine Session. Zuerst: node ls-export.mjs login');
    process.exit(1);
  }
  const wl = workListFile || path.join(__dirname, 'work-list.json');
  if (!fs.existsSync(wl)) {
    console.error(`✗ ${wl} fehlt. Zuerst: node ls-export.mjs enumerate`);
    process.exit(1);
  }
  const root = outRoot || EXPORT_ROOT;
  fs.mkdirSync(root, { recursive: true });
  const doneFile = path.join(root, 'transcripts-done.jsonl');
  const errFile = path.join(root, 'transcripts-errors.jsonl');

  const workList = JSON.parse(fs.readFileSync(wl, 'utf-8'));
  const doneSet = new Set();
  if (fs.existsSync(doneFile)) {
    for (const line of fs.readFileSync(doneFile, 'utf-8').split('\n')) {
      if (!line.trim()) continue;
      try { doneSet.add(JSON.parse(line).stepSid); } catch {}
    }
  }

  const todo = workList.filter((e) => !doneSet.has(e.stepSid));
  console.log(`→ ${workList.length} Videos, ${doneSet.size} erledigt, ${todo.length} offen`);
  if (todo.length === 0) { console.log('✓ Nichts zu tun.'); return; }

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ storageState: AUTH_FILE });
  const page = await context.newPage();
  const token = await captureToken(page);

  const doneStream = fs.createWriteStream(doneFile, { flags: 'a' });
  const errStream = fs.createWriteStream(errFile, { flags: 'a' });

  let ok = 0, empty = 0, err = 0;
  const start = Date.now();

  for (let i = 0; i < todo.length; i++) {
    const e = todo[i];
    const tag = `[${i + 1}/${todo.length}]`;
    process.stdout.write(`${tag} ${e.courseName} · ${(e.stepName || e.lessonName).slice(0, 60)} … `);

    try {
      // Get stepFileLinks for this step via SitemapLessonQuery
      const sl = await gql(page, token, 'SitemapLessonQuery', {
        lessonSid: e.lessonSid,
        topicSid: e.moduleSid,
      });
      const step = sl.lesson?.steps?.find((s) => s.sid === e.stepSid);
      if (!step) throw new Error('Step in SitemapLessonQuery nicht gefunden');

      // Find video stepFileLinks (mimeType null, not a "courses/..." attachment)
      const videoFiles = step.stepFileLinks.filter((sfl) =>
        sfl.downloadable?.mimeType == null && !sfl.downloadable?.id?.startsWith('courses/')
      );

      let gotTranscript = null;
      for (const sfl of videoFiles) {
        const t = await gql(page, token, 'StepFileTranscriptQuery', { id: sfl.id });
        if (t?.stepFileLink?.transcript?.translations?.length) {
          gotTranscript = t.stepFileLink.transcript;
          break;
        }
      }

      if (!gotTranscript) {
        doneStream.write(JSON.stringify({ stepSid: e.stepSid, status: 'no-transcript', ts: new Date().toISOString() }) + '\n');
        console.log('– (kein Transkript)');
        empty++;
        continue;
      }

      const dir = path.join(
        root,
        safeName(e.courseName),
        safeName(e.moduleName),
        safeName(e.sectionName || ''),
      );
      fs.mkdirSync(dir, { recursive: true });
      const baseName = safeName(e.stepName || e.lessonName);
      const vttPath = path.join(dir, `${baseName}.vtt`);
      const jsonPath = path.join(dir, `${baseName}.transcript.json`);

      fs.writeFileSync(jsonPath, JSON.stringify(gotTranscript, null, 2));
      const vtt = transcriptToVTT(gotTranscript);
      if (vtt) fs.writeFileSync(vttPath, vtt);

      const segCount = gotTranscript.translations[0]?.text?.length || 0;
      doneStream.write(JSON.stringify({
        stepSid: e.stepSid, vttPath, jsonPath, segments: segCount, ts: new Date().toISOString(),
      }) + '\n');
      console.log(`✓ ${segCount} Segmente`);
      ok++;
    } catch (ex) {
      const msg = String(ex.message || ex).slice(0, 240).replace(/\n/g, ' ');
      errStream.write(JSON.stringify({
        stepSid: e.stepSid, error: msg, ts: new Date().toISOString(),
      }) + '\n');
      console.log(`✗ ${msg}`);
      err++;
    }
  }

  doneStream.end();
  errStream.end();
  await browser.close();
  const mins = ((Date.now() - start) / 60_000).toFixed(1);
  console.log(`\n✓ Fertig in ${mins} min: ${ok} mit Transkript, ${empty} ohne, ${err} Fehler`);
}

function safeName(s) {
  if (!s) return 'untitled';
  return s.replace(/[/\\?%*:|"<>]+/g, '-').replace(/\s+/g, ' ').trim().slice(0, 180) || 'untitled';
}

async function batch(workListFile, outRoot) {
  if (!fs.existsSync(AUTH_FILE)) {
    console.error('✗ Keine Session. Zuerst: node ls-export.mjs login');
    process.exit(1);
  }
  const wl = workListFile || path.join(__dirname, 'work-list.json');
  if (!fs.existsSync(wl)) {
    console.error(`✗ ${wl} fehlt. Zuerst: node ls-export.mjs enumerate`);
    process.exit(1);
  }
  const root = outRoot || EXPORT_ROOT;
  fs.mkdirSync(root, { recursive: true });
  const doneFile = path.join(root, 'done.jsonl');
  const errFile = path.join(root, 'errors.jsonl');

  const workList = JSON.parse(fs.readFileSync(wl, 'utf-8'));
  const doneSet = new Set();
  if (fs.existsSync(doneFile)) {
    for (const line of fs.readFileSync(doneFile, 'utf-8').split('\n')) {
      if (!line.trim()) continue;
      try { doneSet.add(JSON.parse(line).stepSid); } catch {}
    }
  }

  const todo = workList.filter((e) => !doneSet.has(e.stepSid));
  console.log(`→ Gesamt ${workList.length} Videos, ${doneSet.size} bereits erledigt, ${todo.length} offen`);
  if (todo.length === 0) { console.log('✓ Nichts zu tun.'); return; }

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ storageState: AUTH_FILE, acceptDownloads: true });
  const page = await context.newPage();

  const doneStream = fs.createWriteStream(doneFile, { flags: 'a' });
  const errStream = fs.createWriteStream(errFile, { flags: 'a' });

  let ok = 0, err = 0;
  let consecutiveErr = 0;
  const start = Date.now();
  const randPause = (min, max) => new Promise((r) => setTimeout(r, min + Math.random() * (max - min)));

  for (let i = 0; i < todo.length; i++) {
    const e = todo[i];
    const dir = path.join(
      root,
      safeName(e.courseName),
      safeName(e.moduleName),
      safeName(e.sectionName || ''),
    );
    fs.mkdirSync(dir, { recursive: true });
    const baseName = safeName(e.stepName || e.lessonName);
    const filepath = path.join(dir, `${baseName}.mp4`);

    const tag = `[${i + 1}/${todo.length}]`;
    process.stdout.write(`${tag} ${e.courseName} · ${baseName} … `);

    try {
      await page.goto(e.lessonUrl, { waitUntil: 'domcontentloaded', timeout: 45_000 });
      const dl = await triggerVideoDownloadWithRetry(page, e.lessonUrl);
      await dl.saveAs(filepath);
      const size = fs.statSync(filepath).size;
      doneStream.write(JSON.stringify({
        stepSid: e.stepSid, filepath, size, ts: new Date().toISOString(),
      }) + '\n');
      console.log(`✓ ${(size / 1024 / 1024).toFixed(1)} MB`);
      ok++;
      consecutiveErr = 0;
    } catch (ex) {
      const msg = String(ex.message || ex).slice(0, 240).replace(/\n/g, ' ');
      errStream.write(JSON.stringify({
        stepSid: e.stepSid, lessonUrl: e.lessonUrl, error: msg, ts: new Date().toISOString(),
      }) + '\n');
      console.log(`✗ ${msg}`);
      err++;
      consecutiveErr++;
      if (consecutiveErr >= 3) {
        console.log(`  ⏸ 3 Fehler in Folge — 60 Sek Cool-Down…`);
        await new Promise((r) => setTimeout(r, 60_000));
        consecutiveErr = 0;
      }
    }

    if (i < todo.length - 1) await randPause(3000, 7000);
  }

  doneStream.end();
  errStream.end();
  await browser.close();
  const mins = ((Date.now() - start) / 60_000).toFixed(1);
  console.log(`\n✓ Fertig in ${mins} min: ${ok} OK, ${err} Fehler`);
  console.log(`  Erfolge: ${doneFile}`);
  if (err > 0) console.log(`  Fehler:  ${errFile}  →  'node ls-export.mjs batch' erneut startet nur die offenen Punkte.`);
}

async function record(outFile) {
  if (!fs.existsSync(AUTH_FILE)) {
    console.error('✗ Keine Session. Zuerst: node ls-export.mjs login');
    process.exit(1);
  }
  const target = outFile || path.join(__dirname, 'graphql-recording.jsonl');
  const writer = fs.createWriteStream(target, { flags: 'w' });

  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({ storageState: AUTH_FILE });
  const page = await context.newPage();

  let count = 0;
  page.on('response', async (response) => {
    const url = response.url();
    if (!url.includes('/graphql')) return;
    try {
      const req = response.request();
      const resBody = await response.json().catch(() => null);
      const entry = {
        t: new Date().toISOString(),
        method: req.method(),
        url,
        reqBody: req.postDataJSON(),
        status: response.status(),
        resBody,
      };
      writer.write(JSON.stringify(entry) + '\n');
      count++;
      process.stdout.write(`\r  GraphQL-Calls mitgeschnitten: ${count}`);
    } catch {}
  });

  await page.goto(`${LS_BASE}/admin/courses`);

  console.log(`\n→ Navigiere jetzt im Browser:`);
  console.log(`  1. Klick auf einen Kurs`);
  console.log(`  2. Klick auf ein Modul`);
  console.log(`  3. Klick auf eine Lektion mit Video (Stift-Icon)`);
  console.log(`  4. Optional: noch einen zweiten Kurs`);
  console.log(`\n→ Wenn fertig, hier Enter drücken.\n`);

  await promptEnter('');
  writer.end();
  await browser.close();
  console.log(`\n✓ Aufzeichnung: ${target}`);
}

function usage() {
  console.log(`ls-export — LearningSuite-Migrationstool

Kommandos:
  login                         Einmaliger Login, speichert Session in auth.json
  download <lessonUrl> [outDir] Headless: Auto-Klick Menü → "Video herunterladen" → "Original"
  download-manual <lessonUrl>   Fallback: Browser sichtbar, du klickst selbst
  record [outFile]              Browser sichtbar, GraphQL-Calls beim Navigieren mitschneiden
                                (für Phase-2-Schema-Analyse)
  enumerate [outFile]           Liste aller Videos → work-list.json
                                (direkte GraphQL-Calls via persisted queries)
  batch [workList] [outRoot]    Alle Videos aus work-list.json runterziehen.
                                Resume-fähig: bereits erledigte werden übersprungen.
                                Output: export/{Kurs}/{Modul}/{Section}/{Step}.mp4
  transcripts [workList] [out]  Transkripte als .vtt (Subtitle) + .transcript.json
                                neben jedes Video legen. Rein API-basiert, schnell.

Beispiele:
  node ls-export.mjs login
  node ls-export.mjs download "https://noraweweler.learningsuite.io/admin/editor/…"
  node ls-export.mjs record
`);
}

const [cmd, ...args] = process.argv.slice(2);
switch (cmd) {
  case 'login':
    await login();
    break;
  case 'download':
    if (!args[0]) { usage(); process.exit(1); }
    await download(args[0], args[1]);
    break;
  case 'download-manual':
    if (!args[0]) { usage(); process.exit(1); }
    await download(args[0], args[1], { manual: true });
    break;
  case 'record':
    await record(args[0]);
    break;
  case 'enumerate':
    await enumerate(args[0]);
    break;
  case 'batch':
    await batch(args[0], args[1]);
    break;
  case 'transcripts':
    await transcripts(args[0], args[1]);
    break;
  default:
    usage();
    process.exit(cmd ? 1 : 0);
}
