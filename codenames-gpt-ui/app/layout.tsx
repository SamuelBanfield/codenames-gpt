import type { Metadata } from 'next'
import { Inter, Play } from 'next/font/google'
import './globals.css'
import { WebSocketProvider } from './wsProvider'
import { PlayerProvider } from './playerIdProvider'
import Header from './header'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Codenames GPT',
  description: 'Play codenames with an LLM',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <WebSocketProvider>
          <PlayerProvider>
            <Header />
            {children}
          </PlayerProvider>
        </WebSocketProvider>
      </body>
    </html>
  )
}
