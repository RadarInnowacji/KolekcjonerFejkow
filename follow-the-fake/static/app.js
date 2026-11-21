/* Follow the Fake – interfejs (czysty JavaScript, bez zależności) */
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const PALETTE = ['#00ff41', '#ff3b5c', '#29d9ff', '#ffd23f', '#b26bff', '#ff8a3d', '#5cffc8', '#ff5ad1', '#9dff3b', '#4d8cff', '#e6ff6b', '#ff6b6b'];
const color = (c, size) => (size === 1 ? '#3e7a50' : PALETTE[c % PALETTE.length]);
const CH_LABEL = { tekst: 'Tekst', wizual: 'Wizual', osoby: 'Osoby', narracja: 'Narracja', domeny: 'Domeny', infrastruktura: 'Infrastr.' };
const REL = { duplikat: ['Duplikat', 'chip red'], wariant: ['Wariant', 'chip blue'], 'powiązanie': ['Powiązanie', 'chip blue'], 'podobieństwo': ['Podobieństwo', 'chip'], brak: ['Brak', 'chip'] };
let S = null, G = null, pendingFiles = [];

function toast(msg, ms = 2600) { const t = $('#toast'); t.textContent = msg; t.style.display = 'block'; clearTimeout(t._h); t._h = setTimeout(() => (t.style.display = 'none'), ms); }
async function api(path, body) {
  const r = await fetch(path, body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const j = await r.json().catch(() => ({ error: 'Błędna odpowiedź serwera' }));
  if (!r.ok || j.error) throw new Error(j.error || r.status);
  return j;
}

/* ---------------------------------------------------------- nawigacja */
function go(v) {
  document.querySelectorAll('.view').forEach((x) => x.classList.toggle('on', x.id === 'v-' + v));
  document.querySelectorAll('nav.main a').forEach((a) => a.classList.toggle('on', a.dataset.v === v));
  if (v === 'graf') loadGraph();
  if (v === 'ocena') loadEval();
  if (v === 'metodyka') loadMd();
  if (v === 'zbior') loadSch();
  if (location.hash !== '#' + v) history.replaceState(null, '', '#' + v);
  window.scrollTo({ top: document.querySelector('main').offsetTop - 90, behavior: 'smooth' });
}
document.querySelectorAll('nav.main a').forEach((a) => (a.onclick = () => go(a.dataset.v)));

/* ---------------------------------------------------------- stan */
async function refresh() {
  S = await api('/api/state');
  const st = S.stats;
  $('#stMat').textContent = st.materials; $('#stCamp').textContent = st.campaigns; $('#stLinks').textContent = st.links;
  $('#stDup').textContent = st.duplicates; $('#stDom').textContent = st.domains;
  renderCampaigns(); renderItems(); renderCaps(); renderHero();
}

const ICON_LIST = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3.5" y="3.5" width="17" height="17" rx="1.5"/><path d="M7 8h2M11 8h6M7 12h2M11 12h6M7 16h2M11 16h6"/></svg>';
function renderHero() {
  const box = $('#heroCards');
  const camps = S.campaigns.filter((c) => c.size > 1).slice(0, 3);
  const card = (img, code, cat, meta, title, more, onclick) => `<div class="newsitem" onclick="${onclick}">
      <div class="img" style="${img}">${code ? `<span class="code">${code}</span>` : ''}</div>
      <div><div class="cat">${ICON_LIST}${cat}</div><div class="meta">${meta}</div><div class="title">${esc(title)}</div><span class="more">${more} →</span></div></div>`;
  if (camps.length) {
    box.innerHTML = camps.map((c) => {
      const m = c.members.find((id) => (S.items.find((x) => x.id === id) || {}).thumb);
      const img = m ? `background-image:url('/api/thumb/${m}')` : `background:${color(c.id, c.size)}`;
      const range = c.first_seen ? `${c.first_seen.split('-').reverse().join('.')}` : '';
      return card(img, c.code, 'Kampania', `${range}${range ? '<b>|</b>' : ''}${c.size} materiałów`, c.name, 'Zobacz kampanię', `openCampaign(${c.id})`);
    }).join('');
  } else {
    box.innerHTML = [
      card('background:linear-gradient(135deg,#00ff41,#003d10)', '', 'Start', 'Zbiór demonstracyjny<b>|</b>30 materiałów', 'Wczytaj przykładowy zbiór i zobacz, jak reklamy łączą się w kampanie', 'Wczytaj zbiór', "go('zbior'); loadDemo()"),
      card('background:linear-gradient(135deg,#062010,#000)', '', 'Analiza', 'Zrzut, link, wideo, tekst', 'Sprawdź pojedynczy materiał na tle całego zbioru', 'Analizuj materiał', "go('analiza')"),
      card('background:linear-gradient(135deg,#ff3b5c,#2a0008)', '', 'Metodyka', '6 kanałów cech', 'Jak liczymy podobieństwo i dlaczego łączymy materiały', 'Czytaj więcej', "go('metodyka')"),
    ].join('');
  }
}

function campById(id) { return S.campaigns.find((c) => c.id === id); }
function thumbHtml(id, cls = 'thumb', fallback) {
  const it = S && S.items.find((x) => x.id === id);
  if (it && it.thumb) return `<div class="${cls}" style="background-image:url('/api/thumb/${id}')"></div>`;
  const lab = fallback || (it && it.kinds.includes('url') && !it.kinds.includes('text') ? 'URL' : 'TXT');
  return `<div class="${cls}"><span>${lab}</span></div>`;
}

function renderCampaigns() {
  const box = $('#campList');
  if (!S.campaigns.length) { box.innerHTML = '<div class="empty" style="grid-column:1/-1">Brak materiałów. Wczytaj zbiór w zakładce „Zbiór danych”.</div>'; $('#famList').innerHTML = ''; return; }
  box.innerHTML = S.campaigns.map((c) => {
    const col = color(c.id, c.size);
    const chips = [
      ...c.persons.map(([p, n]) => `<span class="chip blue">👤 ${esc(p)} ·${n}</span>`),
      ...c.topics.map(([t]) => `<span class="chip">${esc(t)}</span>`),
      ...c.domains.slice(0, 3).map(([d]) => `<span class="chip amber">${esc(d)}</span>`),
      ...c.trackers.slice(0, 2).map(([t]) => `<span class="chip red">${esc(t)}</span>`),
    ].join(' ');
    const ev = c.evidence_types.slice(0, 4).map(([k, n]) => `${CH_LABEL[k] || k} ${n}`).join(' · ');
    return `<div class="camp ${c.size === 1 ? 'single' : ''}" style="border-top-color:${col}" onclick="openCampaign(${c.id})">
      <div class="head"><span class="code">${c.code}${c.size === 1 ? ' · pojedynczy' : ''}</span><span class="size">${c.size}</span></div>
      <div class="name">${esc(c.name)}</div>
      <div class="files" style="margin:0">${chips}</div>
      <div class="hint" style="margin-top:10px">spójność ${c.cohesion.toFixed(2)}${c.duplicates ? ` · duplikaty ${c.duplicates}` : ''}${c.first_seen ? ` · ${c.first_seen} → ${c.last_seen}` : ''}</div>
      ${ev ? `<div class="hint">przesłanki: ${ev}</div>` : ''}
      <div class="thumbs">${c.members.slice(0, 6).map((m) => thumbHtml(m)).join('')}</div>
    </div>`;
  }).join('');
  const fam = S.families || [];
  $('#famList').innerHTML = fam.length ? `<h3>Kampanie podobne do siebie</h3><table class="t"><tr><th>Kampania</th><th>Kampania</th><th>Śr. podob.</th><th>Najsilniejsze powiązanie – przesłanki</th></tr>
    ${fam.map((f) => { const a = campById(f.a), b = campById(f.b); return `<tr><td><b>${a.code}</b> ${esc(a.name)}</td><td><b>${b.code}</b> ${esc(b.name)}</td><td>${f.mean.toFixed(2)} (maks. ${f.max.toFixed(2)})</td><td>${f.evidence.map(esc).join('<br>')}</td></tr>`; }).join('')}</table>` : '';
}

function renderItems() {
  const box = $('#itemTable');
  if (!S.items.length) { box.innerHTML = '<div class="empty">Zbiór jest pusty.</div>'; return; }
  box.innerHTML = `<table class="t"><tr><th></th><th>#</th><th>Materiał</th><th>Kampania</th><th>Osoby / tematy</th><th>Domeny</th><th>Kompletność</th><th></th></tr>
  ${S.items.map((it) => { const c = campById(it.campaign); return `<tr>
    <td style="width:56px">${thumbHtml(it.id, 'thumb', it.kinds.includes('video') ? 'WIDEO' : 'TXT')}</td>
    <td>${it.id}</td>
    <td><a href="javascript:openItem(${it.id})"><b>${esc(it.title)}</b></a><div class="hint">${esc(it.date)} · ${esc(it.kinds.join(', '))}${it.label ? ' · etykieta: ' + esc(it.label) : ''}${it.source ? ' · ' + esc(it.source) : ''}</div></td>
    <td><span class="chip" style="border-left:4px solid ${color(c.id, c.size)}">${c.code}</span></td>
    <td>${it.persons.map((p) => `<span class="chip blue">${esc(p)}</span>`).join(' ')} ${it.topics.map((t) => `<span class="chip">${esc(t)}</span>`).join(' ')}</td>
    <td class="hint">${it.domains.map(esc).join('<br>')}</td>
    <td><div class="bar" title="${it.missing.length ? 'brak: ' + it.missing.join(', ') : 'komplet'}"><i style="width:${Math.round(it.completeness * 100)}%"></i></div><div class="hint">${it.missing.length ? 'brak: ' + esc(it.missing.join(', ')) : 'pełne dane'}</div></td>
    <td><button class="btn btn-sm btn-ghost" onclick="delItem(${it.id})" title="Usuń">✕</button></td></tr>`; }).join('')}</table>`;
}

function renderCaps() {
  const c = S.capabilities;
  const chip = (ok, t) => `<span class="chip ${ok ? 'green' : ''}">${ok ? '✓' : '–'} ${t}</span>`;
  $('#caps').innerHTML = [chip(c.ocr, 'OCR (Tesseract)'), chip(c.opencv, 'OpenCV: QR, wideo'), chip(!!c.faces.detector, 'twarze: ' + (c.faces.detector || 'brak modelu')),
    chip(!!c.faces.recognizer, 'rozpoznawanie: ' + (c.faces.reference_people.length ? c.faces.reference_people.length + ' osób' : 'brak bazy')),
    chip(c.llm, 'model wizyjny (opcjonalny)'), chip(c.meta_token, 'Meta Ad Library')].join(' ');
}

/* ---------------------------------------------------------- analiza */
const drop = $('#drop'), inFiles = $('#inFiles');
drop.onclick = () => inFiles.click();
inFiles.onchange = () => addFiles(inFiles.files);
['dragover', 'dragenter'].forEach((e) => drop.addEventListener(e, (ev) => { ev.preventDefault(); drop.classList.add('over'); }));
['dragleave', 'drop'].forEach((e) => drop.addEventListener(e, (ev) => { ev.preventDefault(); drop.classList.remove('over'); }));
drop.addEventListener('drop', (ev) => addFiles(ev.dataTransfer.files));
document.addEventListener('paste', (ev) => { if (document.querySelector('#v-analiza.on') && ev.clipboardData.files.length) addFiles(ev.clipboardData.files); });

function readB64(f) { return new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(r.result); r.onerror = rej; r.readAsDataURL(f); }); }
async function addFiles(list) {
  for (const f of list) {
    if (f.size > 250 * 1024 * 1024) { toast(`${f.name}: plik za duży`); continue; }
    pendingFiles.push({ name: f.name, mime: f.type, b64: await readB64(f), size: f.size });
  }
  renderFiles();
}
function renderFiles() {
  $('#fileList').innerHTML = pendingFiles.map((f, i) => `<span class="chip blue">${esc(f.name)} · ${(f.size / 1024).toFixed(0)} KB <x onclick="pendingFiles.splice(${i},1);renderFiles()">✕</x></span>`).join('');
}

