import random

import pytest

from pro import context
from pro.base import Choice, Random


def test_bcga_rng_is_reproducible():
    context.set_seed(12345)
    first = [Random(0.0, 1.0).getValue() for _ in range(5)]
    first_choice = Choice("a", "b", "c").getValue()

    context.set_seed(12345)
    second = [Random(0.0, 1.0).getValue() for _ in range(5)]
    second_choice = Choice("a", "b", "c").getValue()

    assert first == second
    assert first_choice == second_choice


def test_bcga_rng_does_not_reseed_for_each_value():
    context.set_seed(7)
    values = [Random(0.0, 1.0).getValue() for _ in range(3)]

    assert len(set(values)) == 3


def test_bcga_seed_does_not_mutate_python_global_rng():
    random.seed(999)
    expected = random.random()

    random.seed(999)
    context.set_seed(123)
    actual = random.random()

    assert actual == expected


@pytest.mark.parametrize(
    "weights",
    ([1, -1], [0, 0], [-1, -2]),
)
def test_choice_rejects_invalid_weights(weights):
    with pytest.raises(ValueError):
        Choice("a", "b", weights=weights)


def test_choice_accepts_zero_weight_options():
    context.set_seed(1)
    choice = Choice("never", "always", weights=[0, 1])
    assert choice.getValue() == "always"
