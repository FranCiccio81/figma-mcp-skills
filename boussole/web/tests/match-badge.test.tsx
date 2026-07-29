/**
 * Badge de matching d'une carte d'offre — trois garanties produit.
 *
 * 1. **Score et confiance ne sont jamais fusionnés** (D03). Un score seul
 *    laisse croire à une certitude que le système n'a pas ; c'est le principe
 *    « transparence plutôt que score magique ».
 * 2. **Un critère rédhibitoire n'est jamais masqué** : l'offre reste visible,
 *    badgée. Cacher l'offre priverait l'utilisateur d'un choix qui lui
 *    revient (négocier, candidater quand même).
 * 3. **Jamais de faux score** : sans données de matching, rien n'est affiché
 *    — surtout pas un zéro, qui se lirait comme un jugement.
 *
 * L'accessibilité est vérifiée au passage : l'information ne doit jamais
 * reposer sur la seule couleur (WCAG 2.1 AA, 1.4.1).
 */
import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it } from "vitest";
import { MatchBadge } from "@/components/match/match-badge";
import type { JobMatchSummary } from "@/lib/api/types";
import messages from "@/messages/fr.json";

function afficher(match: JobMatchSummary | null) {
  return render(
    <NextIntlClientProvider locale="fr" messages={messages}>
      <MatchBadge match={match} />
    </NextIntlClientProvider>,
  );
}

function resume(overrides: Partial<JobMatchSummary> = {}): JobMatchSummary {
  return {
    score: 82,
    confidence: 74,
    low_data: false,
    has_blocking: false,
    ...overrides,
  } as JobMatchSummary;
}

describe("badge de matching", () => {
  it("affiche score ET confiance, jamais l'un sans l'autre", () => {
    const { container } = afficher(resume({ score: 82, confidence: 74 }));
    const texte = container.textContent ?? "";
    expect(texte).toContain("82");
    expect(texte).toContain("74");
  });

  it("n'affiche rien du tout sans données de matching", () => {
    const { container } = afficher(null);
    expect(container).toBeEmptyDOMElement();
  });

  it("signale un critère rédhibitoire par du TEXTE, pas par la couleur", () => {
    afficher(resume({ has_blocking: true }));
    const badge = screen.getByText(messages.match.card.blockingBadge);
    expect(badge).toBeInTheDocument();
  });

  it("montre l'offre malgré le critère rédhibitoire", () => {
    const { container } = afficher(resume({ score: 55, has_blocking: true }));
    // Le score reste lisible : l'offre n'est ni masquée ni vidée.
    expect(container.textContent).toContain("55");
  });

  it("dit « données insuffisantes » en toutes lettres", () => {
    afficher(resume({ low_data: true }));
    expect(screen.getByText(messages.match.card.lowData)).toBeInTheDocument();
  });

  it("garde le score lisible en données insuffisantes", () => {
    /* Grisé, jamais `disabled` : un score peu fiable reste une information. */
    const { container } = afficher(resume({ score: 40, low_data: true }));
    expect(container.textContent).toContain("40");
  });
});
