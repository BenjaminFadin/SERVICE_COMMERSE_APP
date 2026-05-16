# Service Commerce App - Documentation & Project Overview

This documentation serves as a reference for the Service Commerce App (Salon Management System). Use this file when requesting changes or debugging to ensure 100% contextual accuracy.

## 噫 Project Overview
A Django-based platform for salon owners to manage bookings. It features a dynamic dashboard with real-time status updates, tabbed scheduling, and performance tracking.

## 唐 Project Structure (Core Components)
- **`marketplace/models.py`**:
    - `Salon`: Business profile (name, logo, address).
    - `Service`: Services offered by salons.
    - `Appointment`: The core booking model.
        - **Fields**: `client` (ForeignKey to User), `salon`, `service`, `start_time`, `status`.
- **`marketplace/views.py`**:
    - `owner_dashboard`: Handles filtering appointments into four categories:
        1. **Pending**: `status="pending"`.
        2. **Today**: `start_time__date=today` (excluding cancelled).
        3. **Upcoming**: `start_time__date > today` (excluding cancelled).
        4. **History**: `start_time__date < today` (includes all statuses).
    - `appointment_change_status`: AJAX endpoint for moving appointments through the lifecycle.
- **`templates/`**:
    - `dashboard.html`: Main owner UI. Contains the tab navigation and AJAX JavaScript.
    - `include/booking_table.html`: Reusable component used by all four tabs.

## 売 Appointment Lifecycle & Logic
Appointments move through the system based on **Status** and **Date**:

| Status | Tab | Available Actions | Next State |
| :--- | :--- | :--- | :--- |
| `pending` | **Pending** | Accept / Cancel | `confirmed` or `cancelled` |
| `confirmed` | **Today / Upcoming** | Complete Order / Cancel | `completed` or `cancelled` |
| `completed` | **History** | None (Past record) | Final |
| `cancelled` | **History** | None (Past record) | Final |

### 套 Automatic Movement
- **To History**: Any appointment where `start_time__date < today` automatically moves to the History tab regardless of status.
- **Between Active Tabs**: When an appointment is "Accepted," it moves from Pending to either Today or Upcoming based on its scheduled date.

## 屏 Technical Implementation Details

### JavaScript / AJAX Workflow
The dashboard uses a global click listener in `dashboard.html` for elements with the `.appt-action` class.
- **Target URL**: `marketplace:appointment_change_status`
- **Mechanism**: Sends a POST request with the `status` string. Upon success (`ok: true`), the page reloads to re-sort the appointments into their correct tabs.

### Template Variables
- **`b.client`**: Accesses the User model.
- **`b.client.profile.phone`**: Accesses the user's phone number via the Profile model.
- **`b.get_status_display`**: Shows the human-readable status (e.g., "Pending" instead of "pending").

## 統 Rules for Future Changes
1. **Model Reference**: Always refer to the appointment user as `client` (not `user`).
2. **Template Inclusion**: `booking_table.html` must always have `{% load i18n %}` and `{% load static %}` at the top.
3. **Status Badges**: Use Bootstrap pill classes:
    - `pending`: `bg-warning text-dark`
    - `confirmed`: `bg-success`
    - `completed`: `bg-info`
    - `cancelled`: `bg-danger`
