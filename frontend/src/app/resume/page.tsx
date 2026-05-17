'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertCircle, ArrowLeft, ArrowRight, Loader2, Sparkles } from 'lucide-react';
import Header from '@/components/layout/Header';
import Footer from '@/components/layout/Footer';
import WizardStepper from '@/components/forms/WizardStepper';
import PersonalInfo from '@/components/forms/PersonalInfo';
import Experience from '@/components/forms/Experience';
import Skills from '@/components/forms/Skills';
import Goals from '@/components/forms/Goals';
import { analyzeResume, saveAnalyzeResult } from '@/lib/api';
import type { WizardFormData } from '@/types';

const STEPS = ['Профиль', 'Опыт', 'Навыки', 'Цели'];

const DRAFT_STORAGE_KEY = 'zarabotok:resume-draft';
const STEP_ERROR_FIELDS: Record<number, string[]> = {
  1: ['job_title', 'location'],
  2: ['experience_years'],
  3: ['skills'],
  4: ['current_salary', 'target_salary', 'resume_text'],
};

const initialData: WizardFormData = {
  job_title: '',
  location: '',
  experience_years: 0,
  experience_entries: [],
  skills: [],
  education_level: 'none',
  resume_text: '',
  current_salary: null,
  target_salary: null,
  force_refresh: false,
};

function loadDraft(): WizardFormData {
  if (typeof window === 'undefined') return initialData;

  try {
    const raw = sessionStorage.getItem(DRAFT_STORAGE_KEY);
    if (!raw) return initialData;

    const parsed = JSON.parse(raw) as Partial<WizardFormData>;
    return {
      ...initialData,
      ...parsed,
      skills: Array.isArray(parsed.skills) ? parsed.skills : initialData.skills,
      experience_entries: Array.isArray(parsed.experience_entries)
        ? parsed.experience_entries
        : initialData.experience_entries,
      current_salary:
        typeof parsed.current_salary === 'number' ? parsed.current_salary : null,
      target_salary:
        typeof parsed.target_salary === 'number' ? parsed.target_salary : null,
      force_refresh: Boolean(parsed.force_refresh),
    };
  } catch {
    return initialData;
  }
}

function getInvalidSteps(validationErrors: Record<string, string>): number[] {
  return Object.entries(STEP_ERROR_FIELDS)
    .filter(([, fields]) => fields.some((field) => validationErrors[field]))
    .map(([step]) => Number(step));
}

function buildResumeText(formData: WizardFormData): string {
  const manualText = formData.resume_text.trim();
  if (manualText) return manualText;

  const experienceText = formData.experience_entries
    .filter((entry) => entry.company.trim() || entry.title.trim() || entry.description.trim())
    .map((entry) =>
      [
        entry.title && `Должность: ${entry.title}`,
        entry.company && `Компания: ${entry.company}`,
        `Длительность: ${entry.duration_months} мес.`,
        entry.description && `Описание: ${entry.description}`,
      ]
        .filter(Boolean)
        .join('; ')
    )
    .join('\n');

  return [
    `Позиция: ${formData.job_title}`,
    `Опыт: ${formData.experience_years} лет`,
    `Локация: ${formData.location}`,
    `Навыки: ${formData.skills.join(', ')}`,
    experienceText,
  ]
    .filter(Boolean)
    .join('\n');
}

function WizardForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const stepParam = parseInt(searchParams.get('step') || '1');
  const currentStep = Math.min(Math.max(stepParam, 1), 4);

  const [formData, setFormData] = useState<WizardFormData>(loadDraft);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    sessionStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(formData));
  }, [formData]);

  const updateData = (partial: Partial<WizardFormData>) => {
    setFormData((prev) => ({ ...prev, ...partial }));
    setSubmitError('');

    const updatedKeys = Object.keys(partial);
    setErrors((prev) => {
      const next = { ...prev };
      updatedKeys.forEach((key) => delete next[key]);
      return next;
    });
  };

  const collectErrors = (step: number | 'all'): Record<string, string> => {
    const newErrors: Record<string, string> = {};
    const shouldValidate = (target: number) => step === 'all' || step === target;

    if (shouldValidate(1)) {
      if (!formData.job_title.trim()) {
        newErrors.job_title = 'Укажите желаемую должность';
      }
      if (!formData.location.trim()) {
        newErrors.location = 'Укажите город';
      }
    }

    if (shouldValidate(2)) {
      if (formData.experience_years < 0 || formData.experience_years > 50) {
        newErrors.experience_years = 'Опыт должен быть от 0 до 50 лет';
      }
    }

    if (shouldValidate(3)) {
      if (formData.skills.length === 0) {
        newErrors.skills = 'Добавьте хотя бы один навык';
      }
    }

    if (shouldValidate(4)) {
      if (formData.current_salary !== null && formData.current_salary <= 0) {
        newErrors.current_salary = 'Зарплата должна быть больше 0';
      }
      if (formData.target_salary !== null && formData.target_salary <= 0) {
        newErrors.target_salary = 'Зарплата должна быть больше 0';
      }
      if (formData.resume_text.length > 12_000) {
        newErrors.resume_text = 'Описание не должно превышать 12 000 символов';
      }
    }

    return newErrors;
  };

  const validate = (step: number | 'all' = currentStep): boolean => {
    const newErrors = collectErrors(step);
    setErrors((prev) => {
      if (step === 'all') return newErrors;

      const next = { ...prev };
      STEP_ERROR_FIELDS[step]?.forEach((field) => delete next[field]);
      return { ...next, ...newErrors };
    });
    return Object.keys(newErrors).length === 0;
  };

  const getFirstInvalidStep = (validationErrors: Record<string, string>): number => {
    return getInvalidSteps(validationErrors)[0] ?? 4;
  };

  const goNext = () => {
    if (!validate()) return;
    if (currentStep < 4) {
      router.push(`/resume?step=${currentStep + 1}`);
    }
  };

  const goBack = () => {
    if (currentStep > 1) {
      router.push(`/resume?step=${currentStep - 1}`);
    }
  };

  const handleSubmit = async () => {
    const validationErrors = collectErrors('all');
    if (Object.keys(validationErrors).length > 0) {
      const firstInvalidStep = getFirstInvalidStep(validationErrors);
      setErrors(validationErrors);
      setSubmitError('Заполните обязательные поля, чтобы запустить оценку.');
      if (firstInvalidStep !== currentStep) {
        router.push(`/resume?step=${firstInvalidStep}`);
      }
      return;
    }

    setLoading(true);
    setSubmitError('');

    try {
      const result = await analyzeResume({
        profile: {
          title: formData.job_title,
          experience_years: formData.experience_years,
          location: formData.location,
          skills: formData.skills,
          resume_text: buildResumeText(formData),
          current_salary: formData.current_salary,
        },
        options: {
          target_salary: formData.target_salary,
          force_refresh: formData.force_refresh,
        },
      });

      saveAnalyzeResult(result);
      router.push(`/results/${encodeURIComponent(result.request_hash)}`);
    } catch (error) {
      setSubmitError(
        error instanceof Error
          ? error.message
          : 'Не удалось выполнить анализ. Проверьте backend и попробуйте снова.'
      );
    } finally {
      setLoading(false);
    }
  };

  const slideVariants = {
    enter: (direction: number) => ({ x: direction > 0 ? 80 : -80, opacity: 0 }),
    center: { x: 0, opacity: 1 },
    exit: (direction: number) => ({ x: direction > 0 ? -80 : 80, opacity: 0 }),
  };

  const stepComponents: Record<number, React.ReactNode> = {
    1: <PersonalInfo data={formData} onChange={updateData} errors={errors} />,
    2: <Experience data={formData} onChange={updateData} errors={errors} />,
    3: <Skills data={formData} onChange={updateData} errors={errors} />,
    4: <Goals data={formData} onChange={updateData} errors={errors} />,
  };
  const invalidSteps = getInvalidSteps(errors);

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Header />

      <main style={{ flex: 1, padding: '40px 0 80px' }}>
        <div className="container-main" style={{ maxWidth: 680 }}>
          <WizardStepper
            currentStep={currentStep}
            steps={STEPS}
            invalidSteps={invalidSteps}
          />

          <div
            className="glass-card"
            style={{ padding: '36px 32px', minHeight: 340 }}
          >
            <AnimatePresence mode="wait" custom={currentStep}>
              <motion.div
                key={currentStep}
                custom={1}
                variants={slideVariants}
                initial="enter"
                animate="center"
                exit="exit"
                transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
              >
                {stepComponents[currentStep]}
              </motion.div>
            </AnimatePresence>
          </div>

          {submitError && (
            <div
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 10,
                marginTop: 16,
                padding: 14,
                borderRadius: 'var(--radius-md)',
                background: 'var(--error-light)',
                color: 'var(--error)',
                fontSize: '0.9rem',
                lineHeight: 1.5,
              }}
            >
              <AlertCircle size={18} style={{ flexShrink: 0, marginTop: 2 }} />
              <span>{submitError}</span>
            </div>
          )}

          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              marginTop: 24,
              gap: 12,
            }}
          >
            <button
              type="button"
              onClick={goBack}
              disabled={currentStep === 1}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '12px 24px',
                borderRadius: 'var(--radius-full)',
                border: '1px solid var(--border-light)',
                background: 'var(--bg-primary)',
                color: currentStep === 1 ? 'var(--text-tertiary)' : 'var(--text-secondary)',
                cursor: currentStep === 1 ? 'not-allowed' : 'pointer',
                fontWeight: 600,
                fontSize: '0.95rem',
                transition: 'all 0.2s',
              }}
            >
              <ArrowLeft size={18} />
              Назад
            </button>

            {currentStep < 4 ? (
              <button
                type="button"
                onClick={goNext}
                className="btn-gradient"
              >
                Далее
                <ArrowRight size={18} />
              </button>
            ) : (
              <button
                type="button"
                onClick={handleSubmit}
                className="btn-gradient"
                disabled={loading}
                style={{ minWidth: 180 }}
              >
                {loading ? (
                  <>
                    <Loader2 size={18} className="animate-spin" />
                    Анализируем...
                  </>
                ) : (
                  <>
                    <Sparkles size={18} />
                    Оценить резюме
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}

export default function ResumePage() {
  return (
    <Suspense>
      <WizardForm />
    </Suspense>
  );
}
