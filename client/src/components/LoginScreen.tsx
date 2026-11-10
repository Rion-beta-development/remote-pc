import { useState } from 'react'
import { authenticate, type AuthResult } from '../lib/protocol'

const ERROR_TEXT: Record<Exclude<AuthResult, 'ok'>, string> = {
  'wrong-password': 'Invalid password. Please try again.',
  unreachable: 'Cannot reach the Remote-PC server. Is it running?',
}

export default function LoginScreen({ onSuccess }: { onSuccess: (pw: string) => void }) {
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [error, setError] = useState<AuthResult>('ok')
  const [busy, setBusy] = useState(false)

  async function submit() {
    const pw = password.trim()
    if (!pw || busy) return
    setBusy(true)
    setError('ok')
    const result = await authenticate(pw)
    setBusy(false)
    if (result === 'ok') onSuccess(pw)
    else setError(result)
  }

  return (
    <div className="h-full flex flex-col items-center justify-center bg-[#0f1420] px-4">
      <img src="/static/icon.png" alt="Remote-PC" className="w-24 h-24 rounded-3xl shadow-lg shadow-cyan-500/20 mb-6" />
      <h1 className="text-3xl font-bold text-cyan-300 mb-1">Remote-PC</h1>
      <p className="text-slate-400 text-sm mb-8">Enter your password to connect</p>

      <form
        className="w-full max-w-xs flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault()
          submit()
        }}
      >
        <div className="relative">
          <input
            type={show ? 'text' : 'password'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password"
            autoFocus
            autoComplete="off"
            className="w-full rounded-xl bg-slate-900 border border-slate-700 px-4 py-3 pr-16 text-slate-200 placeholder-slate-500 outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/30 transition"
          />
          <button
            type="button"
            onClick={() => setShow((s) => !s)}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-slate-400 hover:text-cyan-300 px-2 py-1"
          >
            {show ? 'Hide' : 'Show'}
          </button>
        </div>

        <button
          type="submit"
          disabled={busy}
          className="rounded-xl bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 text-slate-950 font-semibold py-3 transition"
        >
          {busy ? 'Connecting…' : 'Connect'}
        </button>

        {error !== 'ok' && <p className="text-center text-sm text-red-400">{ERROR_TEXT[error]}</p>}
      </form>
    </div>
  )
}
