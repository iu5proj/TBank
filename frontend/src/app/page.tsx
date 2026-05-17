'use client';

import Link from 'next/link';
import { motion } from 'framer-motion';
import {
  ArrowRight,
  BarChart3,
  FileText,
  Lightbulb,
  Target,
  TrendingUp,
  Zap,
} from 'lucide-react';
import Header from '@/components/layout/Header';
import Footer from '@/components/layout/Footer';

const fadeUp = {
  hidden: { opacity: 0, y: 30 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.15, duration: 0.6, ease: [0.22, 1, 0.36, 1] as const },
  }),
};

const steps = [
  {
    icon: FileText,
    title: 'Заполните профиль',
    desc: 'Укажите должность, опыт, навыки и город — это займёт 2 минуты.',
    color: '#6366f1',
  },
  {
    icon: BarChart3,
    title: 'Получите оценку',
    desc: 'ML-модель проанализирует тысячи вакансий и рассчитает вашу зарплатную вилку.',
    color: '#8b5cf6',
  },
  {
    icon: Lightbulb,
    title: 'Улучшайте резюме',
    desc: 'Изучите рекомендации, добавьте нужные навыки — и пересчитайте вилку.',
    color: '#a78bfa',
  },
];

const stats = [
  { value: '150K+', label: 'Вакансий проанализировано' },
  { value: '25+', label: 'Регионов России' },
  { value: '350+', label: 'Навыков в базе' },
  { value: '~88%', label: 'Точность прогноза' },
];

