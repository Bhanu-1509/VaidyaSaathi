/* VaidyaSaathi – doctor and admin panels.
   Loaded before app.js; uses its helpers ($, api, modal, toast, rs, fmtT, fmtD …) at run time. */

/* ================= Shared pieces ================= */
const addDays = (iso, n) => { const d = new Date(iso + 'T12:00:00+05:30'); d.setDate(d.getDate() + n); return istDate(d) };
const todayISO = () => istDate(new Date());
const dLabel = (iso, opt) => new Date(iso + 'T12:00:00+05:30').toLocaleDateString('en-IN', { timeZone: IST, ...opt });
const ageSex = p => [p.age != null ? p.age + ' yrs' : '', p.gender || ''].filter(Boolean).join(', ');
const tile = (n, label, cls = '') => `<div class="tile ${cls}"><b>${n}</b><span>${label}</span></div>`;
const APPT_ACTIONS = {
  booked: [['confirmed', 'Confirm'], ['completed', 'Mark completed'], ['cancelled', 'Cancel']],
  confirmed: [['completed', 'Mark completed'], ['cancelled', 'Cancel']],
};

/* Date navigator: a week strip with counts, arrows, a Today button and a calendar input.
   opts: {selected, counts: async (from, to) => {date: n}, onPick(date)} */
function dateNav(el, opts) {
  let sel = opts.selected || todayISO(), start = addDays(sel, -((new Date(sel + 'T12:00:00+05:30').getDay() + 6) % 7)); // week starts Monday
  const draw = async () => {
    const days = [...Array(7)].map((_, i) => addDays(start, i));
    el.innerHTML = `<div class="dnav"><button class="btn ghost sm" data-w="-7" aria-label="Previous week">‹</button>
      <div class="dates" role="tablist" aria-label="Choose a date">${days.map(d => `<button class="date ${d === sel ? 'on' : ''}" data-d="${d}" role="tab" aria-selected="${d === sel}">
        <small>${d === todayISO() ? 'Today' : dLabel(d, { weekday: 'short' })}</small><b>${dLabel(d, { day: 'numeric' })}</b><small>${dLabel(d, { month: 'short' })}</small><em data-c="${d}">&nbsp;</em></button>`).join('')}</div>
      <button class="btn ghost sm" data-w="7" aria-label="Next week">›</button>
      <div class="dnav-r"><button class="btn ghost sm" id="dtoday">Today</button><label class="cal"><span class="sr">Pick any date</span><input type="date" id="djump" value="${sel}"></label></div></div>`;
    $$('[data-w]', el).forEach(b => b.onclick = () => { start = addDays(start, +b.dataset.w); draw() });
    $$('[data-d]', el).forEach(b => b.onclick = () => pick(b.dataset.d));
    $('#dtoday', el).onclick = () => pick(todayISO(), true);
    $('#djump', el).onchange = e => e.target.value && pick(e.target.value, true);
    if (opts.counts) {
      const c = await opts.counts(days[0], days[6]).catch(() => ({}));
      days.forEach(d => { const em = $(`[data-c="${d}"]`, el); if (em) { const n = c[d] || 0; em.textContent = n ? plural(n, opts.unit || 'booking') : 'None'; em.className = n ? '' : 'none' } });
    }
  };
  const pick = (d, jump) => {
    sel = d; if (jump || d < start || d > addDays(start, 6)) start = addDays(d, -((new Date(d + 'T12:00:00+05:30').getDay() + 6) % 7));
    draw(); opts.onPick(d);
  };
  draw(); opts.onPick(sel);
  return { refresh: draw, get: () => sel };
}

/* Appointment rows for doctors and admins */
function apptRows(list, { showDoctor = false, docs = {}, compact = false }) {
  if (!list.length) return '<div class="empty">No appointments on this day.</div>';
  if (compact) return list.map(a => { const d = docs[a.doctor_id]; return `<div class="row" style="border-bottom:1px solid var(--line);padding:8px 0"><span><b>${fmtT(a.start_time)}</b> ${esc(a.patient.name)}<br><span class="mute small">${esc(d ? d.full_name : 'Doctor #' + a.doctor_id)}${a.reason ? ' · ' + esc(a.reason) : ''}</span></span><span class="tag ${a.status}">${a.status}</span></div>` }).join('');
  return `<div class="tbl appts">${list.map(a => {
    const p = a.patient, d = docs[a.doctor_id], early = new Date(a.start_time) - Date.now() > 15 * 60000;
    const acts = (APPT_ACTIONS[a.status] || []).filter(([v]) => !(v === 'completed' && early));
    return `<div class="tr ${a.status}"><div class="t"><b>${fmtT(a.start_time)}</b><span class="mute small">to ${fmtT(a.end_time)}</span></div>
      <div><b>${esc(p.name)}</b>${ageSex(p) ? ` <span class="mute small">${esc(ageSex(p))}</span>` : ''}
        <div class="small">${p.phone ? `<a href="tel:${esc(p.phone)}" class="lnk">${esc(p.phone)}</a>` : '<span class="mute">No phone on profile</span>'}${p.email ? ` · <a class="lnk" href="mailto:${esc(p.email)}">${esc(p.email)}</a>` : ''}</div>
        ${a.reason ? `<div class="small">Reason: ${esc(a.reason)}</div>` : ''}${a.cancellation_reason ? `<div class="small mute">Cancelled: ${esc(a.cancellation_reason)}</div>` : ''}
        ${showDoctor ? `<div class="small mute">${esc(d ? d.full_name + ', ' + d.specialization.name : 'Doctor #' + a.doctor_id)}</div>` : ''}</div>
      <div><span class="tag ${a.status}">${a.status}</span><div class="mute small">ID ${a.id}</div></div>
      <div class="acts">${acts.map(([v, l]) => `<button class="btn ${v === 'cancelled' ? 'ghost' : v === 'completed' ? '' : 'ghost'} sm" data-act="${a.id}" data-v="${v}">${l}</button>`).join('')}</div></div>`;
  }).join('')}</div>`;
}
function bindApptActions(root, reload) {
  $$('[data-act]', root).forEach(b => b.onclick = async () => {
    const id = b.dataset.act, v = b.dataset.v;
    const send = async reason => { await api('appointment', `/appointments/staff/${id}`, { method: 'PATCH', body: { status: v, cancellation_reason: reason || null } }); toast(v === 'cancelled' ? 'Appointment cancelled' : v === 'completed' ? 'Marked completed' : 'Appointment confirmed'); reload() };
    if (v !== 'cancelled') { b.disabled = true; try { await send() } catch (er) { b.disabled = false; toast(er.message, 1) } return }
    const m = modal(`<h2>Cancel this appointment?</h2><p class="mute">The patient will see it as cancelled in My bookings.</p><form id="f" class="stack"><label>Reason (shown to the patient)<input name="r" maxlength="255" placeholder="For example: doctor unavailable"></label><div class="row"><button type="button" class="btn ghost" id="x">Keep it</button><button class="btn red">Cancel appointment</button></div></form>`);
    $('#x', m).onclick = m.close;
    $('#f', m).onsubmit = async e => { e.preventDefault(); try { await send(new FormData(e.target).get('r')); m.close() } catch (er) { toast(er.message, 1) } };
  });
}
const apptCounts = extra => async (from, to) => Object.fromEntries((await api('appointment', `/appointments/staff/summary?from=${from}&to=${to}${extra || ''}`)).map(x => [x.date, x.active + x.completed]));
function tabsBar(tabs, active, base) {
  return `<div class="tabs scroll" role="tablist">${tabs.map(([k, l]) => `<a href="#/${base}${k ? '/' + k : ''}" role="tab" class="${k === active ? 'on' : ''}" aria-selected="${k === active}">${l}</a>`).join('')}</div>`;
}

