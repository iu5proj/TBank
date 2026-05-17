'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  RefreshCw,
  Sparkles,
  BarChart3,
  MessageSquare,
  Globe,
  AlertCircle,
} from 'lucide-react';
import Header from '@/components/layout/Header';
import Footer from '@/components/layout/Footer';
import SalaryGauge from '@/components/results/SalaryGauge';
import FactorList from '@/components/results/ShapChart';
import RecommendationCard from '@/components/results/RecommendationCard';
import MarketInsights from '@/components/results/MarketInsights';
import { loadAnalyzeResult } from '@/lib/api';
import type { GptOssSalaryResult } from '@/types';

const MOCK_DATA: GptOssSalaryResult = {
  request_hash: 'demo',
  segment: {
    segment_key: 'backend_developer:python:moscow:middle',
    segment_data_version: '2026-05-16',
  },
  market_sample: {
    candidate_vacancies_received: 8,
    vacancies_used_for_estimation: 5,
    used_vacancy_ids: ['hh-1', 'hh-2', 'hh-3', 'hh-4', 'hh-5'],
    excluded_vacancies: [],
    salary_quantiles: {
      p25: 180000,
      p50: 220000,
      p75: 280000,
    },
  },
  salary_range: {
    min: 180000,
    median: 220000,
    max: 280000,
    currency: 'RUB',
  },
  confidence: {
    score: 0.82,
    level: 'high',
    reason: 'Fresh candidate vacancies.',
  },
  matched_skills: ['Python', 'FastAPI', 'PostgreSQL'],
  missing_skills: [
    {
      skill: 'Docker',
      impact: 'medium',
      reason: 'Часто встречается в вакансиях сегмента.',
    },
  ],
  factor_analysis: [
    {
      factor: 'Опыт',
      impact: 'positive',
      explanation: 'Три года коммерческого опыта соответствуют middle-сегменту.',
    },
    {
      factor: 'Навыки',
      impact: 'positive',
      explanation: 'Python, FastAPI и PostgreSQL совпадают с требованиями выбранных вакансий.',
    },
    {
      factor: 'Docker',
      impact: 'negative',
      explanation: 'Навык часто указан в вакансиях, но отсутствует в профиле.',
    },
  ],
  recommendations: [
    {
      priority: 1,
      type: 'skill_gap',
      title: 'Добавьте Docker в стек',
      resume_change:
        'Опишите опыт контейнеризации сервисов или добавьте учебный проект с Docker Compose.',
      expected_salary_effect: 'может повысить уверенность оценки',
    },
    {
      priority: 2,
      type: 'experience_detail',
      title: 'Уточните масштаб задач',
      resume_change:
        'Добавьте в описание опыта нагрузку, размер команды и зоны ответственности.',
      expected_salary_effect: 'помогает модели отнести профиль к верхней части вилки',
    },
  ],
};

const fadeIn = {
  hidden: { opacity: 0, y: 20 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.1, duration: 0.5 },
  }),
};

