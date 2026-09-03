from server.etl.education import classify_requirement, normalize_education_level


def test_bachelor_keywords():
    assert normalize_education_level(["BSc in Computer Science"]) == "bachelor"
    assert normalize_education_level(["B.Sc. in Software Engineering"]) == "bachelor"
    assert normalize_education_level(["Bachelor's in Electrical Engineering"]) == "bachelor"
    assert normalize_education_level(["Bachelor's degree in Computer Science or related field"]) == "bachelor"
    assert normalize_education_level(["Degree in Software Engineering"]) == "bachelor"
    assert normalize_education_level(["equivalent academic degree"]) == "bachelor"


def test_master_keywords():
    assert normalize_education_level(["MSc in Computer Science"]) == "master"
    assert normalize_education_level(["Master's in Computer Science"]) == "master"
    assert normalize_education_level(["Graduate degree in Statistics"]) == "master"


def test_phd_keywords():
    assert normalize_education_level(
        ["PhD in Computer Engineering, Computer Science, Electrical Engineering, or related field"]
    ) == "phd"
    assert normalize_education_level(["Ph.D. in Machine Learning"]) == "phd"


def test_masters_degree_in_field_is_not_read_as_bachelor():
    # "'s degree" / "degree in" are generic signals — a named higher level wins.
    assert classify_requirement("Master's degree in Computer Science")[0] == "master"


def test_or_joins_take_the_lowest_named_level():
    # "Master's degree or PhD" — a master's is the floor.
    assert classify_requirement("Master's degree or PhD in CS")[0] == "master"


def test_optional_degrees_do_not_count():
    assert normalize_education_level(["MSc — advantage"]) == "none"
    assert normalize_education_level(["MSc in Engineering or Computer Science — advantage"]) == "none"
    assert normalize_education_level(
        ["Master's degree in Computer Science or related technical field — preferred"]
    ) == "none"
    assert normalize_education_level(
        ["Master's degree or PhD in Computer Science or related technical field — preferred"]
    ) == "none"


def test_or_equivalent_experience_waives_the_degree():
    assert normalize_education_level(["Degree or equivalent relevant experience"]) == "none"
    assert normalize_education_level(["Scientific degree or equivalent engineering experience"]) == "none"
    # "or equivalent" without "experience" is an equivalent *degree* — still required.
    assert normalize_education_level(["BSc in Computer Science or equivalent"]) == "bachelor"


def test_unrecognised_entries_are_ignored():
    assert normalize_education_level(["Minimum GPA of 85"]) == "none"
    assert normalize_education_level(["Strong academic background from leading institutions"]) == "none"


def test_empty_and_none():
    assert normalize_education_level(None) == "none"
    assert normalize_education_level([]) == "none"


def test_required_bachelor_with_optional_master():
    # two separate entries — the required one sets the floor
    assert normalize_education_level(
        ["Bachelor's in Computer Science", "Master's degree — advantage"]
    ) == "bachelor"


def test_lowest_required_level_wins_across_entries():
    assert normalize_education_level(
        ["PhD in Physics", "BSc in Computer Science"]
    ) == "bachelor"


def test_output_is_a_fixed_point():
    # feeding a canonical level back through the pipeline returns it unchanged
    for level in ("none", "bachelor", "master", "phd"):
        assert normalize_education_level([level]) == level
