/* VaidyaSaathi frontend – plain JavaScript, no build step.
   Sections: helpers · API · cart · header & search · home · doctor page · slot picker ·
   lab tests · lab booking · my bookings · auth · profile · doctor portal · admin · AI assistant · router */

/* ================= Helpers ================= */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const view = h => { $('#app').innerHTML = h };
const IST = 'Asia/Kolkata';
const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const fmtT = iso => new Date(iso).toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit', hour12: true, timeZone: IST });
const fmtD = iso => new Date(iso).toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short', timeZone: IST });
const istHour = iso => +new Date(iso).toLocaleString('en-GB', { hour: '2-digit', hour12: false, timeZone: IST }) % 24;
const istDate = d => d.toLocaleDateString('en-CA', { timeZone: IST });   // YYYY-MM-DD
const rs = n => '₹' + Number(n).toLocaleString('en-IN', { maximumFractionDigits: 0 });
const pctOff = t => Math.round((1 - t.price / t.mrp) * 100);
const plural = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`;
const store = {
  get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d } catch { return d } },
  set(k, v) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, JSON.stringify(v)) } catch { } },
};

function toast(m, err) {
  const t = $('#toast'); t.textContent = m; t.className = (err ? 'err ' : '') + 'show';
  clearTimeout(toast.h); toast.h = setTimeout(() => t.classList.remove('show'), 3800);
}
function modal(h, cls = '') {
  const m = document.createElement('div'); m.className = 'modal';
  m.innerHTML = `<div class="${cls}" role="dialog" aria-modal="true"><button class="x" aria-label="Close">×</button>${h}</div>`;
  const close = () => { m.remove(); document.removeEventListener('keydown', onKey) };
  const onKey = e => { if (e.key === 'Escape') close() };
  m.onclick = e => { if (e.target === m) close() };
  $('.x', m).onclick = close; document.addEventListener('keydown', onKey);
  document.body.append(m); m.close = close;
  setTimeout(() => $('input,textarea,button:not(.x)', m)?.focus(), 30);
  return m;
}
const photo = d => `<div class="ph">${esc((d.full_name || d.name || 'D').replace(/^Dr\.?\s*/i, '')[0] || 'D')}<img src="${esc(d.profile_photo_url || d.photo || '')}" alt="" onerror="this.remove()" loading="lazy"></div>`;
const skel = (n, cls) => `<div class="sk ${cls}"></div>`.repeat(n);

/* ================= API ================= */
let tok = store.get('vs_tok', null);
const setTok = t => { tok = t; store.set('vs_tok', t) };
const me = () => { try { const p = JSON.parse(atob(tok.access_token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'))); return { id: +p.sub, role: p.role } } catch { return null } };
async function refresh() {
  try {
    const r = await fetch('/api/auth/auth/refresh', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh_token: tok.refresh_token }) });
    if (!r.ok) return false; setTok(await r.json()); return true;
  } catch { return false }
}
async function api(svc, path, { method = 'GET', body, retry = true, auth = true } = {}) {
  const h = {}; if (body) h['Content-Type'] = 'application/json'; if (tok && auth) h.Authorization = 'Bearer ' + tok.access_token;
  const r = await fetch(`/api/${svc}${path}`, { method, headers: h, body: body ? JSON.stringify(body) : undefined });
  if (r.status === 401 && tok && retry && svc !== 'auth') {
    if (await refresh()) return api(svc, path, { method, body, auth, retry: false });
    setTok(null); nav(); toast('Your session ended. Please sign in again.', 1); location.hash = '#/login';
  }
  if (r.status === 204) return null;
  const d = await r.json().catch(() => null);
  if (!r.ok) {
    const m = Array.isArray(d?.detail) ? d.detail.map(x => x.msg.replace(/^Value error, /, '')).join('; ') : d?.detail;
    throw Object.assign(new Error(m || 'Request failed (' + r.status + ')'), { status: r.status });
  }
  return d;
}
function need(role) {
  const u = me();
  if (!u || u.role !== role) { sessionStorage.vs_next = location.hash; toast('Sign in as a ' + role + ' to continue', 1); location.hash = '#/login'; return false }
  return true;
}
const cache = {};
const cached = (k, fn, ms = 60000) => {
  const c = cache[k]; if (c && Date.now() - c.t < ms) return c.p;
  const p = fn().catch(e => { delete cache[k]; throw e }); cache[k] = { t: Date.now(), p }; return p;
};
const getDoctors = () => cached('docs', () => api('doctor', '/doctors/', { auth: false }));
const getSpecs = () => cached('specs', () => api('doctor', '/specializations/', { auth: false }));
const getTests = () => cached('tests', () => api('lab', '/lab/tests', { auth: false }), 300000);

/* ================= Cart (lab tests) ================= */
const cart = {
  items: store.get('vs_cart', []),            // [{id, name, price, mrp, fasting_hours, is_package}]
  has(id) { return this.items.some(x => x.id === id) },
  add(t) {
    if (this.has(t.id)) return;
    this.items.push({ id: t.id, name: t.name, price: +t.price, mrp: +t.mrp, fasting_hours: t.fasting_hours, is_package: t.is_package });
    this.save(); toast(`${t.name} added to cart`);
  },
  remove(id) { this.items = this.items.filter(x => x.id !== id); this.save() },
  clear() { this.items = []; this.save() },
  save() { store.set('vs_cart', this.items); cartBar(); nav(); $$('[data-cart]').forEach(paintCartBtn) },
  total() { return this.items.reduce((s, x) => s + x.price, 0) },
  mrp() { return this.items.reduce((s, x) => s + x.mrp, 0) },
};
function paintCartBtn(b) {
  const id = +b.dataset.cart, on = cart.has(id);
  b.textContent = on ? '✓ Added' : 'Add'; b.classList.toggle('ghost', on); b.setAttribute('aria-pressed', on);
  b.closest('.test')?.classList.toggle('in-cart', on);
}
function bindCartBtns(root, tests) {
  const by = Object.fromEntries(tests.map(t => [t.id, t]));
  $$('[data-cart]', root).forEach(b => {
    paintCartBtn(b);
    b.onclick = e => { e.stopPropagation(); const id = +b.dataset.cart; cart.has(id) ? cart.remove(id) : cart.add(by[id]) };
  });
}
function cartBar() {
  const b = $('#cartbar'), n = cart.items.length, onBook = location.hash.startsWith('#/lab/book');
  const show = n > 0 && !onBook && !location.hash.startsWith('#/doctor/') && !location.hash.startsWith('#/admin') && !location.hash.startsWith('#/portal');
  b.hidden = !show; document.body.classList.toggle('has-bar', show);
  if (!show) return;
  const save = cart.mrp() - cart.total();
  b.innerHTML = `<div><b>${plural(n, 'test')} · ${rs(cart.total())}</b>${save > 0 ? ` <span class="off">You save ${rs(save)}</span>` : ''}
    <div class="mute small">${esc(cart.items.map(x => x.name).join(', ')).slice(0, 110)}</div></div>
    <a class="btn lab" href="#/lab/book">Book a slot</a>`;
}

/* ================= Header, sections, global search ================= */
const ICON_SEARCH = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>';
function nav() {
  const u = me(), l = (h, t) => `<a href="#/${h}">${t}</a>`;
  const cartLink = (!u || u.role === 'patient') && cart.items.length ? `<a class="cartlink" href="#/lab/book" aria-label="Lab cart">Cart <b>${cart.items.length}</b></a>` : '';
  const links = !u ? l('login', 'Sign in') + `<a class="btn" href="#/register">Create account</a>`
    : u.role === 'patient' ? l('bookings', 'My bookings') + l('profile', 'Profile')
    : u.role === 'doctor' ? l('portal', 'My appointments') + l('portal/schedule', 'Hours and leave') : l('admin', 'Admin');
  $('#nav').innerHTML = `<a class="brand" href="#/" aria-label="VaidyaSaathi home"><i class="mark"></i><span>VaidyaSaathi</span></a>
    <div class="gsearch">${ICON_SEARCH}<input id="gq" type="search" placeholder="Search doctors, specialities or tests" aria-label="Search doctors, specialities or tests" autocomplete="off"><div class="drop" hidden></div></div>
    <div class="navlinks">${cartLink}${links}${u ? '<a href="#" id="out">Sign out</a>' : ''}</div>`;
  $('#out')?.addEventListener('click', e => { e.preventDefault(); setTok(null); chat.reset(); location.hash = '#/'; nav(); toast('Signed out') });
  bindSearch();
  const h = location.hash || '#/', on = p => p ? 'on' : '';
  const isLab = h.startsWith('#/lab'), isPkg = h.startsWith('#/lab/packages');
  $('#sections').innerHTML = `<a class="${on(!isLab && (h === '#/' || h.startsWith('#/spec') || h.startsWith('#/doctor')))}" href="#/">Doctors</a>
    <a class="${on(isLab && !isPkg)}" href="#/lab">Lab tests</a><a class="${on(isPkg)}" href="#/lab/packages">Health packages</a>
    <a href="#" class="ai" id="askai">Ask Saathi, the booking assistant</a>`;
  $('#askai').onclick = e => { e.preventDefault(); chat.open() };
}
function bindSearch() {
  const inp = $('#gq'), drop = $('.gsearch .drop');
  let items = [], idx = -1;
  const close = () => { drop.hidden = true; idx = -1 };
  const go = a => { close(); inp.value = ''; inp.blur(); location.hash = a.getAttribute('href') };
  inp.oninput = async () => {
    const q = inp.value.trim().toLowerCase();
    if (q.length < 2) return close();
    const [docs, specs, tests] = await Promise.all([getDoctors().catch(() => []), getSpecs().catch(() => []), getTests().catch(() => [])]);
    if (inp.value.trim().toLowerCase() !== q) return;
    const hit = s => String(s || '').toLowerCase().includes(q);
    const D = docs.filter(d => hit(d.full_name) || hit(d.specialization.name)).slice(0, 5);
    const S = specs.filter(s => hit(s.name)).slice(0, 3);
    const T = tests.filter(t => hit(t.name) || hit(t.also_known_as) || hit(t.code) || hit(t.category)).slice(0, 6);
    drop.innerHTML = (S.length ? `<div class="grp">Specialities</div>` + S.map(s => `<a href="#/spec/${s.id}"><span>${esc(s.name)}</span><span class="mute small">See doctors</span></a>`).join('') : '')
      + (D.length ? `<div class="grp">Doctors</div>` + D.map(d => `<a href="#/doctor/${d.id}"><span>${esc(d.full_name)}</span><span class="mute small">${esc(d.specialization.name)}</span></a>`).join('') : '')
      + (T.length ? `<div class="grp">Lab tests and packages</div>` + T.map(t => `<a href="#/lab/test/${t.id}"><span>${esc(t.name)}</span><span class="mute small">${rs(t.price)}</span></a>`).join('') : '')
      || `<div class="none">Nothing matches “${esc(inp.value)}”. Try a speciality like “skin” or a test like “sugar”.</div>`;
    drop.hidden = false; items = $$('a', drop); idx = -1;
    items.forEach(a => a.onmousedown = e => { e.preventDefault(); go(a) });
  };
  inp.onkeydown = e => {
    if (drop.hidden) return;
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault(); idx = (idx + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
      items.forEach((a, i) => a.classList.toggle('on', i === idx)); items[idx]?.scrollIntoView({ block: 'nearest' });
    } else if (e.key === 'Enter' && items.length) { e.preventDefault(); go(items[Math.max(idx, 0)]) }
    else if (e.key === 'Escape') close();
  };
  inp.onblur = () => setTimeout(close, 120);
}
addEventListener('keydown', e => {
  if (e.key === '/' && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) { e.preventDefault(); $('#gq')?.focus() }
});

/* On phones, start filter groups closed so results are visible first. */
const collapseFilters = () => { if (matchMedia('(max-width: 860px)').matches) $$('.filters details').forEach(d => d.open = false) };

/* ================= Home ================= */
let heroTimer;
function hero() {
  const dd = n => { const t = new Date(); t.setDate(t.getDate() + n); return t.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', timeZone: IST }) };
  const slides = [
    ['s1', 'See a doctor this week', 'Pick a specialist, choose a free time and get a confirmed appointment in a few taps.', '#/', 'Find a doctor',
      `<span class="chip">${dd(1)}</span><span class="chip sel">${dd(2)}, 6 slots</span><span class="chip">${dd(3)}, few left</span>`],
    ['s2', 'Lab tests at home from 6 am', 'A trained phlebotomist collects your sample at home, or visit a centre. Free home collection on orders above ₹999.', '#/lab', 'Browse lab tests',
      `<span class="chip">Full Body Checkup</span><span class="chip sel">HbA1c, thyroid, vitamin D</span><span class="chip">Reports in 24 hours</span>`],
    ['s3', 'Not sure who to see?', 'Tell Saathi your symptoms. It suggests the right specialist, finds a free slot and gets it ready for you to confirm.', '#chat', 'Ask Saathi',
      `<span class="chip">“Knee pain for a week”</span><span class="chip sel">Orthopedic, tomorrow 10:30 am</span>`],
  ];
  return `<section class="hero" aria-roledescription="carousel">${slides.map(([c, h, p, href, cta, art], i) => `<div class="slide ${c} ${i ? '' : 'on'}" aria-hidden="${!!i}">
     <div><h2>${h}</h2><p>${p}</p><a class="btn ${c === 's2' ? 'lab' : ''}" href="${href}" ${href === '#chat' ? 'data-openchat' : ''}>${cta}</a></div><div class="art">${art}</div></div>`).join('')}
    <div class="dots">${slides.map((_, i) => `<button aria-label="Slide ${i + 1}" class="${i ? '' : 'on'}" data-i="${i}"></button>`).join('')}</div></section>`;
}
function startHero() {
  const s = $$('.hero .slide'), d = $$('.hero .dots button'); let i = 0;
  const show = n => { i = n; s.forEach((x, j) => { x.classList.toggle('on', j === i); x.setAttribute('aria-hidden', j !== i) }); d.forEach((x, j) => x.classList.toggle('on', j === i)) };
  d.forEach(b => b.onclick = () => { show(+b.dataset.i); restart() });
  const restart = () => { clearInterval(heroTimer); if (!matchMedia('(prefers-reduced-motion: reduce)').matches) heroTimer = setInterval(() => { if (!$('.hero')) return clearInterval(heroTimer); show((i + 1) % s.length) }, 6500) };
  $('.hero').onmouseenter = () => clearInterval(heroTimer); $('.hero').onmouseleave = restart;
  $$('[data-openchat]').forEach(a => a.onclick = e => { e.preventDefault(); chat.open() });
  restart();
}
const docCard = d => `<a class="card" href="#/doctor/${d.id}"><div class="poster">${photo(d)}<div class="tagbar"><span>${rs(d.consultation_fee)}</span><span>${d.experience_years} yrs</span></div></div><b>${esc(d.full_name)}</b><span class="mute">${esc(d.specialization.name)}</span></a>`;
const pkgCard = t => `<div class="pkgcard test"><h3><button data-test="${t.id}">${esc(t.name)}</button></h3><span class="mute small">${esc(t.also_known_as || '')}</span>
  <ul>${t.parameters.slice(0, 4).map(p => `<li>${esc(p)}</li>`).join('')}${t.parameters.length > 4 ? `<li>and ${t.parameters.length - 4} more</li>` : ''}</ul>
  <div class="foot"><div><span class="amt">${rs(t.price)}</span> <span class="strike">${rs(t.mrp)}</span> <span class="off">${pctOff(t)}% off</span></div><button class="btn lab sm" data-cart="${t.id}">Add</button></div></div>`;

async function home(specParam) {
  clearInterval(heroTimer);
  view(`${hero()}<div class="rail">${skel(6, 'poster-sk')}</div>`); startHero();
  const [specs, docs, tests] = await Promise.all([getSpecs(), getDoctors(), getTests().catch(() => [])]);
  const pkgs = tests.filter(t => t.is_package);
  const top = [...docs].sort((a, b) => b.experience_years - a.experience_years).slice(0, 10);
  let sp = +specParam || 0, q = '', sort = '', fee = [], exp = 0;
  const counts = Object.fromEntries(specs.map(s => [s.id, docs.filter(d => d.specialization.id === s.id).length]));
  $('.rail').outerHTML = `${top.length ? `<div class="rail-head"><h2>Doctors you can book</h2><a href="#all">See all ${docs.length}</a></div><div class="rail">${top.map(docCard).join('')}</div>` : ''}
    ${pkgs.length ? `<div class="rail-head"><h2>Popular health packages</h2><a href="#/lab/packages">See all</a></div><div class="rail wide" id="pkgrail">${pkgs.filter(p => p.is_popular).map(pkgCard).join('')}</div>` : ''}
    <h2 id="all" style="margin-top:8px">All doctors</h2>
    <nav class="subnav" aria-label="Specialities"><button class="${sp ? '' : 'on'}" data-s="0">All</button>${specs.map(s => `<button data-s="${s.id}" class="${sp === s.id ? 'on' : ''}">${esc(s.name)}</button>`).join('')}</nav>
    <div class="list"><aside class="filters" aria-label="Filters"><h3>Filters</h3>
      <details open><summary>Consultation fee</summary>${[['u', 'Under ₹500'], ['m', '₹500 to ₹1,000'], ['o', 'Above ₹1,000']].map(([k, l]) => `<label class="ck"><input type="checkbox" data-f="${k}">${l}</label>`).join('')}</details>
      <details open><summary>Experience</summary>${[[0, 'Any'], [5, '5+ years'], [10, '10+ years'], [20, '20+ years']].map(([n, l]) => `<label class="ck"><input type="radio" name="x" value="${n}" ${n ? '' : 'checked'}>${l}</label>`).join('')}</details>
      <details><summary>Speciality</summary>${specs.map(s => `<label class="ck"><input type="radio" name="sp" value="${s.id}" ${sp === s.id ? 'checked' : ''}>${esc(s.name)}<span class="n">${counts[s.id]}</span></label>`).join('')}</details>
      <button class="link" id="clr" style="margin-top:8px">Clear filters</button></aside>
    <section><div class="top"><input class="search" id="q" placeholder="Search by doctor name" aria-label="Search doctors by name"><select id="so" aria-label="Sort doctors"><option value="">Sort: recommended</option><option value="f">Fee: low to high</option><option value="e">Most experienced</option></select></div>
    <div class="mute" id="n" aria-live="polite"></div><div class="grid" id="grid"></div></section></div>`;
  if ($('#pkgrail')) { bindCartBtns($('#pkgrail'), pkgs); $$('#pkgrail [data-test]').forEach(b => b.onclick = () => testModal(pkgs.find(t => t.id === +b.dataset.test))) }
  $('[href="#all"]')?.addEventListener('click', e => { e.preventDefault(); $('#all').scrollIntoView() });
  const inFee = (f, k) => k === 'u' ? f < 500 : k === 'm' ? f >= 500 && f <= 1000 : f > 1000;
  const draw = () => {
    let l = docs.filter(d => (!sp || d.specialization.id === sp) && d.full_name.toLowerCase().includes(q) && d.experience_years >= exp && (!fee.length || fee.some(k => inFee(+d.consultation_fee, k))));
    if (sort === 'f') l.sort((a, b) => a.consultation_fee - b.consultation_fee);
    if (sort === 'e') l.sort((a, b) => b.experience_years - a.experience_years);
    $('#n').textContent = plural(l.length, 'doctor') + ' available to book';
    $('#grid').innerHTML = l.length ? l.map(docCard).join('')
      : `<div class="empty" style="grid-column:1/-1">${docs.length ? 'No doctors match these filters.<br><button class="btn ghost" id="clr2">Clear filters</button>' : 'No doctors have been added yet. An admin can add them from the Admin page.'}</div>`;
    $('#clr2')?.addEventListener('click', clear);
  };
  const setSpec = id => { sp = id; $$('.subnav button').forEach(x => x.classList.toggle('on', +x.dataset.s === sp)); $$('[name=sp]').forEach(r => r.checked = +r.value === sp); draw() };
  const clear = () => { $$('[data-f]').forEach(c => c.checked = false); $('[name=x]').checked = true; fee = []; exp = 0; q = ''; $('#q').value = ''; setSpec(0) };
  $('#q').oninput = e => { q = e.target.value.toLowerCase().trim(); draw() };
  $('#so').onchange = e => { sort = e.target.value; draw() };
  $$('.subnav button').forEach(c => c.onclick = () => setSpec(+c.dataset.s));
  $$('[name=sp]').forEach(r => r.onchange = () => setSpec(+r.value));
  $$('[data-f]').forEach(c => c.onchange = () => { fee = $$('[data-f]:checked').map(x => x.dataset.f); draw() });
  $$('[name=x]').forEach(r => r.onchange = () => { exp = +r.value; draw() });
  $('#clr').onclick = clear;
  collapseFilters(); draw();
  if (sp) $('#all').scrollIntoView();
}

/* ================= Slot picker (doctors and lab) =================
   load(dateString) -> Promise<[{start_time, remaining?}]>; remaining undefined means "no capacity info" */
function picker(el, { days = 10, load, onPick, lab = false, emptyMsg }) {
  const list = [...Array(days)].map((_, i) => { const t = new Date(); t.setDate(t.getDate() + i); return t });
  const wd = t => t.toLocaleDateString('en-IN', { weekday: 'short', timeZone: IST }), mo = t => t.toLocaleDateString('en-IN', { month: 'short', timeZone: IST });
  const dnum = t => t.toLocaleDateString('en-IN', { day: 'numeric', timeZone: IST });
  el.innerHTML = `<div class="${lab ? 'labflow' : ''}"><div class="dates" role="tablist" aria-label="Choose a date">${list.map((t, i) => `<button class="date" role="tab" data-i="${i}" disabled><small>${i ? wd(t) : 'Today'}</small><b>${dnum(t)}</b><small>${mo(t)}</small><em>…</em></button>`).join('')}</div>
    <div class="sl"><div class="empty">Checking availability…</div></div>
    <div class="legend"><span><i></i>Available</span><span><i class="f"></i>Filling fast</span>${lab ? '<span><i class="x"></i>Full</span>' : ''}</div></div>`;
  const out = $('.sl', el), btns = $$('.date', el); let err = '';
  const q = list.map(t => load(istDate(t)).then(s => s.filter(x => new Date(x.start_time) > new Date())).catch(e => { err = e.message; return [] }));
  const free = s => s.filter(x => x.remaining === undefined || x.remaining > 0);
  const show = async i => {
    btns.forEach((b, j) => { b.classList.toggle('on', i === j); b.setAttribute('aria-selected', i === j) }); onPick(null);
    const sl = await q[i];
    out.innerHTML = [['Morning', h => h < 12, '🌅'], ['Afternoon', h => h >= 12 && h < 17, '☀️'], ['Evening', h => h >= 17, '🌙']].map(([n, f, ic]) => {
      const g = sl.filter(s => f(istHour(s.start_time))); if (!g.length) return '';
      return `<div class="part"><span aria-hidden="true">${ic}</span>${n}</div><div class="slots">${g.map(s => {
        const full = s.remaining === 0, few = s.remaining > 0 && s.remaining <= 1;
        return `<button class="slot ${few ? 'few' : ''}" data-t="${esc(s.start_time)}" ${full ? 'disabled' : ''}>${fmtT(s.start_time)}${s.remaining !== undefined ? `<small>${full ? 'Full' : few ? '1 left' : s.remaining + ' left'}</small>` : ''}</button>`;
      }).join('')}</div>`;
    }).join('') || `<div class="empty">No times left on this day.</div>`;
    $$('.slot', out).forEach(b => b.onclick = () => { $$('.slot', out).forEach(x => x.classList.toggle('on', x === b)); onPick(b.dataset.t) });
  };
  q.forEach((p, i) => p.then(sl => {
    const n = free(sl).length, b = btns[i]; b.disabled = !n;
    $('em', b).textContent = n ? (n <= 3 ? 'Few left' : n + ' slots') : 'Full'; $('em', b).className = n && n <= 3 ? 'few' : '';
  }));
  Promise.all(q).then(r => {
    const f = r.findIndex(s => free(s).length);
    if (f < 0) out.innerHTML = `<div class="empty">${esc(err || emptyMsg || 'No free times in the next few days.')}</div>`; else show(f);
  });
  btns.forEach((b, i) => {
    b.onclick = () => show(i);
    b.onkeydown = e => {
      const n = btns.filter(x => !x.disabled), k = n.indexOf(b) + (e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0);
      if (k !== n.indexOf(b) && n[k]) { e.preventDefault(); n[k].focus(); n[k].click() }
    };
  });
}
// scheduling-service returns India-time slots without an offset (e.g. 2026-11-05T09:00:00); add +05:30 so
// browsers in any timezone read them correctly and appointment-service accepts them.
const withIST = t => /([zZ]|[+-]\d\d:?\d\d)$/.test(t) ? t : t + '+05:30';
const doctorSlots = (docId, exclude) => date => api('schedule', `/schedules/doctors/${docId}/available-slots?requested_date=${date}&duration_minutes=30${exclude ? '&exclude_appointment_id=' + exclude : ''}`, { auth: false })
  .then(d => d.slots.map(s => ({ ...s, start_time: withIST(s.start_time), end_time: withIST(s.end_time) })));

function icsDownload(id, start, end, title) {
  const z = t => new Date(t).toISOString().replace(/[-:]|\.\d+/g, '');
  const f = `BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//VaidyaSaathi//EN\r\nBEGIN:VEVENT\r\nUID:${id}@vaidyasaathi\r\nDTSTAMP:${z(Date.now())}\r\nDTSTART:${z(start)}\r\nDTEND:${z(end)}\r\nSUMMARY:${title}\r\nEND:VEVENT\r\nEND:VCALENDAR`;
  const l = document.createElement('a'); l.href = URL.createObjectURL(new Blob([f], { type: 'text/calendar' })); l.download = 'vaidyasaathi.ics'; l.click();
}
function apptTicket(a, d) {
  const m = modal(`<div class="ticket"><div class="ok">✓</div><h2>Appointment booked</h2><div class="stub"><b>${fmtT(a.start_time)}</b>${fmtD(a.start_time)}<div class="mute">${esc(d.full_name || d.name)}, ${esc(d.specialization?.name || d.speciality || '')}</div><div class="mute">Booking ID ${a.id}</div></div>
    <div class="row" style="justify-content:center"><button class="btn ghost" id="ics">Add to calendar</button><button class="btn" id="go">View my bookings</button></div></div>`);
  $('#go', m).onclick = () => { m.close(); location.hash = '#/bookings' };
  $('#ics', m).onclick = () => icsDownload('appt-' + a.id, a.start_time, a.end_time, 'Appointment with ' + (d.full_name || d.name));
}
async function bookAppointment(docId, start, reason) {
  return api('appointment', '/appointments/', { method: 'POST', body: { doctor_id: +docId, start_time: start, reason: reason || null } });
}
function bookingError(er) {
  toast(er.message, 1);
  if (er.status === 409 && /profile/i.test(er.message)) { sessionStorage.vs_after_profile = location.hash; toast('Add your profile details first, then book again.', 1); setTimeout(() => location.hash = '#/profile', 1200) }
}

