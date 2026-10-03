"""`training.classes.class_names`: the one place that orders the 82 names."""

import pytest

from training.classes import class_names


def test_base_names_in_id_order_then_custom_ones():
    # Keys deliberately out of insertion order: the ID decides, not the dict.
    base = {2: "car", 0: "person", 1: "bicycle"}
    assert class_names(base, ["pen", "flower"]) == ["person", "bicycle", "car", "pen", "flower"]


def test_eighty_base_names_plus_two_make_eighty_two():
    base = {index: f"class{index}" for index in range(80)}
    names = class_names(base, ["pen", "flower"])
    assert len(names) == 82
    assert names[79] == "class79"
    assert names[80:] == ["pen", "flower"]


def test_a_custom_name_the_model_already_has_is_refused_by_name():
    with pytest.raises(ValueError, match="knife"):
        class_names({0: "person", 1: "knife"}, ["pen", "knife"])


def test_base_ids_with_a_gap_are_refused():
    with pytest.raises(ValueError, match="0..1"):
        class_names({0: "person", 2: "car"}, ["pen"])


def test_inputs_are_left_untouched():
    base = {0: "person"}
    custom = ["pen"]
    class_names(base, custom)
    assert base == {0: "person"} and custom == ["pen"]
