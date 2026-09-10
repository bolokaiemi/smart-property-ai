# Smart Property AI

Smart Property AI is a multilingual, accessible property-management and apartment-search platform built with FastAPI, Jinja2, SQLAlchemy, JavaScript and a custom AI training layer.

The platform is designed for:

- Apartment seekers
- Tenants
- Landlords
- Property managers
- Maintenance staff
- Platform administrators

Smart Property AI supports apartment searches, voice-activated forms, property administration, maintenance requests, complaints, automated reminders, document processing, communication services and listing analytics.

---

## Project status

The current foundation includes:

- FastAPI application configuration
- Jinja2 template rendering
- Responsive public homepage
- Multilingual language selector
- Voice input and speech output
- Accessibility controls
- Session middleware
- SQLAlchemy database configuration
- Core property-management database models
- German and English legal pages
- Temporary routes for unfinished platform sections
- Security headers
- Request logging
- Error handling
- Health-check endpoint

The authentication, listing, dashboard, AI inference and communication routes are the next development stages.

---

## Core features

### Multilingual conversational AI

- Custom property-focused AI architecture
- Multilingual text conversations
- Voice input and speech output
- Language selection
- Voice-guided form completion
- Text and keyboard alternatives
- AI privacy and permission checks

### Property and apartment search

- Public property listings
- Location and property-type filters
- Room and maximum-rent filters
- Guided apartment search
- Accessibility preference support
- Viewing and appointment requests
- Appointment reminders 30 minutes in advance

### Property management

- Secure landlord portal
- Property and apartment-unit management
- Tenant activity
- Lease management
- Rent-payment records
- Maintenance requests
- Complaints
- Expense tracking
- Document management
- Smart-home device records

### Communication and automation

- Platform messaging
- Email communication
- WhatsApp integration
- SMS and telephone integration
- Rent reminders
- Lease-renewal reminders
- Appointment reminders
- Maintenance follow-ups
- Routine property reports

### Analytics

- Listing impressions
- Listing views
- Search interactions
- Application activity
- Appointment requests
- Login and logout events connected to listings
- Property and occupancy reports

### Privacy and security

- Secure session cookies
- Password hashing
- Role-based access
- Property ownership checks
- Protected document delivery
- Upload validation
- Consent records
- Security audit logs
- AI input and output filtering
- Human approval for sensitive actions

---

## Technology stack

### Backend

- Python
- FastAPI
- Uvicorn
- SQLAlchemy
- SQLite for local development
- PostgreSQL for production
- Jinja2
- Starlette SessionMiddleware
- APScheduler

### Frontend

- HTML5
- CSS3
- JavaScript
- Jinja2 templates
- Web Speech API
- Responsive and accessible components

### Planned AI layer

- PyTorch
- Transformers
- Tokenizers
- Datasets
- Accelerate
- SentencePiece
- scikit-learn
- TensorBoard

---

## Current project structure

```text
smart-property-ai/
│
├── app.py
├── config.py
├── README.md
├── requirements.txt
├── requirements-ai.txt
├── .env
├── .env.example
├── .gitignore
│
├── routes/
│   ├── __init__.py
│   └── main_routes.py
│
├── database/
│   ├── __init__.py
│   ├── database.py
│   └── models.py
│
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── contact.html
│   │
│   ├── legal/
│   │   ├── impressum.html
│   │   ├── datenschutz.html
│   │   ├── privacy.html
│   │   ├── terms.html
│   │   ├── ai_disclosure.html
│   │   └── accessibility.html
│   │
│   └── errors/
│       ├── 400.html
│       ├── 401.html
│       ├── 403.html
│       ├── 404.html
│       ├── 429.html
│       └── 500.html
│
├── static/
│   ├── css/
│   │   └── style.css
│   │
│   ├── js/
│   │   └── main.js
│   │
│   └── images/
│       └── favicon.ico
│
├── uploads/
│   ├── properties/
│   ├── documents/
│   ├── maintenance/
│   ├── complaints/
│   └── profiles/
│
├── logs/
│   └── application.log
│
└── model_artifacts/
    ├── tokenizer/
    ├── base_model/
    ├── fine_tuned_model/
    └── exported_model/
```

---

## Requirements

Before starting, install:

- Python 3.11 or newer
- Visual Studio Code or PyCharm
- Git
- A modern web browser

SQLite is included with Python and does not require a separate installation.

---

## Installation on Windows

### 1. Open the project folder

Open PowerShell or the terminal in Visual Studio Code:

