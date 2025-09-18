import './globals.css';
import { Inter } from 'next/font/google';
import { AuthProvider } from '@/components/auth-context';

const inter = Inter({ subsets: ['latin'] });

export const metadata = {
  title: 'Charlotte',
  description: 'Using AI to make UNC employee workflow simple and easy',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <AuthProvider>
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}