import './globals.css'

export const metadata = {
  title: 'Tax Law Assistant',
  description: 'AI-powered verification engine for Chartered Accountants.',
}

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
