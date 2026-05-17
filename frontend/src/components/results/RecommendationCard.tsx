'use client';

import { motion } from 'framer-motion';
import { Star, Zap, BookOpen, Briefcase, Target } from 'lucide-react';
import type { AnalyzeRecommendation, RecommendationType } from '@/types';

interface RecommendationCardProps {
  rec: AnalyzeRecommendation;
  index: number;
}

const typeConfig: Record<
  RecommendationType,
  { icon: typeof Star; color: string; label: string }
> = {
  skill_gap: { icon: Zap, color: '#2563eb', label: 'Навык' },
  experience_detail: { icon: Briefcase, color: '#16a34a', label: 'Опыт' },
  resume_clarity: { icon: BookOpen, color: '#7c3aed', label: 'Резюме' },
  salary_expectation: { icon: Target, color: '#ea580c', label: 'Ожидания' },
};

export default function RecommendationCard({ rec, index }: RecommendationCardProps) {
  const config = typeConfig[rec.type] || typeConfig.resume_clarity;
  const Icon = config.icon;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.1, duration: 0.4 }}
      style={{
        padding: 24,
        borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--border-light)',
        background: 'var(--bg-primary)',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        transition: 'box-shadow 0.3s, transform 0.3s',
        cursor: 'default',
      }}
      whileHover={{
        boxShadow: '0 8px 24px rgba(0,0,0,0.08)',
        y: -2,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: `${config.color}14`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <Icon size={16} color={config.color} />
          </div>
          <span
            style={{
              fontSize: '0.75rem',
              fontWeight: 700,
              color: config.color,
              textTransform: 'uppercase',
            }}
          >
            {config.label}
          </span>
        </div>

        <span
          style={{
            padding: '4px 10px',
            borderRadius: 'var(--radius-full)',
            background: 'var(--bg-secondary)',
            color: 'var(--text-secondary)',
            fontSize: '0.8rem',
            fontWeight: 700,
            whiteSpace: 'nowrap',
          }}
        >
          #{rec.priority}
        </span>
      </div>

      <h4
        style={{
          fontWeight: 700,
          fontSize: '1rem',
          color: 'var(--text-primary)',
          lineHeight: 1.4,
        }}
      >
        {rec.title}
      </h4>

      <p
        style={{
          fontSize: '0.9rem',
          color: 'var(--text-secondary)',
          lineHeight: 1.6,
        }}
      >
        {rec.resume_change}
      </p>

      {rec.expected_salary_effect && (
        <div
          style={{
            padding: '10px 14px',
            borderRadius: 'var(--radius-sm)',
            background: 'var(--accent-light)',
            fontSize: '0.85rem',
            color: 'var(--accent-primary)',
            fontWeight: 600,
            lineHeight: 1.5,
          }}
        >
          Ожидаемый эффект: {rec.expected_salary_effect}
        </div>
      )}
    </motion.div>
  );
}
