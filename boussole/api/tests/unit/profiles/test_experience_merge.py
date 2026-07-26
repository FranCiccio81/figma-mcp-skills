"""Tests de la fusion d'intervalles d'expérience (total_experience_years).

Cas couverts : disjoints, chevauchants, adjacents, inclus, en cours (end_date
null bornée à aujourd'hui), liste vide (None — dimension inconnue, pas 0).
"""

from datetime import date

from app.modules.profiles.service import compute_total_experience_years

TODAY = date(2026, 7, 24)


def years(periods: list[tuple[date, date | None]]) -> float | None:
    return compute_total_experience_years(periods, today=TODAY)


def test_empty_returns_none() -> None:
    assert years([]) is None


def test_single_interval() -> None:
    # 2 ans exactement (bornes incluses, 365.25 j/an → arrondi 0,1 près).
    assert years([(date(2020, 1, 1), date(2021, 12, 31))]) == 2.0


def test_disjoint_intervals_are_summed() -> None:
    total = years(
        [
            (date(2020, 1, 1), date(2020, 12, 31)),  # 1 an
            (date(2023, 1, 1), date(2023, 12, 31)),  # 1 an, trou de 2 ans
        ]
    )
    assert total == 2.0


def test_overlapping_intervals_are_merged() -> None:
    # Chevauchement de 6 mois : 1,5 an au total, pas 2.
    total = years(
        [
            (date(2020, 1, 1), date(2020, 12, 31)),
            (date(2020, 7, 1), date(2021, 6, 30)),
        ]
    )
    assert total == 1.5


def test_adjacent_intervals_are_merged() -> None:
    # Fin le 31/12, reprise le 01/01 : continuité (adjacence à un jour près).
    total = years(
        [
            (date(2020, 1, 1), date(2020, 12, 31)),
            (date(2021, 1, 1), date(2021, 12, 31)),
        ]
    )
    assert total == 2.0


def test_included_interval_counts_once() -> None:
    # Intervalle inclus dans un autre (cumul d'emplois) : ne compte qu'une fois.
    total = years(
        [
            (date(2020, 1, 1), date(2023, 12, 31)),  # 4 ans
            (date(2021, 1, 1), date(2021, 12, 31)),  # inclus
        ]
    )
    assert total == 4.0


def test_ongoing_experience_runs_until_today() -> None:
    # En cours depuis le 24/07/2024 : 2 ans à la date de référence.
    assert years([(date(2024, 7, 24), None)]) == 2.0


def test_unordered_input_is_sorted_before_merge() -> None:
    total = years(
        [
            (date(2023, 1, 1), date(2023, 12, 31)),
            (date(2020, 1, 1), date(2020, 12, 31)),
            (date(2020, 6, 1), date(2021, 5, 31)),  # chevauche le précédent
        ]
    )
    assert total == 2.4  # 01/2020→05/2021 (~1,4 an) + 2023 (1 an)
