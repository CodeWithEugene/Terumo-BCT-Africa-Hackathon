import { motion, useMotionValue, useReducedMotion, useScroll, useTransform, type MotionValue } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { Logo } from '../components/Shell'
import { Tube, TubesBackdrop } from '../components/Tubes'
import { t } from '../i18n/en'
import { api } from '../lib/api'
import type { ModeInfo, User } from '../types'
import { SignInPanel } from './SignIn'

type Facts = Record<string, string>

/**
 * The blood bag, drawn by us in SVG: outline, ports, label, tubing, a deep red
 * fill with a soft highlight. `level` (0 to 1) is how full it is. The scale on
 * the right reads in days of cover. This red is the one place red is used
 * outside the "Act" status.
 */
function BloodBag({ level }: { level: MotionValue<number> | number }) {
  const top = 86
  const bottom = 356
  const fixed = useMotionValue(typeof level === 'number' ? level : 0)
  const source = typeof level === 'number' ? fixed : level
  const fillY = useTransform(source, (v) => bottom - (bottom - top) * v)
  const fillH = useTransform(source, (v) => (bottom - top) * v + 30)
  return (
    <svg viewBox="0 0 340 470" className="h-full w-full overflow-visible" aria-hidden="true">
      <defs>
        <linearGradient id="blood" x1="0" x2="1">
          <stop offset="0" stopColor="#7d1414" />
          <stop offset="0.45" stopColor="#a11d1d" />
          <stop offset="1" stopColor="#6b0f0f" />
        </linearGradient>
        <linearGradient id="glass" x1="0" x2="1">
          <stop offset="0" stopColor="#ffffff" stopOpacity="0.55" />
          <stop offset="0.5" stopColor="#ffffff" stopOpacity="0" />
        </linearGradient>
        <clipPath id="bag-inside">
          <path d="M62 70h136a26 26 0 0 1 26 26v236a40 40 0 0 1-40 40H76a40 40 0 0 1-40-40V96a26 26 0 0 1 26-26z" />
        </clipPath>
      </defs>
      {/* hanger and ports */}
      <rect x="112" y="14" width="36" height="12" rx="6" fill="none" stroke="#141b4d" strokeOpacity="0.45" strokeWidth="2" />
      <path d="M84 70V46h22v24M154 70V46h22v24" fill="#f4f6fa" stroke="#141b4d" strokeOpacity="0.4" strokeWidth="2" />
      <path d="M52 70V34a8 8 0 0 1 8-8h140a8 8 0 0 1 8 8v36" fill="none" stroke="#141b4d" strokeOpacity="0.4" strokeWidth="2" />
      {/* bag body */}
      <path d="M62 70h136a26 26 0 0 1 26 26v236a40 40 0 0 1-40 40H76a40 40 0 0 1-40-40V96a26 26 0 0 1 26-26z" fill="#fbfcfe" stroke="#141b4d" strokeOpacity="0.5" strokeWidth="2.5" />
      <g clipPath="url(#bag-inside)">
        <motion.rect x="30" width="200" y={fillY} height={fillH} fill="url(#blood)" />
        <motion.rect x="30" width="200" y={fillY} height="5" fill="#c94a4a" opacity="0.7" />
        <rect x="36" y="70" width="70" height="310" fill="url(#glass)" />
      </g>
      {/* label */}
      <rect x="66" y="150" width="128" height="96" rx="6" fill="white" stroke="#141b4d" strokeOpacity="0.3" />
      <text x="80" y="188" fontSize="30" fontWeight="600" fill="#141b4d">O+</text>
      <path d="M80 204h100M80 216h76M80 228h88" stroke="#141b4d" strokeOpacity="0.3" strokeWidth="3" strokeLinecap="round" />
      {/* tubing */}
      <path d="M130 372v26c0 26 44 16 44 44v22" fill="none" stroke="#141b4d" strokeOpacity="0.4" strokeWidth="5" strokeLinecap="round" />
      {/* scale: days of cover */}
      {[0, 7, 14].map((d) => {
        const y = bottom - ((bottom - top) * d) / 14
        return (
          <g key={d}>
            <path d={`M232 ${y}h14`} stroke="#141b4d" strokeWidth="2" />
            <text x="252" y={y + 5} fontSize="15" fontWeight="500" fill="#141b4d">{d}</text>
          </g>
        )
      })}
      <text x="232" y={top - 16} fontSize="12.5" fill="#595959">{t.landing.cover}</text>
    </svg>
  )
}

