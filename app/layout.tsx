/**
 * Root Layout
 */
import { Space_Grotesk } from 'next/font/google'
import { Providers } from '@/components/Providers'
import './globals.css'

const spaceGrotesk = Space_Grotesk({ subsets: ['latin'], variable: '--font-space-grotesk' })

export const metadata = {
  title: 'Abundance - Deep Research',
  description: 'Automated deep research powered by Gemini and Tavily',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="de" suppressHydrationWarning>
      <body className={`${spaceGrotesk.variable} h-screen flex flex-col`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
