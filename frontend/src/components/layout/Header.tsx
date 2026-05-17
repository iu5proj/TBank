'use client';

import Link from 'next/link';
import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { TrendingUp, Menu, X } from 'lucide-react';

export default function Header() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 100,
        background: 'rgba(255, 255, 255, 0.8)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        borderBottom: '1px solid var(--border-light)',
      }}
    >
      <div
        className="container-main"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          height: 64,
        }}
      >
        {/* Logo */}
        <Link
          href="/"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            textDecoration: 'none',
            color: 'var(--text-primary)',
          }}
        >
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: 10,
              background: 'var(--accent-gradient)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <TrendingUp size={20} color="white" />
          </div>
          <span style={{ fontSize: '1.2rem', fontWeight: 800, letterSpacing: '-0.02em' }}>
            Заработок
          </span>
        </Link>

        {/* Desktop Nav */}
        <nav
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 32,
          }}
          className="desktop-nav"
        >
          <Link
            href="/"
            style={{
              textDecoration: 'none',
              color: 'var(--text-secondary)',
              fontSize: '0.9rem',
              fontWeight: 500,
              transition: 'color 0.2s',
            }}
          >
            Главная
          </Link>
          <Link
            href="/resume"
            className="btn-gradient"
            style={{ padding: '8px 20px', fontSize: '0.9rem' }}
          >
            Оценить резюме
          </Link>
        </nav>

        {/* Mobile burger */}
        <button
          className="mobile-burger"
          onClick={() => setMobileOpen(!mobileOpen)}
          style={{
            display: 'none',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: 'var(--text-primary)',
          }}
        >
          {mobileOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      </div>

      {/* Mobile menu */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="mobile-menu"
            style={{
              overflow: 'hidden',
              borderTop: '1px solid var(--border-light)',
              background: 'var(--bg-primary)',
            }}
          >
            <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
              <Link
                href="/"
                onClick={() => setMobileOpen(false)}
                style={{
                  textDecoration: 'none',
                  color: 'var(--text-secondary)',
                  fontSize: '0.95rem',
                  fontWeight: 500,
                  padding: '8px 0',
                }}
              >
                Главная
              </Link>
              <Link
                href="/resume"
                onClick={() => setMobileOpen(false)}
                className="btn-gradient"
                style={{ textAlign: 'center', textDecoration: 'none' }}
              >
                Оценить резюме
              </Link>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <style jsx global>{`
        @media (max-width: 768px) {
          .desktop-nav { display: none !important; }
          .mobile-burger { display: block !important; }
        }
        @media (min-width: 769px) {
          .mobile-menu { display: none !important; }
        }
      `}</style>
    </header>
  );
}