/* ================= Doctor panel ================= */
async function portalPage(tab = '') {
  if (!need('doctor')) return;
  const u = me(), docs = await api('doctor', '/doctors/'), d = docs.find(x => x.auth_user_id === u.id);
  if (!d) return view('<div class="empty"><h2>Your profile is not set up yet</h2><p>Ask the admin to create your doctor profile, then sign in again.</p></div>');
  view(`<div class="dochead">${photo(d)}<div><h1>${esc(d.full_name)}</h1><p class="mute">${esc(d.specialization.name)}, ${d.experience_years} years, ${rs(d.consultation_fee)} per visit</p></div></div>
    ${tabsBar([['', 'Appointments'], ['schedule', 'Hours and leave'], ['profile', 'My profile']], tab, 'portal')}<div id="pt"></div>`);
  const el = $('#pt');
  if (tab === 'schedule') return doctorSchedule(el, d);
  if (tab === 'profile') return doctorProfile(el, d);

  const st = await api('appointment', '/appointments/staff/stats').catch(() => null);
  let filter = 'all', day, list = [];
  el.innerHTML = `${st ? `<div class="tiles">${tile(st.today_active, 'Left today')}${tile(st.today_total, 'Booked today')}${tile(st.upcoming, 'Upcoming')}${tile(st.completed, 'Completed')}</div>` : ''}
    <div class="panel"><div id="dn"></div>
    <div class="row wrap" style="margin:14px 0 4px"><h2 id="dtitle" style="margin:0"></h2><div class="chips" id="fl">${[['all', 'All'], ['active', 'To see'], ['completed', 'Completed'], ['cancelled', 'Cancelled']].map(([k, l]) => `<button data-f="${k}" class="${k === 'all' ? 'on' : ''}">${l}</button>`).join('')}</div></div>
    <div id="al">${skel(2, 'line')}</div></div>`;
  const draw = () => {
    const shown = list.filter(a => filter === 'all' || (filter === 'active' ? ['booked', 'confirmed'].includes(a.status) : a.status === filter));
    $('#dtitle').textContent = `${dLabel(day, { weekday: 'long', day: 'numeric', month: 'long' })} · ${plural(list.filter(a => a.status !== 'cancelled').length, 'patient')}`;
    $('#al').innerHTML = apptRows(shown, {}); bindApptActions($('#al'), load);
  };
  const load = async () => { list = await api('appointment', `/appointments/staff?date=${day}`); draw(); nav_.refresh() };
  $$('#fl button').forEach(b => b.onclick = () => { filter = b.dataset.f; $$('#fl button').forEach(x => x.classList.toggle('on', x === b)); draw() });
  const nav_ = dateNav($('#dn'), { counts: apptCounts(), unit: 'patient', onPick: dd => { day = dd; $('#al').innerHTML = skel(2, 'line'); load().catch(er => $('#al').innerHTML = `<div class="empty">${esc(er.message)}</div>`) } });
}