/* ================= Doctor page ================= */
async function doctorPage(id) {
  view(`<section class="banner"><div class="in"><div class="sk poster-sk" style="width:180px"></div></div></section>`);
  const d = await api('doctor', '/doctors/' + id, { auth: false });
  let chosen = null;
  view(`<section class="banner"><div class="in">${photo(d)}<div><h1>${esc(d.full_name)}</h1><div class="pills"><span>${esc(d.specialization.name)}</span><span>${d.experience_years} years experience</span></div>
    <p>${d.qualifications.map(q => esc(q.degree + (q.institution ? ', ' + q.institution : ''))).join('; ')}</p><div class="price">${rs(d.consultation_fee)} <small>consultation fee</small></div><a class="btn" href="#pickhere" id="jump">Book appointment</a></div></div></section>
    <div class="panel" id="pickhere"><h2>Select date and time</h2><div id="pick"></div></div><div class="bar" id="bar" hidden></div>`);
  $('#jump').onclick = e => { e.preventDefault(); $('#pickhere').scrollIntoView({ behavior: 'smooth' }) };
  picker($('#pick'), {
    load: doctorSlots(id), emptyMsg: 'No free times in the next 10 days. The doctor may be on leave or has not set hours yet.',
    onPick: t => {
      chosen = t; const b = $('#bar'); b.hidden = !t; document.body.classList.toggle('has-bar', !!t); if (!t) return;
      b.innerHTML = `<div><b>${fmtD(t)}, ${fmtT(t)}</b><div class="mute">${esc(d.full_name)}</div></div><button class="btn" id="go">Book for ${rs(d.consultation_fee)}</button>`;
      $('#go').onclick = () => {
        if (!need('patient')) return;
        const m = modal(`<h2>Confirm appointment</h2><p>${esc(d.full_name)}, ${fmtD(chosen)} at ${fmtT(chosen)}. Fee ${rs(d.consultation_fee)}, paid at the clinic.</p><form id="f" class="stack"><label>Reason for visit (optional)<textarea name="reason" rows="3" maxlength="1000" placeholder="For example: knee pain for two weeks"></textarea></label>
          <div class="row"><button type="button" class="btn ghost" id="x">Back</button><button class="btn">Confirm booking</button></div></form>`);
        $('#x', m).onclick = m.close;
        $('#f', m).onsubmit = async e => {
          e.preventDefault(); const btn = e.submitter; btn.disabled = true; btn.textContent = 'Booking…';
          try { const a = await bookAppointment(id, chosen, new FormData(e.target).get('reason')); m.close(); apptTicket(a, d); $('#bar').hidden = true; document.body.classList.remove('has-bar') }
          catch (er) { btn.disabled = false; btn.textContent = 'Confirm booking'; bookingError(er) }
        };
      };
    },
  });
}

