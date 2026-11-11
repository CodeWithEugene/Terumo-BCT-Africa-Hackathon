// The USSD menu and SMS replies, run from the precomputed data (scripts/export_ussd_data.py).
// Same screens as backend/api/ussd.py. Accepting an order needs the app, because this host keeps no database.
import data from '../_data/ussd-data.js'
import { allowSend, configured, normalise, openLookup, sendSms, staffPhones } from './at.js'

const PAGE = 5
const LIMIT = 182
const MORE = '98'
const BACK = 'That choice is not on the screen.\n0. Back'

const con = (t) => 'CON ' + fit(t)
const end = (t) => 'END ' + fit(t)
const fit = (t) => (t.length <= LIMIT ? t : t.slice(0, LIMIT - 1).trimEnd() + '…')
const units = (n) => `${n} unit${n === 1 ? '' : 's'}`
const days = (n) => `${Math.round(n * 10) / 10} day${Math.round(n * 10) / 10 === 1 ? '' : 's'}`

const CUTS = [' County Referral Hospital', ' Teaching and Referral Hospital', ' Level 5 Hospital', ' Sub-County Hospital',
  ' County Hospital', ' Referral Hospital', ' Mission Hospital', ' Private Hospital', ' Hospital']
const short = (name) => CUTS.reduce((n, c) => n.replace(c, ''), name)
const hospitalIds = () => Object.keys(data.hospitals).sort()

export const identify = (phone) => {
  const username = staffPhones()[normalise(phone)]
  const user = username && data.users[username]
  if (user) return { phone, user: { username, ...user } }
  return openLookup() ? { phone, user: null } : null
}

const scopeOf = (caller) => {
  if (!caller.user) return hospitalIds()
  if (caller.user.role === 'hospital_officer') return [caller.user.facility]
  return hospitalIds().filter((id) => data.hospitals[id].centre === caller.user.facility)
}

// `0` goes back one step, `00` goes home.
export const steps = (text = '') => {
  const path = []
  for (const raw of text ? text.split('*') : []) {
    const t = raw.trim()
    if (t === '00') path.length = 0
    else if (t === '0') path.pop()
    else if (t) path.push(t)
  }
  return path
}

// A numbered, paged list. Returns {screen} to show, or {chosen, rest} once a choice is made.
const pick = (options, path, title, line) => {
  let page = 0
  const rest = [...path]
  while (rest[0] === MORE) { page++; rest.shift() }
  const last = Math.max(0, Math.floor((options.length - 1) / PAGE))
  page = Math.min(page, last)
  const shown = options.slice(page * PAGE, (page + 1) * PAGE)
  if (!rest.length) {
    const lines = [title, ...shown.map((o, i) => `${i + 1}. ${line(o)}`)]
    if (page < last) lines.push(`${MORE}. More`)
    lines.push('0. Back')
    return { screen: con(lines.join('\n')) }
  }
  const n = Number(rest[0])
  if (/^\d+$/.test(rest[0]) && n >= 1 && n <= shown.length) return { chosen: shown[n - 1], rest: rest.slice(1) }
  return { screen: con(BACK) }
}

export const ussd = async (phone, text) => {
  try {
    const caller = identify(phone)
    if (!caller) return end('This number is not registered for Providus. Ask your blood bank lead to add it.')
    return await route(caller, steps(text))
  } catch {
    return end('Providus is not available right now. Please try again, or open the app.')
  }
}

const route = async (caller, path) => {
  const u = caller.user
  if (u && u.role === 'hospital_officer') return hospital(caller, u.facility, path)
  const list = scopeOf(caller)
  if (u && !path.length) return con(`Providus ${short(data.hospitals[u.facility]?.name || 'regional centre')}\n1. Hospitals needing action\n2. Choose a hospital`)
  if (!u) return choose(caller, list, path)
  if (path[0] === '1') return needing(caller, list, path.slice(1))
  if (path[0] === '2') return choose(caller, list, path.slice(1))
  return con(BACK)
}

