"""Question dictionary and conservative, auditable keyword themes."""
import re

LIKERT = {v: i for i, v in enumerate(("Strongly disagree", "Slightly disagree",
    "Neither agree nor disagree", "Slightly agree", "Strongly agree"), 1)}
THEMES = {
    "course_experience": {
        "Q1_1": "I found the MicroCert intellectually engaging and stimulating",
        "Q1_2": "The MicroCert set clear expectations, including assessment requirements",
        "Q1_3": "The MicroCert reflected the latest research and practice",
        "Q1_4": "The learning resources were helpful",
        "Q1_5": "Overall, I had a very good learning experience",
    },
    "learning_experience": {
        "Q3.0_1": "I received valuable feedback on my learning progress",
        "Q3.0_2": "I had opportunities to interact meaningfully with peers",
        "Q3.0_3": "I could manage the learning workload within the available timeframe",
        "Q3.0_4": "I was satisfied with the level of industry representation",
    },
    "impact": {
        "Q4.0_1": "I learned new ideas, approaches or skills",
        "Q4.0_2": "I learned to apply knowledge to practice",
        "Q4.0_3": "The MicroCert challenged my way of thinking",
        "Q4.0_4": "I developed skills that will help me in the workplace",
        "Q4.0_5": "I improved my understanding of concepts and principles in the field",
    },
    "assessment": {
        "Q5.0_1": "Assessment tasks allowed me to demonstrate what I had learned",
        "Q5.0_2": "Assessment tasks increased my understanding of core concepts",
        "Q5.0_3": "Assessment tasks were applicable to my current workplace",
        "Q5.0_4": "Assessment tasks were applicable to my future intended workplace",
        "Q5.0_5": "Assessment tasks had grading criteria that I could easily understand",
    },
}
QUESTION_GROUPS = {
    "course_experience": ("Q1", "To what extent do you agree or disagree with the following statements made about the Melbourne MicroCert?"),
    "learning_experience": ("Q3", "Thinking about your learning experience, to what extent do you agree or disagree with the following statements about the Melbourne MicroCert?"),
    "impact": ("Q4", "Thinking about the impact of your learning, to what extent do you agree or disagree with the following statements about the Melbourne MicroCert?"),
    "assessment": ("Q5", "To what extent do you agree or disagree with the following statements about Melbourne MicroCert assessment tasks?"),
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
