import { useCallback, useEffect, useRef, useState } from 'react'
import type { RemoteSession } from '../hooks/useRemoteSession'
import { fetchScreenInfo, mapKey, type ScreenInfo } from '../lib/protocol'

type FitMode = 'fit' | number // percent when number

const ZOOM_STEPS = [50, 75, 100, 125, 150, 200]

export default function Viewer({ session, onDisconnect }: { session: RemoteSession; onDisconnect: () => void }) {
  const [controlling, setControlling] = useState(false)
  const [controlEnabled, setControlEnabled] = useState(true)
  const [fitMode, setFitMode] = useState<FitMode>('fit')
  const [screen, setScreen] = useState<ScreenInfo | null>(null)
  const [copied, setCopied] = useState(false)
  const [scalePct, setScalePct] = useState(100)
  const viewportRef = useRef<HTMLDivElement>(null)
  const imgRef = session.imgRef

  useEffect(() => {
    fetchScreenInfo().then(setScreen)
  }, [])

  // ---- coordinate mapping ----
  const remap = useCallback(
    (clientX: number, clientY: number) => {
      const img = imgRef.current
      if (!img || !screen) return { x: 0, y: 0 }
      const rect = img.getBoundingClientRect()
      if (rect.width <= 0 || rect.height <= 0) return { x: 0, y: 0 }
      const x = Math.max(0, Math.min(clientX - rect.left, rect.width))
      const y = Math.max(0, Math.min(clientY - rect.top, rect.height))
      return {
        x: Math.round((x / rect.width) * screen.width),
        y: Math.round((y / rect.height) * screen.height),
      }
    },
    [imgRef, screen],
  )

  const active = controlling && controlEnabled

  // ---- pointer handlers ----
  function onMouseMove(e: React.MouseEvent) {
    if (!active || session.status !== 'connected') return
    const { x, y } = remap(e.clientX, e.clientY)
    session.send({ type: 'mousemove', x, y })
  }
  function onMouseButton(e: React.MouseEvent, kind: 'mousedown' | 'mouseup') {
    if (!active || session.status !== 'connected') return
    e.preventDefault()
    const { x, y } = remap(e.clientX, e.clientY)
    const button = e.button === 0 ? 'left' : e.button === 2 ? 'right' : 'middle'
    session.send({ type: kind, x, y, button })
  }
  function onWheel(e: React.WheelEvent) {
    if (!active || session.status !== 'connected') return
    e.preventDefault()
    session.send({ type: 'mousescroll', dx: 0, dy: Math.sign(e.deltaY) * (Math.abs(e.deltaY) > 100 ? 3 : 1) })
  }

  // ---- keyboard capture ----
  useEffect(() => {
    if (!active) return
    const down = (e: KeyboardEvent) => {
      if (e.key === 'Tab') e.preventDefault()
      session.send({ type: 'keydown', key: mapKey(e) })
    }
    const up = (e: KeyboardEvent) => session.send({ type: 'keyup', key: mapKey(e) })
    window.addEventListener('keydown', down, true)
    window.addEventListener('keyup', up, true)
    return () => {
      window.removeEventListener('keydown', down, true)
      window.removeEventListener('keyup', up, true)
    }
  }, [active, session])

  // ---- clipboard paste (typed on the remote machine) ----
  useEffect(() => {
    if (!active) return
    const onPaste = (e: ClipboardEvent) => {
      const text = e.clipboardData?.getData('text')
      if (text) session.send({ type: 'type', text })
    }
    document.addEventListener('paste', onPaste)
    return () => document.removeEventListener('paste', onPaste)
  }, [active, session])

  // ---- fullscreen tracking + scale readout ----
  useEffect(() => {
    const onFsChange = () => setFitMode((m) => m) // re-render
    document.addEventListener('fullscreenchange', onFsChange)
    return () => document.removeEventListener('fullscreenchange', onFsChange)
  }, [])

  function updateScaleReadout() {
    const img = imgRef.current
    if (!img || !screen) return
    const rect = img.getBoundingClientRect()
    setScalePct(Math.round((rect.width / screen.width) * 100))
  }
  useEffect(() => {
    const img = imgRef.current
    if (!img) return
    img.addEventListener('load', updateScaleReadout)
    window.addEventListener('resize', updateScaleReadout)
    return () => {
      img.removeEventListener('load', updateScaleReadout)
      window.removeEventListener('resize', updateScaleReadout)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [screen])

  // ---- zoom ----
  function stepZoom(dir: 1 | -1) {
    const idx = fitMode === 'fit' ? ZOOM_STEPS.indexOf(100) : ZOOM_STEPS.indexOf(fitMode as number)
    const next = ZOOM_STEPS[Math.min(Math.max(idx + dir, 0), ZOOM_STEPS.length - 1)]
    setFitMode(next)
  }

  const imageStyle: React.CSSProperties =
    fitMode === 'fit'
      ? { maxWidth: '100%', maxHeight: '100%' }
      : { width: screen ? (screen.width * fitMode) / 100 : undefined }

  const statusColor =
    session.status === 'connected' ? 'text-emerald-400' : session.status === 'connecting' ? 'text-amber-400' : 'text-red-400'

  const publicUrl = location.protocol === 'https:' ? location.origin : null

  return (
    <div className="relative h-full w-full bg-black overflow-hidden">
      {/* viewer */}
      <div
        ref={viewportRef}
        className="h-full w-full flex items-center justify-center overflow-auto"
        onMouseMove={onMouseMove}
        onMouseDown={(e) => onMouseButton(e, 'mousedown')}
        onMouseUp={(e) => onMouseButton(e, 'mouseup')}
        onWheel={onWheel}
        onContextMenu={(e) => e.preventDefault()}
        style={{ cursor: active ? 'crosshair' : 'default' }}
      >
        <img ref={imgRef} alt="Remote screen" draggable={false} style={imageStyle} />
      </div>

      {/* HUD */}
      <div className="absolute top-3 left-3 right-3 flex justify-between items-start pointer-events-none">
        <div className="flex gap-2">
          <span className="rounded-full bg-slate-900/80 border border-slate-700 px-3 py-1 text-xs text-slate-300 backdrop-blur">
            Status <span className={`font-bold ${statusColor}`}>{session.status}</span>
          </span>
          <span className="rounded-full bg-slate-900/80 border border-slate-700 px-3 py-1 text-xs text-slate-300 backdrop-blur">
            FPS <span className="font-bold text-cyan-300">{session.fps}</span>
          </span>
          <span className="rounded-full bg-slate-900/80 border border-slate-700 px-3 py-1 text-xs text-slate-300 backdrop-blur">
            Scale <span className="font-bold text-cyan-300">{scalePct}%</span>
          </span>
        </div>
        <div className="flex gap-2 pointer-events-auto">
          {publicUrl && (
            <button
              onClick={() => {
                navigator.clipboard.writeText(publicUrl).then(() => {
                  setCopied(true)
                  setTimeout(() => setCopied(false), 1500)
                })
              }}
              className="rounded-full bg-slate-900/80 border border-slate-700 px-3 py-1 text-xs text-slate-300 hover:border-cyan-500 backdrop-blur"
            >
              {copied ? 'Copied!' : 'Copy public link'}
            </button>
          )}
          <button
            onClick={() => {
              session.disconnect()
              onDisconnect()
            }}
            className="rounded-full bg-slate-900/80 border border-slate-700 px-3 py-1 text-xs text-red-400 hover:border-red-500 backdrop-blur"
          >
            Disconnect
          </button>
        </div>
      </div>

      {/* controls */}
      <div className="absolute bottom-3 left-3 right-3 flex justify-between items-end pointer-events-none">
        <div className="flex gap-2 pointer-events-auto">
          <button
            onClick={() => setControlEnabled((v) => !v)}
            className={`rounded-lg border px-3 py-1.5 text-xs backdrop-blur transition ${
              controlEnabled
                ? 'bg-cyan-500/90 border-cyan-400 text-slate-950 font-semibold'
                : 'bg-slate-900/80 border-slate-700 text-slate-300 hover:border-cyan-500'
            }`}
          >
            Control: {controlEnabled ? 'ON' : 'OFF'}
          </button>
          <button
            onClick={() => setFitMode('fit')}
            className={`rounded-lg border px-3 py-1.5 text-xs backdrop-blur transition ${
              fitMode === 'fit'
                ? 'bg-cyan-500/90 border-cyan-400 text-slate-950 font-semibold'
                : 'bg-slate-900/80 border-slate-700 text-slate-300 hover:border-cyan-500'
            }`}
          >
            Fit
          </button>
          <button
            onClick={() => stepZoom(1)}
            className="rounded-lg border border-slate-700 bg-slate-900/80 px-3 py-1.5 text-xs text-slate-300 hover:border-cyan-500 backdrop-blur"
          >
            +
          </button>
          <button
            onClick={() => stepZoom(-1)}
            className="rounded-lg border border-slate-700 bg-slate-900/80 px-3 py-1.5 text-xs text-slate-300 hover:border-cyan-500 backdrop-blur"
          >
            −
          </button>
          <button
            onClick={() =>
              document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen()
            }
            className="rounded-lg border border-slate-700 bg-slate-900/80 px-3 py-1.5 text-xs text-slate-300 hover:border-cyan-500 backdrop-blur"
          >
            Fullscreen
          </button>
          <button
            onClick={() => session.send({ type: 'hotkey', keys: ['ctrl', 'shift', 'esc'] })}
            className="rounded-lg border border-slate-700 bg-slate-900/80 px-3 py-1.5 text-xs text-slate-300 hover:border-cyan-500 backdrop-blur"
          >
            Task Manager
          </button>
        </div>
        <p className="text-[11px] text-slate-500 pointer-events-none">
          Ctrl+V pastes clipboard text · Esc releases keys
        </p>
      </div>

      {/* click-to-control overlay */}
      {!controlling && session.status === 'connected' && (
        <div
          className="absolute inset-0 flex flex-col items-center justify-center bg-black/60 cursor-pointer z-20"
          onClick={() => setControlling(true)}
        >
          <h2 className="text-2xl font-bold text-cyan-300 mb-2">Click to take control</h2>
          <p className="text-slate-400 text-sm">Your mouse and keyboard will be sent to the remote PC</p>
        </div>
      )}

      {/* disconnected overlay */}
      {session.status === 'disconnected' && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/70 z-30">
          <h2 className="text-2xl font-bold text-red-400 mb-2">Connection lost</h2>
          <p className="text-slate-400 text-sm mb-4">Retrying automatically…</p>
          <button
            onClick={session.connect}
            className="rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold px-5 py-2 text-sm transition"
          >
            Retry now
          </button>
        </div>
      )}
    </div>
  )
}
