// POST /api/sms/incoming. A staff member texted us. We answer by text, then reply 200 to the gateway.
import { readForm, sendSms, tokenOk } from '../_lib/at.js'
import { smsReply } from '../_lib/menu.js'

export default async function handler(req, res) {
  res.setHeader('Content-Type', 'text/plain; charset=utf-8')
  if (req.method !== 'POST') return res.status(405).send('Use POST.')
  if (!tokenOk(req)) return res.status(403).send('Not allowed.')
  const form = await readForm(req)
  if (form.from) await sendSms([form.from], smsReply(form.from, form.text || ''))
  res.status(200).send('OK')
}