```powershell
cd path\to\smart-property-ai
```

### 2. Create a virtual environment

```powershell
python -m venv venv
```

### 3. Activate the environment

PowerShell:

```powershell
venv\Scripts\Activate.ps1
```

Command Prompt:

```cmd
venv\Scripts\activate
```

If PowerShell blocks activation, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Then activate the environment again:

```powershell
venv\Scripts\Activate.ps1
```

### 4. Upgrade pip

```bash
python -m pip install --upgrade pip
```

### 5. Install the web-platform packages

```bash
pip install fastapi uvicorn jinja2 python-multipart
pip install sqlalchemy alembic psycopg2-binary
pip install itsdangerous python-dotenv email-validator
pip install passlib bcrypt aiofiles pillow
pip install apscheduler websockets httpx pytest
```

Alternatively:

```bash
pip install -r requirements.txt
```

### 6. Save installed packages

```bash
pip freeze > requirements.txt
```

---

## Environment configuration

Create a `.env` file in the main project directory:

```env
APP_NAME=Smart Property AI
APP_VERSION=1.0.0

ENVIRONMENT=development
DEBUG=true

SECRET_KEY=replace_with_a_secure_random_secret
SESSION_COOKIE_NAME=smart_property_session
SESSION_MAX_AGE=604800

DATABASE_URL=sqlite:///./smart_property.db

DEFAULT_LANGUAGE=en
DEFAULT_CURRENCY=EUR

MAX_UPLOAD_SIZE_MB=10

PORT=8000

SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
SMTP_USE_TLS=true

WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=

PHONE_PROVIDER_ACCOUNT_ID=
PHONE_PROVIDER_AUTH_TOKEN=

AI_MODEL_PATH=model_artifacts/exported_model
AI_TOKENIZER_PATH=model_artifacts/tokenizer
AI_MAX_INPUT_LENGTH=512
AI_MAX_OUTPUT_LENGTH=256
```

Generate a secure secret key:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the generated value into `.env`:

```env
SECRET_KEY=your_generated_secret_key
```

Never upload `.env` to GitHub.

---

## Recommended `.env.example`

Create `.env.example`:

```env
APP_NAME=Smart Property AI
APP_VERSION=1.0.0

ENVIRONMENT=development
DEBUG=true

SECRET_KEY=
SESSION_COOKIE_NAME=smart_property_session
SESSION_MAX_AGE=604800

DATABASE_URL=sqlite:///./smart_property.db

DEFAULT_LANGUAGE=en
DEFAULT_CURRENCY=EUR
MAX_UPLOAD_SIZE_MB=10

PORT=8000

SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
SMTP_USE_TLS=true

WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=

PHONE_PROVIDER_ACCOUNT_ID=
PHONE_PROVIDER_AUTH_TOKEN=

AI_MODEL_PATH=model_artifacts/exported_model
AI_TOKENIZER_PATH=model_artifacts/tokenizer
AI_MAX_INPUT_LENGTH=512
AI_MAX_OUTPUT_LENGTH=256
```

---

## Recommended `.gitignore`

Create `.gitignore`:

```gitignore
# Virtual environment
venv/
.venv/

# Python
__pycache__/
*.py[cod]
*.pyo
*.pyd

# Environment secrets
.env

# Databases
*.db
*.sqlite
*.sqlite3

# Logs
logs/
*.log

# Private uploads
uploads/

# AI data and model files
ai/datasets/raw/
ai/datasets/anonymized/
ai/datasets/processed/
ai/checkpoints/
model_artifacts/

# Testing
.pytest_cache/
.coverage
htmlcov/

# IDE files
.vscode/
.idea/

# Operating-system files
Thumbs.db
.DS_Store
```

---

## Create the database

The `database/database.py` file provides:

- SQLAlchemy engine
- Database-session factory
- `get_db()` dependency
- Table creation function

Make sure `app.py` imports:

```python
from database.database import create_database_tables
```

Inside the `lifespan()` function, before `yield`, call:

```python
create_database_tables()

logger.info(
    "Database tables are ready."
)
```

The relevant part should look like:

```python
@asynccontextmanager
async def lifespan(application: FastAPI):
    logger.info("Starting Smart Property AI.")

    create_database_tables()

    logger.info("Database tables are ready.")

    yield

    logger.info("Stopping Smart Property AI.")
```

When the application starts for the first time, SQLAlchemy creates:

```text
smart_property.db
```

---

## Run the application

Start the development server:

```bash
uvicorn app:app --reload
```

