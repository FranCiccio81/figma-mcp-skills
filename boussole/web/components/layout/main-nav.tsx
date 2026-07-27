"use client";

import clsx from "clsx";
import {
  Briefcase,
  LayoutDashboard,
  LogOut,
  Send,
  Settings,
  SlidersHorizontal,
  User,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { apiFetch } from "@/lib/api/client";

interface NavItem {
  href: string;
  labelKey: "dashboard" | "jobs" | "applications" | "profile" | "preferences" | "settings";
  icon: LucideIcon;
}

const NAV_ITEMS: readonly NavItem[] = [
  { href: "/tableau-de-bord", labelKey: "dashboard", icon: LayoutDashboard },
  { href: "/offres", labelKey: "jobs", icon: Briefcase },
  { href: "/candidatures", labelKey: "applications", icon: Send },
  { href: "/profil", labelKey: "profile", icon: User },
  { href: "/preferences", labelKey: "preferences", icon: SlidersHorizontal },
  { href: "/parametres", labelKey: "settings", icon: Settings },
];

/**
 * Sous-entrées de la sidebar desktop (M4) : « Mes documents » vit sous
 * Candidatures (03 : les documents générés sont rattachés au suivi de
 * candidature — SCR-41 ; bibliothèque `GET /generations`, 03 §5 Q1).
 * Sur mobile, la page reste accessible depuis l'écran Candidatures.
 */
const NAV_SUB_ITEMS: readonly { parentHref: string; href: string; labelKey: "documents" }[] = [
  { parentHref: "/candidatures", href: "/candidatures/documents", labelKey: "documents" },
];

function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

/**
 * Navigation principale (03 §3) : sidebar fixe ≥ 1024 px, barre inférieure
 * en dessous. Landmark `nav` unique, item actif marqué `aria-current="page"`,
 * cibles tactiles ≥ 44 px, déconnexion (`POST /auth/logout`) incluse.
 */
export function MainNav() {
  const t = useTranslations("nav");
  const tCommon = useTranslations("common");
  const pathname = usePathname();
  const router = useRouter();
  const [loggingOut, setLoggingOut] = useState(false);

  async function handleLogout() {
    setLoggingOut(true);
    try {
      await apiFetch<undefined>("/auth/logout", { method: "POST" });
    } catch {
      // Session déjà invalide côté API : on retourne quand même à la connexion.
    }
    router.replace("/connexion");
    router.refresh();
  }

  return (
    <nav aria-label={t("mainLabel")}>
      {/* Sidebar desktop */}
      <div className="sticky top-0 hidden h-screen w-60 flex-col border-r border-border bg-surface px-3 py-6 lg:flex">
        <p className="px-3 text-lg font-bold text-content">{tCommon("appName")}</p>
        <ul className="mt-6 flex flex-1 flex-col gap-1">
          {NAV_ITEMS.map(({ href, labelKey, icon: Icon }) => {
            const active = isActive(pathname, href);
            const subItems = NAV_SUB_ITEMS.filter((sub) => sub.parentHref === href);
            return (
              <li key={href}>
                <Link
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={clsx(
                    "flex min-h-11 items-center gap-3 rounded-md px-3 text-sm font-medium transition-colors",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
                    active
                      ? "bg-surface-muted text-action-primary"
                      : "text-content-secondary hover:bg-surface-muted hover:text-content",
                  )}
                >
                  <Icon aria-hidden="true" className="h-5 w-5 shrink-0" />
                  {t(labelKey)}
                </Link>
                {subItems.length > 0 ? (
                  <ul className="mt-0.5 flex flex-col gap-0.5">
                    {subItems.map((sub) => {
                      const subActive = isActive(pathname, sub.href);
                      return (
                        <li key={sub.href}>
                          <Link
                            href={sub.href}
                            aria-current={subActive ? "page" : undefined}
                            className={clsx(
                              "flex min-h-11 items-center rounded-md py-2 pl-11 pr-3 text-sm transition-colors",
                              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
                              subActive
                                ? "bg-surface-muted font-medium text-action-primary"
                                : "text-content-secondary hover:bg-surface-muted hover:text-content",
                            )}
                          >
                            {t(sub.labelKey)}
                          </Link>
                        </li>
                      );
                    })}
                  </ul>
                ) : null}
              </li>
            );
          })}
        </ul>
        <button
          type="button"
          onClick={handleLogout}
          disabled={loggingOut}
          aria-busy={loggingOut}
          className={clsx(
            "flex min-h-11 items-center gap-3 rounded-md px-3 text-sm font-medium text-content-secondary transition-colors",
            "hover:bg-surface-muted hover:text-content",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
            "disabled:pointer-events-none disabled:opacity-50",
          )}
        >
          <LogOut aria-hidden="true" className="h-5 w-5 shrink-0" />
          {t("logout")}
        </button>
      </div>

      {/* Barre inférieure mobile / tablette */}
      <div className="fixed inset-x-0 bottom-0 z-10 border-t border-border bg-surface lg:hidden">
        <ul className="flex">
          {NAV_ITEMS.map(({ href, labelKey, icon: Icon }) => {
            const active = isActive(pathname, href);
            return (
              <li key={href} className="flex-1">
                <Link
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={clsx(
                    "flex min-h-14 flex-col items-center justify-center gap-1 px-1 py-2 text-[11px] font-medium",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus",
                    active ? "text-action-primary" : "text-content-secondary",
                  )}
                >
                  <Icon aria-hidden="true" className="h-5 w-5" />
                  {t(labelKey)}
                </Link>
              </li>
            );
          })}
        </ul>
      </div>
    </nav>
  );
}