/* ================= Lab tests catalogue ================= */
function testModal(t) {
  if (!t) return;
  const m = modal(`<h2 style="padding-right:24px">${esc(t.name)}</h2>${t.also_known_as ? `<p class="mute">${t.is_package ? '' : 'Also called '}${esc(t.also_known_as)}</p>` : ''}
    <div class="facts">${facts(t)}</div><p>${esc(t.description)}</p>
    <h3>${t.is_package ? 'Tests included' : 'What it measures'}</h3><ul class="params">${t.parameters.map(p => `<li>${esc(p)}</li>`).join('')}</ul>
    <h3>Before the test</h3><p>${esc(t.preparation)}</p>
    <div class="row" style="border-top:1px solid var(--line);padding-top:14px;margin-top:6px"><div><span class="amt" style="font-size:22px;font-weight:800">${rs(t.price)}</span> <span class="strike">${rs(t.mrp)}</span> <span class="off">${pctOff(t)}% off</span></div>
    <button class="btn lab" data-cart="${t.id}">Add</button></div>`);
  bindCartBtns(m, [t]);
}
const facts = t => [
  t.is_package ? `<span class="fact pkg">Package</span>` : '',
  `<span class="fact">${esc(t.sample_type)} sample</span>`,
  t.fasting_hours ? `<span class="fact fast">Fasting ${t.fasting_hours} hrs</span>` : `<span class="fact">No fasting</span>`,
  `<span class="fact">Report in ${t.report_hours < 24 ? t.report_hours + ' hrs' : Math.round(t.report_hours / 24) + (t.report_hours >= 48 ? ' days' : ' day')}</span>`,
].join('');
const testCard = t => `<article class="test"><h3><button data-test="${t.id}">${esc(t.name)}</button></h3><span class="aka">${esc(t.is_package ? t.also_known_as : t.also_known_as ? 'Also called ' + t.also_known_as : '')}</span>
  <div class="facts">${facts(t)}</div><span class="mute small">${t.is_package ? 'Includes ' : 'Measures '}${esc(t.parameters.slice(0, 3).join(', '))}${t.parameters.length > 3 ? ` and ${t.parameters.length - 3} more` : ''}</span>
  <div class="foot"><div><span class="amt">${rs(t.price)}</span> <span class="strike">${rs(t.mrp)}</span> <span class="off">${pctOff(t)}% off</span></div><button class="btn lab sm" data-cart="${t.id}">Add</button></div></article>`;

