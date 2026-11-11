// POST /api/ussd, the callback for *384*11400#. Replies start with CON (continue) or END (finish).
import { readForm, tokenOk } from './_lib/at.js'
import { ussd } from './_lib/menu.js'

export default async function handler(req, res) {
  res.setHeader('Content-Type', 'text/plain; charset=utf-8')
  if (req.method !== 'POST') return res.status(405).send('Use POST.')
  if (!tokenOk(req)) return res.status(403).send('Not allowed.')
  const form = await readForm(req)
  res.status(200).send(await ussd(form.phoneNumber || '', form.text || ''))
}
