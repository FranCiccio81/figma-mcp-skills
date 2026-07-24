import { useTranslations } from "next-intl";
import type { ContractType, RemotePolicy } from "@/lib/api/types";

export interface JobBadgesProps {
  contract: ContractType | null;
  remote: RemotePolicy | null;
}

/**
 * Badges contrat / télétravail d'une offre (SCR-20/21). Texte uniquement —
 * jamais d'information portée par la couleur seule (04 §conventions a11y).
 * Une valeur `null` n'affiche rien : « non précisé » n'est montré qu'au détail
 * (M3-a), pas sur les cartes, pour ne pas les surcharger.
 */
export function JobBadges({ contract, remote }: JobBadgesProps) {
  const t = useTranslations("jobs");
  if (!contract && !remote) return null;

  return (
    <ul className="flex flex-wrap gap-2" aria-label={t("badges.label")}>
      {contract ? (
        <li className="rounded-md border border-border bg-surface-muted px-2 py-0.5 text-xs font-medium text-content">
          {t(`contract.${contract}`)}
        </li>
      ) : null}
      {remote ? (
        <li className="rounded-md border border-border bg-surface-muted px-2 py-0.5 text-xs font-medium text-content">
          {t(`remote.${remote}`)}
        </li>
      ) : null}
    </ul>
  );
}
