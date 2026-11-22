"""tools.py - every number the agent reports comes out of one of these functions.

Assignment 3: these are now PLAIN Python functions (no LangChain @tool). server.py
registers them with FastMCP, which builds each tool's schema from the type hints and
its description from the docstring - so any MCP client can call them.

Conventions used by all tools:
  * Type hints on every parameter and the return value (they become the tool schema).
  * The docstring says WHEN to use the tool (the model reads it to choose).
  * Credit hours are floats (Quran Translation is 0.5).
  * Invalid input never raises: the tool returns a plain string starting with
    "Error: ..." so the model can read it and ask the student to fix the input.
    (That is why float-returning tools can also hand back an error string.)
"""

import math
import os
import re

# ---------------------------------------------------------------------------
# Provided data
# ---------------------------------------------------------------------------

# (minimum marks, grade points) - checked from the top down. Below 50 is F = 0.0
GRADE_BANDS = [
    (85, 4.0),  # A
    (80, 3.7),  # A-
    (75, 3.3),  # B+
    (70, 3.0),  # B
    (65, 2.7),  # B-
    (61, 2.3),  # C+
    (58, 2.0),  # C
    (55, 1.7),  # C-
    (50, 1.0),  # D
]

COURSES = {
    1: [("MS-251", "Probability & Statistics", 3.0),
        ("GE-160", "Applications of ICT", 3.0),
        ("GE-169", "Applied Physics", 3.0),
        ("GE-167", "Discrete Structures", 3.0),
        ("HQ-001", "Quran Translation - I", 0.5),
        ("GE-190", "Functional English", 3.0)],
    2: [("CC-112", "Programming Fundamentals", 3.0),
        ("CC-112-L", "Programming Fundamentals Lab", 1.0),
        ("CC-110", "Digital Logic Design", 2.0),
        ("CC-110-L", "Digital Logic Design Lab", 1.0),
        ("MS-252", "Linear Algebra", 3.0),
        ("GE-191", "Expository Writing", 3.0),
        ("GE-163", "Islamic Studies", 2.0),
        ("HQ-002", "Quran Translation - II", 0.5)],
    3: [("CC-211", "Object Oriented Programming", 3.0),
        ("CC-211-L", "Object Oriented Programming Lab", 1.0),
        ("CC-215", "Database Systems", 3.0),
        ("CC-215-L", "Database Systems Lab", 1.0),
        ("CC-210", "Computer Organization & Assembly Language", 3.0),
        ("GE-162", "Calculus & Analytical Geometry", 3.0),
        ("GE-192", "Introduction to Management", 2.0),
        ("HQ-003", "Quran Translation - III", 0.5)],
    4: [("CC-213", "Data Structures", 3.0),
        ("CC-213-L", "Data Structures Lab", 1.0),
        ("CC-312", "Information Security", 3.0),
        ("CC-214", "Computer Networks", 3.0),
        ("CC-212", "Software Engineering", 3.0),
        ("DC-220", "Advanced Database Management Systems", 3.0),
        ("HQ-004", "Quran Translation - IV", 0.5)],
    5: [("CC-313", "Analysis of Algorithms", 3.0),
        ("CC-310", "Artificial Intelligence", 3.0),
        ("DC-320", "Theory of Automata and Formal Languages", 3.0),
        ("DC-321", "Human Computer Interaction", 3.0),
        ("DC-322", "Computer Architecture", 3.0),
        ("EC-330", "Web Technologies / Elective", 3.0),
        ("HQ-005", "Quran Translation - V", 0.5)],
    6: [("CC-311", "Operating Systems", 3.0),
        ("EC-333", "Mobile Application Development / Elective", 3.0),
        ("EC-324", "Software Construction & Development / Elective", 3.0),
        ("EC-335", "Machine Learning / Elective", 3.0),
        ("EC-334", "Game Design and Development / Elective", 3.0),
        ("MS-253", "Multivariable Calculus", 3.0),
        ("HQ-006", "Quran Translation - VI", 0.5)],
    7: [("CC-411", "Final Year Project - I", 2.0),
        ("DC-328", "Parallel & Distributed Computing", 3.0),
        ("EC-345", "Computer Vision / Elective", 3.0),
        ("EC-425", "Software Quality Engineering / Elective", 3.0),
        ("MS-254", "Technical and Business Writing", 3.0),
        ("GE-263", "Entrepreneurship", 2.0),
        ("GE-262", "Professional Practices", 2.0),
        ("HQ-007", "Quran Translation - VII", 0.5)],
    8: [("CC-412", "Final Year Project - II", 4.0),
        ("DC-421", "Compiler Construction", 3.0),
        ("UE-272", "Introduction to Marketing", 3.0),
        ("GE-168", "Ideology and Constitution of Pakistan", 2.0),
        ("GE-363", "Civics and Community Engagement", 2.0),
        ("HQ-008", "Quran Translation - VIII", 0.5)],
}