async function labPage(mode, arg) {
  view(`<section class="labhead"><div class="in"><h1>Lab tests and health packages</h1><p>Home sample collection or a visit to our centre. Reports on your phone.</p>
    <input class="search" id="lq" placeholder="Search tests, for example HbA1c, thyroid, vitamin D" aria-label="Search lab tests">
    <div class="perks"><span>Free home collection above ₹999</span><span>Trained phlebotomists</span><span>Pay at collection</span></div></div></section>
    <div class="tests">${skel(6, 'line')}</div>`);
  let tests, cats;
  try { [tests, cats] = await Promise.all([getTests(), api('lab', '/lab/categories', { auth: false })]) }
  catch (e) { $('.tests').outerHTML = `<div class="empty">${esc(e.message)}</div>`; return }
  let kind = mode === 'packages' ? 'packages' : 'all', cat = mode === 'cat' ? decodeURIComponent(arg) : '', q = '', fast = '', price = '', sort = '';
  $('.tests').outerHTML = `<nav class="subnav lab" aria-label="Test categories"><button data-c="" class="${cat ? '' : 'on'}">All</button>${cats.map(c => `<button data-c="${esc(c.name)}" class="${cat === c.name ? 'on' : ''}">${esc(c.name)}</button>`).join('')}</nav>
    <div class="list"><aside class="filters" aria-label="Filters"><h3>Filters</h3>
      <details open><summary>Show</summary>${[['all', 'Tests and packages'], ['tests', 'Single tests'], ['packages', 'Health packages']].map(([v, l]) => `<label class="ck"><input type="radio" name="k" value="${v}" ${kind === v ? 'checked' : ''} style="accent-color:var(--lab)">${l}</label>`).join('')}</details>
      <details open><summary>Fasting</summary>${[['', 'Any'], ['no', 'No fasting needed'], ['yes', 'Fasting needed']].map(([v, l]) => `<label class="ck"><input type="radio" name="fa" value="${v}" ${v ? '' : 'checked'} style="accent-color:var(--lab)">${l}</label>`).join('')}</details>
      <details open><summary>Price</summary>${[['', 'Any'], ['a', 'Under ₹500'], ['b', '₹500 to ₹1,500'], ['c', 'Above ₹1,500']].map(([v, l]) => `<label class="ck"><input type="radio" name="pr" value="${v}" ${v ? '' : 'checked'} style="accent-color:var(--lab)">${l}</label>`).join('')}</details>
      <button class="link" id="clr" style="color:var(--lab);margin-top:8px">Clear filters</button></aside>
    <section><div class="row wrap"><div class="mute" id="n" aria-live="polite"></div><select id="so" style="width:auto" aria-label="Sort tests"><option value="">Sort: popular first</option><option value="p">Price: low to high</option><option value="d">Biggest discount</option></select></div>
    <div class="tests" id="tl"></div></section></div>`;
  const inPrice = p => price === 'a' ? p < 500 : price === 'b' ? p >= 500 && p <= 1500 : price === 'c' ? p > 1500 : true;
  const draw = () => {
    const ql = q.toLowerCase();
    let l = tests.filter(t => (kind === 'all' || (kind === 'packages') === t.is_package) && (!cat || t.category === cat)
      && (!ql || [t.name, t.also_known_as, t.code, t.category, ...t.parameters].some(s => String(s || '').toLowerCase().includes(ql)))
      && (!fast || (fast === 'yes') === t.fasting_hours > 0) && inPrice(+t.price));
    if (sort === 'p') l.sort((a, b) => a.price - b.price);
    if (sort === 'd') l.sort((a, b) => pctOff(b) - pctOff(a));
    $('#n').textContent = `${plural(l.length, 'result')}${cat ? ' in ' + cat : ''}`;
    $('#tl').innerHTML = l.map(testCard).join('') || `<div class="empty" style="grid-column:1/-1">No tests match. Try another word, or clear the filters.<br><button class="btn lab ghost" id="clr2">Clear filters</button></div>`;
    bindCartBtns($('#tl'), l);
    $$('#tl [data-test]').forEach(b => b.onclick = () => testModal(tests.find(t => t.id === +b.dataset.test)));
    $('#clr2')?.addEventListener('click', clear);
  };
  const setCat = c => { cat = c; $$('.subnav button').forEach(x => x.classList.toggle('on', x.dataset.c === c)); draw() };
  const clear = () => { kind = 'all'; fast = ''; price = ''; q = ''; $('#lq').value = ''; $$('[name=k],[name=fa],[name=pr]').forEach(r => r.checked = r.value === (r.name === 'k' ? 'all' : '')); setCat('') };
  $('#lq').oninput = e => { q = e.target.value.trim(); draw() };
  $$('.subnav button').forEach(b => b.onclick = () => setCat(b.dataset.c));
  $$('[name=k]').forEach(r => r.onchange = () => { kind = r.value; draw() });
  $$('[name=fa]').forEach(r => r.onchange = () => { fast = r.value; draw() });
  $$('[name=pr]').forEach(r => r.onchange = () => { price = r.value; draw() });
  $('#so').onchange = e => { sort = e.target.value; draw() };
  $('#clr').onclick = clear;
  collapseFilters(); draw();
  if (mode === 'test') testModal(tests.find(t => t.id === +arg));
}

