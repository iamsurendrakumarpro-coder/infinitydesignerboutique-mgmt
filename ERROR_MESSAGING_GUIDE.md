# Error Messaging Standards - IDB Management App

This document establishes standardized, user-friendly error messages for the application.

## Philosophy

- **Users are non-technical**: Boutique staff and managers may not understand technical jargon
- **Be specific but simple**: "Your changes couldn't be saved. Try again." not "500 Internal Server Error"
- **Be actionable**: Tell users what to do next: "Please check your internet" not just "Network error"
- **Be reassuring**: Avoid blame language; use "we couldn't" not "you failed"

## Error Message Categories

### 1. Network Errors

**When to use**: API calls fail, timeout, or network unavailable

❌ **Bad**: 
```
"Failed to fetch"
"Network Error"
"Connection timeout"
```

✅ **Good**: 
```
"We're having trouble reaching the server. Please check your internet connection and try again."
```

**Implementation**:
```javascript
// Use in templates
catch (e) {
  showErrorToast('Connection Issue', USER_ERRORS.NETWORK);
}
```

### 2. Authentication/Authorization Errors

**When to use**: User not logged in, invalid credentials, or insufficient permissions

❌ **Bad**: 
```
"401 Unauthorized"
"AUTHENTICATION_REQUIRED"
"Access denied"
```

✅ **Good**: 
```
"Your session has ended. Please log in again."
"You don't have permission to do this."
"Your phone number or PIN is incorrect. Please try again."
```

### 3. Validation Errors

**When to use**: User input is missing or invalid

❌ **Bad**: 
```
"Missing fields"
"Invalid input format"
"Validation failed"
```

✅ **Good**: 
```
"Please fill in all required fields."
"Please enter a valid date (YYYY-MM-DD)."
"Please enter a valid amount."
```

### 4. Data/Record Errors

**When to use**: Record not found, already exists, etc.

❌ **Bad**: 
```
"404 Not Found"
"Duplicate entry"
"Record not found"
```

✅ **Good**: 
```
"Staff member not found. Please check and try again."
"This entry already exists. Please use different information."
```

### 5. Operation Errors

**When to use**: User action failed (save, update, delete, etc.)

❌ **Bad**: 
```
"Failed to save"
"Update error"
"Delete failed (500)"
```

✅ **Good**: 
```
"We couldn't save your changes. Please try again."
"We couldn't update the information. Please try again."
"We couldn't delete this item. Please try again."
```

## Implementation Guide

### In Python (Backend)

**Do NOT do this**:
```python
return jsonify({"error": "Failed"}), 400
return jsonify({"error": "Invalid request"}), 400
```

**Do this**:
```python
from utils.error_messages import INVALID_CREDENTIALS, SAVE_FAILED

return jsonify({"error": INVALID_CREDENTIALS}), 401
return jsonify({"error": SAVE_FAILED}), 400
```

### In JavaScript (Frontend)

**Do NOT do this**:
```javascript
catch (e) {
  dispatchToast('error', 'Error', 'Failed to load');
}
```

**Do this**:
```javascript
catch (e) {
  console.error('Staff load error:', e);
  showErrorToast('Loading Failed', USER_ERRORS.LOAD_FAILED('staff'));
}
```

**Or with context**:
```javascript
const res = await fetch('/api/v1/staff');
if (res.ok) {
  const data = await res.json();
  this.staff = data.records || [];
  showSuccessToast('Success', USER_SUCCESS.LOADED);
} else {
  const err = await res.json().catch(() => ({}));
  console.error('API error:', err);
  showErrorToast('Loading Failed', USER_ERRORS.LOAD_FAILED('staff'));
}
```

## Toast Notification Pattern

Every user interaction should result in feedback:

```javascript
// Initialize page data
async init() {
  try {
    // Load data...
    showSuccessToast('Ready', 'Page loaded');
  } catch (e) {
    showErrorToast('Failed', USER_ERRORS.LOAD_FAILED('data'));
  }
}

// Form submission
async handleSubmit() {
  try {
    const res = await fetch('/api/v1/data', { method: 'POST', ... });
    if (res.ok) {
      showSuccessToast('Success', USER_SUCCESS.SAVED);
      // Redirect or refresh
    } else {
      const err = await res.json();
      showErrorToast('Failed', err.error || USER_ERRORS.SAVE_FAILED);
    }
  } catch (e) {
    showErrorToast('Error', USER_ERRORS.NETWORK);
  }
}
```

## Error Message Format

Use consistent phrasing:

| Category | Format | Example |
|----------|--------|---------|
| Network | "We're having trouble... Please check..." | "We're having trouble reaching the server. Please check your internet connection." |
| Auth | "[Action] requires... " or "Your [thing] has ended" | "Your session has ended. Please log in again." |
| Validation | "Please [verb] [noun]..." | "Please fill in all required fields." |
| Data | "[Data] not found / already exists..." | "Staff member not found. Please refresh and try again." |
| Operation | "We couldn't [action]. Please try again" | "We couldn't save your changes. Please try again." |

## Success Messages

Keep success messages brief and positive:

```
"Saved successfully!"
"Updated successfully!"
"Approved successfully!"
```

## Debugging

Always log the actual error to console for troubleshooting:

```javascript
catch (e) {
  console.error('Detailed error for debugging:', e);  // ← Keep this
  showErrorToast('Failed', USER_ERRORS.SAVE_FAILED);  // ← Show friendly message
}
```

## When to NOT Show an Error

Some errors should not be shown to users:

- Validation errors that the UI should prevent (disable button if form invalid)
- Loading spinners that complete silently (no "loading done" toast unless requested)
- Background sync operations that fail and retry

## Files to Use

- **Python**: `from utils.error_messages import *`
- **JavaScript**: Use `USER_ERRORS` and `USER_SUCCESS` from `static/js/error-messages.js`

## Checklist for New Features

- [ ] All API errors return via `USER_ERRORS` constants
- [ ] Python backend returns user-friendly error messages
- [ ] JavaScript template catches errors and uses USER_ERRORS
- [ ] Success states show toast via USER_SUCCESS
- [ ] Network failures show network-specific message
- [ ] Validation errors are specific (which field?)
- [ ] Errors logged to console for troubleshooting
- [ ] No technical jargon in user-facing messages
- [ ] Errors actionable (tell user what to do next)

## Questions?

Ask: "Would a non-technical person understand this message without technical background?"

If the answer is no, rewrite it.