export default function ResultsPage() {
  const params = useParams();
  const router = useRouter();
  const requestHash = params.id as string;

  const [data, setData] = useState<GptOssSalaryResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    let active = true;

    queueMicrotask(() => {
      if (!active) return;

      if (requestHash === 'demo') {
        setData(MOCK_DATA);
        setLoading(false);
        return;
      }

      const stored = loadAnalyzeResult(requestHash);
      if (stored) {
        setData(stored);
        setErrorMessage('');
      } else {
        setData(null);
        setErrorMessage(
          'Результат не найден в текущей сессии. Запустите анализ резюме заново.'
        );
      }
      setLoading(false);
    });

    return () => {
      active = false;
    };
  }, [requestHash]);

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
        <Header />
        <main style={{ flex: 1, padding: '60px 0' }}>
          <div className="container-main" style={{ maxWidth: 960 }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
              <div className="skeleton" style={{ height: 32, width: 300 }} />
              <div className="glass-card" style={{ padding: 32 }}>
                <div className="skeleton" style={{ height: 48, width: '60%', marginBottom: 16 }} />
                <div className="skeleton" style={{ height: 14, width: '100%', marginBottom: 16 }} />
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <div className="skeleton" style={{ height: 20, width: 100 }} />
                  <div className="skeleton" style={{ height: 20, width: 100 }} />
                  <div className="skeleton" style={{ height: 20, width: 100 }} />
                </div>
              </div>
            </div>
          </div>
        </main>
        <Footer />
      </div>
    );
  }

  if (!data) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
        <Header />
        <main style={{ flex: 1, padding: '60px 0' }}>
          <div className="container-main" style={{ maxWidth: 720 }}>
            <div className="glass-card" style={{ padding: 32, display: 'flex', flexDirection: 'column', gap: 16 }}>
              <AlertCircle size={28} color="var(--error)" />
              <h1 style={{ fontSize: '1.4rem', fontWeight: 800 }}>
                Не удалось открыть результат
              </h1>
              <p style={{ color: 'var(--text-secondary)' }}>{errorMessage}</p>
              <button
                className="btn-gradient"
                style={{ alignSelf: 'flex-start' }}
                onClick={() => router.push('/resume')}
              >
                <RefreshCw size={16} />
                Запустить анализ
              </button>
            </div>
          </div>
        </main>
        <Footer />
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Header />

      <main style={{ flex: 1, padding: '40px 0 80px' }}>
        <div className="container-main" style={{ maxWidth: 960 }}>
          <motion.div
            custom={0}
            variants={fadeIn}
            initial="hidden"
            animate="visible"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: 28,
              flexWrap: 'wrap',
              gap: 12,
            }}
          >
            <button
              onClick={() => router.push('/resume')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: 'var(--text-secondary)',
                fontWeight: 500,
                fontSize: '0.9rem',
              }}
            >
              <ArrowLeft size={18} />
              Изменить резюме
            </button>
            <button
              className="btn-gradient"
              style={{ padding: '8px 18px', fontSize: '0.85rem' }}
              onClick={() => router.push('/resume')}
            >
              <RefreshCw size={16} />
              Пересчитать
            </button>
          </motion.div>

          <motion.div
            custom={1}
            variants={fadeIn}
            initial="hidden"
            animate="visible"
            className="glass-card"
            style={{ padding: '32px 36px', marginBottom: 24 }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                marginBottom: 20,
              }}
            >
              <Sparkles size={18} color="var(--accent-primary)" />
              <h2
                style={{
                  fontSize: '1.1rem',
                  fontWeight: 700,
                  color: 'var(--text-primary)',
                }}
              >
                Зарплатная вилка
              </h2>
            </div>
            <SalaryGauge salary={data.salary_range} />
          </motion.div>

          <div className="bento-grid">
            <motion.div
              custom={2}
              variants={fadeIn}
              initial="hidden"
              animate="visible"
              className="glass-card bento-wide"
              style={{
                padding: 28,
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  marginBottom: 20,
                }}
              >
                <BarChart3 size={18} color="var(--accent-primary)" />
                <h3
                  style={{
                    fontSize: '1rem',
                    fontWeight: 700,
                    color: 'var(--text-primary)',
                  }}
                >
                  Факторы оценки
                </h3>
              </div>
              <FactorList factors={data.factor_analysis} />
            </motion.div>

            <motion.div
              custom={3}
              variants={fadeIn}
              initial="hidden"
              animate="visible"
              className="glass-card"
              style={{ padding: 28 }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  marginBottom: 20,
                }}
              >
                <Globe size={18} color="var(--accent-primary)" />
                <h3
                  style={{
                    fontSize: '1rem',
                    fontWeight: 700,
                    color: 'var(--text-primary)',
                  }}
                >
                  Обзор рынка
                </h3>
              </div>
              <MarketInsights result={data} />
            </motion.div>
          </div>

          {data.recommendations.length > 0 && (
            <motion.div
              custom={4}
              variants={fadeIn}
              initial="hidden"
              animate="visible"
              style={{ marginTop: 32 }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  marginBottom: 20,
                }}
              >
                <MessageSquare size={18} color="var(--accent-primary)" />
                <h3
                  style={{
                    fontSize: '1.1rem',
                    fontWeight: 700,
                    color: 'var(--text-primary)',
                  }}
                >
                  Рекомендации по улучшению
                </h3>
              </div>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
                  gap: 16,
                }}
              >
                {data.recommendations.map((rec, index) => (
                  <RecommendationCard
                    key={`${rec.priority}-${rec.title}`}
                    rec={rec}
                    index={index}
                  />
                ))}
              </div>
            </motion.div>
          )}
        </div>
      </main>

      <Footer />
    </div>
  );
}
