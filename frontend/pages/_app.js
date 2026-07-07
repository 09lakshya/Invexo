import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';
import { useEffect } from 'react';
import '../styles/globals.css';
import { AuthProvider, useAuth } from '../context/AuthContext';
import { ThemeProvider } from '../context/ThemeContext';
import { WebSocketProvider } from '../context/WebSocketContext';
import VexoWidget from '../components/VexoWidget';
import Icon from '../components/Icon';
import { applyDensity, getDensity } from '../services/preferences';

// Pages that don't require authentication
const PUBLIC_PAGES = ['/login'];

function AuthGuard({ children }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  const isPublic = PUBLIC_PAGES.includes(router.pathname);

  useEffect(() => {
    if (!loading && !user && !isPublic) {
      router.replace('/login');
    }
  }, [loading, user, isPublic, router]);

  // Show nothing while checking auth (prevents flash)
  if (loading) {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'var(--bg-primary, #060a14)',
        }}
      >
        <div style={{ textAlign: 'center' }}>
          <div className="spinner" style={{ margin: '0 auto 16px' }} />
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            Loading Invexo…
          </p>
        </div>
      </div>
    );
  }

  // Not logged in + not a public page → don't render (redirect is happening)
  if (!user && !isPublic) {
    return null;
  }

  return children;
}

export default function App({ Component, pageProps }) {
  const router = useRouter();
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        refetchOnWindowFocus: false,
        retry: 1,
      },
    },
  }));

  // Apply the saved display-density preference on every page load so the
  // choice made in Settings persists across the whole app, like the theme does.
  useEffect(() => {
    applyDensity(getDensity());
  }, []);

  return (
    <>
      <Head>
        <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no, viewport-fit=cover" />
      </Head>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <AuthProvider>
            <WebSocketProvider>
              <AuthGuard>
                <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', boxSizing: 'border-box' }}>
                  <div style={{ flex: 1 }}>
                    <Component {...pageProps} />
                  </div>
                  <footer style={{
                    padding: '20px 16px',
                    textAlign: 'center',
                    borderTop: '1px solid var(--border-subtle)',
                    fontSize: '0.72rem',
                    color: 'var(--text-muted)',
                    fontFamily: "'Inter', sans-serif",
                    lineHeight: '1.4',
                  }}>
                    Invexo is for educational purposes only. Developed by Lakshya Hindocha.
                  </footer>
                  <div
                    id="global-legal-disclaimer"
                    style={{
                      background: 'var(--bg-secondary)',
                      borderTop: '1px solid rgba(255, 23, 68, 0.2)',
                      color: 'var(--text-primary)',
                      padding: '16px 24px',
                      textAlign: 'center',
                      fontSize: '0.72rem',
                      fontWeight: '500',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '8px',
                      fontFamily: "'Inter', sans-serif",
                      lineHeight: '1.4',
                    }}
                  >
                    <Icon name="alert" size={15} style={{ color: 'var(--red)', flexShrink: 0, marginTop: '1px' }} />
                    <span style={{ color: 'var(--text-secondary)' }}>
                      <strong style={{ color: 'var(--text-primary)', fontWeight: '700' }}>Legal Disclaimer:</strong> Invexo is not SEBI registered. All content is for educational purposes only and does not constitute investment advice.
                    </span>
                  </div>
                  {!PUBLIC_PAGES.includes(router.pathname) && <VexoWidget />}
                </div>
              </AuthGuard>
            </WebSocketProvider>
          </AuthProvider>
        </ThemeProvider>
      </QueryClientProvider>
    </>
  );
}