Alternatively:

```bash
python app.py
```

Open the homepage:

```text
http://127.0.0.1:8000
```

Open the FastAPI documentation:

```text
http://127.0.0.1:8000/docs
```

Open the health endpoint:

```text
http://127.0.0.1:8000/health
```

Expected health response:

```json
{
    "status": "healthy",
    "application": "Smart Property AI",
    "timestamp": "2026-09-10T12:00:00+00:00"
}
```

---

## Current public routes

The current `routes/main_routes.py` provides:

| Method | URL | Route name | Purpose |
|---|---|---|---|
| GET | `/` | `home` | Homepage |
| GET | `/contact` | `contact_page` | Contact form |
| POST | `/contact` | `submit_contact` | Process contact form |
| POST | `/language` | `set_language` | Set language from a form |
| POST | `/api/language` | `set_language_api` | Set language using JavaScript |
| GET | `/impressum` | `impressum_page` | German legal notice |
| GET | `/datenschutz` | `datenschutz_page` | German privacy statement |
| GET | `/privacy` | `privacy_page` | English privacy policy |
| GET | `/terms` | `terms_page` | Terms of use |
| GET | `/ai-information` | `ai_disclosure_page` | AI disclosure |
| GET | `/accessibility` | `accessibility_page` | Accessibility statement |
| GET | `/about` | `about_page` | About page |
| GET | `/health` | `health_check` | Application health |

---

## Temporary routes

The current `app.py` contains temporary endpoints so the homepage can render without Jinja2 raising `NoMatchFound`.

Temporary routes include:

```text
/login
/register
/logout
/listings
/listings/search
/listings/guided-search
/ai/assistant
/landlord/dashboard
/tenant/dashboard
/admin/dashboard
```

These placeholders must be removed from `app.py` when the corresponding permanent route modules are created.

For example, after creating `routes/auth_routes.py`, remove the temporary:

```python
@app.get("/login", name="login")
@app.get("/register", name="register")
@app.post("/logout", name="logout")
```

Then register the real authentication router:

```python
from routes.auth_routes import router as auth_router

app.include_router(auth_router)
```

Do not keep temporary and permanent routes with the same names.

---

## Jinja2 template structure

`base.html` is the shared template.

It contains:

```html
<title>
    {% block title %}
        Smart Property AI
    {% endblock %}
</title>
```

The page-description block:

```html
<meta
    name="description"
    content="{% block description %}Smart Property AI{% endblock %}"
>
```

The dynamic page-content block:

```html
<main id="main-content" tabindex="-1">
    {% block content %}
    {% endblock %}
</main>
```

The optional page-script block:

```html
{% block scripts %}
{% endblock %}
```

`index.html` extends `base.html`:

```html
{% extends "base.html" %}

{% block title %}
Smart Property AI | Intelligent Property Management
{% endblock %}

{% block content %}
    <!-- Homepage content -->
{% endblock %}
```

---

## Static-file configuration

FastAPI mounts the static directory in `app.py`:

```python
app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static",
)
```

Reference CSS in Jinja2:

```html
<link
    rel="stylesheet"
    href="{{ url_for('static', path='css/style.css') }}"
>
```

Reference JavaScript:

```html
<script
    src="{{ url_for('static', path='js/main.js') }}"
></script>
```

Reference the favicon:

```html
<link
    rel="icon"
    href="{{ url_for('static', path='images/favicon.ico') }}"
>
```

---

## Session configuration

The application requires `SessionMiddleware` because the templates use:

```python
request.session
```

The middleware is configured in `app.py`:

```python
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie=SESSION_COOKIE_NAME,
    max_age=SESSION_MAX_AGE,
    same_site="lax",
    https_only=IS_PRODUCTION,
)
```

In production:

- Use HTTPS.
- Use a permanent secure secret.
- Set `ENVIRONMENT=production`.
- Do not expose the secret in source code.

---

## Database models

The current database models cover:

### Users and security

- `User`
- `UserSession`
- `ConsentRecord`
- `AuditLog`

### Properties and listings

- `Property`
- `Unit`
- `Listing`
- `ListingEvent`

### Tenancies and payments

- `TenantProfile`
- `Lease`
- `Payment`

### Property support

- `MaintenanceRequest`
- `Complaint`
- `Expense`

### Documents and communication

- `Document`
- `Message`
- `Appointment`
- `Notification`
- `CommunicationLog`

### Smart-home services

- `SmartDevice`
- `DeviceAction`

