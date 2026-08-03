#!/usr/bin/env bash
# Vérification post-déploiement — à lancer SUR LE VPS, après `up -d`.
#
#     ./scripts/verifier-deploiement.sh boussole.exemple.fr
#
# Chaque contrôle échoue pour une raison DIFFÉRENTE, et l'ordre compte : un
# `/readyz` en échec n'a pas le même sens selon que la base répond ou non.
# Le script ne s'arrête pas au premier échec — on veut la photo complète.
#
# Distinction importante : `degraded` n'est PAS un échec. Le Redis de cache
# peut tomber sans couper le service (limitation de débit et quotas inactifs
# le temps de l'incident) ; c'est `not_ready` qui bloque.
set -uo pipefail

DOMAINE="${1:-}"
COMPOSE="docker compose -f infra/docker-compose.prod.yml"
ECHECS=0
AVERTISSEMENTS=0

vert()  { printf '  \033[32m✓\033[0m %s\n' "$1"; }
rouge() { printf '  \033[31m✗\033[0m %s\n' "$1"; ECHECS=$((ECHECS + 1)); }
jaune() { printf '  \033[33m!\033[0m %s\n' "$1"; AVERTISSEMENTS=$((AVERTISSEMENTS + 1)); }

if [ -z "$DOMAINE" ]; then
  echo "Usage : $0 <domaine>   (ex. boussole.exemple.fr)" >&2
  exit 2
fi

echo
echo "Vérification du déploiement — $DOMAINE"
echo

# ---------------------------------------------------------------- 1. état
echo "1. Conteneurs"
# `beat` a un start_period de 2 min : il est normalement « starting » au
# début. Ce contrôle est donc à relancer si on vient de démarrer.
for service in postgres redis-persistent redis-cache api worker beat web caddy; do
  etat=$($COMPOSE ps --format '{{.State}}' "$service" 2>/dev/null | head -1)
  sante=$($COMPOSE ps --format '{{.Health}}' "$service" 2>/dev/null | head -1)
  case "$etat|$sante" in
    running\|healthy)  vert  "$service" ;;
    running\|)         vert  "$service (sans sonde)" ;;
    running\|starting) jaune "$service : démarrage en cours — relancer dans 2 min" ;;
    running\|*)        rouge "$service : sonde en échec ($sante)" ;;
    *)                 rouge "$service : $etat" ;;
  esac
done

# --------------------------------------------------------------- 2. readyz
echo
echo "2. L'API se déclare-t-elle prête ?"
reponse=$($COMPOSE exec -T api python -c "
import json, urllib.request
try:
    print(json.dumps(json.load(urllib.request.urlopen('http://localhost:8000/readyz'))))
except Exception as exc:
    print(json.dumps({'status': 'injoignable', 'erreur': str(exc)}))
" 2>/dev/null)
statut=$(printf '%s' "$reponse" | python3 -c "import json,sys; print(json.load(sys.stdin).get('status','?'))" 2>/dev/null || echo "?")
case "$statut" in
  ready)    vert "ready — base, Redis persistant et stockage joignables" ;;
  degraded) jaune "degraded — le service TOURNE, mais le Redis de cache est tombé :
      limitation de débit et quotas inactifs. À corriger, pas à bloquer." ;;
  *)        rouge "$statut"
            printf '      %s\n' "$reponse" ;;
esac

# ------------------------------------------------------------------ 3. TLS
echo
echo "3. HTTPS de l'extérieur"
code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 "https://$DOMAINE/" 2>/dev/null)
# curl écrit déjà « 000 » quand il n'aboutit pas : un repli `|| echo 000`
# les concaténait en « 000000 ». Vu en essayant le script contre un domaine
# inexistant — d'où l'essai.
[ -z "$code" ] && code="000"
case "$code" in
  200|30[0-9]) vert "https://$DOMAINE/ → $code" ;;
  000) rouge "injoignable. Vérifier dans l'ordre : le DNS pointe-t-il sur ce VPS
      (dig +short $DOMAINE), le port 443 est-il ouvert (ufw status), Caddy
      a-t-il obtenu son certificat ($COMPOSE logs caddy | tail -30)" ;;
  *)   rouge "https://$DOMAINE/ → $code" ;;
esac

# Le port de l'API ne doit PAS répondre depuis l'extérieur : c'est ce qui rend
# l'en-tête posé par Caddy infalsifiable.
if curl -sS -o /dev/null --max-time 5 "http://$DOMAINE:8000/healthz" 2>/dev/null; then
  rouge "l'API répond sur le port 8000 depuis l'extérieur — la limitation de
      débit devient contournable. Vérifier qu'aucun port n'est publié en
      dehors de caddy, et le pare-feu."
else
  vert "les ports internes ne répondent pas depuis l'extérieur"
fi

# ----------------------------------------------------------------- 4. beat
echo
echo "4. Ordonnanceur (sans lui, AUCUNE purge RGPD)"
if $COMPOSE exec -T beat sh -c \
   "test \$(find /tmp -maxdepth 1 -name 'boussole-celerybeat-schedule*' -mmin -120 | wc -l) -gt 0" \
   2>/dev/null; then
  vert "beat a écrit son état récemment"
else
  jaune "aucun fichier d'état récent. Normal dans les 2 premières minutes ;
      au-delà, voir $COMPOSE logs beat"
fi

nb_beats=$($COMPOSE ps -q beat 2>/dev/null | wc -l)
if [ "$nb_beats" -eq 1 ]; then
  vert "exactement une instance de beat"
elif [ "$nb_beats" -eq 0 ]; then
  rouge "aucune instance de beat — AUCUNE tâche planifiée ne s'exécute :
      ni ingestion, ni expiration d'offres, ni purge RGPD. La suppression
      d'un compte resterait « en attente » indéfiniment."
else
  rouge "$nb_beats instances de beat — elles DUPLIQUENT chaque tâche
      planifiée, purges comprises. Ne jamais mettre ce service à l'échelle."
fi

# ----------------------------------------------------------- 5. migrations
echo
echo "5. Migrations"
courante=$($COMPOSE exec -T api alembic -c alembic/alembic.ini current 2>/dev/null \
  | grep -oE '^[0-9]{4}' | head -1)
attendue=$(ls api/alembic/versions/[0-9][0-9][0-9][0-9]_*.py 2>/dev/null \
  | sed 's/.*\///' | cut -c1-4 | sort | tail -1)
if [ -n "$courante" ] && [ "$courante" = "$attendue" ]; then
  vert "révision $courante (à jour)"
elif [ -z "$courante" ]; then
  rouge "aucune révision appliquée — lancer le job de migration :
      $COMPOSE run --rm api alembic -c alembic/alembic.ini upgrade head"
else
  rouge "révision $courante, attendue $attendue"
fi

# ----------------------------------------------------------------- verdict
echo
if [ "$ECHECS" -eq 0 ] && [ "$AVERTISSEMENTS" -eq 0 ]; then
  echo "  Tout est vert."
elif [ "$ECHECS" -eq 0 ]; then
  echo "  $AVERTISSEMENTS avertissement(s), aucun blocage."
else
  echo "  $ECHECS échec(s), $AVERTISSEMENTS avertissement(s) — voir ci-dessus."
fi
echo
exit $((ECHECS > 0 ? 1 : 0))
