"""Question dictionary and conservative, auditable keyword themes."""
import re

LIKERT = {v: i for i, v in enumerate(("Strongly disagree", "Slightly disagree",
    "Neither agree nor disagree", "Slightly agree", "Strongly agree"), 1)}
THEMES = {
    "course_experience": {"Q1_1": "Intellectually engaging", "Q1_2": "Clear expectations",
        "Q1_3": "Research and practice", "Q1_4": "Helpful resources", "Q1_5": "Overall learning experience"},
    "learning_experience": {"Q3.0_1": "Valuable feedback", "Q3.0_2": "Peer interaction",
        "Q3.0_3": "Manageable workload", "Q3.0_4": "Industry representation"},
    "impact": {"Q4.0_1": "New ideas and skills", "Q4.0_2": "Application to practice",
        "Q4.0_3": "Challenged thinking", "Q4.0_4": "Workplace skills", "Q4.0_5": "Conceptual understanding"},
    "assessment": {"Q5.0_1": "Demonstrated learning", "Q5.0_2": "Improved understanding",
        "Q5.0_3": "Current workplace relevance", "Q5.0_4": "Future workplace relevance", "Q5.0_5": "Clear grading criteria"},
}
TEXT = {"Q2.1": "recommendation_reason", "Q2.2": "recommendation_reason", "Q2.3": "recommendation_reason",
        "Q6.0": "application", "Q7.0": "best_aspects", "Q8.0": "improvements"}
TOPICS = {
    "access_technology": r"\b(canvas|login|log in|password|access|technical|technology)\b",
    "enrolment": r"\b(enrol\w*|enroll\w*|registration|admission\w*|withdraw\w*)\b",
    "fees_payment": r"\b(fee\w*|payment\w*|invoice\w*|refund\w*|scholarship\w*)\b",
    "assessment_feedback": r"\b(assessment\w*|assignment\w*|feedback|grading|grade\w*|marking)\b",
    "time_workload": r"\b(workload|deadline\w*|extension\w*|schedule\w*|time|timing)\b",
    "certificate_badge": r"\b(certificate\w*|badge\w*|credential\w*|completion)\b",
    "resources_content": r"\b(resource\w*|content|video\w*|reading\w*|material\w*)\b",
    "interaction_teaching": r"\b(peer\w*|discussion\w*|interaction\w*|teacher\w*|tutor\w*|facilitator\w*)\b",
    "practice_application": r"\b(practice|practical|workplace|apply|application|skills?)\b",
}


def topics(value):
    if not value or not str(value).strip():
        return ["no_text"]
    matched = [key for key, pattern in TOPICS.items() if re.search(pattern, str(value), re.I)]
    return matched or ["other_unclassified"]
