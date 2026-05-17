'use client';

import type { WizardFormData } from '@/types';
import { FileText, RefreshCw, WalletCards } from 'lucide-react';

interface GoalsProps {
  data: WizardFormData;
  onChange: (data: Partial<WizardFormData>) => void;
  errors: Record<string, string>;
}

function parseOptionalSalary(value: string): number | null {
  const normalized = value.replace(/\s/g, '');
  if (!normalized) return null;
  const parsed = Number(normalized);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

export default function Goals({ data, onChange, errors }: GoalsProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: 4 }}>
          Цели и описание
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
          Укажите зарплатные ожидания и добавьте пару строк о своём опыте — так оценка будет точнее.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div>
          <label className="input-label">
            <WalletCards size={14} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle' }} />
            Текущая зарплата, ₽
          </label>
          <input
            className="input-field"
            inputMode="numeric"
            placeholder="150000"
            value={data.current_salary ?? ''}
            onChange={(event) => onChange({ current_salary: parseOptionalSalary(event.target.value) })}
          />
          {errors.current_salary && <p className="input-error">{errors.current_salary}</p>}
        </div>

        <div>
          <label className="input-label">
            <WalletCards size={14} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle' }} />
            Желаемая зарплата, ₽
          </label>
          <input
            className="input-field"
            inputMode="numeric"
            placeholder="250000"
            value={data.target_salary ?? ''}
            onChange={(event) => onChange({ target_salary: parseOptionalSalary(event.target.value) })}
          />
          {errors.target_salary && <p className="input-error">{errors.target_salary}</p>}
        </div>
      </div>

      <div>
        <label className="input-label">
          <FileText size={14} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle' }} />
          Текст резюме или краткое описание опыта
        </label>
        <textarea
          className="input-field"
          rows={6}
          placeholder="Например: разрабатывал backend-сервисы на FastAPI, проектировал PostgreSQL-схемы, настраивал Redis..."
          value={data.resume_text}
          onChange={(event) => onChange({ resume_text: event.target.value })}
          style={{ resize: 'vertical' }}
        />
        {errors.resume_text && <p className="input-error">{errors.resume_text}</p>}
      </div>

      <label
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: 10,
          padding: 14,
          borderRadius: 'var(--radius-md)',
          background: 'var(--bg-secondary)',
          color: 'var(--text-secondary)',
          cursor: 'pointer',
        }}
      >
        <input
          type="checkbox"
          checked={data.force_refresh}
          onChange={(event) => onChange({ force_refresh: event.target.checked })}
          style={{ marginTop: 4 }}
        />
        <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontWeight: 700, color: 'var(--text-primary)' }}>
            <RefreshCw size={14} />
            Получить свежий расчёт
          </span>
          <span style={{ fontSize: '0.85rem', lineHeight: 1.5 }}>
            Включите, если уже считали похожий профиль и хотите запросить новую оценку.
          </span>
        </span>
      </label>
    </div>
  );
}