async function doctorSchedule(el, d) {
  const [av, lv] = await Promise.all([api('doctor', `/doctors/${d.id}/availability/`), api('doctor', `/doctors/${d.id}/leaves/`)]);
  const t5 = t => String(t).slice(0, 5), today = todayISO();
  const byDay = DAYS.map((n, i) => [n, av.filter(a => a.day_of_week === i).sort((a, b) => String(a.start_time).localeCompare(b.start_time))]);
  const upcomingLeave = lv.filter(l => l.end_date >= today).sort((a, b) => a.start_date.localeCompare(b.start_date));
  el.innerHTML = `<div class="split"><div>
    <div class="panel"><h2>Weekly hours</h2><p class="mute">Patients can book 30-minute slots inside these hours.</p>
      <div class="week">${byDay.map(([n, rows], i) => `<div class="wd"><b>${n.slice(0, 3)}</b>${rows.map(a => `<span class="hrs">${t5(a.start_time)}–${t5(a.end_time)} <button class="link" data-a="${a.id}" aria-label="Remove ${n} ${t5(a.start_time)}">✕</button></span>`).join('') || '<span class="mute small">Off</span>'}</div>`).join('')}</div>
      <form id="fa" class="inline"><label>Days<select name="days"><option value="0">Monday</option><option value="1">Tuesday</option><option value="2">Wednesday</option><option value="3">Thursday</option><option value="4">Friday</option><option value="5">Saturday</option><option value="6">Sunday</option><option value="wk">Monday to Friday</option><option value="ms">Monday to Saturday</option></select></label>
        <label>From<input type="time" name="start_time" value="09:00" required></label><label>To<input type="time" name="end_time" value="13:00" required></label><button class="btn">Add hours</button></form></div>
    <div class="panel"><h2>Leave</h2>
      ${upcomingLeave.map(l => `<div class="row" style="margin-top:6px"><span><b>${dLabel(l.start_date, { day: 'numeric', month: 'short' })}${l.end_date !== l.start_date ? ' to ' + dLabel(l.end_date, { day: 'numeric', month: 'short', year: 'numeric' }) : ', ' + dLabel(l.start_date, { year: 'numeric' })}</b>${l.reason ? ' · ' + esc(l.reason) : ''}</span><button class="btn ghost sm" data-l="${l.id}">Remove</button></div>`).join('') || '<p class="mute">No leave coming up.</p>'}
      <form id="fl" class="inline" style="margin-top:12px"><label>From<input type="date" name="start_date" min="${today}" required></label><label>To<input type="date" name="end_date" min="${today}" required></label><label>Reason (optional)<input name="reason" maxlength="255"></label><button class="btn">Add leave</button></form>
      <p class="mute small" style="margin-top:8px">Leave cannot overlap days that already have booked patients. Cancel or move those first.</p></div>
  </div><div class="panel"><h2>Check a date</h2><p class="mute">See what patients can book on any day.</p>
    <label>Date<input type="date" id="cd" value="${today}" min="${today}"></label><div id="cs" style="margin-top:12px"></div></div></div>`;
  const reload = () => doctorSchedule(el, d);
  const run = fn => async e => { e.preventDefault?.(); try { await fn(e); toast('Saved'); reload() } catch (er) { toast(er.message, 1) } };
  $('#fa').onsubmit = run(async e => {
    const f = Object.fromEntries(new FormData(e.target)), days = f.days === 'wk' ? [0, 1, 2, 3, 4] : f.days === 'ms' ? [0, 1, 2, 3, 4, 5] : [+f.days];
    for (const day_of_week of days) await api('doctor', `/doctors/${d.id}/availability/`, { method: 'POST', body: { day_of_week, start_time: f.start_time, end_time: f.end_time } });
  });
  $('#fl').onsubmit = run(e => { const b = {}; new FormData(e.target).forEach((v, k) => { if (v) b[k] = v }); return api('doctor', `/doctors/${d.id}/leaves/`, { method: 'POST', body: b }) });
  $$('[data-a]').forEach(b => b.onclick = run(() => api('doctor', `/doctors/${d.id}/availability/${b.dataset.a}`, { method: 'DELETE' })));
  $$('[data-l]').forEach(b => b.onclick = run(() => api('doctor', `/doctors/${d.id}/leaves/${b.dataset.l}`, { method: 'DELETE' })));
  const check = async () => {
    const day = $('#cd').value; if (!day) return;
    const onLeave = lv.find(l => l.start_date <= day && l.end_date >= day);
    $('#cs').innerHTML = '<div class="mute">Checking…</div>';
    try {
      const [slots, appts] = await Promise.all([doctorSlots(d.id)(day), api('appointment', `/appointments/staff?date=${day}`)]);
      const busy = appts.filter(a => ['booked', 'confirmed'].includes(a.status));
      $('#cs').innerHTML = `<h3>${dLabel(day, { weekday: 'long', day: 'numeric', month: 'long' })}</h3>
        ${onLeave ? `<div class="note">You are on leave this day.</div>` : `<p>${plural(slots.length, 'free slot')}, ${plural(busy.length, 'booked patient')}.</p>
        <div class="slots">${slots.map(s => `<span class="slot static">${fmtT(s.start_time)}</span>`).join('') || '<span class="mute">No free slots.</span>'}</div>
        ${busy.length ? '' : `<button class="btn ghost" id="block" style="margin-top:14px">Take this day off</button>`}`}`;
      $('#block')?.addEventListener('click', run(() => api('doctor', `/doctors/${d.id}/leaves/`, { method: 'POST', body: { start_date: day, end_date: day, reason: 'Day off' } })));
    } catch (er) { $('#cs').innerHTML = `<div class="empty">${esc(er.message)}</div>` }
  };
  $('#cd').onchange = check; check();
}

function doctorProfile(el, d) {
  el.innerHTML = `<div class="panel" style="max-width:640px"><h2>My profile</h2>
    <dl class="kv"><dt>Name</dt><dd>${esc(d.full_name)}</dd><dt>Email</dt><dd>${esc(d.email)}</dd><dt>Speciality</dt><dd>${esc(d.specialization.name)}</dd>
    <dt>Experience</dt><dd>${d.experience_years} years</dd><dt>Consultation fee</dt><dd>${rs(d.consultation_fee)}</dd>
    <dt>Qualifications</dt><dd>${d.qualifications.map(q => esc(q.degree + (q.institution ? ', ' + q.institution : ''))).join('<br>') || '—'}</dd></dl>
    <p class="mute small">To change these details, ask the admin. Patients see this on your booking page.</p><a class="btn ghost" href="#/doctor/${d.id}">See my public page</a></div>`;
}

/* ================= Admin panel ================= */
const ADMIN_TABS = [['', 'Dashboard'], ['doctors', 'Doctors'], ['appointments', 'Appointments'], ['patients', 'Patients'], ['tests', 'Lab tests'], ['lab', 'Lab bookings'], ['centres', 'Lab centres']];
async function adminPage(tab = '') {
  if (!need('admin')) return;
  view(`<h1>Admin</h1>${tabsBar(ADMIN_TABS, tab, 'admin')}<div id="ad">${skel(2, 'line')}</div>`);
  const el = $('#ad');
  const fn = { '': adminDashboard, doctors: adminDoctors, appointments: adminAppointments, patients: adminPatients, tests: adminTests, lab: adminLabBookings, centres: adminCentres }[tab] || adminDashboard;
  try { await fn(el) } catch (er) { el.innerHTML = `<div class="empty">${esc(er.message)}</div>` }
}

