/**
 * Login Page
 */
'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Eye, EyeOff, Unlock, ShieldCheck, AlertCircle } from 'lucide-react'

export default function LoginPage() {
  const router = useRouter()
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      })

      if (response.ok) {
        router.push('/')
        router.refresh()
      } else {
        const data = await response.json()
        setError(data.error || 'Falsches Passwort')
      }
    } catch (err) {
      setError('Verbindungsfehler')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="h-screen flex items-center justify-center">
      <div className="w-full max-w-md mx-4 p-4 sm:p-8 rounded-2xl shadow-2xl" style={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))' }}>
        <div className="text-center mb-6 sm:mb-8">
          <div
            className="w-16 h-16 sm:w-20 sm:h-20 rounded-2xl mx-auto mb-4 sm:mb-6 flex items-center justify-center p-0 overflow-visible"
            style={{ background: 'linear-gradient(135deg, hsl(var(--primary)) 0%, hsl(var(--primary) / 0.8) 100%)', boxShadow: '0 8px 32px hsl(var(--primary) / 0.4), 0 0 60px hsl(var(--primary) / 0.2)' }}
          >
            <img src="/bergbild2.svg" alt="Abundance Logo" className="w-[247%] h-[247%]" style={{ filter: 'drop-shadow(0 4px 8px rgba(0,0,0,0.3))', imageRendering: 'auto', WebkitBackfaceVisibility: 'hidden', backfaceVisibility: 'hidden', transform: 'translateZ(0)' }} />
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold mb-2 abundance-title">Abundance</h1>
          <p className="text-sm opacity-70">Passwort eingeben um fortzufahren</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 sm:space-y-6">
          {error && (
            <div className="p-4 rounded-lg flex items-center gap-3" style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)' }}>
              <AlertCircle className="w-5 h-5 text-red-400" />
              <span className="text-red-400 text-sm font-medium">{error}</span>
            </div>
          )}

          <div className="space-y-2">
            <label htmlFor="password" className="block text-sm font-medium opacity-80">Passwort</label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                id="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Passwort eingeben..."
                required
                className="w-full px-4 py-3 pr-12 rounded-lg border focus:outline-none focus:ring-2 transition"
                style={{ background: 'hsl(var(--background))', borderColor: 'hsl(var(--border))', color: 'hsl(var(--foreground))' }}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 p-2 rounded hover:bg-gray-700 transition"
              >
                {showPassword ? <EyeOff className="w-5 h-5 opacity-50" /> : <Eye className="w-5 h-5 opacity-50" />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full px-6 py-3 rounded-lg font-semibold transition hover:scale-105 active:scale-95 flex items-center justify-center gap-2 shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
            style={{ background: 'hsl(var(--primary))', color: 'white' }}
          >
            <Unlock className="w-5 h-5" />
            {loading ? 'Anmelden...' : 'Anmelden'}
          </button>
        </form>

        <div className="mt-8 pt-6 border-t" style={{ borderColor: 'hsl(var(--border))' }}>
          <div className="flex items-center justify-center gap-2 text-xs opacity-60">
            <ShieldCheck className="w-4 h-4" />
            <span>Geschützt durch Passwort-Authentifizierung</span>
          </div>
        </div>
      </div>
    </div>
  )
}
