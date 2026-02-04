REQUIRED_PERSONA_FIELDS = {
    # For diet: collect a solid core persona before answering.
    # Order of fields controls the question order.
    "diet": [
        "age",          # 1) age
        "height_cm",    # 2) ask height + weight together (weight will be auto-extracted)
        "diet_type",    # 3) veg / non-veg / egg
        "activity_level",  # 4) desk-based vs active
        "goal",         # 5) goal (fat loss / muscle gain / general)
    ],
    # For fitness, goal + age + activity are enough initially.
    "fitness": [
        "age",
        "activity_level",
        "goal",
    ],
    # For skin/hair, ask targeted questions when relevant.
    "skin": [
        "skin_type",
    ],
    "hair": [
        "hair_type",          # straight / wavy / curly
        "scalp_condition",    # oily / dry / normal / sensitive
        "dandruff",           # yes / no / sometimes
        "stress_level",       # low / medium / high
        "hairfall_duration",  # since when
    ],
}