function Beat({ index, facts }: { index: number; facts: Facts }) {
  const beat = t.landing.beats[index]
  const pct = Number(facts.requests_not_fully_met_pct ?? 0)
  const oneIn = pct > 0 ? Math.round(100 / pct) : 0
  const title = index === 0 ? beat.title(oneIn) : (beat.title as () => string)()
  const text =
    index === 0
      ? (beat.text as (h: string, r: string) => string)(facts.emergency_median_hours ?? '–', Number(facts.requests ?? 0).toLocaleString('en-GB'))
      : index === 1
        ? (beat.text as (d: string) => string)(String(Math.round(Number(facts.collections_drop_in_breaks_pct ?? 0))))
        : (beat.text as () => string)()
  return (
    <>
      <p className="flex items-center gap-3 text-xs font-medium tracking-[0.08em] text-muted uppercase">
        {String(index + 1).padStart(2, '0')} · {beat.label}
        <span className="h-px w-16 bg-line" aria-hidden="true" />
      </p>
      <h2 className="mt-4 max-w-[15ch] text-[clamp(2rem,5.4vw,4rem)] leading-[1.05] font-semibold tracking-[-0.015em] text-ink">{title}</h2>
      <p className="mt-5 max-w-[46ch] text-base leading-relaxed">{text}</p>
    </>
  )
}

/** Desktop and tablet: a pinned stage. The headline changes per beat, the bag fills and tilts, tubes drift at different depths. */
function ScrollStory({ facts }: { facts: Facts }) {
  const ref = useRef<HTMLDivElement>(null)
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start start', 'end end'] })
  const level = useTransform(scrollYProgress, [0, 0.3, 0.62, 1], [0.12, 0.2, 0.62, 1])
  const tiltY = useTransform(scrollYProgress, [0, 0.5, 1], [-16, 6, -6])
  const tiltX = useTransform(scrollYProgress, [0, 1], [7, -3])
  const glowX = useTransform(scrollYProgress, [0, 1], ['-8%', '18%'])
  const near = useTransform(scrollYProgress, [0, 1], [60, -220])
  const mid = useTransform(scrollYProgress, [0, 1], [30, -110])
  const far = useTransform(scrollYProgress, [0, 1], [10, -40])
  const spin = useTransform(scrollYProgress, [0, 1], [-6, 8])
  const opacities = [
    useTransform(scrollYProgress, [0, 0.26, 0.34], [1, 1, 0]),
    useTransform(scrollYProgress, [0.3, 0.38, 0.6, 0.68], [0, 1, 1, 0]),
    useTransform(scrollYProgress, [0.64, 0.72, 1], [0, 1, 1]),
  ]
  const shifts = [
    useTransform(scrollYProgress, [0.26, 0.34], [0, -24]),
    useTransform(scrollYProgress, [0.3, 0.38, 0.6, 0.68], [24, 0, 0, -24]),
    useTransform(scrollYProgress, [0.64, 0.72], [24, 0]),
  ]
  return (
    <div ref={ref} className="relative h-[360vh]">
      <div className="sticky top-0 flex h-dvh items-center overflow-hidden">
        <motion.div className="pointer-events-none absolute top-[12%] left-0 h-[55vh] w-[60vw] rounded-full bg-sky-soft opacity-80 blur-[90px]" style={{ x: glowX }} aria-hidden="true" />
        {/* tubes at three depths: further back is smaller, fainter and slightly blurred */}
        <div className="pointer-events-none absolute inset-0" style={{ perspective: 900 }} aria-hidden="true">
          <motion.svg viewBox="0 0 80 240" className="absolute top-[14%] right-[38%] h-40 opacity-40 blur-[2px]" style={{ y: far, rotate: spin }}>
            <Tube x={20} y={10} height={210} width={40} level={0.5} />
          </motion.svg>
          <motion.svg viewBox="0 0 80 240" className="absolute top-[58%] right-[6%] h-56 opacity-60 blur-[1px]" style={{ y: mid, rotate: spin }}>
            <Tube x={20} y={10} height={210} width={40} level={0.7} />
          </motion.svg>
          <motion.svg viewBox="0 0 80 240" className="absolute top-[8%] right-[2%] h-72 opacity-80" style={{ y: near, rotate: -12 }}>
            <Tube x={20} y={10} height={210} width={40} level={0.35} />
          </motion.svg>
          <motion.svg viewBox="0 0 80 240" className="absolute top-[66%] left-[44%] h-44 opacity-50 blur-[1.5px]" style={{ y: mid, rotate: 16 }}>
            <Tube x={20} y={10} height={210} width={40} level={0.6} />
          </motion.svg>
        </div>
        <div className="relative mx-auto grid w-full max-w-[1120px] grid-cols-[1.25fr_1fr] items-center gap-8 px-6">
          <div className="relative min-h-[26rem]">
            {[0, 1, 2].map((i) => (
              <motion.div key={i} className="absolute inset-0 flex flex-col justify-center" style={{ opacity: opacities[i], y: shifts[i] }}>
                <Beat index={i} facts={facts} />
              </motion.div>
            ))}
          </div>
          <div className="flex justify-center" style={{ perspective: 1000 }}>
            <motion.div className="h-[min(64vh,30rem)] w-[min(40vh,19rem)] drop-shadow-[0_30px_40px_rgba(20,27,77,0.12)]" style={{ rotateY: tiltY, rotateX: tiltX, transformStyle: 'preserve-3d' }}>
              <BloodBag level={level} />
            </motion.div>
          </div>
        </div>
        <p className="absolute bottom-6 left-1/2 -translate-x-1/2 text-xs tracking-[0.08em] text-muted uppercase">{t.landing.scroll} ↓</p>
      </div>
    </div>
  )
}

