/**
 * static/js/error-messages.js - Standardized error message constants for JavaScript
 * 
 * Use these functions for user-facing error messages to ensure consistency
 * and friendly language for non-technical users.
 */

const USER_ERRORS = {
  // Network & Connection
  NETWORK: "We're having trouble reaching the server. Please check your internet connection and try again.",
  TIMEOUT: "The request is taking too long. Please try again.",
  
  // Authentication
  AUTH_REQUIRED: "Your session has ended. Please log in again.",
  INVALID_CREDS: "Your phone number or PIN is incorrect. Please try again.",
  ACCESS_DENIED: "You don't have permission to do this.",
  
  // PIN/Security
  PIN_MISMATCH: "The PINs don't match. Please try again.",
  PIN_TOO_SHORT: "PIN must be 4 digits.",
  CURRENT_PIN_WRONG: "Your current PIN is incorrect. Please try again.",
  
  // Validation
  MISSING: "Please fill in all required fields.",
  INVALID: "Some fields have invalid information. Please check and try again.",
  INVALID_DATE: "Please use the correct date format.",
  INVALID_AMOUNT: "Please enter a valid amount.",
  
  // Data
  NOT_FOUND: "Not found. Please refresh and try again.",
  DUPLICATE: "This already exists. Please use different information.",
  
  // Operations
  SAVE_FAILED: "We couldn't save your changes. Please try again.",
  UPDATE_FAILED: "We couldn't update. Please try again.",
  DELETE_FAILED: "We couldn't delete this. Please try again.",
  ADD_FAILED: "We couldn't add this. Please try again.",
  
  // Specific
  PUNCH_FAILED: "We couldn't record your punch. Please try again.",
  APPROVAL_FAILED: "We couldn't approve this. Please try again.",
  LOAD_FAILED: (noun) => `We couldn't load your ${noun}. Please try again.`,
};

// Success Messages
const USER_SUCCESS = {
  SAVED: "Saved successfully!",
  UPDATED: "Updated successfully!",
  DELETED: "Deleted successfully!",
  ADDED: "Added successfully!",
  APPROVED: "Approved successfully!",
  REJECTED: "Rejected successfully!",
  PUNCH: "Recorded successfully!",
};

/**
 * Convert API error response to user-friendly message
 * Improves on raw try/catch with contextual information
 */
function convertErrorToUserMessage(error, fallback = USER_ERRORS.NETWORK) {
  // Network errors
  if (!error || error.message === 'Failed to fetch') {
    return USER_ERRORS.NETWORK;
  }
  
  // Timeout
  if (error.message === 'Request timeout') {
    return USER_ERRORS.TIMEOUT;
  }
  
  // Return fallback or error message
  return typeof error === 'string' ? error : (error.message || fallback);
}

/**
 * Display error toast with user-friendly message
 * Usage: showErrorToast('Failed to save', USER_ERRORS.SAVE_FAILED)
 */
function showErrorToast(title, message) {
  dispatchToast('error', title, message);
}

/**
 * Display success toast
 * Usage: showSuccessToast('Success', USER_SUCCESS.SAVED)
 */
function showSuccessToast(title, message) {
  dispatchToast('success', title, message);
}
