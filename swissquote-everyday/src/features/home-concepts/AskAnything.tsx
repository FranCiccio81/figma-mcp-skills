/**
 * "Ask me anything" — the pull half of the assistant.
 *
 * Variant D already pushes: the wealth-analysis tile decides what stands out
 * and says so. This is the other direction — an open field, so a client with
 * a question that the dashboard does not happen to answer is not left
 * hunting for the screen that does.
 *
 * Two deliberate limits, both of which a real service would have to keep:
 *   • It never answers here. Submitting hands the question to the assistant
 *     surface with the text prefilled — Home is not a chat log, and an answer
 *     rendered inline would have nowhere to show its sources.
 *   • It cannot move money. The note under the field says so on the screen,
 *     not in a settings page, because that is where the expectation is set.
 */
import { useState } from 'react';
import { useStore } from '../../state/store';
import { AiLabel } from './shared';

/** Openers the client can take instead of typing. Drawn from what is on the screen. */
export function AskAnything({ suggestions = [] }: { suggestions?: string[] }) {
  const { nav } = useStore();
  const [question, setQuestion] = useState('');

  const submit = (text: string) => {
    const trimmed = text.trim();
    if (trimmed) nav.ask(trimmed);
  };

  return (
    <section className="ask" aria-label="Ask Swissquote">
      <div className="ask__head">
        <AiLabel>Ask me anything</AiLabel>
      </div>
      <form
        className="ask__field"
        onSubmit={(e) => {
          e.preventDefault();
          submit(question);
        }}
      >
        <input
          className="ask__input"
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about your money…"
          aria-label="Ask about your portfolio, the market or a transaction"
        />
        <button type="submit" className="ask__submit" aria-label="Ask" disabled={question.trim() === ''}>
          ↑
        </button>
      </form>
      {suggestions.length > 0 && (
        /* Two openers, never more: a wall of suggested questions is a menu,
           and a menu is the thing an open field exists to replace. */
        <div className="chip-row ask__suggestions">
          {suggestions.slice(0, 2).map((s) => (
            <button key={s} type="button" className="chip" onClick={() => submit(s)}>
              {s}
            </button>
          ))}
        </div>
      )}
      <p className="micro m-0 ask__note">
        Answers describe your own accounts and name where each figure came from. Nothing moves until you confirm
        it yourself.
      </p>
    </section>
  );
}
