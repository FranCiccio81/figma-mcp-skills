/**
 * Badge du contrôle d'ancrage — trois états, et le troisième compte.
 *
 * Le composant modélise depuis toujours `check === null` → « Ancrage non
 * re-vérifié (texte édité) ». L'API ne le lui envoyait jamais : après une
 * édition manuelle elle renvoyait le verdict d'origine, `passed` compris,
 * et la coche verte « Ancrage vérifié » restait affichée sur un texte écrit
 * à la main que personne n'avait contrôlé.
 *
 * Le correctif est côté API (`_anchoring_out`, testé dans
 * `tests/unit/generation/test_ancrage_apres_edition_manuelle.py`). Ce fichier
 * fixe l'autre moitié du contrat : que l'affichage traite bien `null` comme
 * un « on ne sait pas » et non comme un « rien à signaler ». Les deux moitiés
 * doivent tenir ensemble — c'est leur désaccord qui a produit le défaut.
 *
 * Accessibilité vérifiée au passage : l'état ne repose jamais sur la seule
 * couleur (WCAG 2.1 AA, 1.4.1), chaque badge porte son libellé.
 */
import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it } from "vitest";
import { AnchoringBadge } from "@/components/generation/badges";
import type { AnchoringCheck } from "@/lib/api/types";
import messages from "@/messages/fr.json";

const libelles = messages.generation.anchoring;

function afficher(check: AnchoringCheck | null) {
  return render(
    <NextIntlClientProvider locale="fr" messages={messages}>
      <AnchoringBadge check={check} />
    </NextIntlClientProvider>,
  );
}

describe("AnchoringBadge", () => {
  it("dit « non re-vérifié » quand l'API ne se prononce pas", () => {
    afficher(null);
    expect(screen.getByText(libelles.badgeManual)).toBeInTheDocument();
    expect(screen.queryByText(libelles.badgePassed)).not.toBeInTheDocument();
  });

  it("ne montre la coche verte que sur un verdict positif réel", () => {
    afficher({ status: "passed", unanchored_claims: [] });
    expect(screen.getByText(libelles.badgePassed)).toBeInTheDocument();
  });

  it("avertit sur un verdict négatif", () => {
    afficher({ status: "failed", unanchored_claims: ["expert Kubernetes"] });
    expect(screen.getByText(libelles.badgeFailed)).toBeInTheDocument();
  });

  it("porte toujours un libellé, jamais la couleur seule", () => {
    for (const check of [
      null,
      { status: "passed", unanchored_claims: [] } as AnchoringCheck,
      { status: "failed", unanchored_claims: [] } as AnchoringCheck,
    ]) {
      const { container, unmount } = afficher(check);
      expect(container.textContent?.trim()).not.toBe("");
      unmount();
    }
  });
});
