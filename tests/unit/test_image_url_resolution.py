"""Tests for image URL resolution — relative paths + request base_url."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.shared.infrastructure.url_utils import resolve_image_url, to_relative_path


# ---------------------------------------------------------------------------
# to_relative_path
# ---------------------------------------------------------------------------


class TestToRelativePath:
    def test_already_relative(self):
        assert to_relative_path("/uploads/meals/abc.jpg") == "/uploads/meals/abc.jpg"

    def test_absolute_url_stripped(self):
        result = to_relative_path("http://localhost:8000/uploads/meals/abc.jpg")
        assert result == "/uploads/meals/abc.jpg"

    def test_with_different_host(self):
        result = to_relative_path("http://192.168.1.5:8000/uploads/meals/abc.jpg")
        assert result == "/uploads/meals/abc.jpg"

    def test_https_stripped(self):
        result = to_relative_path("https://example.com/uploads/avatars/x.jpg")
        assert result == "/uploads/avatars/x.jpg"

    def test_none_returns_none(self):
        assert to_relative_path(None) is None

    def test_empty_string_returns_empty(self):
        assert to_relative_path("") == ""


# ---------------------------------------------------------------------------
# resolve_image_url
# ---------------------------------------------------------------------------


class TestResolveImageUrl:
    def test_resolves_with_base_url_trailing_slash(self):
        result = resolve_image_url(
            "/uploads/meals/abc.jpg", "http://192.168.1.5:8000/"
        )
        assert result == "http://192.168.1.5:8000/uploads/meals/abc.jpg"

    def test_resolves_with_base_url_no_trailing_slash(self):
        result = resolve_image_url(
            "/uploads/meals/abc.jpg", "http://192.168.1.5:8000"
        )
        assert result == "http://192.168.1.5:8000/uploads/meals/abc.jpg"

    def test_none_path_returns_none(self):
        result = resolve_image_url(None, "http://localhost:8000/")
        assert result is None

    def test_empty_path_returns_none(self):
        result = resolve_image_url("", "http://localhost:8000/")
        assert result is None

    def test_handles_legacy_absolute_url_in_db(self):
        """If DB has an absolute URL from before the fix, resolve correctly."""
        result = resolve_image_url(
            "http://old-server:8000/uploads/meals/abc.jpg",
            "http://192.168.1.5:8000/",
        )
        assert result == "http://192.168.1.5:8000/uploads/meals/abc.jpg"

    def test_avatar_url_resolved(self):
        result = resolve_image_url(
            "/uploads/avatars/face.png", "http://10.0.0.1:8000/"
        )
        assert result == "http://10.0.0.1:8000/uploads/avatars/face.png"


# ---------------------------------------------------------------------------
# meal_to_response uses resolve_image_url
# ---------------------------------------------------------------------------


class TestMealResponseResolution:
    def _make_meal(self, image_url: str | None = None):  # noqa: ANN202
        """Create a minimal mock Meal object."""
        meal = MagicMock()
        meal.id = uuid.uuid4()
        meal.name = "Test Salad"
        meal.image_url = image_url
        meal.calories = 300.0
        meal.protein_g = 25.0
        meal.carbs_g = 20.0
        meal.fat_g = 10.0
        meal.meal_type = "lunch"
        meal.confidence_score = 0.9
        meal.tags = []
        meal.logged_at = datetime.now(timezone.utc)
        meal.created_at = datetime.now(timezone.utc)
        return meal

    def test_relative_path_resolved_with_base_url(self):
        from app.meals.application.meal_crud import meal_to_response

        meal = self._make_meal(image_url="/uploads/meals/abc.jpg")
        resp = meal_to_response(meal, base_url="http://192.168.1.5:8000/")
        assert resp.image_url == "http://192.168.1.5:8000/uploads/meals/abc.jpg"

    def test_none_image_stays_none(self):
        from app.meals.application.meal_crud import meal_to_response

        meal = self._make_meal(image_url=None)
        resp = meal_to_response(meal, base_url="http://192.168.1.5:8000/")
        assert resp.image_url is None

    def test_legacy_absolute_url_rewritten(self):
        from app.meals.application.meal_crud import meal_to_response

        meal = self._make_meal(image_url="http://old:8000/uploads/meals/abc.jpg")
        resp = meal_to_response(meal, base_url="http://192.168.1.5:8000/")
        assert resp.image_url == "http://192.168.1.5:8000/uploads/meals/abc.jpg"

    def test_without_base_url_returns_raw(self):
        """Backwards compat: no base_url keeps the stored value."""
        from app.meals.application.meal_crud import meal_to_response

        meal = self._make_meal(image_url="/uploads/meals/abc.jpg")
        resp = meal_to_response(meal)
        assert resp.image_url == "/uploads/meals/abc.jpg"


# ---------------------------------------------------------------------------
# user_to_settings uses resolve_image_url
# ---------------------------------------------------------------------------


class TestUserSettingsResolution:
    def _make_user(self, avatar_url: str | None = None):  # noqa: ANN202
        """Create a minimal mock User object."""
        user = MagicMock()
        user.id = uuid.uuid4()
        user.email = "u@example.com"
        user.name = "Test"
        user.avatar_url = avatar_url
        user.calorie_goal = 2100
        user.water_goal_ml = 2500
        user.dietary_preferences = "[]"
        return user

    def test_relative_avatar_resolved(self):
        from app.users.application.user_use_cases import user_to_settings

        user = self._make_user(avatar_url="/uploads/avatars/face.png")
        resp = user_to_settings(user, base_url="http://192.168.1.5:8000/")
        assert resp.avatar_url == "http://192.168.1.5:8000/uploads/avatars/face.png"

    def test_none_avatar_stays_none(self):
        from app.users.application.user_use_cases import user_to_settings

        user = self._make_user(avatar_url=None)
        resp = user_to_settings(user, base_url="http://192.168.1.5:8000/")
        assert resp.avatar_url is None

    def test_legacy_absolute_avatar_rewritten(self):
        from app.users.application.user_use_cases import user_to_settings

        user = self._make_user(
            avatar_url="http://old:8000/uploads/avatars/face.png"
        )
        resp = user_to_settings(user, base_url="http://192.168.1.5:8000/")
        assert resp.avatar_url == "http://192.168.1.5:8000/uploads/avatars/face.png"

    def test_without_base_url_returns_raw(self):
        from app.users.application.user_use_cases import user_to_settings

        user = self._make_user(avatar_url="/uploads/avatars/face.png")
        resp = user_to_settings(user)
        assert resp.avatar_url == "/uploads/avatars/face.png"
