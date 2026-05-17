'use client';

import type { WizardFormData } from '@/types';
import { Briefcase, MapPin } from 'lucide-react';

interface PersonalInfoProps {
  data: WizardFormData;
  onChange: (data: Partial<WizardFormData>) => void;
  errors: Record<string, string>;
}

export default function PersonalInfo({ data, onChange, errors }: PersonalInfoProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: 4 }}>
          Расскажите о себе
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
          Укажите желаемую должность и ваш город
        </p>
      </div>

      {/* Job Title */}
      <div>
        <label className="input-label">
          <Briefcase size={14} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle' }} />
          Желаемая должность
        </label>
        <input
          className="input-field"
          placeholder="Например: Senior Python Developer"
          value={data.job_title}
          onChange={(e) => onChange({ job_title: e.target.value })}
        />
        {errors.job_title && <p className="input-error">{errors.job_title}</p>}
      </div>

      {/* Location */}
      <div>
        <label className="input-label">
          <MapPin size={14} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle' }} />
          Город / Регион
        </label>
        <input
          className="input-field"
          placeholder="Например: Москва"
          value={data.location}
          onChange={(e) => onChange({ location: e.target.value })}
        />
        {errors.location && <p className="input-error">{errors.location}</p>}
      </div>
    </div>
  );
}