async function adminDashboard(el) {
  const today = todayISO();
  const [docs, pats, ap, lab, todayAppts, todayLab] = await Promise.all([
    api('doctor', '/doctors/'), api('auth', '/auth/admin/users?role=patient').catch(() => []),
    api('appointment', '/appointments/staff/stats').catch(() => null), api('lab', '/lab/admin/stats').catch(() => null),
    api('appointment', `/appointments/staff?date=${today}`).catch(() => []), api('lab', `/lab/admin/bookings?date=${today}`).catch(() => [])]);
  const dn = Object.fromEntries(docs.map(d => [d.id, d]));
  el.innerHTML = `<h2>Doctors and patients</h2><div class="tiles">${tile(docs.length, 'Active doctors')}${tile(pats.length, 'Patients')}${ap ? tile(ap.today_active, 'Appointments left today') + tile(ap.upcoming, 'Upcoming appointments') + tile(ap.completed, 'Completed') : ''}</div>
    ${lab ? `<h2>Lab</h2><div class="tiles lab">${tile(lab.today, 'Collections today')}${tile(lab.awaiting_collection, 'Waiting for collection')}${tile(lab.in_lab, 'In the lab')}${tile(lab.reports_ready, 'Reports sent')}${tile(rs(lab.revenue_this_month), 'Lab bookings this month')}${tile(lab.active_tests + ' + ' + lab.active_packages, 'Tests + packages')}</div>` : ''}
    <div class="split2"><div class="panel"><div class="row"><h2>Today's appointments</h2><a class="lnk" href="#/admin/appointments">See all</a></div>${apptRows(todayAppts.slice(0, 8), { docs: dn, compact: true })}</div>
    <div class="panel"><div class="row"><h2>Today's lab collections</h2><a class="lnk" href="#/admin/lab">See all</a></div>${todayLab.length ? todayLab.slice(0, 8).map(b => `<div class="row" style="border-bottom:1px solid var(--line);padding:8px 0"><span><b>${fmtT(b.slot_start)}</b> ${esc(b.patient_name)}<br><span class="mute small">${b.collection_type === 'home' ? 'Home, ' + esc(b.pincode || '') : esc(b.centre?.name || '')} · ${plural(b.items.length, 'test')}</span></span><span class="tag ${b.status}">${b.status.replace('_', ' ')}</span></div>`).join('') : '<div class="empty">No lab collections today.</div>'}</div></div>`;
}

