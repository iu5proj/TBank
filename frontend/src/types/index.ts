/* TypeScript mirrors of the FastAPI Pydantic contracts. */

export interface ExperienceEntry {
  company: string;
  title: string;
  duration_months: number;
  description: string;
}

export type EducationLevel = 'none' | 'bachelor' | 'master' | 'phd';

export interface ResumeCreate {
  job_title: string;
  experience_years: number;
  skills: string[];
  location: string;
  education_level: EducationLevel;
  experience_entries: ExperienceEntry[];
}

export interface ResumeUpdate {
  job_title?: string;
  experience_years?: number;
  skills?: string[];
  location?: string;
  education_level?: EducationLevel;
  experience_entries?: ExperienceEntry[];
}

export interface ResumeResponse {
  id: string;
  user_id: string;
  job_title: string;
  experience_years: number;
  skills: string[];
  location: string;
  education_level: string;
  experience_entries: ExperienceEntry[];
  updated_at: string;
  created_at: string;
}

export interface ResumeProfile {
  title: string;
  experience_years: number;
  location: string;
  skills: string[];
  resume_text: string;
  current_salary?: number | null;
}

export interface AnalyzeOptions {
  target_salary?: number | null;
  force_refresh: boolean;
}

export interface AnalyzeRequest {
  profile: ResumeProfile;
  options: AnalyzeOptions;
}

export interface SegmentOut {
  segment_key: string;
  segment_data_version: string;
}

export interface SalaryQuantiles {
  p25: number;
  p50: number;
  p75: number;
}

export interface ExcludedVacancy {
  id: string;
  reason: string;
}

export interface MarketSample {
  candidate_vacancies_received: number;
  vacancies_used_for_estimation: number;
  used_vacancy_ids: string[];
  excluded_vacancies: ExcludedVacancy[];
  salary_quantiles: SalaryQuantiles;
}

export interface SalaryRange {
  min: number;
  median: number;
  max: number;
  currency: 'RUB';
}

export interface Confidence {
  score: number;
  level: 'low' | 'medium' | 'high';
  reason: string;
}

export interface MissingSkill {
  skill: string;
  impact: 'low' | 'medium' | 'high';
  reason: string;
}

export interface Factor {
  factor: string;
  impact: 'positive' | 'negative' | 'neutral';
  explanation: string;
}

export type RecommendationType =
  | 'skill_gap'
  | 'experience_detail'
  | 'resume_clarity'
  | 'salary_expectation';

export interface AnalyzeRecommendation {
  priority: number;
  type: RecommendationType;
  title: string;
  resume_change: string;
  expected_salary_effect?: string | null;
}

export interface GptOssSalaryResult {
  request_hash: string;
  segment: SegmentOut;
  market_sample: MarketSample;
  salary_range: SalaryRange;
  confidence: Confidence;
  matched_skills: string[];
  missing_skills: MissingSkill[];
  factor_analysis: Factor[];
  recommendations: AnalyzeRecommendation[];
}

export interface AnalyzeResponse {
  status: 'success' | 'error';
  source?: 'gpt-oss-20b' | 'grounded-fallback' | 'cache' | null;
  data?: GptOssSalaryResult | null;
  code?: string | null;
  message?: string | null;
  validation_errors?: string[] | null;
}

export interface WizardFormData {
  job_title: string;
  location: string;
  experience_years: number;
  experience_entries: ExperienceEntry[];
  skills: string[];
  education_level: EducationLevel;
  resume_text: string;
  current_salary: number | null;
  target_salary: number | null;
  force_refresh: boolean;
}
