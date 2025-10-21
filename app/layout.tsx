/**
 * Root Layout
 */
import { Playfair_Display } from 'next/font/google'
import { Providers } from '@/components/Providers'
import './globals.css'

const playfairDisplay = Playfair_Display({ subsets: ['latin'], variable: '--font-playfair', weight: ['400', '500', '600', '700'] })

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
      <body className={`${playfairDisplay.variable} h-screen flex flex-col`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
