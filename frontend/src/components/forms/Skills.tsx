'use client';

import { useState, type KeyboardEvent } from 'react';
import type { WizardFormData } from '@/types';
import { X, Plus, Code2 } from 'lucide-react';

interface SkillsProps {
  data: WizardFormData;
  onChange: (data: Partial<WizardFormData>) => void;
  errors: Record<string, string>;
}

const POPULAR_SKILLS = [
  'Python', 'JavaScript', 'TypeScript', 'React', 'Node.js',
  'PostgreSQL', 'Docker', 'Kubernetes', 'FastAPI', 'Git',
  'SQL', 'Linux', 'AWS', 'CI/CD', 'Redis',
  'Java', 'C#', 'Go', 'Rust', 'MongoDB',
];

export default function Skills({ data, onChange, errors }: SkillsProps) {
  const [input, setInput] = useState('');

  const addSkill = (skill: string) => {
    const trimmed = skill.trim();
    if (trimmed && !data.skills.includes(trimmed)) {
      onChange({ skills: [...data.skills, trimmed] });
    }
    setInput('');
  };

  const removeSkill = (skill: string) => {
    onChange({ skills: data.skills.filter((s) => s !== skill) });
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addSkill(input);
    }
  };

  const suggestions = POPULAR_SKILLS.filter(
    (s) => !data.skills.includes(s)
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: 4 }}>
          Навыки
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
          Добавьте ваши технические и профессиональные навыки
        </p>
      </div>

      {/* Input */}
      <div>
        <label className="input-label">
          <Code2 size={14} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle' }} />
          Введите навык и нажмите Enter
        </label>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            className="input-field"
            placeholder="Python, Docker, SQL..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <button
            type="button"
            onClick={() => addSkill(input)}
            className="btn-gradient"
            style={{ padding: '10px 16px', flexShrink: 0 }}
          >
            <Plus size={18} />
          </button>
        </div>
        {errors.skills && <p className="input-error">{errors.skills}</p>}
      </div>

      {/* Selected skills */}
      {data.skills.length > 0 && (
        <div>
          <label className="input-label" style={{ marginBottom: 10 }}>
            Выбранные навыки ({data.skills.length})
          </label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {data.skills.map((skill) => (
              <span key={skill} className="skill-tag">
                {skill}
                <button type="button" onClick={() => removeSkill(skill)}>
                  <X size={14} />
                </button>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Suggestions */}
      {suggestions.length > 0 && (
        <div>
          <label className="input-label" style={{ marginBottom: 10 }}>
            Популярные навыки
          </label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {suggestions.slice(0, 12).map((skill) => (
              <button
                key={skill}
                type="button"
                onClick={() => addSkill(skill)}
                style={{
                  padding: '6px 14px',
                  borderRadius: 'var(--radius-full)',
                  border: '1px solid var(--border-light)',
                  background: 'var(--bg-primary)',
                  color: 'var(--text-secondary)',
                  cursor: 'pointer',
                  fontSize: '0.85rem',
                  fontWeight: 500,
                  transition: 'all 0.2s',
                }}
              >
                + {skill}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
