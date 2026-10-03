"""`training/kaggle/train.py`: COCO JSON -> YOLO labels, by category name.

The training run itself is covered by `test_training_smoke.py`; here only the
pure conversion, on a hand-made `instances_*.json` whose category ids and order
differ from the model's class order.
"""

from __future__ import annotations

import pytest

from training.kaggle.train import coco_labels

# The model's order: what `data.yaml` names 0..N-1.
NAMES = ["person", "bicycle", "car", "pen", "flower"]

# COCO's own ids (1, 3, 18) and order deliberately differ from NAMES.
INSTANCES = {
    "categories": [
        {"id": 18, "name": "car"},
        {"id": 1, "name": "person"},
        {"id": 3, "name": "bicycle"},
    ],
    "images": [
        {"id": 7, "file_name": "a.jpg", "width": 100, "height": 50},
        {"id": 9, "file_name": "b.jpg", "width": 200, "height": 100},
        {"id": 11, "file_name": "empty.jpg", "width": 64, "height": 64},
    ],
    "annotations": [
        {"image_id": 7, "category_id": 18, "bbox": [10, 5, 20, 10], "iscrowd": 0},
        {"image_id": 7, "category_id": 1, "bbox": [50, 0, 50, 50], "iscrowd": 0},
        {"image_id": 9, "category_id": 3, "bbox": [0, 0, 100, 50], "iscrowd": 0},
        {"image_id": 9, "category_id": 1, "bbox": [0, 0, 10, 10], "iscrowd": 1},
    ],
}


def test_every_image_converts_by_category_name():
    labels = coco_labels(INSTANCES, NAMES, count=10, seed=0)

    # Worked by hand: a.jpg car [10,5,20,10] in 100x50 -> centre (20,10) -> 0.2 0.2, size 0.2 0.2.
    assert labels == {
        "a.jpg": ["2 0.200000 0.200000 0.200000 0.200000",
                  "0 0.750000 0.500000 0.500000 1.000000"],
        "b.jpg": ["1 0.250000 0.250000 0.500000 0.500000"],  # the crowd box is skipped
        "empty.jpg": [],  # no annotation: a negative, still an image
    }


def test_a_seeded_subset_of_the_requested_size():
    first = coco_labels(INSTANCES, NAMES, count=2, seed=3)

    assert len(first) == 2
    assert set(first) <= {"a.jpg", "b.jpg", "empty.jpg"}
    assert coco_labels(INSTANCES, NAMES, count=2, seed=3) == first


def test_a_category_the_model_does_not_know_is_refused():
    with pytest.raises(ValueError, match="car"):
        coco_labels(INSTANCES, ["person", "bicycle"], count=10, seed=0)