MAX_SEMESTER = 8
REPORTS_DIR = "reports"
MAX_REPORT_CHARS = 20_000
_EPS = 1e-9


# ---------------------------------------------------------------------------
# Small helpers (not tools)
# ---------------------------------------------------------------------------

def _is_number(x) -> bool:
    """True for real, finite numbers (bool, NaN and inf are rejected)."""
    return (
        isinstance(x, (int, float))
        and not isinstance(x, bool)
        and math.isfinite(x)
    )


def _round2(x: float) -> float:
    """Round to 2 decimals (tiny epsilon avoids float artefacts like 3.005 -> 3.0)."""
    return round(x + _EPS, 2)


def _valid_semester(s) -> bool:
    return isinstance(s, int) and not isinstance(s, bool) and 1 <= s <= MAX_SEMESTER


def _semester_hours(semester: int) -> float:
    return sum(ch for _, _, ch in COURSES[semester])


# ---------------------------------------------------------------------------
# The seven required tools
# ---------------------------------------------------------------------------

def marks_to_grade_points(marks: int) -> float | str:
    """Convert ONE course's final marks (0-100, whole number) into PUCIT grade points.

    Use this whenever the student gives marks for a course and you need the grade
    points (e.g. 78 -> 3.3). Call it once per course. Never convert marks yourself.
    Returns an error string if the marks are not a whole number from 0 to 100.
    """
    if not _is_number(marks) or marks != int(marks):
        return "Error: marks must be a whole number between 0 and 100"
    marks = int(marks)
    if marks < 0 or marks > 100:
        return "Error: marks must be between 0 and 100"
    for minimum, points in GRADE_BANDS:
        if marks >= minimum:
            return points
    return 0.0  # below 50 -> F


def calculate_semester_gpa(grade_points: list[float], credit_hours: list[float]) -> float | str:
    """Calculate ONE semester's credit-weighted GPA from grade points and credit hours.

    Use this after you have the grade points (from marks_to_grade_points) and the
    credit hours (from get_semester_courses) of the courses being counted. The two
    lists must be the same length and in the same course order.
    Formula: sum(grade_point * credit_hours) / sum(credit_hours).
    Returns an error string on invalid input.
    """
    if not isinstance(grade_points, list) or not isinstance(credit_hours, list):
        return "Error: grade_points and credit_hours must be lists"
    if len(grade_points) == 0 or len(credit_hours) == 0:
        return "Error: grade_points and credit_hours must not be empty"
    if len(grade_points) != len(credit_hours):
        return (
            "Error: grade_points and credit_hours must have the same length "
            f"(got {len(grade_points)} and {len(credit_hours)})"
        )
    if not all(_is_number(g) and 0.0 <= g <= 4.0 for g in grade_points):
        return "Error: every grade point must be a number between 0.0 and 4.0"
    if not all(_is_number(c) and c > 0 for c in credit_hours):
        return "Error: every credit hour value must be a number greater than 0"

    total_ch = sum(credit_hours)
    weighted = sum(g * c for g, c in zip(grade_points, credit_hours))
    return _round2(weighted / total_ch)


