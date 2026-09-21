# Smart Property AI

Smart Property AI is a multilingual property-management platform built with FastAPI, Jinja2, SQLAlchemy, JavaScript, and CSS.

The platform supports public apartment searches, landlord and tenant portals, property management, applications, viewing appointments, maintenance requests, document management, accessible voice controls, and a conversational AI assistant.

## Current project status

The application starts successfully with Uvicorn.

The following areas are currently available:

- Public homepage
- Contact page
- User registration and login
- Logout and password reset
- Email verification templates
- Public property listings
- Guided apartment search
- Rental applications
- Viewing appointments
- Tenant portal
- Landlord portal
- Property and unit management
- Lease management
- Maintenance requests
- Complaints
- Payments
- Documents
- Expenses and reports
- Messages and notifications
- Smart-home device pages
- Multilingual controls
- Voice-enabled forms
- Speech output
- CSRF protection
- Session authentication
- Privacy and legal pages
- SQLite database integration

The landlord dashboard is now displaying successfully.

The next development stage is completing the internal `ai/` package and connecting it to `routes/ai_routes.py`.

## Main features

### Multilingual conversational AI

- Multilingual assistant interface
- Language selection
- Speech-to-text input
- Read-aloud responses
- Voice-activated forms
- Accessible keyboard navigation
- Responsible AI disclosure
- Conversation safety checks

### Apartment search

- Public property listings
- Property search filters
- Property detail pages
- Guided apartment search
- Rental application forms
- Viewing appointment booking
- Appointment reminders

### Landlord portal

- Secure landlord dashboard
- Portfolio statistics
- Recent landlord activity
- Upcoming appointments
- Property management
- Unit management
- Tenant management
- Lease management
- Rental applications
- Viewing appointments
- Maintenance requests
- Complaints
- Payments
- Documents
- Expenses
- Reports
- Messages
- Notifications
- Smart-home devices
- Landlord settings

### Tenant portal

- Secure tenant dashboard
- Lease details
- Payment records
- Maintenance requests
- Complaints
- Documents
- Messages
- Appointments
- Notifications
- Tenant profile

### Automation

The project foundation includes support for:

- Rent reminders
- Lease-renewal reminders
- Appointment reminders
- Email communication
- WhatsApp communication
- Phone communication
- Routine reports
- Maintenance notifications

### Privacy and security

- Session-based authentication
- Role-based permissions
- CSRF protection
- Password hashing
- File validation
- Privacy controls
- Audit logging
- Responsible AI notices
- Secure landlord and tenant routes

## Technology stack

- Python 3.11 or newer
- FastAPI
- Uvicorn
- Jinja2
- SQLAlchemy
- SQLite for local development
- Starlette SessionMiddleware
- HTML5
- Modern CSS
- Vanilla JavaScript
- Web Speech API

## Project structure

```text
smart property ai/
│
├── app.py
├── config.py
├── requirements.txt
├── README.md
├── .env
├── .env.example
├── .gitignore
├── render.yaml
├── render-build.sh
├── Dockerfile
│
├── database/
│   ├── __init__.py
│   ├── database.py
│   ├── models.py
│   └── migrations/
│       ├── env.py
│       ├── script.py.mako
│       └── versions/
│
├── routes/
│   ├── __init__.py
│   ├── main_routes.py
│   ├── auth_routes.py
│   ├── listing_routes.py
│   ├── application_routes.py
│   ├── ai_routes.py
│   ├── tenant_routes.py
│   ├── landlord_routes.py
│   ├── document_routes.py
│   ├── payment_routes.py
│   ├── maintenance_routes.py
│   ├── message_routes.py
│   ├── notification_routes.py
│   ├── automation_routes.py
│   └── admin_routes.py
│
├── services/
│   ├── __init__.py
│   ├── auth_service.py
│   ├── property_service.py
│   ├── unit_service.py
│   ├── listing_service.py
│   ├── application_service.py
│   ├── appointment_service.py
│   ├── tenant_service.py
│   ├── landlord_service.py
│   ├── lease_service.py
│   ├── payment_service.py
│   ├── maintenance_service.py
│   ├── complaint_service.py
│   ├── document_service.py
│   ├── message_service.py
│   ├── notification_service.py
│   ├── contact_service.py
│   ├── email_service.py
│   ├── whatsapp_service.py
│   ├── phone_service.py
│   ├── image_service.py
│   ├── expense_service.py
│   ├── report_service.py
│   ├── smart_home_service.py
│   └── audit_service.py
│
├── security/
│   ├── __init__.py
│   ├── passwords.py
│   ├── permissions.py
│   ├── csrf.py
│   ├── rate_limit.py
│   ├── file_validation.py
│   ├── privacy.py
│   └── audit.py
│
├── ai/
│   ├── __init__.py
│   ├── assistant.py
│   ├── inference.py
│   ├── prompts.py
│   ├── safety.py
│   ├── language.py
│   ├── preprocessing.py
│   ├── train.py
│   ├── evaluate.py
│   ├── model_registry.py
│   ├── datasets/
│   │   ├── raw/
│   │   ├── processed/
│   │   └── README.md
│   ├── checkpoints/
│   │   └── .gitkeep
│   └── tests/
│       ├── test_assistant.py
│       ├── test_safety.py
│       ├── test_languages.py
│       └── test_inference.py
│
├── automation/
│   ├── __init__.py
│   ├── scheduler.py
│   ├── rent_reminders.py
│   ├── lease_renewals.py
│   ├── appointment_reminders.py
│   ├── routine_reports.py
│   └── notification_jobs.py
│
├── integrations/
│   ├── __init__.py
│   ├── email_provider.py
│   ├── whatsapp_provider.py
│   ├── phone_provider.py
│   ├── payment_provider.py
│   ├── storage_provider.py
│   └── smart_home_provider.py
│
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── contact.html
│   ├── auth/
│   ├── legal/
│   ├── listings/
│   ├── ai/
│   ├── landlord/
│   ├── tenant/
│   ├── admin/
│   └── errors/
│
├── static/
│   ├── css/
│   │   ├── style.css
│   │   ├── auth.css
│   │   ├── property.css
│   │   ├── listings.css
│   │   ├── tenant.css
│   │   ├── landlord.css
│   │   ├── ai-assistant.css
│   │   ├── chat-overlay.css
│   │   ├── contact.css
│   │   ├── accessibility.css
│   │   └── responsive.css
│   ├── js/
│   │   ├── main.js
│   │   ├── auth.js
│   │   ├── property.js
│   │   ├── listings.js
│   │   ├── tenant.js
│   │   ├── landlord.js
│   │   ├── ai-assistant.js
│   │   ├── chat-overlay.js
│   │   ├── contact.js
│   │   ├── language-selector.js
│   │   ├── voice-forms.js
│   │   ├── speech-output.js
│   │   └── guided-search.js
│   └── images/
│       ├── favicon.ico
│       ├── logo.svg
│       └── listing-placeholder.svg
│
├── uploads/
│   └── .gitkeep
│
├── logs/
│   └── .gitkeep
│
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_auth.py
    ├── test_listings.py
    ├── test_applications.py
    ├── test_appointments.py
    ├── test_ai_routes.py
    ├── test_tenant_routes.py
    ├── test_landlord_routes.py
    ├── test_contact.py
    ├── test_permissions.py
    └── test_models.py