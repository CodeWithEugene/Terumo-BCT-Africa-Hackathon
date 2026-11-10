import { useEffect, useState } from 'react'

export type Route =
  | { page: 'brief' }
  | { page: 'group'; id: string }
  | { page: 'region' }
  | { page: 'decisions' }
  | { page: 'accuracy' }
  | { page: 'privacy' }

function parse(hash: string): Route {
  const path = hash.replace(/^#\/?/, '')
  const [first, ...rest] = path.split('/')
  if (first === 'group' && rest.length) return { page: 'group', id: decodeURIComponent(rest.join('/')) }
  if (first === 'region' || first === 'decisions' || first === 'accuracy' || first === 'privacy') return { page: first }
  return { page: 'brief' }
}

export function href(route: Route): string {
  if (route.page === 'brief') return '#/'
  if (route.page === 'group') return `#/group/${encodeURIComponent(route.id)}`
  return `#/${route.page}`
}

export function go(route: Route): void {
  window.location.hash = href(route)
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parse(window.location.hash))
  useEffect(() => {
    const onChange = () => setRoute(parse(window.location.hash))
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return route
}