async function analyze() {
  const body = { url: $('#inUrl').value.trim(), text: $('#inText').value.trim(), files: pendingFiles, network: $('#optNet').checked, save: $('#optSave').checked };
  if (!body.url && !body.text && !body.files.length) return toast('Podaj adres, tekst albo plik.');
  const b = $('#btnAnalyze'); b.disabled = true; b.innerHTML = '<span class="spinner"></span> Analizuję…';
  $('#result').innerHTML = `<div class="empty"><span class="spinner dark"></span><div style="margin-top:12px">Wyodrębniam cechy${body.network ? ', sprawdzam domeny i przekierowania' : ''}, porównuję ze zbiorem…</div></div>`;
  try {
    const r = await api('/api/analyze', body);
    renderResult(r);
    if (body.save) { pendingFiles = []; renderFiles(); $('#inUrl').value = ''; $('#inText').value = ''; await refresh(); }
  } catch (e) { $('#result').innerHTML = `<div class="empty">Błąd: ${esc(e.message)}</div>`; }
  b.disabled = false; b.textContent = 'Analizuj';
}

function channelsHtml(ch) {
  return `<div class="channels">${Object.keys(CH_LABEL).map((k) => { const v = ch[k]; return `<div class="c">${CH_LABEL[k]} ${v == null ? '–' : v.toFixed(2)}<div class="bar"><i style="width:${v == null ? 0 : Math.round(v * 100)}%; background:${v == null ? 'transparent' : ''}"></i></div></div>`; }).join('')}</div>`;
}
function evidenceHtml(ev, hard) {
  return `<ul class="ev">${(ev || []).map((x) => `<li class="${x.weight >= 0.85 && x.channel !== 'osoby' && x.channel !== 'narracja' ? 'hard' : ''}">${esc(x.text)}</li>`).join('')}${hard && hard.length ? `<li class="hard"><b>Twardy dowód:</b> ${esc(hard.join(', '))}</li>` : ''}</ul>`;
}