def calculate_new_cgpa(
    current_cgpa: float,
    completed_credit_hours: float,
    semester_gpa: float,
    semester_credit_hours: float,
) -> float | str:
    """Project the student's new CGPA after ONE more semester.

    Use this for questions like "my CGPA is 3.1 with 64 credit hours; if I get a 3.6
    this semester, where do I end up?". Needs the current CGPA, the credit hours
    completed so far, the GPA achieved (or hoped for) this semester, and this
    semester's credit hours.
    Formula: (cgpa*completed_ch + sem_gpa*sem_ch) / (completed_ch + sem_ch).
    Returns an error string on invalid input.
    """
    if not (_is_number(current_cgpa) and 0.0 <= current_cgpa <= 4.0):
        return "Error: current_cgpa must be between 0.0 and 4.0"
    if not (_is_number(completed_credit_hours) and completed_credit_hours >= 0):
        return "Error: completed_credit_hours must be 0 or more"
    if not (_is_number(semester_gpa) and 0.0 <= semester_gpa <= 4.0):
        return "Error: semester_gpa must be between 0.0 and 4.0"
    if not (_is_number(semester_credit_hours) and semester_credit_hours > 0):
        return "Error: semester_credit_hours must be greater than 0"

    total_ch = completed_credit_hours + semester_credit_hours
    new_cgpa = (
        current_cgpa * completed_credit_hours + semester_gpa * semester_credit_hours
    ) / total_ch
    return _round2(new_cgpa)


def required_gpa_for_target(
    target_cgpa: float,
    current_cgpa: float,
    completed_credit_hours: float,
    remaining_credit_hours: float,
) -> float | str:
    """Calculate the GPA the student must AVERAGE over the next remaining_credit_hours
    of coursework to reach target_cgpa.

    Use this for "what do I need to get X?" questions. The result can be ABOVE 4.0,
    which means the target is impossible over that window - the correct tool output
    is not a usable answer then, so widen the window (see the system prompt). A
    result of 0.0 means the target is already secured even with a 0.0 GPA.
    Formula: (target*(completed_ch + remaining_ch) - cgpa*completed_ch) / remaining_ch.
    Returns an error string on invalid input.
    """
    if not (_is_number(target_cgpa) and 0.0 <= target_cgpa <= 4.0):
        return "Error: target_cgpa must be between 0.0 and 4.0"
    if not (_is_number(current_cgpa) and 0.0 <= current_cgpa <= 4.0):
        return "Error: current_cgpa must be between 0.0 and 4.0"
    if not (_is_number(completed_credit_hours) and completed_credit_hours >= 0):
        return "Error: completed_credit_hours must be 0 or more"
    if not (_is_number(remaining_credit_hours) and remaining_credit_hours > 0):
        return "Error: remaining_credit_hours must be greater than 0"

    required = (
        target_cgpa * (completed_credit_hours + remaining_credit_hours)
        - current_cgpa * completed_credit_hours
    ) / remaining_credit_hours

    if required <= 0:
        return 0.0
    rounded = _round2(required)
    # Never let rounding turn an impossible value (e.g. 4.004) into a "possible" 4.0
    if required > 4.0 + _EPS and rounded <= 4.0:
        rounded = 4.01
    return rounded


def get_semester_courses(semester: int) -> str:
    """Return the graded courses and credit hours of one semester (1-8) of the
    BS Computer Science scheme, plus the semester's total credit hours.

    Use this to look up credit hours for a course before computing a GPA, to check
    which courses belong to a semester, or when the student asks what a semester
    contains. Math Deficiency (MD-001/MD-002) is non-credit and is not listed.
    Returns an error string if the semester is not 1-8.
    """
    if not _valid_semester(semester):
        return "Error: semester must be between 1 and 8"
    lines = [f"Semester {semester} courses:"]
    for code, name, ch in COURSES[semester]:
        lines.append(f"- {code} | {name} | {ch} credit hours")
    lines.append(f"Total: {_round2(_semester_hours(semester))} credit hours")
    return "\n".join(lines)


def get_remaining_credit_hours(current_semester: int) -> float | str:
    """Total graded credit hours from the student's CURRENT semester through
    semester 8 (the current semester is included because it is not finished yet).

    Use this for "what do I need to graduate with X?" questions and to know the
    widest possible window (all remaining hours) when widening an unreachable
    target. Example: current_semester=5 -> semesters 5+6+7+8 = 70.0.
    Returns an error string if the semester is not 1-8.
    """
    if not _valid_semester(current_semester):
        return "Error: semester must be between 1 and 8"
    total = sum(_semester_hours(s) for s in range(current_semester, MAX_SEMESTER + 1))
    return _round2(total)


