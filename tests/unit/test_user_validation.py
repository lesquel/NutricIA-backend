"""Tests for UserGoalsUpdate field constraints."""

import pytest
from pydantic import ValidationError

from app.users.presentation import UserGoalsUpdate


class TestUserGoalsUpdateConstraints:
    """calorie_goal and water_goal_ml must be >= 1 when provided."""

    def test_positive_values_pass(self) -> None:
        update = UserGoalsUpdate(calorie_goal=2000, water_goal_ml=2500)
        assert update.calorie_goal == 2000
        assert update.water_goal_ml == 2500

    def test_zero_calorie_goal_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UserGoalsUpdate(calorie_goal=0)

    def test_negative_calorie_goal_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UserGoalsUpdate(calorie_goal=-1)

    def test_zero_water_goal_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UserGoalsUpdate(water_goal_ml=0)

    def test_negative_water_goal_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UserGoalsUpdate(water_goal_ml=-100)

    def test_none_calorie_goal_is_valid(self) -> None:
        update = UserGoalsUpdate(calorie_goal=None)
        assert update.calorie_goal is None

    def test_none_water_goal_is_valid(self) -> None:
        update = UserGoalsUpdate(water_goal_ml=None)
        assert update.water_goal_ml is None

    def test_both_none_is_valid(self) -> None:
        update = UserGoalsUpdate()
        assert update.calorie_goal is None
        assert update.water_goal_ml is None