/* ================= Lab booking (checkout) ================= */
async function labBookPage() {
  if (!cart.items.length) return view(`<div class="empty"><h2>Your lab cart is empty</h2><p>Add tests or a health package, then come back to pick a time.</p><a class="btn lab" href="#/lab">Browse lab tests</a></div>`);
  if (!need('patient')) return;
  view('<div class="empty">Loading…</div>');
  const [centres, prof] = await Promise.all([api('lab', '/lab/centres', { auth: false }), api('patient', '/patients/me').catch(() => null)]);
  const st = { type: 'home', centre: centres[0]?.id || null, slot: null };
  const fasting = Math.max(0, ...cart.items.map(x => x.fasting_hours || 0));
  const lastName = store.get('vs_name', '');
  view(`<h1>Book lab tests</h1><p class="mute">Three quick steps. You pay at the time of sample collection.</p>
  <div class="steps"><div>
    <section class="step"><h2><span class="num">1</span>Patient and collection</h2>
      <div class="two"><label>Patient name<input id="pname" required minlength="2" maxlength="150" value="${esc(lastName)}" autocomplete="name"></label>
      <label>Mobile number<input id="pphone" type="tel" required value="${esc(prof?.phone_number || '')}" placeholder="10-digit mobile" autocomplete="tel"></label></div>
      <p class="mute small" style="margin-top:6px">Booking for a family member? Enter their name.</p>
      <div class="choice" role="radiogroup" aria-label="Collection type">
        <label><input type="radio" name="ct" value="home" checked><span><b>Home collection</b><span class="mute small">6 am to 12 pm. ${cart.total() >= 999 ? 'Free for this order.' : '₹99, free above ₹999.'}</span></span></label>
        <label><input type="radio" name="ct" value="centre" ${centres.length ? '' : 'disabled'}><span><b>Visit a lab centre</b><span class="mute small">${centres.length ? `${plural(centres.length, 'centre')}, 7 am to 7 pm. No collection fee.` : 'No centres added yet.'}</span></span></label>
      </div>
      <div id="where"></div>
      <button class="btn lab" id="next1" style="margin-top:12px">Continue to date and time</button>
    </section>
    <section class="step locked" id="s2"><h2><span class="num">2</span>Date and time</h2>
      ${fasting ? `<div class="note">Your order includes a test that needs ${fasting} hours of fasting. Pick an early morning slot.</div>` : ''}<div id="lpick"><p class="mute">Finish step 1 first.</p></div></section>
    <section class="step locked" id="s3"><h2><span class="num">3</span>Review and confirm</h2><div id="review"><p class="mute">Pick a time first.</p></div></section>
  </div>
  <aside class="summary step"><h2>Order summary</h2><div id="sum"></div></aside></div>`);

  const fee = () => st.type === 'home' && cart.total() < 999 ? 99 : 0;
  const summary = () => {
    $('#sum').innerHTML = cart.items.map(x => `<div class="line"><span>${esc(x.name)}</span><span>${rs(x.price)} <button class="link" data-rm="${x.id}" aria-label="Remove ${esc(x.name)}" style="color:var(--bad);margin-left:4px">✕</button></span></div>`).join('')
      + `<div class="line"><span>Collection fee</span><span>${fee() ? rs(fee()) : 'Free'}</span></div>`
      + (cart.mrp() > cart.total() ? `<div class="line off"><span>You save</span><span>${rs(cart.mrp() - cart.total())}</span></div>` : '')
      + `<div class="line tot"><span>To pay</span><span>${rs(cart.total() + fee())}</span></div><a class="link" href="#/lab" style="color:var(--lab);font-size:14px">+ Add more tests</a>`;
    $$('[data-rm]').forEach(b => b.onclick = () => { cart.remove(+b.dataset.rm); cart.items.length ? (summary(), review()) : labBookPage() });
  };
  const where = () => {
    $('#where').innerHTML = st.type === 'home'
      ? `<div class="two"><label style="grid-column:1/-1">Full address<textarea id="addr" rows="2" maxlength="500" placeholder="House number, street, area, landmark">${esc(prof?.address || '')}</textarea></label>
         <label>Pincode<input id="pin" inputmode="numeric" maxlength="6" placeholder="6 digits"></label></div>`
      : `<div class="choice">${centres.map(c => `<label><input type="radio" name="cen" value="${c.id}" ${st.centre === c.id ? 'checked' : ''}><span><b>${esc(c.name)}</b><span class="mute small">${esc(c.address)}, ${esc(c.city)} ${esc(c.pincode)}<br>Open ${c.opens} to ${c.closes}${c.phone ? ', ' + esc(c.phone) : ''}</span></span></label>`).join('')}</div>`;
    $$('[name=cen]').forEach(r => r.onchange = () => { st.centre = +r.value; resetLater() });
  };
  const resetLater = () => { st.slot = null; $('#s2').classList.add('locked'); $('#s3').classList.add('locked'); $('#lpick').innerHTML = '<p class="mute">Finish step 1 first.</p>'; review() };
  const review = () => {
    if (!st.slot) { $('#review').innerHTML = '<p class="mute">Pick a time first.</p>'; return }
    const c = centres.find(x => x.id === st.centre);
    $('#review').innerHTML = `<p><b>${fmtD(st.slot)}, ${fmtT(st.slot)}</b><br>${st.type === 'home' ? 'Home collection at ' + esc($('#addr')?.value || st.addr || '') : 'At ' + esc(c?.name || '')}</p>
      <p class="mute">For ${esc(st.name)}, ${esc(st.phone)}. ${plural(cart.items.length, 'test')}, ${rs(cart.total() + fee())} to pay at collection.</p>
      <button class="btn lab" id="confirm">Confirm booking</button>`;
    $('#confirm').onclick = confirm;
  };
  const step1ok = () => {
    st.name = $('#pname').value.trim(); st.phone = $('#pphone').value.trim();
    if (st.name.length < 2) return toast('Enter the patient’s name', 1), $('#pname').focus(), false;
    if (!/^\+?[0-9 ]{7,20}$/.test(st.phone)) return toast('Enter a valid mobile number', 1), $('#pphone').focus(), false;
    if (st.type === 'home') {
      st.addr = $('#addr').value.trim(); st.pin = $('#pin').value.trim();
      if (st.addr.length < 10) return toast('Enter the full address for home collection', 1), $('#addr').focus(), false;
      if (!/^\d{6}$/.test(st.pin)) return toast('Enter a 6-digit pincode', 1), $('#pin').focus(), false;
    } else if (!st.centre) return toast('Choose a lab centre', 1), false;
    return true;
  };
  $$('[name=ct]').forEach(r => r.onchange = () => { st.type = r.value; where(); summary(); resetLater() });
  $('#next1').onclick = () => {
    if (!step1ok()) return;
    store.set('vs_name', st.name);
    $('#s2').classList.remove('locked'); $('#s2').scrollIntoView({ behavior: 'smooth', block: 'start' });
    picker($('#lpick'), {
      days: 8, lab: true, emptyMsg: 'No free times in the next week. Try the other collection type.',
      load: date => api('lab', `/lab/slots?collection_type=${st.type}&requested_date=${date}${st.type === 'centre' ? '&centre_id=' + st.centre : ''}`, { auth: false }),
      onPick: t => { st.slot = t; $('#s3').classList.toggle('locked', !t); review(); if (t) $('#s3').scrollIntoView({ behavior: 'smooth', block: 'nearest' }) },
    });
  };
  const confirm = async () => {
    const b = $('#confirm'); b.disabled = true; b.textContent = 'Booking…';
    try {
      const bk = await api('lab', '/lab/bookings/', { method: 'POST', body: {
        test_ids: cart.items.map(x => x.id), collection_type: st.type, centre_id: st.type === 'centre' ? st.centre : null,
        patient_name: st.name, contact_phone: st.phone, address: st.type === 'home' ? st.addr : null, pincode: st.type === 'home' ? st.pin : null, slot_start: st.slot } });
      cart.clear(); labTicket(bk);
    } catch (er) { b.disabled = false; b.textContent = 'Confirm booking'; toast(er.message, 1); if (er.status === 409) $('#next1').click() }
  };
  where(); summary();
}
function labTicket(bk) {
  const m = modal(`<div class="ticket"><div class="ok lab">✓</div><h2>Lab tests booked</h2><div class="stub"><b>${fmtT(bk.slot_start)}</b>${fmtD(bk.slot_start)}
    <div class="mute">${bk.collection_type === 'home' ? 'Home collection' : esc(bk.centre?.name || 'Lab centre')}, ${plural(bk.items.length, 'test')}, ${rs(bk.total)} to pay</div><div class="mute">Booking ID L${bk.id}</div></div>
    ${bk.items.some(i => i.fasting_hours) ? '<div class="note">Remember to fast before your sample is taken. Water is fine.</div>' : ''}
    <div class="row" style="justify-content:center"><button class="btn lab ghost" id="ics">Add to calendar</button><button class="btn lab" id="go">View my bookings</button></div></div>`);
  $('#go', m).onclick = () => { m.close(); location.hash = '#/bookings/lab' };
  $('#ics', m).onclick = () => icsDownload('lab-' + bk.id, bk.slot_start, new Date(new Date(bk.slot_start).getTime() + 1800000).toISOString(), 'Lab sample collection');
  m.addEventListener('click', e => { if (e.target === m) location.hash = '#/bookings/lab' });
}

