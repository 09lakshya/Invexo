import Head from 'next/head';
import { useRouter } from 'next/router';
import { useEffect } from 'react';
import '../styles/globals.css';
import { AuthProvider, useAuth } from '../context/AuthContext';
import { ThemeProvider } from '../context/ThemeContext';
import { WebSocketProvider } from '../context/WebSocketContext';

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
  return (
    <>
      <Head>
        <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no, viewport-fit=cover" />
      </Head>
      <ThemeProvider>
        <AuthProvider>
          <WebSocketProvider>
            <AuthGuard>
              <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', paddingBottom: '48px', boxSizing: 'border-box' }}>
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
              </div>
              <div
                id="global-legal-disclaimer"
                style={{
                  position: 'fixed',
                  bottom: 0,
                  left: 0,
                  right: 0,
                  background: 'rgba(13, 18, 36, 0.95)',
                  backdropFilter: 'blur(16px)',
                  WebkitBackdropFilter: 'blur(16px)',
                  borderTop: '1px solid rgba(255, 23, 68, 0.25)',
                  color: 'var(--text-primary)',
                  padding: '12px 24px',
                  textAlign: 'center',
                  fontSize: '0.72rem',
                  fontWeight: '500',
                  zIndex: 999999,
                  boxShadow: '0 -4px 30px rgba(0, 0, 0, 0.5)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  fontFamily: "'Inter', sans-serif",
                  lineHeight: '1.4',
                }}
              >
                <span style={{ color: 'var(--red)', fontWeight: 'bold', fontSize: '0.85rem' }}>⚠️</span>
                <span style={{ color: 'var(--text-secondary)' }}>
                  <strong style={{ color: 'var(--text-primary)', fontWeight: '700' }}>Legal Disclaimer:</strong> Invexo is not SEBI registered. All content is for educational purposes only and does not constitute investment advice.
                </span>
              </div>
            </AuthGuard>
          </WebSocketProvider>
        </AuthProvider>
      </ThemeProvider>
    </>
  );
}