export default function LandingPage() {
  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Header />

      {/* ─── Hero Section ──────────────────────────────── */}
      <section
        style={{
          position: 'relative',
          overflow: 'hidden',
          padding: '80px 0 100px',
          background: 'var(--bg-primary)',
        }}
      >
        {/* Background orbs */}
        <div
          className="bg-orb animate-float"
          style={{
            width: 500,
            height: 500,
            background: 'rgba(99, 102, 241, 0.08)',
            top: -100,
            right: -150,
          }}
        />
        <div
          className="bg-orb"
          style={{
            width: 400,
            height: 400,
            background: 'rgba(139, 92, 246, 0.06)',
            bottom: -100,
            left: -100,
            animationDelay: '2s',
          }}
        />

        <div
          className="container-main"
          style={{ position: 'relative', zIndex: 1, textAlign: 'center' }}
        >
          {/* Heading */}
          <motion.h1
            custom={0}
            variants={fadeUp}
            initial="hidden"
            animate="visible"
            style={{
              fontSize: 'clamp(2.2rem, 5vw, 3.8rem)',
              fontWeight: 900,
              lineHeight: 1.1,
              letterSpacing: '-0.03em',
              color: 'var(--text-primary)',
              maxWidth: 720,
              margin: '0 auto 20px',
            }}
          >
            Узнай свою{' '}
            <span
              style={{
                background: 'var(--accent-gradient)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
              }}
            >
              рыночную стоимость
            </span>
          </motion.h1>

          {/* Subtitle */}
          <motion.p
            custom={1}
            variants={fadeUp}
            initial="hidden"
            animate="visible"
            style={{
              fontSize: 'clamp(1rem, 2vw, 1.2rem)',
              color: 'var(--text-secondary)',
              maxWidth: 560,
              margin: '0 auto 40px',
              lineHeight: 1.7,
            }}
          >
            Заполни профиль — получи точную зарплатную вилку, факторный анализ
            и персональные рекомендации по увеличению дохода.
          </motion.p>

          {/* CTA */}
          <motion.div
            custom={2}
            variants={fadeUp}
            initial="hidden"
            animate="visible"
          >
            <Link
              href="/resume"
              className="btn-gradient"
              style={{
                fontSize: '1.05rem',
                padding: '14px 36px',
                textDecoration: 'none',
              }}
            >
              Оценить резюме бесплатно
              <ArrowRight size={18} />
            </Link>
          </motion.div>
        </div>
      </section>

      {/* ─── Stats Section ─────────────────────────────── */}
      <section style={{ padding: '0 0 80px', background: 'var(--bg-primary)' }}>
        <div className="container-main">
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
              gap: 20,
              background: 'var(--bg-secondary)',
              borderRadius: 'var(--radius-xl)',
              padding: '32px 24px',
              border: '1px solid var(--border-light)',
            }}
          >
            {stats.map((stat, i) => (
              <motion.div
                key={stat.label}
                custom={i}
                variants={fadeUp}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true }}
                style={{ textAlign: 'center' }}
              >
                <div
                  style={{
                    fontSize: '2rem',
                    fontWeight: 800,
                    background: 'var(--accent-gradient)',
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent',
                    backgroundClip: 'text',
                  }}
                >
                  {stat.value}
                </div>
                <div style={{ color: 'var(--text-tertiary)', fontSize: '0.85rem', marginTop: 4 }}>
                  {stat.label}
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── How it Works ──────────────────────────────── */}
      <section style={{ padding: '80px 0', background: 'var(--bg-secondary)' }}>
        <div className="container-main">
          <motion.div
            custom={0}
            variants={fadeUp}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            style={{ textAlign: 'center', marginBottom: 56 }}
          >
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '6px 16px',
                background: 'var(--accent-light)',
                color: 'var(--accent-primary)',
                borderRadius: 'var(--radius-full)',
                fontSize: '0.8rem',
                fontWeight: 600,
                marginBottom: 16,
              }}
            >
              <Zap size={14} />
              Как это работает
            </span>
            <h2
              style={{
                fontSize: 'clamp(1.6rem, 3vw, 2.4rem)',
                fontWeight: 800,
                letterSpacing: '-0.02em',
                color: 'var(--text-primary)',
              }}
            >
              Три шага до идеального резюме
            </h2>
          </motion.div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
              gap: 24,
            }}
          >
            {steps.map((step, i) => (
              <motion.div
                key={step.title}
                custom={i + 1}
                variants={fadeUp}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true }}
                className="glass-card"
                style={{ padding: 32 }}
              >
                <div
                  style={{
                    width: 56,
                    height: 56,
                    borderRadius: 14,
                    background: `${step.color}12`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    marginBottom: 20,
                  }}
                >
                  <step.icon size={28} color={step.color} />
                </div>
                <div
                  style={{
                    fontSize: '0.8rem',
                    fontWeight: 700,
                    color: 'var(--accent-primary)',
                    marginBottom: 8,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                  }}
                >
                  Шаг {i + 1}
                </div>
                <h3
                  style={{
                    fontSize: '1.2rem',
                    fontWeight: 700,
                    color: 'var(--text-primary)',
                    marginBottom: 10,
                  }}
                >
                  {step.title}
                </h3>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem', lineHeight: 1.6 }}>
                  {step.desc}
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── Features ──────────────────────────────────── */}
      <section style={{ padding: '80px 0', background: 'var(--bg-primary)' }}>
        <div className="container-main">
          <motion.div
            custom={0}
            variants={fadeUp}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            style={{ textAlign: 'center', marginBottom: 56 }}
          >
            <h2
              style={{
                fontSize: 'clamp(1.6rem, 3vw, 2.4rem)',
                fontWeight: 800,
                letterSpacing: '-0.02em',
                color: 'var(--text-primary)',
                marginBottom: 12,
              }}
            >
              Что вы получите
            </h2>
            <p style={{ color: 'var(--text-secondary)', maxWidth: 500, margin: '0 auto' }}>
              Не просто цифра — а полная картина вашей позиции на рынке
            </p>
          </motion.div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 24 }}>
            {[
              {
                icon: Target,
                title: 'Зарплатная вилка (p25 / p50 / p75)',
                desc: 'Три квантиля: минимум, медиана и максимум рынка для вашего профиля.',
              },
              {
                icon: BarChart3,
                title: 'SHAP-анализ факторов',
                desc: 'Узнайте, какие навыки повышают вашу оценку, а каких критически не хватает.',
              },
              {
                icon: TrendingUp,
                title: 'Итеративное улучшение',
                desc: 'Добавьте рекомендованный навык — пересчитайте вилку и увидьте рост.',
              },
            ].map((feat, i) => (
              <motion.div
                key={feat.title}
                custom={i + 1}
                variants={fadeUp}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true }}
                style={{
                  padding: 28,
                  borderRadius: 'var(--radius-lg)',
                  border: '1px solid var(--border-light)',
                  background: 'var(--bg-primary)',
                  transition: 'box-shadow 0.3s',
                }}
              >
                <feat.icon size={24} color="var(--accent-primary)" style={{ marginBottom: 16 }} />
                <h3 style={{ fontWeight: 700, fontSize: '1.05rem', marginBottom: 8, color: 'var(--text-primary)' }}>
                  {feat.title}
                </h3>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: 1.6 }}>
                  {feat.desc}
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── CTA Bottom ────────────────────────────────── */}
      <section
        style={{
          padding: '80px 0',
          background: 'var(--bg-secondary)',
          textAlign: 'center',
        }}
      >
        <div className="container-main">
          <motion.div
            custom={0}
            variants={fadeUp}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
          >
            <h2
              style={{
                fontSize: 'clamp(1.5rem, 3vw, 2.2rem)',
                fontWeight: 800,
                marginBottom: 16,
                color: 'var(--text-primary)',
              }}
            >
              Готовы узнать свою цену?
            </h2>
            <p
              style={{
                color: 'var(--text-secondary)',
                marginBottom: 32,
                maxWidth: 440,
                margin: '0 auto 32px',
              }}
            >
              Бесплатно. Без регистрации. Результат за 30 секунд.
            </p>
            <Link
              href="/resume"
              className="btn-gradient"
              style={{ fontSize: '1.05rem', padding: '14px 36px', textDecoration: 'none' }}
            >
              Начать оценку
              <ArrowRight size={18} />
            </Link>
          </motion.div>
        </div>
      </section>

      <Footer />
    </div>
  );
}
