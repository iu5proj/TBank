import { TrendingUp } from 'lucide-react';

export default function Footer() {
  return (
    <footer
      style={{
        borderTop: '1px solid var(--border-light)',
        background: 'var(--bg-primary)',
        padding: '40px 0',
        marginTop: 'auto',
      }}
    >
      <div
        className="container-main"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 16,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: 8,
              background: 'var(--accent-gradient)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <TrendingUp size={16} color="white" />
          </div>
          <span
            style={{
              fontSize: '0.95rem',
              fontWeight: 700,
              color: 'var(--text-primary)',
            }}
          >
            Заработок
          </span>
        </div>

        <p style={{ color: 'var(--text-tertiary)', fontSize: '0.85rem' }}>
          © {new Date().getFullYear()} Samosir Team · T-Bank Hackathon
        </p>
      </div>
    </footer>
  );
}
