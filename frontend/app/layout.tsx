/**
 * Root Layout
 */
import { Playfair_Display } from 'next/font/google'
import { headers } from 'next/headers'
import { connection } from 'next/server'
import { Providers } from '@/components/Providers'
import './globals.css'

const playfairDisplay = Playfair_Display({ subsets: ['latin'], variable: '--font-playfair', weight: ['400', '500', '600', '700'] })

export const metadata = {
  title: 'Abundance — Evidenzbasierte Recherche',
  description: 'Komplexe Fragen mit Evidenz, Gegenbelegen und transparenter Unsicherheit untersuchen.',
}

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  // A per-request render lets Next.js attach the CSP nonce generated in proxy.ts
  // to its framework scripts.
  await connection()
  const nonce = (await headers()).get('x-nonce') ?? undefined

  return (
    <html lang="de" suppressHydrationWarning>
      <body className={`${playfairDisplay.variable} h-screen flex flex-col`}>
        <Providers nonce={nonce}>{children}</Providers>
      </body>
    </html>
  )
}