const choose = async (caller, list, path) => {
  const r = pick(list, path, caller.user ? 'Choose a hospital' : 'Providus (demo, view only)\nChoose a hospital',
    (id) => short(data.hospitals[id].name).slice(0, 26))
  return r.screen ?? hospital(caller, r.chosen, r.rest)
}

const needing = async (caller, list, path) => {
  const flagged = list.map((id) => {
    const g = data.hospitals[id].products.RBC?.groups || []
    return [id, g.filter((x) => x.status === 'act').length, g.filter((x) => x.status === 'watch').length]
  }).filter((r) => r[1] || r[2]).sort((a, b) => b[1] - a[1] || b[2] - a[2])
  if (!flagged.length) return con('No hospital needs action or watching today.\n0. Back')
  const r = pick(flagged, path, 'Needing action (Act/Watch)', (x) => `${short(data.hospitals[x[0]].name).slice(0, 18)} ${x[1]}A ${x[2]}W`)
  return r.screen ?? hospital(caller, r.chosen[0], r.rest)
}

const hospital = async (caller, id, path) => {
  const h = data.hospitals[id]
  if (!path.length) return con(`${short(h.name).slice(0, 30)}\n1. Today's alert\n2. Cover by blood group\n3. Suggested orders\n4. Text me the alert\n0. Back`)
  const [first, ...rest] = path
  if (first === '1') return alert(h)
  if (first === '2') return cover(h, rest)
  if (first === '3') return orders(caller, h, rest)
  if (first === '4') return textMe(caller, id, h)
  return con(BACK)
}

const alert = (h) => {
  const g = h.products.RBC?.groups
  if (!g?.length) return con('This hospital does not hold red cells. Requests are filled from the regional centre.\n0. Back')
  const act = g.filter((x) => x.status === 'act').map((x) => x.group)
  const watch = g.filter((x) => x.status === 'watch').map((x) => x.group)
  const lines = [data.day, h.summary]
  if (act.length) lines.push('ACT: ' + act.join(' '))
  if (watch.length) lines.push('WATCH: ' + watch.join(' '))
  const d = g.find((x) => x.delivery)?.delivery
  if (d) lines.push(`Next delivery ${d}`)
  lines.push('0. Back')
  return con(lines.join('\n'))
}

const coverLine = (x) => `${x.group} ${x.statusLabel} ${x.cover == null ? 'none' : x.capped ? '14+d' : x.cover.toFixed(1) + 'd'}`

const cover = (h, path) => {
  const held = Object.entries(h.products)
  if (!held.length) return con('No blood products are held here.\n0. Back')
  const a = pick(held, path, 'Which product?', ([, p]) => p.label)
  if (a.screen) return a.screen
  const [, product] = a.chosen
  const b = pick(product.groups, a.rest, `${product.label} cover (days)`, coverLine)
  if (b.screen) return b.screen
  const x = b.chosen
  const c = x.cover == null ? 'no use expected' : x.capped ? '14+ days of cover' : `${days(x.cover)} of cover`
  const lines = [`${x.group} ${product.label}: ${x.statusLabel}`, `${units(x.shelf)} on shelf, ${c}`]
  if (x.stockout) lines.push(`Likely short from ${x.stockout}`)
  if (x.delivery) lines.push(`Next delivery ${x.delivery}`)
  if (x.quantity) lines.push(`Suggested: ${units(x.quantity)}`)
  lines.push('0. Back')
  return con(lines.join('\n'))
}

const orders = (caller, h, path) => {
  const g = (h.products.RBC?.groups || []).filter((x) => ['act', 'watch'].includes(x.status) && x.quantity)
  if (!g.length) return con('No order is suggested today.\n0. Back')
  const r = pick(g, path, 'Suggested orders (red cells)', (x) => `${x.group} ${units(x.quantity)}`)
  if (r.screen) return r.screen
  const x = r.chosen
  return con(`${x.group}: ${x.title}\n${x.sum}\nTo accept, open the app and sign in.\n0. Back`)
}

