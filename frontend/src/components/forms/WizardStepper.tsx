'use client';

import { Check } from 'lucide-react';

interface WizardStepperProps {
  currentStep: number;
  steps: string[];
  invalidSteps?: number[];
}

export default function WizardStepper({
  currentStep,
  steps,
  invalidSteps = [],
}: WizardStepperProps) {
  return (
    <div className="stepper">
      {steps.map((label, i) => {
        const stepNum = i + 1;
        const isActive = stepNum === currentStep;
        const isCompleted = stepNum < currentStep;
        const hasError = invalidSteps.includes(stepNum);

        return (
          <div key={label} style={{ display: 'contents' }}>
            <div className="stepper-step">
              <div
                className={`stepper-circle ${isActive ? 'active' : ''} ${isCompleted && !hasError ? 'completed' : ''} ${hasError ? 'error' : ''}`}
              >
                {isCompleted && !hasError ? <Check size={18} /> : stepNum}
              </div>
              <span
                className={`stepper-label ${isActive ? 'active' : ''} ${hasError ? 'error' : ''}`}
              >
                {label}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div className={`stepper-line ${isCompleted ? 'completed' : ''}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}
