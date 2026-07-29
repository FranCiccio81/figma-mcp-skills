import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./i18n.ts");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Les appels API passent par le proxy BFF même origine (app/api/[...path]/route.ts, D11).
  // Aucun rewrite direct vers l'API : le proxy transmet cookies, CSRF et Accept-Language.

  // `infra/Dockerfile.web` copie `.next/standalone` et lance `node server.js` :
  // sans cette ligne, Next ne produit ni l'un ni l'autre et le build de l'image
  // échoue sur un `COPY` introuvable. Le Dockerfile le disait lui-même en
  // commentaire (« prêt pour un projet Next.js standard AVEC output:
  // standalone ») — personne n'avait ajouté la ligne.
  output: "standalone",

  // Next annonce sa présence et sa version à chaque réponse HTML. C'est un
  // renseignement gratuit offert à qui cherche une version vulnérable.
  poweredByHeader: false,

  /**
   * En-têtes de sécurité sur les pages HTML.
   *
   * 12 §1 et 09 §215 promettent tous deux « CSP/HSTS posés par le front/edge ».
   * Vérifié en revue sur le front réellement compilé en production : **aucun**
   * de ces en-têtes n'était posé, et aucun manifeste d'edge n'existe dans le
   * dépôt. Le middleware de l'API ne couvre que `/api/*` — or la surface XSS
   * et clickjacking, c'est le HTML.
   *
   * Une promesse déléguée à une couche qui n'existe pas n'est pas déléguée :
   * elle est absente. Le front la tient donc lui-même. Un edge qui les
   * reposerait plus tard ne casse rien — les valeurs sont compatibles.
   */
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          {
            // `unsafe-inline` sur les styles : Next injecte ses styles en
            // ligne. Les scripts, eux, ne l'ont pas — c'est le vecteur qui
            // compte pour du contenu affiché depuis des CV et des offres.
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              "script-src 'self'",
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' data:",
              "font-src 'self'",
              // Le navigateur ne parle jamais directement à l'API (D11).
              "connect-src 'self'",
              "frame-ancestors 'none'",
              "base-uri 'self'",
              "form-action 'self'",
              "object-src 'none'",
            ].join("; "),
          },
          { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          // Le produit ne demande ni caméra, ni micro, ni position.
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=(), payment=()",
          },
        ],
      },
    ];
  },
};

export default withNextIntl(nextConfig);