async function adminDoctors(el, newId = '') {
  const [specs, docs] = await Promise.all([api('doctor', '/specializations/'), api('doctor', '/doctors/')]);
  const i = (n, l, t = 'text', x = '') => `<label>${l}<input name="${n}" type="${t}" ${x} required></label>`;
  el.innerHTML = `<div class="split"><div><div class="panel"><div class="row wrap"><h2>Doctors (${docs.length})</h2><input class="search" id="dq" placeholder="Search name or speciality" style="max-width:260px"></div>
    <div class="tbl" id="dl"></div></div></div>
    <div><div class="panel"><h2>Add a doctor</h2><p class="mute small">Creates the sign-in account and the public profile together.</p>
      <form id="fd" class="stack">${i('full_name', 'Full name', 'text', 'minlength=2 placeholder="Dr. Asha Menon"')}${i('email', 'Email (used to sign in)', 'email')}${i('password', 'Temporary password (12+ characters)', 'password', 'minlength=12 autocomplete="new-password"')}
      <div class="two"><label>Speciality<select name="specialization_id">${specs.map(s => `<option value="${s.id}">${esc(s.name)}</option>`).join('')}</select></label>${i('experience_years', 'Experience (years)', 'number', 'min=0 value=0')}</div>
      <div class="two">${i('consultation_fee', 'Fee (₹)', 'number', 'min=0 step=1')}${i('degree', 'Degree', 'text', 'placeholder="MBBS, MD"')}</div>
      <label>Institution (optional)<input name="institution"></label>
      <label>Photo link<input name="profile_photo_url" type="url" required placeholder="https://i.pravatar.cc/400?img=12"></label>
      <button class="btn">Add doctor</button></form>
      <details style="margin-top:12px"><summary class="lnk">Profile only, for an existing login</summary><form id="f2" class="stack" style="margin-top:10px">${i('auth_user_id', 'Login user ID', 'number', `min=1 value="${newId}"`)}<p class="mute small">Use this if a login was created but its profile was not. Fill the form above too; only the profile part is used.</p><button class="btn ghost">Create profile only</button></form></details></div>
    <div class="panel"><h2>Specialities (${specs.length})</h2><div class="chips static">${specs.map(s => `<span>${esc(s.name)} <em>${docs.filter(d => d.specialization.id === s.id).length}</em></span>`).join('')}</div>
      <form id="fs" class="inline" style="margin-top:12px"><label>New speciality<input name="name" required minlength="2" placeholder="Psychiatrist"></label><button class="btn ghost">Add</button></form></div></div></div>`;
  const draw = q => {
    const l = docs.filter(d => !q || (d.full_name + ' ' + d.specialization.name).toLowerCase().includes(q));
    $('#dl').innerHTML = l.map(d => `<div class="tr doc">${photo(d)}<div><b>${esc(d.full_name)}</b><div class="mute small">${esc(d.specialization.name)}, ${d.experience_years} yrs, ${rs(d.consultation_fee)}</div><div class="small">${esc(d.email)}</div></div>
      <div class="acts"><button class="btn ghost sm" data-e="${d.id}">Edit</button><button class="btn ghost sm" data-h="${d.id}">Hours</button><a class="btn ghost sm" href="#/doctor/${d.id}">Page</a><button class="btn ghost sm" data-x="${d.id}">Deactivate</button></div></div>`).join('') || '<div class="empty">No doctors yet. Add one with the form.</div>';
    $$('[data-e]').forEach(b => b.onclick = () => editDoctor(docs.find(d => d.id === +b.dataset.e), specs, () => adminPage('doctors')));
    $$('[data-h]').forEach(b => b.onclick = () => doctorHours(docs.find(d => d.id === +b.dataset.h)));
    $$('[data-x]').forEach(b => b.onclick = () => {
      const m = modal(`<h2>Deactivate this doctor?</h2><p>They will no longer appear to patients. Existing appointments stay as they are.</p><div class="row"><button class="btn ghost" id="x">Keep active</button><button class="btn red" id="y">Deactivate</button></div>`);
      $('#x', m).onclick = m.close;
      $('#y', m).onclick = async () => { try { await api('doctor', `/doctors/${b.dataset.x}/deactivate`, { method: 'PATCH' }); delete cache.docs; m.close(); toast('Doctor deactivated'); adminPage('doctors') } catch (er) { toast(er.message, 1) } };
    });
  };
  $('#dq').oninput = e => draw(e.target.value.toLowerCase().trim()); draw('');
  const profileBody = (f, uid) => ({ auth_user_id: uid, full_name: f.full_name, email: f.email, profile_photo_url: f.profile_photo_url, experience_years: +f.experience_years, consultation_fee: f.consultation_fee, specialization_id: +f.specialization_id, qualifications: [{ degree: f.degree, institution: f.institution || null }] });
  $('#fd').onsubmit = async e => {
    e.preventDefault(); const f = Object.fromEntries(new FormData(e.target)), b = e.submitter; b.disabled = true; b.textContent = 'Adding…';
    let u;
    try { u = await api('auth', '/auth/admin/doctors', { method: 'POST', body: { full_name: f.full_name, email: f.email, password: f.password } }) }
    catch (er) { b.disabled = false; b.textContent = 'Add doctor'; return toast(er.message, 1) }
    try { await api('doctor', '/doctors/', { method: 'POST', body: profileBody(f, u.id) }); delete cache.docs; toast(`${f.full_name} added. They can sign in now.`); adminPage('doctors') }
    catch (er) { b.disabled = false; b.textContent = 'Add doctor'; toast(`Login created (user ID ${u.id}) but the profile failed: ${er.message}. Fix it and use “Profile only”.`, 1); $('#f2 [name=auth_user_id]').value = u.id; $('#f2').closest('details').open = true }
  };
  $('#f2').onsubmit = async e => {
    e.preventDefault(); const fd = $('#fd'); if (!fd.reportValidity()) return;
    try { await api('doctor', '/doctors/', { method: 'POST', body: profileBody(Object.fromEntries(new FormData(fd)), +new FormData(e.target).get('auth_user_id')) }); delete cache.docs; toast('Doctor profile created'); adminPage('doctors') } catch (er) { toast(er.message, 1) }
  };
  $('#fs').onsubmit = async e => { e.preventDefault(); try { await api('doctor', '/specializations/', { method: 'POST', body: { name: new FormData(e.target).get('name') } }); delete cache.specs; toast('Speciality added'); adminPage('doctors') } catch (er) { toast(er.message, 1) } };
}
function editDoctor(d, specs, done) {
  const m = modal(`<h2>Edit ${esc(d.full_name)}</h2><form id="f" class="stack" style="max-width:none">
    <div class="two"><label>Full name<input name="full_name" value="${esc(d.full_name)}" required minlength="2"></label><label>Email<input name="email" type="email" value="${esc(d.email)}" required></label>
    <label>Speciality<select name="specialization_id">${specs.map(s => `<option value="${s.id}" ${s.id === d.specialization.id ? 'selected' : ''}>${esc(s.name)}</option>`).join('')}</select></label>
    <label>Experience (years)<input name="experience_years" type="number" min="0" value="${d.experience_years}" required></label>
    <label>Fee (₹)<input name="consultation_fee" type="number" min="0" step="1" value="${Number(d.consultation_fee)}" required></label></div>
    <label>Photo link<input name="profile_photo_url" type="url" value="${esc(d.profile_photo_url)}" required></label>
    <p class="mute small">Changing the email here changes the public profile only. The doctor still signs in with their original email.</p>
    <div class="row"><button type="button" class="btn ghost" id="x">Cancel</button><button class="btn">Save changes</button></div></form>`);
  $('#x', m).onclick = m.close;
  $('#f', m).onsubmit = async e => {
    e.preventDefault(); const f = Object.fromEntries(new FormData(e.target));
    try { await api('doctor', `/doctors/${d.id}`, { method: 'PATCH', body: { ...f, experience_years: +f.experience_years, specialization_id: +f.specialization_id } }); delete cache.docs; m.close(); toast('Doctor updated'); done() } catch (er) { toast(er.message, 1) }
  };
}
async function doctorHours(d) {
  const m = modal(`<h2>${esc(d.full_name)}: hours and leave</h2><div id="hb" class="mute">Loading…</div>`);
  try {
    const [av, lv] = await Promise.all([api('doctor', `/doctors/${d.id}/availability/`), api('doctor', `/doctors/${d.id}/leaves/`)]);
    const t5 = t => String(t).slice(0, 5);
    $('#hb', m).outerHTML = `<div class="week">${DAYS.map((n, i) => `<div class="wd"><b>${n.slice(0, 3)}</b>${av.filter(a => a.day_of_week === i).map(a => `<span class="hrs">${t5(a.start_time)}–${t5(a.end_time)}</span>`).join('') || '<span class="mute small">Off</span>'}</div>`).join('')}</div>
      <h3 style="margin-top:14px">Upcoming leave</h3>${lv.filter(l => l.end_date >= todayISO()).map(l => `<div>${l.start_date} to ${l.end_date}${l.reason ? ', ' + esc(l.reason) : ''}</div>`).join('') || '<p class="mute">None.</p>'}
      <p class="mute small">Doctors change these themselves under Hours and leave.</p>`;
  } catch (er) { $('#hb', m).textContent = er.message }
}

async function adminAppointments(el) {
  const docs = await api('doctor', '/doctors/'), dn = Object.fromEntries(docs.map(d => [d.id, d]));
  let day, doc = '', status = '';
  el.innerHTML = `<div class="panel"><div class="row wrap" style="justify-content:flex-start;gap:12px;margin-bottom:12px">
      <label>Doctor<select id="fdoc"><option value="">All doctors</option>${docs.map(d => `<option value="${d.id}">${esc(d.full_name)}</option>`).join('')}</select></label>
      <label>Status<select id="fst"><option value="">All</option><option value="booked">Booked</option><option value="confirmed">Confirmed</option><option value="completed">Completed</option><option value="cancelled">Cancelled</option></select></label></div>
    <div id="dn"></div><h2 id="dtitle" style="margin:16px 0 8px"></h2><div id="al"></div></div>`;
  const load = async () => {
    $('#al').innerHTML = skel(2, 'line');
    const list = await api('appointment', `/appointments/staff?date=${day}${doc ? '&doctor_id=' + doc : ''}${status ? '&status=' + status : ''}`);
    $('#dtitle').textContent = `${dLabel(day, { weekday: 'long', day: 'numeric', month: 'long' })} · ${plural(list.length, 'appointment')}`;
    $('#al').innerHTML = apptRows(list, { showDoctor: true, docs: dn }); bindApptActions($('#al'), () => { load(); nv.refresh() });
  };
  let nv;
  const mk = () => { nv = dateNav($('#dn'), { selected: day, counts: apptCounts(doc ? '&doctor_id=' + doc : ''), unit: 'booking', onPick: d => { day = d; load().catch(er => $('#al').innerHTML = `<div class="empty">${esc(er.message)}</div>`) } }) };
  $('#fdoc').onchange = e => { doc = e.target.value; mk() };
  $('#fst').onchange = e => { status = e.target.value; load() };
  mk();
}

