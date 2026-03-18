import './globals.css'

export const metadata = {
    title: 'NIOS Study',
    description: 'PYQ-based daily plans, built from official NIOS material.',
}

export default function RootLayout({ children }) {
    return (
        <html lang="en">
            <body>{children}</body>
        </html>
    )
}
