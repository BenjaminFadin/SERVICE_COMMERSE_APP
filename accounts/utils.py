from django.core.cache import cache

def code_is_valid(email, code):
    """
    Retrieves the code from the cache using the email as the key.
    If it matches the user input, it returns True.
    """
    # We fetch the code stored in the cache
    stored_code = cache.get(f"reset_code_{email}")
    
    # Return True if codes match, False otherwise
    return str(stored_code) == str(code)