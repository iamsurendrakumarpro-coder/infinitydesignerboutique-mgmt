"""
utils/error_messages.py - Standardized user-friendly error messages.

Use these messages for all user-facing errors to ensure consistency
and friendly language for non-technical users.
"""

# Network & Connection Errors
NETWORK_ERROR = "We're having trouble reaching the server. Please check your internet connection and try again."
NETWORK_TIMEOUT = "The request is taking too long. Please try again."
CONNECTION_LOST = "Your connection was lost. Please check your internet and try again."

# Authentication Errors
AUTHENTICATION_REQUIRED = "Your session has ended. Please log in again."
INVALID_CREDENTIALS = "Your phone number or PIN is incorrect. Please try again."
AUTH_FAILED = "Unable to verify your identity. Please try again."

# Authorization/Permission Errors
ACCESS_DENIED = "You don't have permission to perform this action."
STAFF_ONLY = "This action is only available to staff members."
ADMIN_ONLY = "This action is only available to administrators."
MANAGER_ONLY = "This action is only available to managers."

# PIN/Password Errors
PIN_MISMATCH = "The PINs don't match. Please try again."
PIN_TOO_SHORT = "PIN must be 4 digits. Please try again."
PIN_CHANGE_FAILED = "We couldn't update your PIN. Please try again."
CURRENT_PIN_INCORRECT = "Your current PIN is incorrect. Please try again."

# Validation Errors - General
MISSING_FIELDS = "Please fill in all required fields."
INVALID_INPUT = "One or more fields contain invalid information. Please check and try again."
INVALID_DATE_FORMAT = "Please use the date format shown (YYYY-MM-DD)."
INVALID_EMAIL = "Please enter a valid email address."
INVALID_PHONE = "Please enter a valid phone number."
INVALID_AMOUNT = "Please enter a valid amount."

# Validation Errors - Business Logic
INVALID_DATE_RANGE = "Start date must be before or equal to end date."
INVALID_TIME_RANGE = "Start time must be before end time."
DUPLICATE_ENTRY = "This entry already exists. Please use different information."

# Data Not Found Errors
STAFF_NOT_FOUND = "Staff member not found. Please check and try again."
REQUEST_NOT_FOUND = "Request not found. It may have been deleted."
RECORD_NOT_FOUND = "Record not found. Please refresh and try again."
DESIGNATION_NOT_FOUND = "Role not found. Please check and try again."
SETTLEMENT_NOT_FOUND = "Settlement not found. Please refresh and try again."

# Save/Update Errors
SAVE_FAILED = "We couldn't save your changes. Please try again."
UPDATE_FAILED = "We couldn't update the information. Please try again."
DELETE_FAILED = "We couldn't delete this item. Please try again."
ADD_FAILED = "We couldn't add this item. Please try again."

# Specific Operation Errors
REQUEST_FAILED = "We couldn't complete this request. Please try again."
PUNCH_FAILED = "We couldn't record your punch. Please try again."
APPROVAL_FAILED = "We couldn't process your approval. Please try again."
REJECTION_FAILED = "We couldn't process your rejection. Please try again."
SETTLEMENT_GENERATION_FAILED = "We couldn't generate settlements. Please try again."
IMAGE_UPLOAD_FAILED = "We couldn't upload your image. Please try again."
IMAGE_TOO_LARGE = "Your image is too large. Please use an image smaller than 10 MB."

# Loading/Processing Errors
LOAD_FAILED_WITH_ACTION = "We couldn't load {noun}. Please try again."  # Use: LOAD_FAILED_WITH_ACTION.format(noun="staff")
PROCESSING_FAILED = "We couldn't process your request. Please try again."

# Success Messages (for consistency)
SAVE_SUCCESS = "Changes saved successfully."
UPDATE_SUCCESS = "Updated successfully."
DELETE_SUCCESS = "Deleted successfully."
ADD_SUCCESS = "Added successfully."
APPROVAL_SUCCESS = "Approved successfully."
REJECTION_SUCCESS = "Rejected successfully."
PUNCH_SUCCESS = "Recorded successfully."


def get_load_error(noun: str) -> str:
    """Generate a standardized load error message for a noun."""
    return f"We couldn't load your {noun.lower()}. Please try refreshing the page or try again later."


def get_save_error(noun: str, context: str = "") -> str:
    """Generate a standardized save error message for a noun with optional context."""
    if context:
        return f"We couldn't save your {noun.lower()}: {context}. Please try again."
    return f"We couldn't save your {noun.lower()}. Please try again."
