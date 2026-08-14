/**
 * Lombard margin call — interruptive and unmissable, never a toast (§6).
 * Blocks the screen until the client picks a route.
 */
import { useEffect, useRef } from 'react';
import { money } from '../lib/format';
import { useStore } from '../state/store';

export function MarginCallModal() {
  const { state, dispatch } = useStore();
  const ref = useRef<HTMLDivElement>(null);
  const notice = state.notices.find((n) => n.kind === 'marginCall');

  useEffect(() => {
    if (notice) ref.current?.focus();
  }, [notice]);

  if (!state.flags.marginCall || !notice) return null;
  const shortfall = notice.shortfall ?? 0;

  return (
    <>
      <div className="scrim" aria-hidden="true" />
      <div
        className="modal"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="margin-call-title"
        aria-describedby="margin-call-body"
        tabIndex={-1}
        ref={ref}
      >
        <h2 id="margin-call-title" className="m-0" style={{ color: 'var(--color-text-error)', fontSize: 'var(--font-size-title)', marginBottom: 'var(--space-sm)' }}>
          Margin call on your Lombard credit
        </h2>
        <p id="margin-call-body" className="m-0" style={{ marginBottom: 'var(--space-md)' }}>
          {notice.body}
        </p>
        <div className="flex flex-col" style={{ gap: 'var(--space-xs)' }}>
          <button
            type="button"
            className="btn btn--danger"
            onClick={() => {
              dispatch({ type: 'manualTransferIn', amount: shortfall });
              dispatch({ type: 'resolveMarginCall' });
            }}
          >
            Add {money(shortfall)} now
          </button>
          <button type="button" className="btn btn--secondary" onClick={() => dispatch({ type: 'resolveMarginCall' })}>
            Sell positions to restore cover
          </button>
          <p className="caption m-0">
            If you do nothing by the deadline, Swissquote may sell positions for you. Call +41 44 825 88 88 to talk it through.
          </p>
        </div>
      </div>
    </>
  );
}
