import { useState } from 'react'
import LoginScreen from './components/LoginScreen'
import Viewer from './components/Viewer'
import { useRemoteSession } from './hooks/useRemoteSession'

export default function App() {
  const [password, setPassword] = useState<string | null>(null)
  const session = useRemoteSession(password ?? '')

  if (password === null) {
    return <LoginScreen onSuccess={setPassword} />
  }
  return <Viewer session={session} onDisconnect={() => setPassword(null)} />
}
