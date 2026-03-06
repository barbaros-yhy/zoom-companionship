import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Zoom Companion',
  description: 'Meeting transcription and summaries',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