function renderResult(r) {
  const m = r.material;
  const cls = r.decision === 'nowy wzorzec' ? 'new' : r.decision === 'duplikat' ? 'dup' : 'known';
  const code = r.final_campaign_code || r.campaign_code;
  const head = r.decision === 'nowy wzorzec' ? 'Nowy wzorzec – nie pasuje do znanych kampanii' : r.decision === 'duplikat' ? `Duplikat materiału #${r.duplicate_of}` : 'Należy do znanej kampanii';
  $('#result').innerHTML = `
    <div class="verdict ${cls}">
      ${r.thumb ? `<div class="thumb" style="width:72px;height:72px;background-image:url('${r.thumb}')"></div>` : ''}
      <div style="flex:1"><div class="big">${head}</div><div style="opacity:.85; margin-top:4px">${esc(r.reason)}</div></div>
      ${code ? `<span class="code">${code}</span>` : ''}
    </div>
    <div class="card" style="border-top:0">
      <div class="row" style="justify-content:space-between"><b>Pewność decyzji</b><b>${Math.round((r.confidence || 0) * 100)}%</b></div>
      <div class="bar" style="margin:6px 0 16px"><i style="width:${Math.round((r.confidence || 0) * 100)}%"></i></div>
      ${r.campaign_name ? `<div class="muted" style="margin-bottom:10px">Kampania: <b>${esc(r.campaign_name)}</b></div>` : ''}
      <h3>Najbardziej podobne incydenty</h3>
      ${r.similar.length ? r.similar.map((s) => `<div class="sim">
        <a href="javascript:openItem(${s.id})">${thumbHtml(s.id)}</a>
        <div><a href="javascript:openItem(${s.id})"><b>#${s.id} ${esc(s.title)}</b></a> <span class="${(REL[s.relation] || REL.brak)[1]}">${(REL[s.relation] || REL.brak)[0]}</span>
          ${evidenceHtml(s.evidence, s.hard)}${channelsHtml(s.channels)}</div>
        <div class="score">${s.score.toFixed(2)}<small>wynik</small></div></div>`).join('') : '<div class="muted">Brak podobnych materiałów w zbiorze.</div>'}
      ${r.campaign_scores && r.campaign_scores.length ? `<h4>Dopasowanie do kampanii (średnia / maks.)</h4>${r.campaign_scores.map((c) => { const cc = campById(c.campaign); return `<div class="row" style="font-size:14px"><span class="chip" style="min-width:70px">${cc ? cc.code : 'K-' + (c.campaign + 1)}</span> ${c.mean.toFixed(2)} / ${c.max.toFixed(2)} <span class="hint">${cc ? esc(cc.name) : ''}</span></div>`; }).join('')}` : ''}
    </div>`;
  $('#features').innerHTML = featuresHtml(m);
}

