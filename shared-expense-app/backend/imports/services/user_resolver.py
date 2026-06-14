import re
from django.contrib.auth import get_user_model

User = get_user_model()

# Alias Fallback Dictionary for future expansion
ALIAS_MAP = {
    # "csv_alias": "db_username"
}

def normalize_name(raw_name):
    """
    Normalizes a raw name by:
      - Collapsing duplicate spaces
      - Converting to lowercase
      - Removing leading/trailing punctuation and whitespace
    """
    if not raw_name:
        return ""
    # Collapse multiple whitespaces and strip
    name = re.sub(r'\s+', ' ', str(raw_name)).strip()
    # Convert to lowercase
    name = name.lower()
    # Remove leading/trailing punctuation characters commonly found in CSV fields
    name = name.strip('\'".,()[]{}!?;:-')
    return name

def resolve_user(raw_name: str) -> tuple:
    """
    Resolves a raw string name from a CSV to an existing User object.
    Returns:
        (User, strategy_name) if resolved, or (None, "failed") if resolution fails.
    """
    normalized = normalize_name(raw_name)
    if not normalized:
        return None, "failed"

    # STEP 5: Alias fallback
    if normalized in ALIAS_MAP:
        target_username = ALIAS_MAP[normalized]
        try:
            user = User.objects.get(username__iexact=target_username)
            return user, "alias_fallback"
        except User.DoesNotExist:
            pass

    # Load active user list for multi-stage matching
    all_users = list(User.objects.all())

    # STEP 1: Case-insensitive username match
    for u in all_users:
        if u.username.strip().lower() == normalized:
            return u, "username_case_insensitive"

    # STEP 2: Case-insensitive first_name match
    for u in all_users:
        if u.first_name and u.first_name.strip().lower() == normalized:
            return u, "first_name_match"

    # STEP 3: Case-insensitive full name match
    for u in all_users:
        full_name = f"{u.first_name or ''} {u.last_name or ''}".strip()
        if full_name and re.sub(r'\s+', ' ', full_name).lower() == normalized:
            return u, "full_name_match"

    # STEP 4: Unique prefix match
    # Match if database name starts with CSV name, or CSV name starts with database name + ' '
    candidates = []
    for u in all_users:
        db_names = [u.username.strip().lower()]
        if u.first_name:
            db_names.append(u.first_name.strip().lower())
        full_name = f"{u.first_name or ''} {u.last_name or ''}".strip()
        if full_name:
            db_names.append(re.sub(r'\s+', ' ', full_name).lower())

        is_match = False
        for db_name in db_names:
            if db_name.startswith(normalized) or normalized.startswith(db_name + " "):
                is_match = True
                break
        
        if is_match:
            candidates.append(u)

    # Deduplicate matching candidates by primary key ID
    unique_candidates = []
    seen_ids = set()
    for cand in candidates:
        if cand.id not in seen_ids:
            unique_candidates.append(cand)
            seen_ids.add(cand.id)

    # Resolve only if exactly one candidate matches (no guessing)
    if len(unique_candidates) == 1:
        return unique_candidates[0], "prefix_match"

    return None, "failed"