async function adminPatients(el) {
  let users = await api('auth', '/auth/admin/users?role=patient');
  el.innerHTML = `<div class="panel"><div class="row wrap"><h2>Patients (${users.length})</h2><input class="search" id="pq" placeholder="Search name or email" style="max-width:280px"></div><div class="tbl" id="pl"></div>
    <p class="mute small" style="margin-top:10px">Blocked patients cannot sign in or book. Their existing bookings stay.</p></div>`;
  const draw = q => {
    const l = users.filter(u => !q || (u.full_name + ' ' + u.email).toLowerCase().includes(q));
    $('#pl').innerHTML = l.map(u => `<div class="tr pat"><div><b>${esc(u.full_name)}</b><div class="small"><a class="lnk" href="mailto:${esc(u.email)}">${esc(u.email)}</a></div></div>
      <div class="mute small">Joined ${new Date(u.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', timeZone: IST })}</div>
      <div>${u.is_active ? '<span class="tag booked">Active</span>' : '<span class="tag cancelled">Blocked</span>'}</div>
      <div class="acts"><button class="btn ghost sm" data-u="${u.id}" data-a="${!u.is_active}">${u.is_active ? 'Block' : 'Unblock'}</button></div></div>`).join('') || '<div class="empty">No patients match.</div>';
    $$('[data-u]').forEach(b => b.onclick = async () => { try { const r = await api('auth', `/auth/admin/users/${b.dataset.u}/active`, { method: 'PATCH', body: { is_active: b.dataset.a === 'true' } }); users = users.map(x => x.id === r.id ? r : x); toast(r.is_active ? 'Patient unblocked' : 'Patient blocked'); draw($('#pq').value.toLowerCase().trim()) } catch (er) { toast(er.message, 1) } });
  };
  $('#pq').oninput = e => draw(e.target.value.toLowerCase().trim()); draw('');
}

