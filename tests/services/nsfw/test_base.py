import pytest

from app.services.nsfw.base import BaseNSFWFilter


class _IncompleteFilter(BaseNSFWFilter):
    pass


class TestBaseFilterContract:

    def test_base_filter_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError):
            BaseNSFWFilter()  # type: ignore[abstract]

    def test_subclass_without_methods_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError):
            _IncompleteFilter()  # type: ignore[abstract]
