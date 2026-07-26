"""Couche IA multi-provider (D08) — sorties JSON validées Pydantic.

M2 : interface ``LLMProvider`` + ``FakeProvider`` déterministe + tâche
``extract_job`` (étage 2 de secours, 07 §5.2). Providers réels
(Anthropic + fallback) branchés en M3+ 🟡.
"""