/** Phones, and anyone who asks for reduced motion: the same content as plain stacked sections. */
function StackedStory({ facts, still }: { facts: Facts; still: boolean }) {
  return (
    <div className="mx-auto max-w-[1120px] px-4 sm:px-6">
      {[0, 1, 2].map((i) => (
        <motion.section
          key={i}
          className="relative grid items-center gap-6 border-b border-line py-[clamp(2.5rem,9vw,5rem)] md:grid-cols-[1.3fr_1fr]"
          initial={still ? false : { opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.4, ease: 'easeOut' }}
        >
          {i === 0 && <div className="pointer-events-none absolute -top-6 -left-10 h-56 w-[80vw] max-w-md rounded-full bg-sky-soft opacity-70 blur-3xl" aria-hidden="true" />}
          <div className="relative">
            <Beat index={i} facts={facts} />
          </div>
          <div className="relative mx-auto h-64 w-40 md:h-80 md:w-52">
            <BloodBag level={[0.14, 0.55, 1][i]} />
          </div>
        </motion.section>
      ))}
    </div>
  )
}

export default function Landing({ onSignedIn }: { onSignedIn: (user: User, mode: ModeInfo) => void }) {
  const reduce = useReducedMotion()
  const [facts, setFacts] = useState<Facts>({})
  const [wide, setWide] = useState(() => window.matchMedia('(min-width: 768px)').matches)
  useEffect(() => {
    api.get<Facts>('/api/public-facts').then(setFacts).catch(() => undefined)
    const query = window.matchMedia('(min-width: 768px)')
    const onChange = () => setWide(query.matches)
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [])

  return (
    <div className="min-h-dvh">
      <header className="fixed inset-x-0 top-0 z-30 bg-sky-soft/90 backdrop-blur">
        <div className="mx-auto flex max-w-[1120px] items-center justify-between gap-3 px-4 py-2.5 sm:px-6">
          <span className="flex items-center gap-2.5">
            <Logo />
            <span className="text-[0.9375rem] font-semibold text-ink">{t.appName}</span>
          </span>
          <a href="#sign-in" className="inline-flex min-h-11 items-center rounded-control bg-primary px-4 text-sm font-medium text-white no-underline hover:bg-[#0e1338]">
            {t.landing.signIn}
          </a>
        </div>
      </header>

      <main className="pt-16">
        {wide && !reduce ? <ScrollStory facts={facts} /> : <StackedStory facts={facts} still={!!reduce} />}

        <section id="sign-in" className="relative scroll-mt-20 overflow-hidden bg-bg-alt">
          <TubesBackdrop />
          <div className="relative mx-auto max-w-[1120px] px-4 py-[clamp(3rem,8vw,6rem)] sm:px-6">
            <p className="flex items-center gap-3 text-xs font-medium tracking-[0.08em] text-muted uppercase">
              04 · {t.landing.signInLabel}
              <span className="h-px w-16 bg-line" aria-hidden="true" />
            </p>
            <h2 className="mt-4 text-[clamp(2rem,5vw,3.25rem)] leading-[1.08] font-semibold tracking-[-0.015em] text-ink">{t.landing.signInTitle}</h2>
            <p className="mt-4 max-w-[48ch] text-base">{t.signIn.lead}</p>
            <SignInPanel onSignedIn={onSignedIn} />
            <p className="mt-12 border-t border-line pt-4 text-[0.8125rem] text-muted">{t.syntheticNote}</p>
          </div>
        </section>
      </main>
    </div>
  )
}
