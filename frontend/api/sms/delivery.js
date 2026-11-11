// POST /api/sms/delivery. Africa's Talking tells us whether a text reached the phone. Nothing is stored here.
import { readForm, tokenOk } from '../_lib/at.js'

export default async function handler(req, res) {
  res.setHeader('Content-Type', 'text/plain; charset=utf-8')
  if (req.method !== 'POST') return res.status(405).send('Use POST.')
  if (!tokenOk(req)) return res.status(403).send('Not allowed.')
  const form = await readForm(req)
  console.log('sms delivery', form.status, form.failureReason || '')
  res.status(200).send('OK')
}
