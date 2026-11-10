export type WsStatus = 'connecting' | 'connected' | 'disconnected'

export function wsUrl(token: string): string {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${location.host}/ws?token=${encodeURIComponent(token)}`
}

export function mapKey(e: KeyboardEvent): string {
  if (e.key === ' ') return 'space'
  const arrows: Record<string, string> = {
    ArrowUp: 'up',
    ArrowDown: 'down',
    ArrowLeft: 'left',
    ArrowRight: 'right',
  }
  if (e.key in arrows) return arrows[e.key]
  if (e.key === 'Control') return 'ctrl'
  if (e.key === 'Escape') return 'esc'
  return e.key.toLowerCase()
}

export interface ScreenInfo {
  width: number
  height: number
}

export async function fetchScreenInfo(): Promise<ScreenInfo | null> {
  try {
    const res = await fetch(`${location.origin}/screen-info`)
    if (!res.ok) return null
    return await res.json()
  } catch {
    return null
  }
}

export type AuthResult = 'ok' | 'wrong-password' | 'unreachable'

export async function authenticate(password: string): Promise<AuthResult> {
  try {
    const res = await fetch(`${location.origin}/auth`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    })
    return res.ok ? 'ok' : 'wrong-password'
  } catch {
    return 'unreachable'
  }
}
