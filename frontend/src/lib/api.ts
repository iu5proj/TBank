import type {
  AnalyzeRequest,
  AnalyzeResponse,
  GptOssSalaryResult,
  ResumeCreate,
  ResumeResponse,
  ResumeUpdate,
} from '@/types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';
const API_AUTH_TOKEN = process.env.NEXT_PUBLIC_API_AUTH_TOKEN || '';
const REQUEST_TIMEOUT = 15_000;
const ANALYZE_TIMEOUT = Number(process.env.NEXT_PUBLIC_ANALYZE_TIMEOUT_MS || 120_000);
const RESULT_STORAGE_PREFIX = 'zarabotok:analysis:';

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

function formatErrorDetail(error: unknown, fallback: string): string {
  if (!error || typeof error !== 'object') return fallback;

  const detail = (error as { detail?: unknown }).detail;
  if (typeof detail === 'string') return detail;

  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === 'string') return item;
        if (item && typeof item === 'object') {
          const message = (item as { msg?: unknown }).msg;
          const location = (item as { loc?: unknown }).loc;
          if (typeof message === 'string') {
            return Array.isArray(location)
              ? `${location.join('.')}: ${message}`
              : message;
          }
        }
        return JSON.stringify(item);
      })
      .join('; ');
  }

  const message = (error as { message?: unknown }).message;
  return typeof message === 'string' ? message : fallback;
}

function proxyErrorMessage(status: number, endpoint: string): string {
  if (status === 500 && API_BASE.startsWith('/')) {
    return `Backend недоступен. Запустите FastAPI на http://localhost:8000 и попробуйте снова. Запрос: ${API_BASE}${endpoint}`;
  }

  return `API error ${status}`;
}

async function request<T>(
  endpoint: string,
  options?: RequestInit & { timeout?: number }
): Promise<T> {
  const { timeout = REQUEST_TIMEOUT, ...fetchOptions } = options || {};
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      ...fetchOptions,
      headers: {
        'Content-Type': 'application/json',
        ...(API_AUTH_TOKEN ? { Authorization: `Bearer ${API_AUTH_TOKEN}` } : {}),
        ...fetchOptions.headers,
      },
      signal: controller.signal,
    });

    if (!res.ok) {
      const error = await res.json().catch(() => null);
      throw new ApiError(
        res.status,
        formatErrorDetail(error, proxyErrorMessage(res.status, endpoint))
      );
    }

    return res.json();
  } catch (err) {
    if (err instanceof ApiError) throw err;

    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new ApiError(
        408,
        `Запрос превысил таймаут (${Math.round(timeout / 1000)} c)`
      );
    }

    throw new ApiError(
      0,
      `Не удалось подключиться к серверу. Проверьте, что backend запущен и доступен по ${API_BASE}`
    );
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function checkHealth(): Promise<boolean> {
  try {
    const baseUrl = API_BASE.replace(/\/api\/v1$/, '');
    const res = await fetch(`${baseUrl}/health`, {
      signal: AbortSignal.timeout(3000),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function createResume(
  data: ResumeCreate
): Promise<ResumeResponse> {
  return request('/resumes', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function getResume(id: string): Promise<ResumeResponse> {
  return request(`/resumes/${id}`);
}

export async function updateResume(
  id: string,
  data: ResumeUpdate
): Promise<ResumeResponse> {
  return request(`/resumes/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function analyzeResume(
  data: AnalyzeRequest
): Promise<GptOssSalaryResult> {
  const response = await request<AnalyzeResponse>('/analyze', {
    method: 'POST',
    body: JSON.stringify(data),
    timeout: ANALYZE_TIMEOUT,
  });

  if (response.status !== 'success' || !response.data) {
    const validation = response.validation_errors?.join('; ');
    throw new ApiError(
      200,
      validation || response.message || response.code || 'Анализ не выполнен'
    );
  }

  return response.data;
}

export function saveAnalyzeResult(result: GptOssSalaryResult): void {
  if (typeof window === 'undefined') return;
  sessionStorage.setItem(
    `${RESULT_STORAGE_PREFIX}${result.request_hash}`,
    JSON.stringify(result)
  );
}

export function loadAnalyzeResult(
  requestHash: string
): GptOssSalaryResult | null {
  if (typeof window === 'undefined') return null;

  const raw = sessionStorage.getItem(`${RESULT_STORAGE_PREFIX}${requestHash}`);
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw) as GptOssSalaryResult;
    return parsed.request_hash === requestHash ? parsed : null;
  } catch {
    return null;
  }
}
