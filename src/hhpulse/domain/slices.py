"""Search slices whose counts refer to the full filtered search population."""

from hhpulse.domain.enums import SearchTarget
from hhpulse.domain.value_objects import QueryFilter

OPTIONS: dict[SearchTarget, dict[str, tuple[str, tuple[str, ...]]]] = {
    SearchTarget.VACANCY: {
        "low_responses": ("label", ("low_performance",)),
        "salary_present": ("label", ("with_salary",)),
        "work_format": (
            "work_format",
            ("ON_SITE", "REMOTE", "HYBRID", "FIELD_WORK", "FLY_IN_FLY_OUT"),
        ),
        "employment": ("employment_form", ("FULL", "PART", "PROJECT", "FLY_IN_FLY_OUT")),
        "education": (
            "education",
            ("not_required_or_not_specified", "higher", "special_secondary"),
        ),
    },
    SearchTarget.RESUME: {
        "salary_present": ("label", ("only_with_salary",)),
        "work_format": (
            "work_format",
            ("ON_SITE", "REMOTE", "HYBRID", "FIELD_WORK", "FLY_IN_FLY_OUT"),
        ),
        "employment": ("employment", ("full", "part", "project", "volunteer", "probation")),
        "education": (
            "education_level",
            (
                "higher",
                "bachelor",
                "master",
                "candidate",
                "doctor",
                "unfinished_higher",
                "secondary",
                "special_secondary",
            ),
        ),
    },
}


def selected_filters(target: SearchTarget, names: tuple[str, ...]) -> tuple[QueryFilter, ...]:
    unknown = set(names) - OPTIONS[target].keys()
    if unknown:
        raise ValueError(f"unsupported {target.value} slices: {', '.join(sorted(unknown))}")
    return tuple(
        QueryFilter.one(key, value)
        for name in names
        for key, values in (OPTIONS[target][name],)
        for value in values
    )


def slice_cost(target: SearchTarget, names: tuple[str, ...]) -> int:
    selected_filters(target, names)
    return sum(len(OPTIONS[target][name][1]) for name in names)
