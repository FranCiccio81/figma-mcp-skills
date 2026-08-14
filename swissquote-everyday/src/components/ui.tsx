/**
 * Shared Bridge-styled atoms/molecules for the prototype.
 * All colours/spacing resolve to tokens via the BEM classes in app.css.
 */
import { useEffect, useRef, type ReactNode } from 'react';
import type { EngineStatus } from '../state/types';

/** §9.7 — every screen carries the concept label. */
export function ConceptBadge() {
  return <p className="concept-badge m-0">Concept — not a product commitment</p>;
}

export function ScreenHeader({ title, onBack }: { title: string; onBack?: () => void }) {
  return (
    <header className="screen-header">
      {onBack && (
        <button type="button" className="screen-header__back" onClick={onBack} aria-label="Back">
          ←
        </button>
      )}
      <h1 className="screen-header__title m-0">{title}</h1>
    </header>
  );
}

/** Accessible switch — 44pt touch target, state announced via role/aria-checked. */
export function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      className="toggle"
      onClick={() => onChange(!checked)}
    >
      <span className="toggle__track">
        <span className="toggle__thumb" />
      </span>
    </button>
  );
}

export const STATUS_LABELS: Record<EngineStatus, string> = {
  healthy: 'Healthy',
  approachingMinimum: 'Approaching minimum',
  autoCoverPending: 'Auto Cover pending',
  autoCoverExecuted: 'Auto Cover executed',
  autoCoverFailed: 'Auto Cover could not run',
  rulesPaused: 'Rules paused',
};

export function StatusPill({ status }: { status: EngineStatus }) {
  return (
    <span className={`status-pill status-pill--${status}`}>
      <span className="status-pill__dot" aria-hidden="true" />
      {STATUS_LABELS[status]}
    </span>
  );
}

/** Bottom sheet (~85% height) with scrim, Escape-to-close and initial focus. */
export function Sheet({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  return (
    <>
      <button type="button" className="scrim" aria-label="Close" onClick={onClose} />
      <div className="sheet" role="dialog" aria-modal="true" aria-label={title} tabIndex={-1} ref={ref}>
        <div className="sheet__grabber" aria-hidden="true" />
        <div className="sheet__body">
          <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-sm)' }}>
            <h2 className="screen-header__title m-0">{title}</h2>
            <button type="button" className="btn btn--ghost" onClick={onClose}>
              Close
            </button>
          </div>
          {children}
        </div>
      </div>
    </>
  );
}