/* ================= My bookings ================= */
const LAB_STEPS = [['booked', 'Booked'], ['sample_collected', 'Sample collected'], ['processing', 'Processing'], ['report_ready', 'Report ready']];
const whenBox = iso => `<div class="when"><small>${new Date(iso).toLocaleDateString('en-IN', { month: 'short', timeZone: IST })}</small><b>${new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', timeZone: IST })}</b><small>${new Date(iso).toLocaleDateString('en-IN', { weekday: 'short', timeZone: IST })}</small><div class="t">${fmtT(iso)}</div></div>`;
async function bookingsPage(tab = 'appointments') {
  if (!need('patient')) return;
  view(`<h1>My bookings</h1><div class="tabs" role="tablist"><button data-t="appointments">Appointments</button><button data-t="lab">Lab tests</button></div><div id="bl">${skel(3, 'line')}</div>`);
  const [appts, docs, labs] = await Promise.all([api('appointment', '/appointments/me').catch(() => []), getDoctors().catch(() => []), api('lab', '/lab/bookings/me').catch(() => [])]);
  const now = new Date(), dn = Object.fromEntries(docs.map(d => [d.id, d]));
  const live = a => ['booked', 'confirmed'].includes(a.status) && new Date(a.start_time) > now;
  const sortUp = (l, k) => [...l.filter(x => new Date(x[k]) > now).sort((a, b) => new Date(a[k]) - new Date(b[k])), ...l.filter(x => new Date(x[k]) <= now).sort((a, b) => new Date(b[k]) - new Date(a[k]))];
  const tabs = $$('.tabs button');
  tabs[0].innerHTML = `Appointments<span class="n">${appts.filter(live).length}</span>`;
  tabs[1].innerHTML = `Lab tests<span class="n">${labs.filter(b => !['cancelled', 'report_ready'].includes(b.status)).length}</span>`;
  const drawAppts = () => {
    $('#bl').innerHTML = appts.length ? sortUp(appts, 'start_time').map(a => {
      const d = dn[a.doctor_id], ok = live(a);
      return `<div class="bk ${ok ? '' : 'past'}">${whenBox(a.start_time)}<div><b>${esc(d ? d.full_name : 'Doctor #' + a.doctor_id)}</b> <span class="tag ${a.status}">${a.status}</span>
        <div class="mute">${esc(d ? d.specialization.name : '')}${d ? ', ' + rs(d.consultation_fee) : ''}</div>${a.reason ? `<div class="small">Reason: ${esc(a.reason)}</div>` : ''}${a.cancellation_reason ? `<div class="small mute">Cancelled: ${esc(a.cancellation_reason)}</div>` : ''}<div class="mute small">Booking ID ${a.id}</div></div>
        ${ok ? `<div class="acts"><button class="btn ghost sm" data-r="${a.id}" data-d="${a.doctor_id}">Reschedule</button><button class="btn ghost sm" data-c="${a.id}">Cancel</button></div>` : '<div></div>'}</div>`;
    }).join('') : `<div class="empty">You have no appointments yet.<br><a class="btn" href="#/">Find a doctor</a></div>`;
    $$('[data-c]').forEach(b => b.onclick = () => {
      const m = modal(`<h2>Cancel this appointment?</h2><form id="f" class="stack"><label>Reason (optional)<input name="r" maxlength="255"></label><div class="row"><button type="button" class="btn ghost" id="x">Keep it</button><button class="btn red">Cancel appointment</button></div></form>`);
      $('#x', m).onclick = m.close;
      $('#f', m).onsubmit = async e => { e.preventDefault(); try { await api('appointment', `/appointments/${b.dataset.c}/cancel`, { method: 'PATCH', body: { cancellation_reason: new FormData(e.target).get('r') || null } }); m.close(); toast('Appointment cancelled'); bookingsPage('appointments') } catch (er) { toast(er.message, 1) } };
    });
    $$('[data-r]').forEach(b => b.onclick = () => {
      let t = null;
      const m = modal(`<h2>Pick a new time</h2><div id="pk"></div><div class="row" style="margin-top:16px"><button class="btn ghost" id="x">Close</button><button class="btn" id="ok" disabled>Move appointment</button></div>`);
      $('#x', m).onclick = m.close;
      picker($('#pk', m), { load: doctorSlots(b.dataset.d, b.dataset.r), onPick: s => { t = s; $('#ok', m).disabled = !s } });
      $('#ok', m).onclick = async () => { try { await api('appointment', `/appointments/${b.dataset.r}/reschedule`, { method: 'PATCH', body: { start_time: t } }); m.close(); toast('Appointment moved to ' + fmtD(t) + ', ' + fmtT(t)); bookingsPage('appointments') } catch (er) { toast(er.message, 1) } };
    });
  };
  const drawLab = () => {
    $('#bl').innerHTML = labs.length ? sortUp(labs, 'slot_start').map(b => {
      const i = LAB_STEPS.findIndex(s => s[0] === b.status), cancellable = b.status === 'booked' && new Date(b.slot_start) > now;
      return `<div class="bk ${b.status === 'cancelled' ? 'past' : ''}">${whenBox(b.slot_start)}<div><b>${esc(b.items.map(x => x.name).join(', '))}</b>
        <div class="mute">${b.collection_type === 'home' ? 'Home collection, ' + esc(b.address || '') : esc(b.centre?.name || 'Lab centre')}</div>
        <div class="small">For ${esc(b.patient_name)}. ${rs(b.total)}${+b.collection_fee ? ' including ' + rs(b.collection_fee) + ' collection fee' : ''}. Booking ID L${b.id}</div>
        ${b.status === 'cancelled' ? `<span class="tag cancelled" style="margin-top:8px">Cancelled</span>` : `<div class="track">${LAB_STEPS.map(([, l], j) => `<span class="${j <= i ? 'done' : ''}">${l}</span>`).join('')}</div>`}</div>
        <div class="acts">${b.report_url ? `<a class="btn lab sm" href="${esc(b.report_url)}" target="_blank" rel="noopener">Download report</a>` : ''}${cancellable ? `<button class="btn ghost sm" data-lc="${b.id}">Cancel</button>` : ''}</div></div>`;
    }).join('') : `<div class="empty">You have no lab bookings yet.<br><a class="btn lab" href="#/lab">Browse lab tests</a></div>`;
    $$('[data-lc]').forEach(btn => btn.onclick = () => {
      const m = modal(`<h2>Cancel this lab booking?</h2><form id="f" class="stack"><label>Reason (optional)<input name="r" maxlength="255"></label><div class="row"><button type="button" class="btn ghost" id="x">Keep it</button><button class="btn red">Cancel booking</button></div></form>`);
      $('#x', m).onclick = m.close;
      $('#f', m).onsubmit = async e => { e.preventDefault(); try { await api('lab', `/lab/bookings/${btn.dataset.lc}/cancel`, { method: 'PATCH', body: { cancellation_reason: new FormData(e.target).get('r') || null } }); m.close(); toast('Lab booking cancelled'); bookingsPage('lab') } catch (er) { toast(er.message, 1) } };
    });
  };
  const show = t => { tabs.forEach(b => { b.classList.toggle('on', b.dataset.t === t); b.setAttribute('aria-selected', b.dataset.t === t) }); history.replaceState(null, '', '#/bookings' + (t === 'lab' ? '/lab' : '')); t === 'lab' ? drawLab() : drawAppts() };
  tabs.forEach(b => b.onclick = () => show(b.dataset.t));
  show(tab);
}

