import './globals.css';
import { Inter } from 'next/font/google';
import MsalProviderWrapper from '@/components/msal-provider-wrapper';

const inter = Inter({ subsets: ['latin'] });

export const metadata = {
  title: 'Charlotte',
  description: 'Using AI to make UNC employee workflow simple and easy',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <MsalProviderWrapper>
          {children}
        </MsalProviderWrapper>
      </body>
    </html>
  );
}