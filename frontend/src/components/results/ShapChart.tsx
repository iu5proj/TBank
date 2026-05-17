'use client';

import { motion } from 'framer-motion';
import { ArrowUp, ArrowDown, Minus } from 'lucide-react';
import type { Factor } from '@/types';

interface FactorListProps {
  factors: Factor[];
}

const impactConfig = {
  positive: {
    icon: ArrowUp,
    label: 'усиливает',
    color: 'var(--success)',
    background: 'var(--success-light)',
  },
  negative: {
    icon: ArrowDown,
    label: 'снижает',
    color: 'var(--error)',
    background: 'var(--error-light)',
  },
  neutral: {
    icon: Minus,
    label: 'нейтрально',
    color: 'var(--text-tertiary)',
    background: 'var(--bg-tertiary)',
  },
} satisfies Record<
  Factor['impact'],
  { icon: typeof ArrowUp; label: string; color: string; background: string }
>;

export default function FactorList({ factors }: FactorListProps) {
  if (factors.length === 0) {
    return (
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
        Модель не вернула отдельные факторы влияния для этого расчета.
      </p>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {factors.map((factor, index) => {
        const config = impactConfig[factor.impact];
        const Icon = config.icon;

        return (
          <motion.div
            key={`${factor.factor}-${index}`}
            initial={{ opacity: 0, x: -16 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.08 }}
            style={{
              display: 'grid',
              gridTemplateColumns: '150px 1fr',
              gap: 12,
              padding: 14,
              borderRadius: 'var(--radius-md)',
              background: 'var(--bg-secondary)',
            }}
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <strong
                style={{
                  color: 'var(--text-primary)',
                  fontSize: '0.9rem',
                  lineHeight: 1.35,
                }}
              >
                {factor.factor}
              </strong>
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  alignSelf: 'flex-start',
                  padding: '4px 10px',
                  borderRadius: 'var(--radius-full)',
                  background: config.background,
                  color: config.color,
                  fontSize: '0.75rem',
                  fontWeight: 700,
                }}
              >
                <Icon size={13} />
                {config.label}
              </span>
            </div>
            <p
              style={{
                color: 'var(--text-secondary)',
                fontSize: '0.9rem',
                lineHeight: 1.55,
              }}
            >
              {factor.explanation}
            </p>
          </motion.div>
        );
      })}
    </div>
  );
}
