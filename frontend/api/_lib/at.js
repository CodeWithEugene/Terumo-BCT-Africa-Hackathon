// Africa's Talking helpers for the Vercel functions: settings, phone numbers, callback check, sending texts.
// Settings (Vercel, Project, Settings, Environment Variables): AT_API_KEY, AT_USERNAME, AT_CALLBACK_TOKEN,
// SP_STAFF_PHONES (254712345678=amina,254700000001=grace), SP_USSD_OPEN (1 or 0), optional AT_SENDER_ID.

export const normalise = (phone = '') => {
  let d = String(phone).replace(/\D/g, '')
  if (d.startsWith('0') && d.length === 10) d = '254' + d.slice(1)
  else if (d.length === 9) d = '254' + d
  return d
}

export const staffPhones = () => {
  const out = {}
  for (const item of (process.env.SP_STAFF_PHONES || '').split(',')) {
    const [phone, name] = item.split('=')
    if (phone && name && normalise(phone)) out[normalise(phone)] = name.trim().toLowerCase()
  }
  return out
}

export const openLookup = () => (process.env.SP_USSD_OPEN ?? '1') !== '0'
export const configured = () => Boolean(process.env.AT_API_KEY && process.env.AT_USERNAME)

// Africa's Talking does not sign callbacks, so a secret token on the address is the check.
export const tokenOk = (req) => {
  const expected = process.env.AT_CALLBACK_TOKEN
  if (!expected) return true
  const url = new URL(req.url, 'http://x')
  return url.searchParams.get('token') === expected
}

// Vercel parses form posts into req.body. Fall back to reading the raw text if it did not.
export const readForm = async (req) => {
  if (req.body && typeof req.body === 'object' && !Buffer.isBuffer(req.body)) return req.body
  const raw = typeof req.body === 'string' ? req.body : Buffer.isBuffer(req.body) ? req.body.toString() : await new Promise((ok) => {
    let s = ''
    req.on('data', (c) => (s += c))
    req.on('end', () => ok(s))
  })
  return Object.fromEntries(new URLSearchParams(raw))
}

const recent = new Map()
// A small guard against running up the SMS bill. It resets when the function restarts, which is acceptable here.
export const allowSend = (phone, limit = 4, windowMs = 3600_000) => {
  const key = normalise(phone)
  const now = Date.now()
  const list = (recent.get(key) || []).filter((t) => now - t < windowMs)
  if (list.length >= limit) return false
  list.push(now)
  recent.set(key, list)
  return true
}

// Never throws. A gateway outage must not break the menu.
export const sendSms = async (to, message) => {
  if (!configured()) return { ok: false, note: 'SMS is not set up on this server.' }
  const username = process.env.AT_USERNAME
  const body = new URLSearchParams({ username, to: to.map((p) => '+' + normalise(p)).join(','), message: message.slice(0, 160) })
  if (process.env.AT_SENDER_ID) body.set('from', process.env.AT_SENDER_ID)
  const url = username === 'sandbox'
    ? 'https://api.sandbox.africastalking.com/version1/messaging'
    : 'https://api.africastalking.com/version1/messaging'
  try {
    const res = await fetch(url, {
      method: 'POST', body, signal: AbortSignal.timeout(6000),
      headers: { apiKey: process.env.AT_API_KEY, Accept: 'application/json', 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    const json = await res.json()
    const rows = json?.SMSMessageData?.Recipients || []
    const good = rows.filter((r) => String(r.status).toLowerCase() === 'success' || [100, 101, 102].includes(r.statusCode))
    return { ok: good.length > 0, note: good.length ? 'Sent.' : 'The gateway refused the message.' }
  } catch {
    return { ok: false, note: 'The message was not sent. The SMS gateway did not answer.' }
  }
}
