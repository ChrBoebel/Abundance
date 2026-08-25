import type { Metadata } from 'next'
import SharedReportView from '@/components/SharedReportView'

export const metadata: Metadata = {
  title: 'Geteilte Recherche | Abundance',
  robots: { index: false, follow: false, nocache: true },
}

export default async function SharedResearchPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params
  return <SharedReportView token={token} />
}