async function adminTests(el) {
  const tests = await api('lab', '/lab/admin/tests');
  const cats = [...new Set(tests.map(t => t.category))].sort();
  let q = '', cat = '', kind = '';
  el.innerHTML = `<div class="panel"><div class="row wrap" style="gap:10px"><h2 style="margin:0">Tests and packages (${tests.length})</h2>
      <div class="row wrap" style="gap:8px"><button class="btn lab sm" id="addt">Add test</button><button class="btn lab ghost sm" id="addp">Add package</button></div></div>
    <div class="row wrap" style="justify-content:flex-start;gap:10px;margin:12px 0"><input class="search" id="tq" placeholder="Search name or code" style="max-width:260px">
      <select id="tc" style="width:auto"><option value="">All categories</option>${cats.map(c => `<option>${esc(c)}</option>`).join('')}</select>
      <select id="tk" style="width:auto"><option value="">Tests and packages</option><option value="t">Single tests</option><option value="p">Packages</option><option value="off">Hidden from patients</option></select></div>
    <div class="tbl" id="tl"></div></div>`;
  const draw = () => {
    const l = tests.filter(t => (!q || (t.name + ' ' + t.code + ' ' + (t.also_known_as || '')).toLowerCase().includes(q)) && (!cat || t.category === cat)
      && (!kind || (kind === 't' ? !t.is_package : kind === 'p' ? t.is_package : !t.is_active)));
    $('#tl').innerHTML = l.map(t => `<div class="tr test-row ${t.is_active ? '' : 'dim'}"><div><b>${esc(t.name)}</b> ${t.is_package ? '<span class="fact pkg">Package</span>' : ''}${t.is_popular ? ' <span class="fact">Popular</span>' : ''}${t.is_active ? '' : ' <span class="tag cancelled">Hidden</span>'}
        <div class="mute small">${esc(t.code)} · ${esc(t.category)} · ${esc(t.sample_type)} · ${t.fasting_hours ? 'fasting ' + t.fasting_hours + ' hrs' : 'no fasting'} · report in ${t.report_hours} hrs</div></div>
      <div><b>${rs(t.price)}</b> <span class="strike">${rs(t.mrp)}</span></div>
      <div class="acts"><button class="btn ghost sm" data-e="${t.id}">Edit</button><button class="btn ghost sm" data-v="${t.id}">${t.is_active ? 'Hide' : 'Show'}</button></div></div>`).join('') || '<div class="empty">No tests match.</div>';
    $$('#tl [data-e]').forEach(b => b.onclick = () => testForm(tests, tests.find(t => t.id === +b.dataset.e)));
    $$('#tl [data-v]').forEach(b => b.onclick = async () => { const t = tests.find(x => x.id === +b.dataset.v); try { const r = await api('lab', `/lab/admin/tests/${t.id}`, { method: 'PATCH', body: { is_active: !t.is_active } }); Object.assign(t, r); delete cache.tests; toast(r.is_active ? 'Shown to patients' : 'Hidden from patients'); draw() } catch (er) { toast(er.message, 1) } });
  };
  $('#tq').oninput = e => { q = e.target.value.toLowerCase().trim(); draw() };
  $('#tc').onchange = e => { cat = e.target.value; draw() };
  $('#tk').onchange = e => { kind = e.target.value; draw() };
  $('#addt').onclick = () => testForm(tests, null, false);
  $('#addp').onclick = () => testForm(tests, null, true);
  draw();
}
function testForm(all, t, pkg = t?.is_package) {
  const v = (k, d = '') => esc(t ? t[k] ?? d : d), cats = [...new Set(all.map(x => x.category))].sort();
  const singles = all.filter(x => !x.is_package && x.is_active);
  const m = modal(`<h2>${t ? 'Edit ' + esc(t.name) : pkg ? 'Add a health package' : 'Add a lab test'}</h2><form id="f" class="stack" style="max-width:none">
    <div class="two"><label>Name<input name="name" required minlength="2" value="${v('name')}"></label>
      ${t ? `<label>Code<input value="${v('code')}" disabled></label>` : `<label>Code (capitals, unique)<input name="code" required pattern="[A-Z0-9_]{2,40}" placeholder="${pkg ? 'PKG_MONSOON' : 'VIT_D3'}"></label>`}
      <label>Category<input name="category" required list="cats" value="${v('category')}"><datalist id="cats">${cats.map(c => `<option>${esc(c)}</option>`).join('')}</datalist></label>
      <label>${pkg ? 'Short summary' : 'Also called'}<input name="also_known_as" value="${v('also_known_as')}" placeholder="${pkg ? '6 tests' : 'Other names patients search for'}"></label>
      <label>Price (₹)<input name="price" type="number" min="1" step="1" required value="${t ? Number(t.price) : ''}"></label><label>MRP (₹)<input name="mrp" type="number" min="1" step="1" required value="${t ? Number(t.mrp) : ''}"></label>
      <label>Sample<input name="sample_type" value="${v('sample_type', 'Blood')}" required></label><label>Fasting (hours, 0 if none)<input name="fasting_hours" type="number" min="0" max="24" value="${v('fasting_hours', 0)}"></label>
      <label>Report in (hours)<input name="report_hours" type="number" min="1" value="${v('report_hours', 24)}"></label><label class="ck" style="align-self:end"><input type="checkbox" name="is_popular" ${t?.is_popular ? 'checked' : ''}>Show as popular</label></div>
    <label>Description<textarea name="description" rows="2" maxlength="2000">${v('description')}</textarea></label>
    <label>Preparation<input name="preparation" maxlength="1000" value="${v('preparation')}" placeholder="No special preparation needed."></label>
    ${pkg ? `<fieldset class="pick"><legend>Tests in this package</legend><input class="search" id="pf" placeholder="Filter tests"><div class="picklist">${singles.map(s => `<label class="ck"><input type="checkbox" name="inc" value="${esc(s.code)}" ${t?.included_codes.includes(s.code) ? 'checked' : ''}>${esc(s.name)} <span class="n">${rs(s.price)}</span></label>`).join('')}</div><p class="mute small" id="pinfo"></p></fieldset>`
      : `<label>What it measures (one per line)<textarea name="parameters" rows="3">${t ? esc(t.parameters.join('\n')) : ''}</textarea></label>`}
    <div class="row"><button type="button" class="btn ghost" id="x">Cancel</button><button class="btn lab">${t ? 'Save changes' : pkg ? 'Add package' : 'Add test'}</button></div></form>`);
  $('#x', m).onclick = m.close;
  if (pkg) {
    const info = () => { const c = $$('[name=inc]:checked', m), sum = c.reduce((s, x) => s + +singles.find(y => y.code === x.value).price, 0); $('#pinfo', m).textContent = `${plural(c.length, 'test')} selected, ₹${sum.toLocaleString('en-IN')} if bought separately.` };
    $$('[name=inc]', m).forEach(c => c.onchange = info); info();
    $('#pf', m).oninput = e => { const q = e.target.value.toLowerCase(); $$('.picklist label', m).forEach(l => l.hidden = !l.textContent.toLowerCase().includes(q)) };
  }
  $('#f', m).onsubmit = async e => {
    e.preventDefault(); const fd = new FormData(e.target), b = {};
    ['name', 'code', 'category', 'also_known_as', 'sample_type', 'description', 'preparation'].forEach(k => { if (fd.has(k)) b[k] = fd.get(k).trim() || (k === 'also_known_as' ? null : '') });
    ['price', 'mrp'].forEach(k => b[k] = fd.get(k)); ['fasting_hours', 'report_hours'].forEach(k => b[k] = +fd.get(k));
    b.is_popular = fd.has('is_popular');
    if (pkg) b.included_codes = fd.getAll('inc'); else b.parameters = String(fd.get('parameters') || '').split('\n').map(s => s.trim()).filter(Boolean);
    if (!t) b.is_package = !!pkg;
    try { await api('lab', t ? `/lab/admin/tests/${t.id}` : '/lab/admin/tests', { method: t ? 'PATCH' : 'POST', body: b }); delete cache.tests; m.close(); toast(t ? 'Saved' : pkg ? 'Package added' : 'Test added'); adminPage('tests') } catch (er) { toast(er.message, 1) }
  };
}