/* ================= Auth ================= */
async function loginPage() {
  view(`<div class="auth"><img src="assets/logo.png" alt=""><div><h1>Sign in</h1><form id="f" class="stack"><label>Email<input name="email" type="email" required autocomplete="username"></label>
   <label>Password<input name="password" type="password" required autocomplete="current-password"></label><button class="btn">Sign in</button>
   <span class="mute">Doctors and admins sign in here too. New patient? <a href="#/register" style="color:var(--pri);font-weight:600">Create an account</a></span></form></div></div>`);
  $('#f').onsubmit = async e => {
    e.preventDefault(); const b = e.submitter; b.disabled = true;
    try {
      setTok(await api('auth', '/auth/login', { method: 'POST', body: Object.fromEntries(new FormData(e.target)) })); nav();
      const r = me().role, n = sessionStorage.vs_next; sessionStorage.removeItem('vs_next');
      toast('Signed in'); location.hash = r === 'doctor' ? '#/portal' : r === 'admin' ? '#/admin' : n || '#/';
    } catch (er) { b.disabled = false; toast(er.message, 1) }
  };
}
async function registerPage() {
  let name = '', email = '', reg = '', timer;
  const shell = (t, inner) => view(`<div class="auth"><img src="assets/logo.png" alt=""><div><h1>${t}</h1>${inner}</div></div>`);
  let sent = null;   // last /request-otp reply: {delivery: 'email'|'console', dev_code?}
  const send = async b => (sent = await api('auth', '/auth/register/request-otp', { method: 'POST', body: b }));
  const step1 = () => {
    clearInterval(timer);
    shell('Create your account', `<form id="f" class="stack"><label>Full name<input name="full_name" required minlength="2" value="${esc(name)}" autocomplete="name"></label><label>Email<input name="email" type="email" required value="${esc(email)}" autocomplete="email"></label>
      <button class="btn">Send verification code</button><span class="mute">We will email a 6-digit code to confirm this address.</span></form>`);
    $('#f').onsubmit = async e => {
      e.preventDefault(); const b = Object.fromEntries(new FormData(e.target)); e.submitter.disabled = true;
      try { await send(b); name = b.full_name; email = b.email; store.set('vs_name', name); step2() } catch (er) { e.submitter.disabled = false; toast(er.message, 1) }
    };
  };
  const step2 = () => {
    const viaLog = sent?.delivery === 'console';
    const notice = !viaLog ? `<p class="mute">We sent a 6-digit code to <b>${esc(email)}</b>. It expires in 10 minutes. Check your spam folder if it isn’t in your inbox.</p>`
      : `<div class="note info"><b>Email sending isn’t set up on this server yet</b>, so no email was sent.${sent.dev_code ? ` Your code is <b class="devcode">${sent.dev_code}</b>.` : ' Find the code with: <code>docker compose logs notification-service</code>'}<br><span class="small">To send real emails, fill in the SMTP settings in .env (see README).</span></div>`;
    shell(viaLog ? 'Enter your code' : 'Check your email', `<form id="f" class="stack">${notice}
      <label>Verification code<input name="otp" class="otp" inputmode="numeric" autocomplete="one-time-code" maxlength="6" required autofocus></label>
      <button class="btn">Verify email</button><div class="row"><button type="button" class="link" id="rs"></button><button type="button" class="link" id="ch">Use a different email</button></div></form>`);
    let left = 60; const rsb = $('#rs'), tick = () => { rsb.disabled = left > 0; rsb.textContent = left > 0 ? `Resend code in ${left}s` : 'Resend code' }; tick();
    clearInterval(timer); timer = setInterval(() => { if (!$('#rs')) return clearInterval(timer); left--; tick(); if (left <= 0) clearInterval(timer) }, 1000);
    rsb.onclick = async () => { try { await send({ full_name: name, email }); toast(sent?.delivery === 'console' ? 'New code created' : 'A new code is on its way'); step2() } catch (er) { toast(er.message, 1) } };
    $('#ch').onclick = step1;
    const inp = $('[name=otp]'); if (sent?.dev_code) inp.placeholder = sent.dev_code; inp.oninput = () => { inp.value = inp.value.replace(/\D/g, ''); if (inp.value.length === 6) $('#f').requestSubmit() };
    $('#f').onsubmit = async e => {
      e.preventDefault(); const otp = inp.value.trim(); if (!/^\d{6}$/.test(otp)) return toast('Enter the 6-digit code', 1);
      try { reg = (await api('auth', '/auth/register/verify-otp', { method: 'POST', body: { email, otp } })).registration_token; clearInterval(timer); step3() } catch (er) { toast(er.message, 1); inp.select() }
    };
  };
  const step3 = () => {
    shell('Set your password', `<form id="f" class="stack"><p class="mute">Email verified: <b>${esc(email)}</b></p><label>Password (8 or more characters)<input name="password" type="password" minlength="8" required autocomplete="new-password"></label>
      <label>Confirm password<input name="again" type="password" required autocomplete="new-password"></label><button class="btn">Create account</button></form>`);
    $('#f').onsubmit = async e => {
      e.preventDefault(); const f = Object.fromEntries(new FormData(e.target)); if (f.password !== f.again) return toast('Passwords do not match', 1);
      try {
        await api('auth', '/auth/register/complete', { method: 'POST', body: { registration_token: reg, full_name: name, password: f.password } });
        setTok(await api('auth', '/auth/login', { method: 'POST', body: { email, password: f.password } })); nav(); toast('Account created. Add your details to start booking.'); location.hash = '#/profile';
      } catch (er) { toast(er.message, 1); if (er.status === 401) step1() }
    };
  };
  step1();
}

/* ================= Patient profile ================= */
async function profilePage() {
  if (!need('patient')) return;
  let p = null; try { p = await api('patient', '/patients/me') } catch (e) { if (e.status !== 404) throw e }
  const f = (n, l, t = 'text', x = '') => `<label>${l}<input name="${n}" type="${t}" value="${esc(p?.[n] || '')}" ${x}></label>`;
  view(`<h1>${p ? 'Your details' : 'Complete your profile'}</h1><p class="mute">${p ? 'These details are shared with your doctor when you book.' : 'Add these once. They are needed before your first booking.'}</p>
   <div class="panel" style="max-width:640px"><form id="f" class="stack" style="max-width:none"><div class="two">${f('phone_number', 'Mobile number', 'tel', 'minlength=7 maxlength=20')}${f('date_of_birth', 'Date of birth', 'date')}</div>
   <label>Gender<select name="gender">${['', 'Female', 'Male', 'Other'].map(g => `<option ${p?.gender === g ? 'selected' : ''} value="${g}">${g || 'Prefer not to say'}</option>`).join('')}</select></label>${f('address', 'Address')}
   <div class="two">${f('emergency_contact_name', 'Emergency contact name')}${f('emergency_contact_phone', 'Emergency contact phone', 'tel', 'minlength=7 maxlength=20')}</div><button class="btn">Save details</button></form></div>`);
  $('#f').onsubmit = async e => {
    e.preventDefault(); const b = {}; new FormData(e.target).forEach((v, k) => { if (v) b[k] = v });
    try { await api('patient', '/patients/me', { method: p ? 'PATCH' : 'POST', body: b }); toast('Details saved'); if (!p) location.hash = sessionStorage.vs_after_profile || '#/'; else profilePage() } catch (er) { toast(er.message, 1) }
  };
}

/* Doctor and admin panels live in staff.js */

