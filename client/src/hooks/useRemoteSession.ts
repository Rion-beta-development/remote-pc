import { useCallback, useEffect, useRef, useState } from 'react'
import { wsUrl, type WsStatus } from '../lib/protocol'

export interface RemoteSession {
  status: WsStatus
  fps: number
  imgRef: React.RefObject<HTMLImageElement | null>
  connect: () => void
  disconnect: () => void
  send: (msg: Record<string, unknown>) => void
}

const MAX_BACKOFF_MS = 15000

export function useRemoteSession(password: string): RemoteSession {
  const [status, setStatus] = useState<WsStatus>('disconnected')
  const [fps, setFps] = useState(0)
  const wsRef = useRef<WebSocket | null>(null)
  const imgRef = useRef<HTMLImageElement | null>(null)
  const manualClose = useRef(false)
  const attempts = useRef(0)
  const retryTimer = useRef<number | undefined>(undefined)
  const fpsCount = useRef(0)
  const fpsWindow = useRef(performance.now())

  const send = useCallback((msg: Record<string, unknown>) => {
    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg))
  }, [])

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return
    manualClose.current = false
    setStatus('connecting')
    const ws = new WebSocket(wsUrl(password))
    wsRef.current = ws

    ws.onopen = () => {
      attempts.current = 0
      setStatus('connected')
    }
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data)
        if (msg.type === 'frame' && imgRef.current) {
          imgRef.current.src = 'data:image/jpeg;base64,' + msg.data
          fpsCount.current++
          const now = performance.now()
          if (now - fpsWindow.current >= 1000) {
            setFps(fpsCount.current)
            fpsCount.current = 0
            fpsWindow.current = now
          }
        }
      } catch {
        // ignore malformed frames
      }
    }
    ws.onclose = () => {
      wsRef.current = null
      setStatus('disconnected')
      if (manualClose.current) return
      attempts.current += 1
      const delay = Math.min(2000 * 2 ** attempts.current, MAX_BACKOFF_MS)
      retryTimer.current = window.setTimeout(connect, delay)
    }
    ws.onerror = () => ws.close()
  }, [password])

  const disconnect = useCallback(() => {
    manualClose.current = true
    if (retryTimer.current !== undefined) {
      clearTimeout(retryTimer.current)
      retryTimer.current = undefined
    }
    wsRef.current?.close()
    wsRef.current = null
    setStatus('disconnected')
  }, [])

  // heartbeat
  useEffect(() => {
    const id = window.setInterval(() => send({ type: 'ping' }), 5000)
    return () => clearInterval(id)
  }, [send])

  useEffect(() => {
    connect()
    return () => disconnect()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return { status, fps, imgRef, connect, disconnect, send }
}
