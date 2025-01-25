import re
from unidecode import unidecode


def slugify_persian(text):
    # Step 1: Transliterate Persian characters to Latin
    text = unidecode(text)

    # Step 2: Convert to lowercase
    text = text.lower()

    # Step 3: Replace spaces and underscores with hyphens
    text = re.sub(r"[\s_]+", "-", text)

    # Step 4: Remove invalid characters (keep alphanumeric, hyphen)
    text = re.sub(r"[^a-z0-9-]", "", text)

    # Step 5: Remove leading or trailing hyphens
    text = text.strip("-")

    return text