function featuresHtml(m) {
  const I = m.infra, E = m.entities, N = m.narrative, Q = m.quality;
  const list = (a, c = 'chip') => (a && a.length ? a.map((x) => `<span class="${c}">${esc(x)}</span>`).join(' ') : '<span class="hint">—</span>');
  const inv = (m.investigations || []).map((v) => `<div style="margin-bottom:12px"><b>${esc(v.input_url)}</b> <span class="chip ${v.status === 'ok' ? 'green' : 'red'}">${esc(v.status)}${v.http_status ? ' ' + v.http_status : ''}</span>
      ${(v.redirect_chain || []).length > 1 ? `<div class="hint">przekierowania: ${v.redirect_chain.map((x) => esc(x.url.replace(/^https?:\/\//, '').slice(0, 60)) + (x.client_side ? ' (JS)' : '')).join(' → ')}</div>` : ''}
      ${v.page_title ? `<div class="hint">tytuł strony: ${esc(v.page_title)}</div>` : ''}
      ${(v.errors || []).length ? `<div class="hint">błędy: ${esc(v.errors.join('; '))}</div>` : ''}</div>`).join('');
  return `<div class="card"><h3>Wyodrębnione cechy</h3>
    <div class="grid2" style="gap:30px">
      <div>
        <h4>Narracja</h4><dl class="kv">
          <dt>Słowa kluczowe</dt><dd>${list(N.keywords)}</dd><dt>Tematy</dt><dd>${list(N.topics, 'chip blue')}</dd>
          <dt>Chwyty manipulacyjne</dt><dd>${list(N.manipulation, 'chip amber')}</dd><dt>Kwoty</dt><dd>${list(N.amounts)}</dd>
          ${N.hints && N.hints.length ? `<dt>Opis modelu</dt><dd>${N.hints.map(esc).join('<br>')}</dd>` : ''}</dl>
        <h4>Byty</h4><dl class="kv">
          <dt>Wizerunki osób</dt><dd>${list(E.persons, 'chip blue')}</dd><dt>Marki / logotypy</dt><dd>${list(E.brands)}</dd>
          <dt>Podszywanie się</dt><dd>${list(E.impersonation, 'chip red')}</dd>
          <dt>Telefony / e-maile</dt><dd>${list([...E.phones, ...E.emails])}</dd><dt>Portfele krypto</dt><dd>${list(E.wallets, 'chip red')}</dd>
          <dt>Twarze</dt><dd>${m.visual.faces.length ? m.visual.faces.length + ' (hashe wycinków)' : '—'}</dd>
          <dt>Kreacje / klatki</dt><dd>${m.visual.images.length} obraz(y), ${m.visual.frames.length} klatek wideo</dd></dl>
      </div>
      <div>
        <h4>Infrastruktura</h4><dl class="kv">
          <dt>Adresy URL</dt><dd>${list(m.urls.slice(0, 6))}</dd><dt>Domeny</dt><dd>${list(I.domains, 'chip amber')}</dd>
          <dt>Łańcuch domen</dt><dd>${I.redirect_domains.length ? I.redirect_domains.map(esc).join(' → ') : '—'}</dd>
          <dt>Trackery</dt><dd>${list(I.trackers, 'chip red')}</dd><dt>IP / sieć</dt><dd>${list([...I.ips, ...I.ip_nets])}</dd>
          <dt>Serwery DNS</dt><dd>${list(I.nameservers)}</dd><dt>Rejestrator</dt><dd>${list(I.registrars)}</dd>
          <dt>Data rejestracji</dt><dd>${I.created.length ? esc(I.created.join(', ')) + (I.min_age_days != null ? ` (domena ma ${I.min_age_days} dni)` : '') : '—'}</dd>
          <dt>Certyfikat TLS</dt><dd>${list(I.tls_issuers)} ${I.cert_names.length ? `<span class="hint">${I.cert_names.length} nazw w certyfikatach</span>` : ''}</dd>
          <dt>Formularze wrażliwe</dt><dd>${list(I.sensitive_inputs, 'chip red')}</dd><dt>Szkielet DOM</dt><dd>${I.dom_shingles.length ? I.dom_shingles.length + ' fragmentów' : '—'}</dd></dl>
        ${inv ? `<h4>Śledztwo URL</h4>${inv}` : ''}
        <h4>Kompletność danych</h4><div class="files">${Object.entries(Q.channels).map(([k, ok]) => `<span class="chip ${ok ? 'green' : ''}">${ok ? '✓' : '✕'} ${k}</span>`).join(' ')}</div>
        <div class="hint" style="margin-top:6px">Brakujące kanały nie obniżają podobieństwa – są pomijane przy liczeniu wyniku.</div>
        ${m.log && m.log.length ? `<h4>Dziennik</h4><div class="hint">${m.log.map(esc).join('<br>')}</div>` : ''}
      </div>
    </div></div>`;
}

/* ---------------------------------------------------------- szuflada */
function openDrawer(html) { $('#drawer').innerHTML = html; $('#drawer').classList.add('on'); $('#shade').classList.add('on'); $('#drawer').scrollTop = 0; }
function closeDrawer() { $('#drawer').classList.remove('on'); $('#shade').classList.remove('on'); }
document.addEventListener('keydown', (e) => e.key === 'Escape' && closeDrawer());

async function openItem(id) {
  const it = await api('/api/item/' + id);
  const c = campById(it.campaign);
  openDrawer(`<div class="dh"><div><div style="opacity:.8; font-size:13px">MATERIAŁ #${id} · ${c ? c.code : ''}</div><div style="font-size:20px; font-weight:900; line-height:1.25">${esc(it.title)}</div></div><button class="close" onclick="closeDrawer()">×</button></div>
    <div class="db">
      ${it.thumb ? `<img src="${it.thumb}" style="max-width:100%; border:1px solid var(--line); margin-bottom:14px">` : ''}
      ${it.text ? `<h4>Tekst (wpisany + OCR + strona)</h4><div style="white-space:pre-wrap; font-size:13.5px; background:#f6f8fb; padding:12px; max-height:220px; overflow:auto">${esc(it.text.slice(0, 3000))}</div>` : ''}
      <h4>Powiązane materiały</h4>
      ${it.neighbors.length ? it.neighbors.map((s) => `<div class="sim"><a href="javascript:openItem(${s.id})">${thumbHtml(s.id)}</a><div><a href="javascript:openItem(${s.id})"><b>#${s.id} ${esc(s.title)}</b></a> <span class="${(REL[s.relation] || REL.brak)[1]}">${(REL[s.relation] || REL.brak)[0]}</span>${evidenceHtml(s.evidence, s.hard)}${channelsHtml(s.channels)}</div><div class="score">${s.score.toFixed(2)}</div></div>`).join('') : '<div class="muted">Brak powiązań powyżej progu.</div>'}
      ${featuresHtml(it)}
    </div>`);
}

function openCampaign(cid) {
  const c = campById(cid);
  const items = S.items.filter((i) => i.campaign === cid);
  const row = (k, arr, cls = 'chip') => (arr.length ? `<dt>${k}</dt><dd>${arr.map(([v, n]) => `<span class="${cls}">${esc(v)} ·${n}</span>`).join(' ')}</dd>` : '');
  openDrawer(`<div class="dh"><div><div style="opacity:.8; font-size:13px">${c.code} · ${c.size} materiał(ów) · spójność ${c.cohesion.toFixed(2)}</div><div style="font-size:20px; font-weight:900; line-height:1.25">${esc(c.name)}</div></div><button class="close" onclick="closeDrawer()">×</button></div>
    <div class="db"><dl class="kv">${row('Wizerunki', c.persons, 'chip blue')}${row('Tematy', c.topics)}${row('Chwyty', c.manipulation, 'chip amber')}${row('Marki', c.brands)}${row('Domeny', c.domains, 'chip amber')}${row('Trackery', c.trackers, 'chip red')}${row('Słowa kluczowe', c.keywords)}${row('Przesłanki (kanały)', c.evidence_types.map(([k, n]) => [CH_LABEL[k] || k, n]))}
      ${c.first_seen ? `<dt>Aktywność</dt><dd>${c.first_seen} → ${c.last_seen}</dd>` : ''}${c.labels.length ? `<dt>Etykiety w zbiorze</dt><dd>${c.labels.map(([l, n]) => `${esc(l)} ×${n}`).join(', ')}</dd>` : ''}</dl>
      <h4>Materiały</h4>${items.map((i) => `<div class="sim" style="grid-template-columns:64px 1fr"><a href="javascript:openItem(${i.id})">${thumbHtml(i.id)}</a><div><a href="javascript:openItem(${i.id})"><b>#${i.id} ${esc(i.title)}</b></a><div class="hint">${esc(i.date)} · ${esc(i.domains.join(', '))}</div></div></div>`).join('')}
    </div>`);
}

/* ---------------------------------------------------------- zbiór */
const dropImp = $('#dropImp'), inImp = $('#inImp');
dropImp.onclick = () => inImp.click();
inImp.onchange = () => inImp.files[0] && importFile(inImp.files[0]);
['dragover', 'dragenter'].forEach((e) => dropImp.addEventListener(e, (ev) => { ev.preventDefault(); dropImp.classList.add('over'); }));
['dragleave', 'drop'].forEach((e) => dropImp.addEventListener(e, (ev) => { ev.preventDefault(); dropImp.classList.remove('over'); }));
dropImp.addEventListener('drop', (ev) => ev.dataTransfer.files[0] && importFile(ev.dataTransfer.files[0]));

async function importFile(f) {
  const net = $('#impNet').checked;
  $('#impStatus').innerHTML = `<span class="spinner dark"></span> Wczytywanie ${esc(f.name)}…`;
  try {
    const body = f.name.toLowerCase().endsWith('.zip') ? { zip_b64: await readB64(f), network: net } : { raw: await f.text(), name: f.name, network: net };
    pollJob(await api('/api/import', body));
  } catch (e) { $('#impStatus').textContent = 'Błąd: ' + e.message; }
}
async function loadDemo() { $('#impStatus').innerHTML = '<span class="spinner dark"></span> Wczytywanie zbioru demonstracyjnego…'; pollJob(await api('/api/demo', {})); }
async function pollJob(job) {
  const tick = async () => {
    const j = await api('/api/job/' + job.id);
    $('#impStatus').innerHTML = j.finished ? `Gotowe: ${j.done} materiałów${j.errors ? `, błędy: ${j.errors.length}` : ''}.` : `<span class="spinner dark"></span> Przetwarzanie ${j.done}/${j.total}…`;
    if (j.finished) { await refresh(); toast('Zbiór wczytany i pogrupowany'); } else setTimeout(tick, 900);
  };
  tick();
}
async function clearAll() { if (!confirm('Usunąć wszystkie materiały ze zbioru?')) return; await api('/api/clear', {}); await refresh(); toast('Zbiór wyczyszczony'); }
async function delItem(id) { if (!confirm('Usunąć materiał #' + id + '?')) return; await api('/api/delete', { id }); await refresh(); }

async function loadSch() {
  const s = await api('/api/scheduler');
  const c = s.config;
  $('#schKw').value = (c.keywords || []).join('\n'); $('#schOn').checked = !!c.enabled; $('#schInt').value = c.interval_min; $('#schDom').checked = !!c.recheck_domains;
  $('#schTok').innerHTML = c.token_present ? '<span class="chip green">✓ token Meta Ad Library ustawiony</span>' : '<span class="chip amber">brak META_ACCESS_TOKEN – skan biblioteki reklam wyłączony, działa ponowne sprawdzanie domen</span>';
  $('#schLog').innerHTML = (s.log || []).map((l) => `${esc(l.t.replace('T', ' '))} – ${esc(l.msg)}`).join('<br>') || 'Brak przebiegów.';
}
async function saveSch() {
  await api('/api/scheduler', { keywords: $('#schKw').value.split('\n').map((x) => x.trim()).filter(Boolean), enabled: $('#schOn').checked, interval_min: +$('#schInt').value || 60, recheck_domains: $('#schDom').checked });
  toast('Harmonogram zapisany'); loadSch();
}
async function runSch() { await api('/api/scheduler/run', {}); toast('Przebieg uruchomiony w tle'); setTimeout(async () => { await loadSch(); await refresh(); }, 6000); }

/* ---------------------------------------------------------- ocena */
async function loadEval() {
  const r = await api('/api/evaluate');
  if (!r.available) { $('#evalBox').innerHTML = `<div class="empty">${esc(r.reason)}<br><br><button class="btn btn-ghost btn-sm" onclick="go('zbior')">Wczytaj zbiór z etykietami</button></div>`; return; }
  const f2 = (x) => (typeof x === 'number' ? x.toFixed(2) : x);
  const M = (n, l, d) => `<div class="metric"><div class="n">${n == null ? '—' : f2(n)}</div><div class="l">${l}</div>${d ? `<div class="hint">${d}</div>` : ''}</div>`;
  $('#evalBox').innerHTML = `<div class="grid3">
    ${M(r.pair_f1, 'F1 par', `precyzja ${r.pair_precision} · czułość ${r.pair_recall}`)}${M(r.bcubed_f1, 'B-cubed F1', `precyzja ${r.bcubed_precision} · czułość ${r.bcubed_recall}`)}
    ${M(r.ari, 'Adjusted Rand Index', `NMI ${r.nmi} · jednorodność ${r.homogeneity} · kompletność ${r.completeness}`)}
    ${M(r.loo_assign_acc, 'Przypisanie nowych wariantów', `${r.loo_assign_n} prób (leave-one-out)`)}${M(r.loo_new_acc, 'Rozpoznanie osobnych kampanii', `${r.loo_new_n} prób – materiał nie powinien być połączony`)}
    ${M(`${r.found_campaigns} / ${r.true_campaigns}`, 'Kampanie: wykryte / prawdziwe', `${r.n} materiałów z etykietą`)}</div>
    ${r.mistakes.length ? `<h3 style="margin-top:28px">Błędy do przejrzenia</h3><table class="t"><tr><th>Materiał</th><th>Etykieta</th><th>Problem</th></tr>${r.mistakes.map((m) => `<tr><td><a href="javascript:openItem(${m.id})">#${m.id}</a></td><td>${esc(m.label)}</td><td>${esc(m.error)}</td></tr>`).join('')}</table>` : '<p class="muted" style="margin-top:20px">Brak błędów na tym zbiorze.</p>'}`;
}

/* ---------------------------------------------------------- metodyka (mini-markdown) */
function md(src) {
  const lines = src.replace(/\r/g, '').split('\n'); let out = '', inList = false, inCode = false, table = [];
  const inline = (s) => esc(s).replace(/`([^`]+)`/g, '<code>$1</code>').replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>').replace(/(^|[\s(])\*([^*\s][^*]*)\*/g, '$1<i>$2</i>').replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
  const flushT = () => {
    if (!table.length) return;
    const rows = table.filter((r) => !/^\|[\s:|-]+\|?\s*$/.test(r));
    out += '<table>' + rows.map((r, i) => '<tr>' + r.trim().replace(/^\||\|$/g, '').split('|').map((c) => (i ? '<td>' : '<th>') + inline(c.trim()) + (i ? '</td>' : '</th>')).join('') + '</tr>').join('') + '</table>';
    table = [];
  };
  for (const l of lines) {
    if (l.startsWith('```')) { if (inCode) { out += '</pre>'; inCode = false; } else { flushT(); out += '<pre>'; inCode = true; } continue; }
    if (inCode) { out += esc(l) + '\n'; continue; }
    if (l.startsWith('|')) { table.push(l); continue; } else flushT();
    if (/^\s*[-*] /.test(l)) { if (!inList) { out += '<ul>'; inList = true; } out += '<li>' + inline(l.replace(/^\s*[-*] /, '')) + '</li>'; continue; }
    if (inList) { out += '</ul>'; inList = false; }
    const h = l.match(/^(#{1,4}) (.*)/);
    if (h) out += `<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`;
    else if (l.startsWith('> ')) out += '<blockquote>' + inline(l.slice(2)) + '</blockquote>';
    else if (l.trim()) out += '<p>' + inline(l) + '</p>';
  }
  flushT(); if (inList) out += '</ul>';
  return out;
}
async function loadMd() { if ($('#mdBox').dataset.ok) return; const r = await api('/api/methodology'); $('#mdBox').innerHTML = md(r.md); $('#mdBox').dataset.ok = 1; }

/* ---------------------------------------------------------- graf (układ siłowy, SVG) */
async function loadGraph() { G = await api('/api/graph'); layoutGraph(); drawGraph(); }
function layoutGraph() {
  const n = G.nodes.length, W = 1200, H = 800, sizeOf = {};
  G.campaigns.forEach((c) => (sizeOf[c.id] = c.size));
  const camps = [...new Set(G.nodes.map((x) => x.c))];
  const centers = {};
  camps.forEach((c, i) => { const a = (2 * Math.PI * i) / camps.length; const r = sizeOf[c] === 1 ? 360 : 230; centers[c] = [W / 2 + r * Math.cos(a), H / 2 + r * Math.sin(a)]; });
  G.nodes.forEach((v) => { const [cx, cy] = centers[v.c]; v.x = cx + (Math.random() - 0.5) * 60; v.y = cy + (Math.random() - 0.5) * 60; v.vx = v.vy = 0; });
  const byId = Object.fromEntries(G.nodes.map((v) => [v.id, v]));
  const E = G.edges.filter((e) => e.s >= S.config.link_t || e.h);
  for (let it = 0; it < 260; it++) {
    const k = 1 - it / 260;
    for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) {
      const a = G.nodes[i], b = G.nodes[j]; let dx = a.x - b.x, dy = a.y - b.y; const d2 = dx * dx + dy * dy + 0.01; if (d2 > 90000) continue;
      const f = 900 / d2; dx *= f; dy *= f; a.vx += dx; a.vy += dy; b.vx -= dx; b.vy -= dy;
    }
    for (const e of E) { const a = byId[e.a], b = byId[e.b]; const dx = b.x - a.x, dy = b.y - a.y; const d = Math.sqrt(dx * dx + dy * dy) || 1; const f = (d - 70) * 0.02 * e.s; a.vx += (dx / d) * f; a.vy += (dy / d) * f; b.vx -= (dx / d) * f; b.vy -= (dy / d) * f; }
    for (const v of G.nodes) { const [cx, cy] = centers[v.c]; v.vx += (cx - v.x) * 0.012; v.vy += (cy - v.y) * 0.012; v.x += Math.max(-20, Math.min(20, v.vx)) * k; v.y += Math.max(-20, Math.min(20, v.vy)) * k; v.vx *= 0.5; v.vy *= 0.5; }
  }
  G.byId = byId; G.sizeOf = sizeOf;
  const xs = G.nodes.map((v) => v.x), ys = G.nodes.map((v) => v.y);
  G.view = n ? { x: Math.min(...xs) - 60, y: Math.min(...ys) - 60, w: Math.max(...xs) - Math.min(...xs) + 120, h: Math.max(...ys) - Math.min(...ys) + 120 } : { x: 0, y: 0, w: W, h: H };
}
function drawGraph() {
  if (!G) return;
  const svg = $('#gsvg'), weak = $('#gWeak').checked, labels = $('#gLabels').checked;
  if (!G.nodes.length) { svg.innerHTML = ''; $('#gLegend').innerHTML = '<span class="hint">Brak materiałów.</span>'; return; }
  const E = G.edges.filter((e) => weak || e.s >= S.config.link_t || e.h);
  const v = G.view; svg.setAttribute('viewBox', `${v.x} ${v.y} ${v.w} ${v.h}`);
  let h = '';
  E.forEach((e, i) => { const a = G.byId[e.a], b = G.byId[e.b]; const same = a.c === b.c; h += `<line class="gedge" data-i="${G.edges.indexOf(e)}" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="${e.h ? '#ff3b5c' : same ? '#1fae4c' : '#ffd23f'}" stroke-width="${(1 + e.s * 4) * Math.max(1, v.w / 900)}" stroke-opacity="${e.s >= S.config.link_t ? 0.75 : 0.35}" ${same ? '' : 'stroke-dasharray="6 5"'}/>`; });
  const R = Math.max(14, v.w / 48), fs = Math.max(11, v.w / 95);
  G.nodes.forEach((n) => { const col = color(n.c, G.sizeOf[n.c]); h += `<g class="gnode" data-id="${n.id}" transform="translate(${n.x},${n.y})"><circle r="${R}" fill="${col}" stroke="#000" stroke-width="${R / 6}" style="filter:drop-shadow(0 0 6px ${col})"/>${n.img ? `<clipPath id="cp${n.id}"><circle r="${R * 0.78}"/></clipPath><image href="/api/thumb/${n.id}" x="${-R * 0.78}" y="${-R * 0.78}" width="${R * 1.56}" height="${R * 1.56}" clip-path="url(#cp${n.id})" preserveAspectRatio="xMidYMid slice"/>` : ''}${labels ? `<text y="${R + fs * 1.1}" text-anchor="middle" style="font-size:${fs}px; font-weight:700">#${n.id}</text>` : ''}<title>#${n.id} ${esc(n.t)}</title></g>`; });
  svg.innerHTML = h;
  svg.querySelectorAll('.gnode').forEach((g) => (g.onclick = (ev) => { ev.stopPropagation(); openItem(+g.dataset.id); }));
  svg.querySelectorAll('.gedge').forEach((l) => (l.onclick = (ev) => { ev.stopPropagation(); showEdge(G.edges[+l.dataset.i]); }));
  $('#gLegend').innerHTML = G.campaigns.filter((c) => c.size > 1).map((c) => `<span><i style="background:${color(c.id, c.size)}"></i>${c.code}</span>`).join('') + '<span><i style="background:#3e7a50"></i>pojedyncze</span><span><i style="background:#ff3b5c; height:3px"></i>twardy dowód</span><span><i style="background:#ffd23f; height:3px"></i>między kampaniami</span>';
}
function showEdge(e) {
  const p = $('#gPanel'); const a = G.byId[e.a], b = G.byId[e.b];
  p.style.display = 'block';
  p.innerHTML = `<div class="row" style="justify-content:space-between"><b>Powiązanie #${e.a} ↔ #${e.b}</b><button class="btn btn-sm btn-ghost" onclick="this.parentNode.parentNode.style.display='none'">✕</button></div>
    <div class="score" style="text-align:left; margin:8px 0">${e.s.toFixed(2)} <span class="${(REL[e.r] || REL.brak)[1]}" style="font-size:13px">${(REL[e.r] || REL.brak)[0]}</span></div>
    <div class="hint"><a href="javascript:openItem(${e.a})">#${e.a} ${esc(a.t)}</a><br><a href="javascript:openItem(${e.b})">#${e.b} ${esc(b.t)}</a></div>
    <h4>Przesłanki</h4><ul class="ev">${e.ev.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>${channelsHtml(e.ch)}`;
}
(function panZoom() {
  const svg = $('#gsvg'); let drag = null;
  svg.addEventListener('wheel', (ev) => { if (!G) return; ev.preventDefault(); const f = ev.deltaY > 0 ? 1.12 : 0.89; const r = svg.getBoundingClientRect(); const mx = G.view.x + ((ev.clientX - r.left) / r.width) * G.view.w, my = G.view.y + ((ev.clientY - r.top) / r.height) * G.view.h; G.view = { x: mx - (mx - G.view.x) * f, y: my - (my - G.view.y) * f, w: G.view.w * f, h: G.view.h * f }; svg.setAttribute('viewBox', `${G.view.x} ${G.view.y} ${G.view.w} ${G.view.h}`); }, { passive: false });
  svg.addEventListener('mousedown', (ev) => (drag = { x: ev.clientX, y: ev.clientY, v: { ...G.view } }));
  window.addEventListener('mouseup', () => (drag = null));
  window.addEventListener('mousemove', (ev) => { if (!drag || !G) return; const r = svg.getBoundingClientRect(); G.view.x = drag.v.x - ((ev.clientX - drag.x) / r.width) * drag.v.w; G.view.y = drag.v.y - ((ev.clientY - drag.y) / r.height) * drag.v.h; svg.setAttribute('viewBox', `${G.view.x} ${G.view.y} ${G.view.w} ${G.view.h}`); });
})();

/* ---------------------------------------------------------- start */
refresh().then(() => { const v = location.hash.slice(1); if (v && document.getElementById('v-' + v)) go(v); }).catch((e) => toast('Błąd połączenia z serwerem: ' + e.message, 6000));

/* ---------------------------------------------------------- deszcz znaków (Matrix) */
(function rain() {
  const cv = document.getElementById('rain');
  if (!cv || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const ctx = cv.getContext('2d');
  const CH = 'ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ0123456789FAKE$#<>/=';
  const FS = 16;
  let cols = [], w = 0, h = 0, last = 0;
  const resize = () => {
    const r = cv.getBoundingClientRect();
    w = cv.width = Math.max(1, Math.floor(r.width));
    h = cv.height = Math.max(1, Math.floor(r.height));
    cols = Array.from({ length: Math.ceil(w / FS) }, () => Math.random() * -50);
  };
  resize();
  window.addEventListener('resize', resize);
  const draw = (t) => {
    requestAnimationFrame(draw);
    if (t - last < 55 || document.hidden || cv.getBoundingClientRect().bottom < 0) return;
    last = t;
    ctx.fillStyle = 'rgba(0,0,0,0.09)';
    ctx.fillRect(0, 0, w, h);
    ctx.font = FS + 'px monospace';
    for (let i = 0; i < cols.length; i++) {
      const y = cols[i] * FS;
      const c = CH[(Math.random() * CH.length) | 0];
      ctx.fillStyle = Math.random() < 0.06 ? '#d6ffe0' : '#00ff41';
      ctx.fillText(c, i * FS, y);
      if (y > h && Math.random() > 0.975) cols[i] = 0;
      cols[i] += 1;
    }
  };
  requestAnimationFrame(draw);
})();
