import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./i18n.ts");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Les appels API passent par le proxy BFF même origine (app/api/[...path]/route.ts, D11).
  // Aucun rewrite direct vers l'API : le proxy transmet cookies, CSRF et Accept-Language.
};

export default withNextIntl(nextConfig);
