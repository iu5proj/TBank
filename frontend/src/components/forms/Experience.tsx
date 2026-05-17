'use client';

import { useState } from 'react';
import type { ExperienceEntry, WizardFormData } from '@/types';
import { Plus, Trash2, Clock, Building2, Info } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface ExperienceProps {
  data: WizardFormData;
  onChange: (data: Partial<WizardFormData>) => void;
  errors: Record<string, string>;
}

const emptyEntry: ExperienceEntry = {
  company: '',
  title: '',
  duration_months: 12,
  description: '',
};

export default function Experience({ data, onChange, errors }: ExperienceProps) {
  const entries = data.experience_entries;
  const hasExperience = data.experience_years > 0;
  const [experienceYearsInput, setExperienceYearsInput] = useState(
    data.experience_years > 0 ? String(data.experience_years) : ''
  );

  const handleYearsChange = (value: string) => {
    setExperienceYearsInput(value);

    if (value.trim() === '') {
      onChange({ experience_years: 0, experience_entries: [] });
      return;
    }

    const years = parseFloat(value);
    const parsed = isNaN(years) ? 0 : Math.max(0, years);
    onChange({ experience_years: parsed });
    // Если опыт стал 0, очищаем места работы
    if (parsed === 0) {
      onChange({ experience_years: 0, experience_entries: [] });
    }
  };

  const addEntry = () => {
    onChange({ experience_entries: [...entries, { ...emptyEntry }] });
  };

  const removeEntry = (index: number) => {
    onChange({ experience_entries: entries.filter((_, i) => i !== index) });
  };

  const updateEntry = (index: number, field: keyof ExperienceEntry, value: string | number) => {
    const updated = entries.map((e, i) =>
      i === index ? { ...e, [field]: value } : e
    );
    onChange({ experience_entries: updated });
  };

  const updateDuration = (index: number, value: string) => {
    if (value.trim() === '') {
      updateEntry(index, 'duration_months', 0);
      return;
    }

    const months = parseInt(value, 10);
    updateEntry(
      index,
      'duration_months',
      Number.isNaN(months) ? 0 : Math.min(600, Math.max(1, months))
    );
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: 4 }}>
          Опыт работы
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
          Укажите общий стаж — от этого зависит точность оценки
        </p>
      </div>

      {/* Total experience */}
      <div>
        <label className="input-label">
          <Clock size={14} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle' }} />
          Общий опыт работы (лет)
        </label>
        <input
          className="input-field"
          type="number"
          min={0}
          max={50}
          step={0.5}
          placeholder="0"
          value={experienceYearsInput}
          onChange={(e) => handleYearsChange(e.target.value)}
        />
        {errors.experience_years && (
          <p className="input-error">{errors.experience_years}</p>
        )}

        {/* Hint for 0 experience */}
        <AnimatePresence>
          {!hasExperience && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 8,
                padding: '10px 14px',
                marginTop: 10,
                borderRadius: 'var(--radius-sm)',
                background: 'var(--accent-light)',
                color: 'var(--accent-primary)',
                fontSize: '0.85rem',
                lineHeight: 1.5,
              }}
            >
              <Info size={16} style={{ flexShrink: 0, marginTop: 2 }} />
              <span>
                Без опыта? Не проблема — ML-модель оценит вашу стоимость по навыкам,
                образованию и региону. Переходите к следующему шагу.
              </span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Experience entries — only show when experience > 0 */}
      <AnimatePresence>
        {hasExperience && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3 }}
            style={{ display: 'flex', flexDirection: 'column', gap: 16, overflow: 'hidden' }}
          >
            <div>
              <label className="input-label" style={{ marginBottom: 4 }}>
                <Building2 size={14} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle' }} />
                Места работы
              </label>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', margin: 0 }}>
                Детализация повышает точность прогноза — ML анализирует описания
              </p>
            </div>

            {entries.map((entry, i) => (
              <div
                key={i}
                style={{
                  padding: 20,
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-light)',
                  background: 'var(--bg-secondary)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 12,
                  position: 'relative',
                }}
              >
                <button
                  type="button"
                  onClick={() => removeEntry(i)}
                  style={{
                    position: 'absolute',
                    top: 12,
                    right: 12,
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    color: 'var(--error)',
                    opacity: 0.6,
                    transition: 'opacity 0.2s',
                  }}
                  onMouseOver={(e) => (e.currentTarget.style.opacity = '1')}
                  onMouseOut={(e) => (e.currentTarget.style.opacity = '0.6')}
                >
                  <Trash2 size={16} />
                </button>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div>
                    <label className="input-label" style={{ fontSize: '0.8rem' }}>Компания</label>
                    <input
                      className="input-field"
                      placeholder="Яндекс"
                      value={entry.company}
                      onChange={(e) => updateEntry(i, 'company', e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="input-label" style={{ fontSize: '0.8rem' }}>Должность</label>
                    <input
                      className="input-field"
                      placeholder="Backend Developer"
                      value={entry.title}
                      onChange={(e) => updateEntry(i, 'title', e.target.value)}
                    />
                  </div>
                </div>

                <div>
                  <label className="input-label" style={{ fontSize: '0.8rem' }}>
                    Длительность (месяцев)
                  </label>
                  <input
                    className="input-field"
                    type="number"
                    min={1}
                    max={600}
                    placeholder="24"
                    value={entry.duration_months || ''}
                    onChange={(e) => updateDuration(i, e.target.value)}
                  />
                </div>

                <div>
                  <label className="input-label" style={{ fontSize: '0.8rem' }}>
                    Описание обязанностей
                  </label>
                  <textarea
                    className="input-field"
                    rows={3}
                    placeholder="Разрабатывал высоконагруженные сервисы на Python..."
                    value={entry.description}
                    onChange={(e) => updateEntry(i, 'description', e.target.value)}
                    style={{ resize: 'vertical' }}
                  />
                </div>
              </div>
            ))}

            <button
              type="button"
              onClick={addEntry}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
                padding: '12px 20px',
                border: '2px dashed var(--border-medium)',
                borderRadius: 'var(--radius-md)',
                background: 'transparent',
                color: 'var(--text-secondary)',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '0.9rem',
                transition: 'all 0.2s',
              }}
            >
              <Plus size={18} />
              Добавить место работы
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