---

## Listing analytics

The `ListingEvent` model can track:

```text
impression
listing_view
login
logout
search_click
appointment_request
application_started
application_submitted
```

To connect login and logout activity to a listing:

1. Save the current listing ID in the session before redirecting to login.
2. Record a login event after successful authentication.
3. Record a logout event before clearing the session.
4. Store the listing ID, user ID, session ID and event timestamp.
5. Hash or minimize network identifiers before storage.

---

## Frontend JavaScript

`static/js/main.js` provides:

- Responsive navigation
- Escape-key menu closing
- Text-size controls
- High-contrast mode
- Browser-storage preferences
- Page speech output
- Language selection
- Voice-assisted apartment search
- External-link security

The language selector sends:

```json
{
    "language": "de"
}
```

to:

```text
POST /api/language
```

The backend stores the language in:

```python
request.session["language"]
```

---

## Accessibility

The platform currently includes:

- Skip link
- Semantic headings
- Keyboard-accessible navigation
- Visible focus indicators
- Text-size controls
- High-contrast mode
- Reduced-motion support
- Screen-reader status messages
- Voice and text input choices
- Responsive page layouts
- Print styles

WCAG 2.2 Level AA is a development target. Do not claim full compliance until the platform has completed an appropriate accessibility audit.

---

## Legal templates

The project contains:

```text
templates/legal/impressum.html
templates/legal/datenschutz.html
templates/legal/privacy.html
templates/legal/terms.html
templates/legal/ai_disclosure.html
templates/legal/accessibility.html
```

Replace all placeholder values such as:

```text
[Full name or company name]
[Street and house number]
[Contact email address]
[Privacy email address]
[Telephone number]
[Retention period]
```

before publishing.

The legal pages must reflect the services actually used for:

- Hosting
- Email
- WhatsApp
- SMS
- Telephone
- Payments
- Maps
- Calendar
- Analytics
- Speech recognition
- AI processing
- Smart-home devices

The final documents should be reviewed before production deployment.

---

## Planned authentication system

The authentication module should provide:

```text
GET  /login
POST /login
GET  /register
POST /register
POST /logout
GET  /forgot-password
POST /forgot-password
GET  /reset-password/{token}
POST /reset-password/{token}
```

Required features:

- Secure password hashing
- Remember Me
- Password-reset tokens
- Session creation
- Session expiration
- Role-based redirection
- Email verification
- Login-attempt protection
- Audit logging

Roles:

```text
administrator
landlord
property_manager
maintenance_staff
tenant
applicant
```

Public users should be able to browse property listings. Authentication should be required for applications, appointments, private documents, payments, complaints and portal access.

---

## Planned AI training structure

```text
ai/
├── training/
│   ├── collect_dataset.py
│   ├── anonymize_dataset.py
│   ├── clean_dataset.py
│   ├── prepare_dataset.py
│   ├── train_tokenizer.py
│   ├── train.py
│   ├── fine_tune.py
│   ├── evaluate.py
│   └── export_model.py
│
├── inference/
│   ├── inference.py
│   ├── model_loader.py
│   ├── assistant.py
│   ├── intent_classifier.py
│   └── response_generator.py
│
├── speech/
│   ├── speech_to_text.py
│   ├── text_to_speech.py
│   └── language_detector.py
│
├── vision/
│   ├── image_processor.py
│   ├── property_analyzer.py
│   └── damage_detector.py
│
├── safety/
│   ├── prompt_guard.py
│   ├── privacy_filter.py
│   ├── permission_checker.py
│   └── output_validator.py
│
├── datasets/
│   ├── raw/
│   ├── anonymized/
│   ├── processed/
│   ├── validation/
│   └── test/
│
└── checkpoints/
```

---

## Install AI dependencies

Do not install the large AI packages until the normal web platform is running correctly.

Create `requirements-ai.txt`:

```text
torch
transformers
tokenizers
datasets
accelerate
sentencepiece
evaluate
scikit-learn
pandas
numpy
tensorboard
```

Install them:

```bash
pip install -r requirements-ai.txt
```

---

## AI training sequence

Run the training programs in this order:

```bash
python ai/training/collect_dataset.py
python ai/training/anonymize_dataset.py
python ai/training/clean_dataset.py
python ai/training/prepare_dataset.py
python ai/training/train_tokenizer.py
python ai/training/train.py
python ai/training/evaluate.py
python ai/training/export_model.py
```

`train.py` is required because it performs the actual model training.

For genuine training from scratch, `train.py` must:

