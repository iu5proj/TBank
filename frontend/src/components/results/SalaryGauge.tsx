'use client';

import { motion } from 'framer-motion';
import type { SalaryRange } from '@/types';

interface SalaryGaugeProps {
  salary: SalaryRange;
}

function formatSalary(n: number): string {
  return `${new Intl.NumberFormat('ru-RU').format(n)} ₽`;
}

export default function SalaryGauge({ salary }: SalaryGaugeProps) {
  const maxValue = Math.max(salary.max * 1.15, 1);
  const minWidth = (salary.min / maxValue) * 100;
  const medianWidth = (salary.median / maxValue) * 100;
  const maxWidth = (salary.max / maxValue) * 100;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ fontSize: '2.4rem', fontWeight: 900, color: 'var(--text-primary)' }}>
          {formatSalary(salary.median)}
        </span>
        <span style={{ color: 'var(--text-tertiary)', fontSize: '0.9rem' }}>
          медиана рынка
        </span>
      </div>

      <div style={{ position: 'relative', paddingTop: 32 }}>
        <div
          style={{
            height: 14,
            background: 'var(--bg-tertiary)',
            borderRadius: 'var(--radius-full)',
            overflow: 'hidden',
            position: 'relative',
          }}
        >
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${maxWidth}%` }}
            transition={{ duration: 1, ease: [0.22, 1, 0.36, 1], delay: 0.2 }}
            style={{
              position: 'absolute',
              left: 0,
              top: 0,
              height: '100%',
              background: 'rgba(139, 92, 246, 0.2)',
              borderRadius: 'var(--radius-full)',
            }}
          />
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${medianWidth}%` }}
            transition={{ duration: 1, ease: [0.22, 1, 0.36, 1], delay: 0.1 }}
            style={{
              position: 'absolute',
              left: 0,
              top: 0,
              height: '100%',
              background: 'rgba(99, 102, 241, 0.35)',
              borderRadius: 'var(--radius-full)',
            }}
          />
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${minWidth}%` }}
            transition={{ duration: 1, ease: [0.22, 1, 0.36, 1] }}
            style={{
              position: 'absolute',
              left: 0,
              top: 0,
              height: '100%',
              background: 'var(--accent-gradient)',
              borderRadius: 'var(--radius-full)',
            }}
          />
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: 12,
            marginTop: 12,
            fontSize: '0.8rem',
          }}
        >
          <div style={{ textAlign: 'left' }}>
            <div style={{ fontWeight: 700, color: 'var(--text-primary)' }}>
              {formatSalary(salary.min)}
            </div>
            <div style={{ color: 'var(--text-tertiary)' }}>нижняя граница</div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontWeight: 700, color: 'var(--accent-primary)' }}>
              {formatSalary(salary.median)}
            </div>
            <div style={{ color: 'var(--text-tertiary)' }}>медиана</div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontWeight: 700, color: 'var(--text-primary)' }}>
              {formatSalary(salary.max)}
            </div>
            <div style={{ color: 'var(--text-tertiary)' }}>верхняя граница</div>
          </div>
        </div>
      </div>
    </div>
  );
}