/* ================= AI assistant (Saathi) ================= */
const chat = {
  msgs: (() => { try { return JSON.parse(sessionStorage.vs_chat || '[]') } catch { return [] } })(),   // [{role, text, cards?, memo?, err?}]
  busy: false, isOpen: false, mode: null,
  save() { try { sessionStorage.vs_chat = JSON.stringify(this.msgs.slice(-40)) } catch { } },
  reset() { this.msgs = []; this.save(); if (this.isOpen) this.render() },
  fab() { $('#chat').innerHTML = `<button class="fab" aria-label="Ask Saathi, the booking assistant"><i class="mark"></i><span>Ask Saathi</span></button>`; $('.fab').onclick = () => this.open() },
  open() {
    this.isOpen = true;
    $('#chat').innerHTML = `<section class="chatbox" role="dialog" aria-label="Saathi booking assistant">
      <div class="chathead"><i class="mark"></i><div><b>Saathi</b><br><small id="cmode">Finds doctors, free slots and lab tests</small></div><button id="cnew" title="Start a new chat">New chat</button><button id="cx" aria-label="Close assistant" style="font-size:20px">×</button></div>
      <div class="msgs" id="msgs" aria-live="polite"></div><div class="sugg" id="sugg"></div>
      <form class="chatin" id="cf"><textarea id="ci" placeholder="Type a message" aria-label="Message" maxlength="1500"></textarea><button class="btn">Send</button></form>
      <div class="chatnote">Saathi is not a doctor. In an emergency call 112 or 108.</div></section>`;
    $('#cx').onclick = () => this.close(); $('#cnew').onclick = () => this.reset();
    const ci = $('#ci');
    ci.onkeydown = e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); $('#cf').requestSubmit() } };
    ci.oninput = () => { ci.style.height = '42px'; ci.style.height = Math.min(ci.scrollHeight, 110) + 'px' };
    $('#cf').onsubmit = e => { e.preventDefault(); this.send(ci.value) };
    document.addEventListener('keydown', this.esc);
    if (!this.mode) api('ai', '/ai/status', { auth: false }).then(s => { this.mode = s.mode; this.paintMode() }).catch(() => { });
    this.render(); this.paintMode(); ci.focus();
  },
  esc: e => { if (e.key === 'Escape' && chat.isOpen && !$('.modal')) chat.close() },
  close() { this.isOpen = false; document.removeEventListener('keydown', this.esc); this.fab() },
  paintMode() { if (this.mode === 'basic' && $('#cmode')) $('#cmode').textContent = 'Basic mode: symptom matching' },
  render() {
    const box = $('#msgs'); if (!box) return;
    const hello = { role: 'assistant', text: 'Hi, I’m Saathi. Tell me what’s bothering you and I’ll suggest the right doctor and a free time. I can also help you pick lab tests.' };
    box.innerHTML = [hello, ...this.msgs].map((m, i) => `<div class="msg ${m.role === 'user' ? 'user' : 'bot'} ${m.err ? 'err' : ''}">${esc(m.text)}</div>${(m.cards || []).map((c, j) => this.card(c, i - 1, j)).join('')}`).join('')
      + (this.busy ? '<div class="msg bot typing" aria-label="Saathi is typing"><i></i><i></i><i></i></div>' : '');
    $('#sugg').innerHTML = this.msgs.length ? '' : ['I have fever and body ache for 3 days', 'Book a skin doctor this week', 'Which tests check for diabetes?', 'Full body checkup under ₹1,500']
      .map(s => `<button type="button">${esc(s)}</button>`).join('');
    $$('#sugg button').forEach(b => b.onclick = () => this.send(b.textContent));
    this.bindCards(box);
    box.scrollTop = box.scrollHeight;
  },
  card(c, mi, ci) {
    if (c.type === 'doctors') return `<div class="ccard">${c.doctors.map(d => `<div class="cdoc">${photo(d)}<div><b>${esc(d.name)}</b>${esc(d.speciality)}, ${d.experience_years} yrs, ${rs(d.fee)}</div><a class="btn ghost sm" href="#/doctor/${d.id}">See slots</a></div>`).join('')}</div>`;
    if (c.type === 'lab_tests') return `<div class="ccard">${c.tests.map(t => `<div class="ctest"><div><b>${esc(t.name)}</b><div class="mute">${rs(t.price)} <span class="strike">${rs(t.mrp)}</span>${t.fasting_hours ? `, fasting ${t.fasting_hours} hrs` : ''}</div></div><button class="btn lab sm" data-cart="${t.id}">Add</button></div>`).join('')}<a class="link" href="#/lab/book" style="color:var(--lab);font-size:13px">Go to cart and book</a></div>`;
    if (c.type === 'appointment') {
      const done = c.booked;
      return `<div class="cappt ${done ? 'done' : ''}"><span class="mute small">${done ? 'Booked' : 'Ready to book'}</span><div class="when2">${fmtD(c.start_time)}, ${fmtT(c.start_time)}</div>
        <div>${esc(c.doctor.name)}, ${esc(c.doctor.speciality)}. Fee ${rs(c.doctor.fee)}</div>${c.reason ? `<div class="small mute">Reason: ${esc(c.reason)}</div>` : ''}
        ${done ? `<div class="small">Booking ID ${c.booked}. <a href="#/bookings" style="color:var(--pri)">View my bookings</a></div>` : `<div class="row" style="justify-content:flex-start"><button class="btn sm" data-book="${mi}:${ci}">Confirm booking</button><a class="btn ghost sm" href="#/doctor/${c.doctor.id}">Other times</a></div>`}</div>`;
    }
    return '';
  },
  bindCards(box) {
    const tests = this.msgs.flatMap(m => (m.cards || []).filter(c => c.type === 'lab_tests').flatMap(c => c.tests)).map(t => ({ ...t, sample_type: '', parameters: t.includes || [] }));
    bindCartBtns(box, tests);
    $$('[data-book]', box).forEach(b => b.onclick = async () => {
      const [mi, ci] = b.dataset.book.split(':').map(Number), c = this.msgs[mi].cards[ci];
      if (me()?.role !== 'patient') { toast('Sign in as a patient to confirm this booking', 1); sessionStorage.vs_next = location.hash; location.hash = '#/login'; return }
      b.disabled = true; b.textContent = 'Booking…';
      try {
        const a = await bookAppointment(c.doctor.id, c.start_time, c.reason);
        c.booked = a.id; this.msgs.push({ role: 'assistant', text: `Done. Your appointment with ${c.doctor.name} on ${fmtD(a.start_time)} at ${fmtT(a.start_time)} is booked.` });
        this.save(); this.render(); apptTicket(a, c.doctor);
      } catch (er) { b.disabled = false; b.textContent = 'Confirm booking'; bookingError(er); if (er.status === 409 && !/profile/i.test(er.message)) this.send('That slot was just taken. Please find another time.') }
    });
  },
  async send(text) {
    text = String(text || '').trim(); if (!text || this.busy) return;
    $('#ci') && ($('#ci').value = '', $('#ci').style.height = '42px');
    this.msgs.push({ role: 'user', text }); this.busy = true; this.save(); this.render();
    const history = this.msgs.filter(m => !m.err).slice(-20).map(m => ({ role: m.role, text: m.memo ? `${m.text}\n[Context for the assistant: ${m.memo}]` : m.text }));
    try {
      const r = await api('ai', '/ai/chat', { method: 'POST', body: { messages: history }, auth: false });
      this.mode = r.mode; this.msgs.push({ role: 'assistant', text: r.reply, cards: r.cards, memo: r.memo });
    } catch (er) { this.msgs.push({ role: 'assistant', text: er.message, err: true }) }
    this.busy = false; this.save(); this.render(); this.paintMode();
  },
};

/* ================= Router ================= */
const routes = [
  [/^\/$/, () => home()], [/^\/spec\/(\d+)$/, home], [/^\/doctor\/(\d+)$/, doctorPage],
  [/^\/lab$/, () => labPage()], [/^\/lab\/packages$/, () => labPage('packages')], [/^\/lab\/cat\/(.+)$/, c => labPage('cat', c)], [/^\/lab\/test\/(\d+)$/, id => labPage('test', id)],
  [/^\/lab\/book$/, labBookPage],
  [/^\/login$/, loginPage], [/^\/register$/, registerPage],
  [/^\/(?:bookings|appointments)$/, () => bookingsPage()], [/^\/bookings\/lab$/, () => bookingsPage('lab')],
  [/^\/profile$/, profilePage], [/^\/portal$/, () => portalPage()], [/^\/portal\/(schedule|profile)$/, t => portalPage(t)],
  [/^\/admin$/, () => adminPage()], [/^\/admin\/(doctors|appointments|patients|tests|lab|centres)$/, t => adminPage(t)],
];
async function route() {
  nav(); cartBar(); document.body.classList.toggle('has-bar', !$('#cartbar').hidden);
  document.body.classList.toggle('staff', ['doctor', 'admin'].includes(me()?.role));   // the assistant is for patients
  $$('.modal').forEach(m => m.remove());
  const h = location.hash.slice(1) || '/'; scrollTo(0, 0);
  for (const [re, fn] of routes) {
    const m = h.match(re);
    if (m) { try { await fn(...m.slice(1)) } catch (e) { view(`<div class="empty"><h2>Something went wrong</h2><p>${esc(e.message)}</p><button class="btn ghost" onclick="route()">Try again</button></div>`) } return }
  }
  view('<div class="empty"><h2>Page not found</h2><a class="btn" href="#/">Back to doctors</a></div>');
}
addEventListener('hashchange', route);
chat.fab(); route();