const textMe = async (caller, id, h) => {
  if (!configured()) return end('SMS is not set up on this server yet.')
  if (!allowSend(caller.phone)) return end('You have asked for several texts already. Try again in an hour.')
  if (!h.alert) return end('This hospital does not hold red cells, so there is no alert to send.')
  const r = await sendSms([caller.phone], h.alert)
  return end(r.ok ? 'The alert is on its way to your phone.' : 'The text could not be sent. Try again later.')
}

// --- SMS replies, under 160 characters ---
const HELP = 'Providus SMS. Text ALERT, COVER O-, ORDERS or HOSPITALS. Add a hospital name to look one up, e.g. ALERT Thika.'
const GROUPS = ['O+', 'A+', 'B+', 'AB+', 'O-', 'A-', 'B-', 'AB-']

const findHospital = (caller, query, home) => {
  if (!query) return home ? { id: home } : { problem: 'Add a hospital name, e.g. ALERT Thika.' }
  const hits = scopeOf(caller).filter((id) => data.hospitals[id].name.toLowerCase().includes(query.toLowerCase()))
  if (hits.length === 1) return { id: hits[0] }
  if (!hits.length) return { problem: 'No hospital matches that name.' }
  return { problem: 'Be more specific: ' + hits.slice(0, 4).map((id) => short(data.hospitals[id].name).slice(0, 14)).join(', ') + '.' }
}

export const smsReply = (phone, text) => {
  const caller = identify(phone)
  if (!caller) return 'This number is not registered for Providus.'
  const w = String(text || '').trim().split(/\s+/).filter(Boolean)
  const command = (w[0] || 'HELP').toUpperCase()
  const home = caller.user?.role === 'hospital_officer' ? caller.user.facility : null
  const swap = (s) => s.toUpperCase().replace('POS', '+').replace('NEG', '-')
  if (['ALERT', 'BRIEF', 'STATUS'].includes(command)) {
    const f = findHospital(caller, w.slice(1).join(' '), home)
    return f.problem || data.hospitals[f.id].alert || 'That hospital does not hold red cells.'
  }
  if (command === 'COVER') {
    const group = w.slice(1).map(swap).find((x) => GROUPS.includes(x))
    if (!group) return 'Text COVER and a group, e.g. COVER O- or COVER A+ Thika.'
    const f = findHospital(caller, w.slice(1).filter((x) => swap(x) !== group).join(' '), home)
    if (f.problem) return f.problem
    const h = data.hospitals[f.id]
    const x = h.products.RBC?.groups.find((g) => g.group.replace('−', '-') === group)
    if (!x) return `${short(h.name).slice(0, 20)} does not hold ${group} red cells.`
    const c = x.cover == null ? 'no use' : x.capped ? '14+ days' : days(x.cover)
    return `${short(h.name).slice(0, 18)} ${x.group}: ${x.statusLabel}. ${x.shelf} units, cover ${c}.${x.delivery ? ` Next delivery ${x.delivery}.` : ''}`.slice(0, 160)
  }
  if (command === 'ORDERS') {
    const f = findHospital(caller, w.slice(1).join(' '), home)
    if (f.problem) return f.problem
    const g = (data.hospitals[f.id].products.RBC?.groups || []).filter((x) => ['act', 'watch'].includes(x.status) && x.quantity)
    return g.length ? `Suggested units: ${g.map((x) => `${x.group} ${x.quantity}`).join(', ')}. Open the app to accept or change.`.slice(0, 160) : 'No order is suggested today.'
  }
  if (command === 'HOSPITALS') {
    const flagged = scopeOf(caller).map((id) => [(data.hospitals[id].products.RBC?.groups || []).filter((x) => x.status === 'act').length, short(data.hospitals[id].name).slice(0, 14)])
      .filter((r) => r[0]).sort((a, b) => b[0] - a[0])
    return flagged.length ? ('Act today: ' + flagged.slice(0, 6).map(([n, name]) => `${name} ${n}`).join(', ')).slice(0, 160) : 'No hospital needs action today.'
  }
  return HELP.slice(0, 160)
}
