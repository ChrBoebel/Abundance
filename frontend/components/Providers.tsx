/**
 * Client-side providers wrapper
 */
'use client'

import { ThemeProvider } from 'next-themes'

export function Providers({ children, nonce }: { children: React.ReactNode; nonce?: string }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false} nonce={nonce}>
      {children}
    </ThemeProvider>
  )
}
