"""
Internationalization (i18n) utilities for OAuth Authorization pages.

Supports English (en) and Persian/Farsi (fa) languages.
Language is auto-detected from Accept-Language header or query parameter.
"""

# Translation dictionary for OAuth authorization pages
TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        # Page title
        "page_title": "Authorization Required - MCP Hub",
        # Header section
        "auth_required": "Authorization Required",
        "wants_access": "{client_name} wants to access your MCP Hub",
        # Client information
        "client_info": "Client Information",
        "client_id_label": "Client ID:",
        "redirect_uri_label": "Redirect URI:",
        # Permissions section
        "requested_permissions": "Requested Permissions:",
        "no_permissions": "No specific permissions requested",
        # Form section
        "enter_api_key": "Enter your API Key to authorize",
        "api_key_placeholder": "cmp_xxxxxxxxxxxxxxxx",
        "api_key_note": "Your API key will be validated and used to grant permissions to this application.",
        # Buttons
        "approve": "Authorize",
        "deny": "Deny",
        # Security notice
        "security_note": "Security Note:",
        "security_message": "Only authorize applications you trust. The OAuth token will inherit the permissions from your API key.",
        # Error page
        "error_title": "Authorization Error - MCP Hub",
        "auth_error": "Authorization Error",
        "unable_to_complete": "Unable to complete the authorization request",
        "error_code": "Error Code:",
        "error_description": "Description:",
        "common_solutions": "Common Solutions:",
        "solution_1": "Verify your API key is correct and active",
        "solution_2": "Check that the client application is properly configured",
        "solution_3": "Ensure the redirect URI matches the registered URI",
        "return_to_app": "Return to Application",
        "close_window": "Close Window",
        "need_help": "Need help? Check the",
        "documentation": "documentation",
        # Footer
        "secured_with": "This connection is secured with OAuth 2.1 + PKCE",
    },
    "fa": {
        # Page title
        "page_title": "احراز هویت مورد نیاز - MCP Hub",
        # Header section
        "auth_required": "احراز هویت مورد نیاز",
        "wants_access": "{client_name} می‌خواهد به MCP Hub شما دسترسی داشته باشد",
        # Client information
        "client_info": "اطلاعات برنامه",
        "client_id_label": "شناسه برنامه:",
        "redirect_uri_label": "آدرس بازگشت:",
        # Permissions section
        "requested_permissions": "دسترسی‌های درخواستی:",
        "no_permissions": "دسترسی خاصی درخواست نشده",
        # Form section
        "enter_api_key": "API Key خود را برای احراز هویت وارد کنید",
        "api_key_placeholder": "cmp_xxxxxxxxxxxxxxxx",
        "api_key_note": "API Key شما اعتبارسنجی شده و برای اعطای دسترسی به این برنامه استفاده خواهد شد.",
        # Buttons
        "approve": "تایید",
        "deny": "رد",
        # Security notice
        "security_note": "نکته امنیتی:",
        "security_message": "فقط برنامه‌هایی را که به آن‌ها اعتماد دارید تایید کنید. توکن OAuth دسترسی‌های API Key شما را به ارث خواهد برد.",
        # Error page
        "error_title": "خطای احراز هویت - MCP Hub",
        "auth_error": "خطای احراز هویت",
        "unable_to_complete": "امکان تکمیل درخواست احراز هویت وجود ندارد",
        "error_code": "کد خطا:",
        "error_description": "توضیحات:",
        "common_solutions": "راه‌حل‌های رایج:",
        "solution_1": "اطمینان حاصل کنید که API Key شما صحیح و فعال است",
        "solution_2": "بررسی کنید که برنامه به درستی پیکربندی شده است",
        "solution_3": "اطمینان حاصل کنید که آدرس بازگشت با آدرس ثبت‌شده مطابقت دارد",
        "return_to_app": "بازگشت به برنامه",
        "close_window": "بستن پنجره",
        "need_help": "نیاز به کمک دارید؟",
        "documentation": "مستندات",
        # Footer
        "secured_with": "این اتصال با OAuth 2.1 + PKCE امن شده است",
    },
}


def detect_language(accept_language: str | None = None, query_lang: str | None = None) -> str:
    """
    Detect user's preferred language from Accept-Language header or query parameter.

    Args:
        accept_language: Accept-Language header value (e.g., "en-US,en;q=0.9,fa;q=0.8")
        query_lang: Explicit language parameter from query string (takes priority)

    Returns:
        Language code: "en" or "fa"
    """
    # Priority 1: Explicit query parameter
    if query_lang:
        lang = query_lang.lower().strip()
        if lang in ["fa", "persian", "farsi"]:
            return "fa"
        if lang in ["en", "english"]:
            return "en"

    # Priority 2: Accept-Language header
    if accept_language:
        # Parse Accept-Language header
        # Format: "en-US,en;q=0.9,fa;q=0.8,fa-IR;q=0.7"
        languages = []
        for lang_entry in accept_language.split(","):
            # Extract language code (ignore quality value)
            lang = lang_entry.split(";")[0].strip().lower()
            languages.append(lang)

        # Check for Persian/Farsi
        for lang in languages:
            if lang.startswith("fa"):  # fa, fa-IR, fa-AF
                return "fa"

        # Check for English
        for lang in languages:
            if lang.startswith("en"):  # en, en-US, en-GB
                return "en"

    # Default: English
    return "en"


def get_translation(lang: str, key: str, **kwargs) -> str:
    """
    Get translated string for the given language and key.

    Args:
        lang: Language code ("en" or "fa")
        key: Translation key
        **kwargs: Format arguments for string interpolation

    Returns:
        Translated string with format arguments applied

    Example:
        >>> get_translation("en", "wants_access", client_name="ChatGPT")
        'ChatGPT wants to access your MCP Hub'

        >>> get_translation("fa", "wants_access", client_name="ChatGPT")
        'ChatGPT می‌خواهد به MCP Hub شما دسترسی داشته باشد'
    """
    # Get language dictionary (fallback to English)
    lang_dict = TRANSLATIONS.get(lang, TRANSLATIONS["en"])

    # Get translation (fallback to key itself)
    text = lang_dict.get(key, key)

    # Apply format arguments if provided
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError):
            # If formatting fails, return raw text
            return text

    return text


def get_all_translations(lang: str) -> dict[str, str]:
    """
    Get all translations for a language as a dictionary.

    Useful for passing to templates.

    Args:
        lang: Language code ("en" or "fa")

    Returns:
        Dictionary of all translations for the language
    """
    return TRANSLATIONS.get(lang, TRANSLATIONS["en"])


def get_language_name(lang: str) -> str:
    """
    Get human-readable language name.

    Args:
        lang: Language code

    Returns:
        Language name in its native form
    """
    names = {"en": "English", "fa": "فارسی"}
    return names.get(lang, "English")
