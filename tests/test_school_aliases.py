import json
from pathlib import Path

import pytest

from core import DataValidationError, DefaultNormalizer, load_school_aliases

LOCAL_ALIASES = Path(__file__).resolve().parents[1] / "config/school-aliases.json"


def test_complete_local_list_and_school_rename() -> None:
    document = json.loads(LOCAL_ALIASES.read_text(encoding="utf-8"))
    assert len(document) >= 658
    assert sum(len(values) for values in document.values()) >= 730
    normalizer = DefaultNormalizer(school_aliases=load_school_aliases(LOCAL_ALIASES))
    canonical = normalizer.school("北京师范大学香港浸会大学联合国际学院")
    for alias in ["北师香港浸会大学", "Beijing Normal-Hong Kong Baptist University",
                  "“北京师范大学-香港浸会大学联合国际学院”"]:
        assert normalizer.school(alias) == canonical
    assert normalizer.school("Tsinghua University") == "清华大学"
    assert normalizer.school("Taizhou University") not in {"台州学院", "泰州学院"}
    assert normalizer.school("Wuyi University") not in {"五邑大学", "武夷学院"}


@pytest.mark.parametrize("reverse", [False, True])
def test_ambiguous_normalized_aliases_do_not_merge_schools(tmp_path, reverse) -> None:
    entries = [("甲大学", ["Shared University", "乙大学"]),
               ("乙大学", ["ＳＨＡＲＥＤ-University", "Unique University"])]
    path = tmp_path / "schools.json"
    path.write_text(json.dumps(dict(entries[::-1] if reverse else entries)), encoding="utf-8")
    normalizer = DefaultNormalizer(school_aliases=load_school_aliases(path))
    assert normalizer.school("Shared University") == "shareduniversity"
    assert normalizer.school("Unique University") == "乙大学"
    assert normalizer.school("乙大学") == "乙大学"


def test_legacy_flat_mapping_and_empty_override(tmp_path) -> None:
    path = tmp_path / "schools.json"
    path.write_text(json.dumps({"Peking University": "北京大学"}), encoding="utf-8")
    assert load_school_aliases(path) == {"pekinguniversity": "北京大学"}
    path.write_text("{}", encoding="utf-8")
    assert load_school_aliases(path) == {}


@pytest.mark.parametrize("document", [[], {"School": 1}, {"School": [1]}, {"School": ["---"]}])
def test_invalid_aliases_report_file_context(tmp_path, document) -> None:
    path = tmp_path / "schools.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(DataValidationError, match="schools.json"):
        load_school_aliases(path)


def test_missing_or_malformed_file_does_not_silently_disable_aliases(tmp_path) -> None:
    path = tmp_path / "schools.json"
    with pytest.raises(DataValidationError, match="schools.json"):
        load_school_aliases(path)
    path.write_text("{", encoding="utf-8")
    with pytest.raises(DataValidationError, match="schools.json"):
        load_school_aliases(path)
