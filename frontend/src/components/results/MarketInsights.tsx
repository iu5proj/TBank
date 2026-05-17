'use client';

import { BarChart3, Search, Target, BadgeCheck } from 'lucide-react';
import type { GptOssSalaryResult } from '@/types';

interface MarketInsightsProps {
  result: GptOssSalaryResult;
}

const confidenceLabels: Record<string, string> = {
  low: 'низкая',
  medium: 'средняя',
  high: 'высокая',
};

export default function MarketInsights({ result }: MarketInsightsProps) {
  const missingSkills = result.missing_skills.map((item) => item.skill);
  const matchPercent =
    result.matched_skills.length + missingSkills.length === 0
      ? 0
      : (result.matched_skills.length /
          (result.matched_skills.length + missingSkills.length)) *
        100;

  const metrics = [
    {
      icon: Search,
      label: 'Вакансий получено',
      value: result.market_sample.candidate_vacancies_received.toLocaleString('ru-RU'),
    },
    {
      icon: BarChart3,
      label: 'Использовано в оценке',
      value: result.market_sample.vacancies_used_for_estimation.toLocaleString('ru-RU'),
    },
    {
      icon: Target,
      label: 'Совпадение навыков',
      value: `${matchPercent.toFixed(0)}%`,
    },
    {
      icon: BadgeCheck,
      label: 'Уверенность',
      value: confidenceLabels[result.confidence.level] || result.confidence.level,
      color:
        result.confidence.level === 'high'
          ? 'var(--success)'
          : result.confidence.level === 'medium'
            ? 'var(--warning)'
            : 'var(--error)',
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
          gap: 12,
        }}
      >
        {metrics.map((metric) => (
          <div
            key={metric.label}
            style={{
              padding: 16,
              borderRadius: 'var(--radius-md)',
              background: 'var(--bg-secondary)',
              textAlign: 'center',
            }}
          >
            <metric.icon
              size={20}
              color="var(--accent-primary)"
              style={{ marginBottom: 8 }}
            />
            <div
              style={{
                fontSize: '1.3rem',
                fontWeight: 800,
                color: metric.color || 'var(--text-primary)',
              }}
            >
              {metric.value}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginTop: 4 }}>
              {metric.label}
            </div>
          </div>
        ))}
      </div>

      <div
        style={{
          padding: 14,
          borderRadius: 'var(--radius-md)',
          background: 'var(--bg-secondary)',
          color: 'var(--text-secondary)',
          fontSize: '0.85rem',
          lineHeight: 1.5,
        }}
      >
        <div style={{ fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
          {result.segment.segment_key}
        </div>
        Версия данных: {result.segment.segment_data_version}. {result.confidence.reason}
      </div>

      {missingSkills.length > 0 && (
        <div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              marginBottom: 8,
            }}
          >
            <BarChart3 size={14} color="var(--error)" />
            <span
              style={{
                fontSize: '0.85rem',
                fontWeight: 600,
                color: 'var(--text-secondary)',
              }}
            >
              Недостающие навыки
            </span>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {missingSkills.map((skill) => (
              <span
                key={skill}
                style={{
                  padding: '4px 12px',
                  borderRadius: 'var(--radius-full)',
                  background: 'var(--error-light)',
                  color: 'var(--error)',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                }}
              >
                {skill}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
