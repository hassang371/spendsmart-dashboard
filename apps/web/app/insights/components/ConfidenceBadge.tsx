'use client';

import type { ForecastConfidence, ModelType } from '@/lib/api/forecast.types';

interface ConfidenceBadgeProps {
  modelType: ModelType;
  confidence: ForecastConfidence;
}

function copyFor(modelType: ModelType, confidence: ForecastConfidence): string {
  if (modelType === 'chronos2') {
    return 'Population model · getting to know your pattern';
  }
  if (confidence === 'high') {
    return 'Personalised · high confidence';
  }
  if (confidence === 'medium') {
    return 'Personalised · medium confidence';
  }
  return 'Personalised · low confidence';
}

/** Per LLD 011 §ConfidenceBadge — sets honest expectations. */
export default function ConfidenceBadge({ modelType, confidence }: ConfidenceBadgeProps) {
  const palette =
    confidence === 'high'
      ? 'border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-700 dark:bg-emerald-950 dark:text-emerald-100'
      : confidence === 'medium'
        ? 'border-blue-300 bg-blue-50 text-blue-900 dark:border-blue-700 dark:bg-blue-950 dark:text-blue-100'
        : 'border-slate-300 bg-slate-50 text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100';

  return (
    <span
      data-testid="confidence-badge"
      data-confidence={confidence}
      data-model-type={modelType}
      className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-medium ${palette}`}
    >
      {copyFor(modelType, confidence)}
    </span>
  );
}