async function adminLabBookings(el) {
  let status = '', day = '';
  el.innerHTML = `<div class="panel"><div class="row wrap" style="justify-content:flex-start;gap:12px;margin-bottom:12px"><label>Status<select id="fs"><option value="">All</option>${LAB_STEPS.concat([['cancelled', 'Cancelled']]).map(([v, l]) => `<option value="${v}">${l}</option>`).join('')}</select></label>
    <label class="ck" style="align-self:end"><input type="checkbox" id="alld">Show all dates</label></div><div id="dn"></div><h2 id="dtitle" style="margin:16px 0 8px"></h2><div id="ll"></div></div>`;
  const load = async () => {
    $('#ll').innerHTML = skel(2, 'line');
    const qs = new URLSearchParams(Object.entries({ status, date: day }).filter(([, v]) => v)).toString();
    const list = await api('lab', '/lab/admin/bookings' + (qs ? '?' + qs : ''));
    $('#dtitle').textContent = (day ? dLabel(day, { weekday: 'long', day: 'numeric', month: 'long' }) : 'All dates') + ' · ' + plural(list.length, 'booking');
    $('#ll').innerHTML = list.length ? list.map(b => `<div class="bk">${whenBox(b.slot_start)}<div><b>${esc(b.patient_name)}</b>, <a class="lnk" href="tel:${esc(b.contact_phone)}">${esc(b.contact_phone)}</a> <span class="tag ${b.status}">${b.status.replace('_', ' ')}</span>
        <div class="small">${esc(b.items.map(x => x.name).join(', '))}</div><div class="mute small">${b.collection_type === 'home' ? 'Home: ' + esc(b.address) + ' ' + esc(b.pincode) : esc(b.centre?.name || '')}. ${rs(b.total)}${+b.collection_fee ? ' incl. ' + rs(b.collection_fee) + ' collection' : ''}. Booking L${b.id}</div>
        ${b.items.some(i => i.fasting_hours) ? '<div class="small" style="color:var(--warn)">Fasting test</div>' : ''}${b.report_url ? `<a class="small lnk" href="${esc(b.report_url)}" target="_blank" rel="noopener">Open report</a>` : ''}${b.cancellation_reason ? `<div class="mute small">Cancelled: ${esc(b.cancellation_reason)}</div>` : ''}</div>
        <div class="acts">${b.status === 'booked' ? `<button class="btn lab sm" data-s="${b.id}" data-v="sample_collected">Sample collected</button>` : ''}${b.status === 'sample_collected' ? `<button class="btn lab sm" data-s="${b.id}" data-v="processing">Processing</button>` : ''}
        ${['sample_collected', 'processing'].includes(b.status) ? `<button class="btn lab ghost sm" data-rep="${b.id}">Add report link</button>` : ''}${b.status === 'booked' ? `<button class="btn ghost sm" data-s="${b.id}" data-v="cancelled">Cancel</button>` : ''}</div></div>`).join('') : '<div class="empty">No lab bookings match.</div>';
    $$('[data-s]').forEach(x => x.onclick = async () => { try { await api('lab', `/lab/admin/bookings/${x.dataset.s}`, { method: 'PATCH', body: { status: x.dataset.v } }); toast('Booking updated'); load() } catch (er) { toast(er.message, 1) } });
    $$('[data-rep]').forEach(x => x.onclick = () => {
      const m = modal(`<h2>Add report link</h2><p class="mute">Upload the report PDF somewhere the patient can open it (for example Google Drive with link sharing on) and paste the link. The booking is then marked report ready.</p><form id="f" class="stack"><label>Report link<input name="u" type="url" required placeholder="https://"></label><button class="btn lab">Save and mark ready</button></form>`);
      $('#f', m).onsubmit = async e => { e.preventDefault(); try { await api('lab', `/lab/admin/bookings/${x.dataset.rep}`, { method: 'PATCH', body: { report_url: new FormData(e.target).get('u') } }); m.close(); toast('Report added'); load() } catch (er) { toast(er.message, 1) } };
    });
  };
  const labCounts = async (from, to) => {
    const all = await api('lab', '/lab/admin/bookings'), c = {};
    all.filter(b => b.status !== 'cancelled').forEach(b => { const d = istDate(new Date(b.slot_start)); if (d >= from && d <= to) c[d] = (c[d] || 0) + 1 });
    return c;
  };
  dateNav($('#dn'), { counts: labCounts, onPick: d => { day = d; $('#alld').checked = false; load() } });
  $('#fs').onchange = e => { status = e.target.value; load() };
  $('#alld').onchange = e => { day = e.target.checked ? '' : todayISO(); load() };
}

async function adminCentres(el) {
  const centres = await api('lab', '/lab/admin/centres');
  const field = (c, n, l, t = 'text', x = '') => `<label>${l}<input name="${n}" type="${t}" value="${esc(c?.[n] ?? '')}" ${x}></label>`;
  const form = c => `<div class="two">${field(c, 'name', 'Name', 'text', 'required minlength=2')}${field(c, 'phone', 'Phone (optional)', 'tel')}</div>${field(c, 'address', 'Address', 'text', 'required minlength=5')}
    <div class="two">${field(c, 'city', 'City', 'text', 'required')}${field(c, 'pincode', 'Pincode', 'text', 'required pattern="\\d{6}" inputmode="numeric"')}${field(c, 'opens', 'Opens', 'time', 'required')}${field(c, 'closes', 'Closes', 'time', 'required')}</div>`;
  el.innerHTML = `<div class="split"><div class="panel"><h2>Centres (${centres.filter(c => c.is_active).length} open)</h2><div class="tbl">${centres.map(c => `<div class="tr centre ${c.is_active ? '' : 'dim'}"><div><b>${esc(c.name)}</b>${c.is_active ? '' : ' <span class="tag cancelled">Closed</span>'}<div class="small">${esc(c.address)}, ${esc(c.city)} ${esc(c.pincode)}</div><div class="mute small">Open ${c.opens} to ${c.closes}${c.phone ? ' · ' + esc(c.phone) : ''}</div></div>
      <div class="acts"><button class="btn ghost sm" data-e="${c.id}">Edit</button><button class="btn ghost sm" data-t="${c.id}">${c.is_active ? 'Close' : 'Reopen'}</button></div></div>`).join('') || '<div class="empty">No centres yet.</div>'}</div></div>
    <div class="panel"><h2>Add a centre</h2><form id="fc" class="stack" style="max-width:none">${form({ opens: '07:00', closes: '19:00' })}<button class="btn lab">Add centre</button></form></div></div>`;
  const body = f => { const b = {}; new FormData(f).forEach((v, k) => b[k] = v.trim() || null); return b };
  $('#fc').onsubmit = async e => { e.preventDefault(); try { await api('lab', '/lab/admin/centres', { method: 'POST', body: body(e.target) }); toast('Centre added'); adminPage('centres') } catch (er) { toast(er.message, 1) } };
  $$('[data-t]').forEach(b => b.onclick = async () => { const c = centres.find(x => x.id === +b.dataset.t); try { await api('lab', `/lab/admin/centres/${c.id}`, { method: 'PATCH', body: { is_active: !c.is_active } }); toast(c.is_active ? 'Centre closed' : 'Centre reopened'); adminPage('centres') } catch (er) { toast(er.message, 1) } });
  $$('[data-e]').forEach(b => b.onclick = () => {
    const c = centres.find(x => x.id === +b.dataset.e);
    const m = modal(`<h2>Edit centre</h2><form id="f" class="stack" style="max-width:none">${form(c)}<div class="row"><button type="button" class="btn ghost" id="x">Cancel</button><button class="btn lab">Save changes</button></div></form>`);
    $('#x', m).onclick = m.close;
    $('#f', m).onsubmit = async e => { e.preventDefault(); try { await api('lab', `/lab/admin/centres/${c.id}`, { method: 'PATCH', body: body(e.target) }); m.close(); toast('Centre updated'); adminPage('centres') } catch (er) { toast(er.message, 1) } };
  });
}
