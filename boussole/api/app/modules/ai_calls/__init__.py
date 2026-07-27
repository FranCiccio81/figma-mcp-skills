"""Module de données ``ai_calls`` — journal des appels LLM (11 §1).

``ai_calls`` n'appartient à aucun module métier : c'est une table
transversale alimentée par la COUCHE PROVIDER (:mod:`app.ai.calls`), jamais
par les tâches. Elle a néanmoins besoin d'une entrée au registre de purge
(D21) parce qu'elle porte un ``user_id`` — d'où ce module minimal, réduit
au contrat ``purge_user`` / ``export_user``.

Particularité (RM-Q-2, 11 §2) : la purge est une **anonymisation**
(``user_id → NULL``), pas une suppression — les métadonnées agrégées
(coût, latence, taux d'échec par tâche) restent exploitables une fois le
compte supprimé.
"""
