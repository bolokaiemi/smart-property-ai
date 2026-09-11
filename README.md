## Project status

The Smart Property AI foundation and authentication system are now working.

### Completed

- FastAPI application
- Jinja2 template system
- Responsive homepage
- Main navigation
- Single Login/Logout control
- Multilingual selector
- Voice and accessibility controls
- SQLAlchemy database connection
- SQLite development database
- Core database models
- SessionMiddleware configuration
- Secure registration
- Username or email login
- Remember Me support
- Logout and session clearing
- Password hashing with PBKDF2-SHA256
- Forgot-password flow
- Signed password-reset links
- Email-verification flow
- User consent records
- Authentication audit logs
- Role-based permission helpers
- Property-access permission helpers
- German and English legal pages
- Responsive authentication pages
- Password-strength feedback
- Password-confirmation feedback
- Security headers
- Application logging
- Health-check endpoint

### Authentication files

```text
routes/
└── auth_routes.py

services/
├── __init__.py
└── auth_service.py

security/
├── __init__.py
├── passwords.py
└── permissions.py

templates/
└── auth/
    ├── login.html
    ├── register.html
    ├── forgot_password.html
    ├── reset_password.html
    ├── reset_password_sent.html
    └── verify_email.html

static/
├── css/
│   └── auth.css
└── js/
    └── auth.js
```

---

## Authentication routes

| Method | URL | Route name | Purpose |
|---|---|---|---|
| GET | `/login` | `login` | Display login page |
| POST | `/login` | `login_submit` | Authenticate user |
| GET | `/register` | `register` | Display registration page |
| POST | `/register` | `register_submit` | Create user account |
| POST | `/logout` | `logout` | Clear authenticated session |
| GET | `/forgot-password` | `forgot_password_page` | Display account-recovery form |
| POST | `/forgot-password` | `forgot_password_submit` | Generate reset instructions |
| GET | `/reset-password/{token}` | `reset_password_page` | Display password-reset form |
| POST | `/reset-password/{token}` | `reset_password_submit` | Save the new password |
| GET | `/verify-email/{token}` | `verify_email` | Verify an email address |

---

## Authentication behavior

### Registration

Public registration currently supports:

```text
applicant
tenant
landlord
```

The following roles cannot be selected through public registration:

```text
administrator
property_manager
maintenance_staff
```

Those roles must be assigned by an authorized administrator.

### Login

Users can log in using either:

- Username
- Email address

The login process:

1. Normalizes the username or email.
2. Finds the account in the database.
3. Verifies the password hash.
4. Checks that the account is active.
5. Creates the authenticated session.
6. Records the login in the audit log.
7. Redirects the user according to their role.

### Role destinations

| Role | Default destination |
|---|---|
| Applicant | `/listings` |
| Tenant | `/tenant/dashboard` |
| Landlord | `/landlord/dashboard` |
| Property manager | `/landlord/dashboard` |
| Maintenance staff | `/maintenance/dashboard` |
| Administrator | `/admin/dashboard` |

### Password policy

Passwords must contain:

- At least 10 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one number
- At least one special character

Passwords are stored using PBKDF2-SHA256 hashes. Readable passwords must never be saved in the database or logs.

### Password reset

Password-reset links:

- Are cryptographically signed
- Expire after one hour
- Are connected to a specific account
- Become invalid after the password changes
- Are displayed only during local development

Production reset links must be sent privately through the configured email service.

### Email verification

Email-verification links:

- Are cryptographically signed
- Expire after 24 hours
- Are connected to the registered user
- Are displayed only during local development

Production verification links must be delivered by email.

### Remember Me

Remember Me stores only the username or email identifier in browser storage. It must never store the password.

### Consent records

Registration records the user’s choices for:

- Privacy Policy
- Terms of Use
- Optional AI model-training consent

User conversations are not automatically added to the AI training dataset.

---

## Authentication security

The authentication layer includes:

- Signed session cookies
- Secure password hashing
- Generic failed-login messages
- Dummy password checks
- Safe internal redirects
- Active-account validation
- Role-based access
- Property-level access checks
- Consent records
- Hashed IP information in audit records
- Password-reset expiration
- Email-verification expiration
- No readable passwords in storage
- No passwords or tokens in application logs

In production:

- Set `ENVIRONMENT=production`
- Use HTTPS
- Use a permanent secure `SECRET_KEY`
- Configure CSRF protection
- Configure login rate limiting
- Send verification links through email
- Send password-reset links through email
- Do not display signed tokens on pages

---

## Registering the authentication router

`app.py` imports the authentication router:

```python
from routes.auth_routes import router as auth_router
```

It is registered with:

```python
app.include_router(main_router)
app.include_router(auth_router)
```

The old temporary login, registration and logout routes have been removed from `app.py`.

---

## Current temporary routes

The following sections still use temporary routes:

```text
/listings
/listings/search
/listings/guided-search
/ai/assistant
/landlord/dashboard
/tenant/dashboard
/admin/dashboard
```

Remove each temporary route only after its permanent route module has been created and registered.

Do not keep temporary and permanent routes with identical route names.

---

## Test the authentication system

Start the application:

```bash
uvicorn app:app --reload
```

Open:

```text
http://127.0.0.1:8000/register
```

Test the following workflow:

1. Register a new account.
2. Open the development email-verification link.
3. Verify the email address.
4. Log in using the username.
5. Log out.
6. Log in using the email address.
7. Test Remember Me.
8. Request a password-reset link.
9. Set a new password.
10. Confirm the old password no longer works.
11. Confirm the new password works.
12. Confirm invalid or expired reset links are rejected.

Run automated tests with:

```bash
pytest
```

---

## Completed development stages

```text
1. FastAPI application foundation       Complete
2. Jinja2 base and homepage              Complete
3. CSS and frontend controls             Complete
4. Database connection and models        Complete
5. Legal and accessibility pages         Complete
6. Authentication and authorization      Complete
7. Property and unit management          Next
8. Public property listings              Pending
9. Guided apartment search               Pending
10. Landlord dashboard                   Pending
11. Tenant dashboard                     Pending
12. Lease and payment management         Pending
13. Maintenance and complaints           Pending
14. Documents and expenses               Pending
15. Appointments and reminders           Pending
16. Listing analytics                    Pending
17. Communication automation             Pending
18. AI assistant interface               Pending
19. Voice-activated forms                Pending
20. Image processing                     Pending
21. AI dataset and model training        Pending
22. Smart-home integration               Pending
23. Complete testing and deployment      Pending
```

---

## Next development stage

The next stage is property and apartment-unit management.

Create:

```text
services/
├── property_service.py
└── unit_service.py

routes/
├── property_routes.py
└── unit_routes.py

templates/
└── landlord/
    ├── properties.html
    ├── add_property.html
    ├── edit_property.html
    ├── property_details.html
    └── units.html

static/
├── css/
│   └── property.css
└── js/
    └── property.js
```

The property-management stage will allow authenticated landlords and property managers to:

- Add properties
- View their properties
- Edit property information
- Activate or deactivate properties
- Add apartment units
- Edit apartment units
- Record rent and deposit amounts
- Record room and accessibility information
- Mark units as vacant, occupied or unavailable
- Prevent unauthorized users from managing properties                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      