def save_report(filename: str, content: str) -> str:
    """Save a text summary (semester GPA, projected CGPA, or a target plan) to a file
    and return a confirmation message.

    Use this ONLY after the student has explicitly said yes to saving a report.
    Never call it on your own. filename should be something like
    "semester5_plan.txt" (.txt or .md; folders are not allowed). Files are written
    into the local "reports" folder. Returns an error string on invalid input.
    """
    if not isinstance(filename, str) or not filename.strip():
        return "Error: filename must not be empty"
    if not isinstance(content, str) or not content.strip():
        return "Error: content must not be empty"
    if len(content) > MAX_REPORT_CHARS:
        return f"Error: content is too long (max {MAX_REPORT_CHARS} characters)"

    name = os.path.basename(filename.strip().replace("\\", "/")).replace(" ", "_")
    if not name or name.startswith(".") or not re.fullmatch(r"[A-Za-z0-9_.\-]+", name):
        return (
            "Error: filename may only contain letters, digits, '_', '-' and '.' "
            "(no folders)"
        )
    root, ext = os.path.splitext(name)
    if ext == "":
        name += ".txt"
    elif ext.lower() not in (".txt", ".md"):
        return "Error: filename must end with .txt or .md"

    try:
        os.makedirs(REPORTS_DIR, exist_ok=True)
        path = os.path.join(REPORTS_DIR, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content.strip() + "\n")
    except OSError as exc:
        return f"Error: could not save the report ({exc.strerror or exc})"
    return f"Report saved to {path}"


# ---------------------------------------------------------------------------
# Two small helper tools (extra) - they keep ALL arithmetic out of the model.
# They are what the unreachable-target rule uses to build its horizons.
# ---------------------------------------------------------------------------

def get_completed_credit_hours(current_semester: int) -> float | str:
    """Total graded credit hours of all semesters BEFORE the student's current
    semester (i.e. what a student who finished every earlier semester has done).

    Use this when the student tells you their current semester but not their
    completed credit hours. State the assumption to the student ("assuming you
    completed all of semesters 1-4"). Example: current_semester=5 -> 64.0.
    Returns 0.0 for semester 1. Returns an error string if the semester is not 1-8.
    """
    if not _valid_semester(current_semester):
        return "Error: semester must be between 1 and 8"
    total = sum(_semester_hours(s) for s in range(1, current_semester))
    return _round2(total)


def get_horizon_credit_hours(start_semester: int, num_semesters: int) -> float | str:
    """Total graded credit hours of num_semesters consecutive semesters starting at
    start_semester (the window is cut off at semester 8).

    Use this to build the horizons for the unreachable-target rule: with
    start_semester=5, num_semesters=1 gives Semester V only (18.5), 2 gives
    Semesters V-VI (37.0), 3 gives V-VII (55.5). Returns an error string on
    invalid input.
    """
    if not _valid_semester(start_semester):
        return "Error: semester must be between 1 and 8"
    if not isinstance(num_semesters, int) or isinstance(num_semesters, bool) or num_semesters < 1:
        return "Error: num_semesters must be 1 or more"
    last = min(start_semester + num_semesters - 1, MAX_SEMESTER)
    total = sum(_semester_hours(s) for s in range(start_semester, last + 1))
    return _round2(total)


def get_credit_hours(semesters: list[int]) -> float | str:
    """Total graded credit hours of an explicit list of semesters (each 1-8).

    Use this to add up the credit hours of specific semesters that are not
    necessarily consecutive or ending at semester 8. Example: semesters=[5, 6]
    -> 37.0 (Semester V 18.5 + Semester VI 18.5). Duplicates are counted once.
    Returns an error string if the list is empty or a semester is not 1-8.
    """
    if not isinstance(semesters, list) or len(semesters) == 0:
        return "Error: semesters must be a non-empty list of numbers from 1 to 8"
    if not all(_valid_semester(s) for s in semesters):
        return "Error: every semester must be a whole number between 1 and 8"
    return _round2(sum(_semester_hours(s) for s in set(semesters)))


ALL_TOOLS = [
    marks_to_grade_points,
    calculate_semester_gpa,
    calculate_new_cgpa,
    required_gpa_for_target,
    get_semester_courses,
    get_remaining_credit_hours,
    save_report,
    get_completed_credit_hours,
    get_horizon_credit_hours,
    get_credit_hours,
]