1. Load the custom tokenizer.
2. Load the training configuration.
3. Initialize a new model configuration.
4. Initialize random model weights.
5. Load the processed training dataset.
6. Train for the configured number of epochs.
7. Evaluate against validation data.
8. Save checkpoints.
9. Record training metrics.
10. Export the completed model.

Training a large general-purpose multilingual model from random weights requires substantial datasets and GPU resources. Begin with a small property-specific model and expand it after evaluation.

---

## Testing

Run all tests:

```bash
pytest
```

Recommended test areas:

- Registration and login
- Password reset
- Session security
- Role permissions
- Property ownership
- Listing visibility
- Listing analytics
- Tenant privacy
- Protected documents
- Image-upload validation
- Rent reminders
- Lease renewals
- Appointment reminders
- Multilingual input
- Voice-form confirmation
- Prompt injection
- AI privacy leakage
- AI hallucinations
- Unauthorized smart-device actions

---

## Troubleshooting

### SessionMiddleware error

Error:

```text
AssertionError: SessionMiddleware must be installed to access request.session
```

Confirm `app.py` contains:

```python
from starlette.middleware.sessions import SessionMiddleware

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
)
```

Install its signing dependency:

```bash
pip install itsdangerous
```

### Form parsing error

Error:

```text
The python-multipart library must be installed to use form parsing.
```

Install:

```bash
pip install python-multipart
```

### Static files do not load

Confirm the directory exists:

```text
static/
├── css/
├── js/
└── images/
```

Confirm `app.py` contains:

```python
app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static",
)
```

### Jinja2 `NoMatchFound`

This means a template called `url_for()` with a route name that has not been registered.

For example:

```html
{{ url_for('login') }}
```

requires:

```python
@router.get("/login", name="login")
async def login(...):
    ...
```

Confirm every template route name matches its FastAPI `name`.

### Template not found

Confirm the template filename and directory match exactly:

```python
name="legal/ai_disclosure.html"
```

must exist at:

```text
templates/legal/ai_disclosure.html
```

### Database tables are missing

Confirm `app.py` calls:

```python
create_database_tables()
```

during startup.

Stop and restart Uvicorn after changing database models.

During development, use Alembic migrations once the database begins storing important information. Do not delete a production database to apply schema changes.

---

## Recommended development order

1. Confirm the homepage works.
2. Confirm CSS and JavaScript load.
3. Confirm all legal pages open.
4. Confirm the SQLite database is created.
5. Build authentication routes and templates.
6. Remove temporary authentication routes.
7. Build property and unit services.
8. Build listing routes and templates.
9. Remove temporary listing routes.
10. Build the landlord portal.
11. Build the tenant portal.
12. Add maintenance and complaint services.
13. Add documents and protected downloads.
14. Add appointments and reminders.
15. Add analytics and reporting.
16. Add email communication.
17. Add WhatsApp and telephone integrations.
18. Build the AI chat interface.
19. Prepare and review the AI dataset.
20. Train and evaluate the custom model.
21. Add image and document analysis.
22. Complete privacy, security and accessibility testing.
23. Deploy the production application.

---

## Production checklist

Before public deployment:

- Replace all legal-page placeholders.
- Use PostgreSQL instead of SQLite.
- Set a strong permanent `SECRET_KEY`.
- Set `ENVIRONMENT=production`.
- Enable HTTPS.
- Use secure session cookies.
- Remove temporary routes.
- Remove development debug mode.
- Configure database migrations.
- Validate all uploaded files.
- Protect uploaded documents.
- Configure backups.
- Configure email and communication providers.
- Add rate limiting.
- Add CSRF protection.
- Review role and ownership permissions.
- Complete privacy documentation.
- Complete security testing.
- Complete accessibility testing.
- Evaluate the AI for accuracy and safety.
- Require human approval for high-risk actions.

---

## Important security notice

Never commit or publish:

- `.env`
- Passwords
- API keys
- Authentication tokens
- Private tenant documents
- Raw personal training data
- Database backups
- Model datasets containing personal data
- Application or security logs containing sensitive information

---

## License

Add your selected license here before public distribution.

```text
Copyright © 2026 [Ebivien:Ebi Emmerich-Adehor].
All rights reserved.
```

---

## Contact

```text
Smart Property AI
[Ebi Emmerich-Adehor]
[Street and house number]
[Postcode] Herne
North Rhine-Westphalia
Germany

Email: [ebivien42@gmail.com]
Telephone: [+49]
```