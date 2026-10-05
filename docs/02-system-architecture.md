# System Architecture

## 1. Overview

Paulines Daily Missal uses a hybrid backend architecture combining FastAPI and Django.

FastAPI acts as the main API layer used by the mobile application.

Django provides the ORM, database models, migrations, and administration interface used to manage application content.

PostgreSQL is the persistent database.

---

## 2. High-Level Architecture

```text
                    React Native Mobile App
                             |
                             | HTTP/JSON
                             v
                    +-------------------+
                    |      FastAPI      |
                    |    API Layer      |
                    +-------------------+
                       |             |
                       |             |
                       v             v
              +---------------+   +----------------------+
              |  Django ORM   |   | External Calendar    |
              |               |   | API                  |
              +---------------+   +----------------------+
                       |
                       v
                +-------------+
                | PostgreSQL  |
                |  Database   |
                +-------------+
                       ^
                       |
                +-------------+
                | Django      |
                | Admin / CMS |
                +-------------+
```

## 3. Main Components
# 3.1 React Native Mobile Application

The React Native application is the client used by end users.

It communicates with the backend through HTTP requests.

The mobile application does not directly communicate with PostgreSQL.

Typical flow:

```text
    User
     |
     v
    React Native Screen
    |
    v
    HTTP Request
    |
    v
    FastAPI Endpoint
```
# 3.2 FastAPI

FastAPI is the primary communication layer between the mobile application and the backend.

Its responsibilities include:

Receiving HTTP requests
Validating request data
Authenticating users
Calling backend services
Retrieving application data
Returning JSON responses

The API is organized under:

/api/v1/

The API documentation is generated automatically from the FastAPI application.

Development documentation:

/api/docs

OpenAPI specification:

/api/openapi.json
# 4. FastAPI Request Flow

A typical API request follows this pattern:

```text
    Mobile App
    |
    | GET /api/v1/readings/today
    v
    FastAPI Router
    |
    v
    Endpoint
    |
    v
    Service / Business Logic
    |
    v
    Django ORM
    |
    v
    PostgreSQL
    |
    v
    Service
    |
    v
    FastAPI Response
    |
    v
    Mobile App
```

The important separation is:

Router/endpoint handles the HTTP request.
Service handles business logic.
ORM handles database interaction.
PostgreSQL stores the data.
# 5. Django ORM

Django's ORM provides the connection between Python model classes and PostgreSQL database tables.

For example:

LiturgicalDay.objects.filter(...)

allows backend Python code to query the database using Django models instead of writing raw SQL for every operation.

Conceptually:

```text 
    Python Model
        |
        | Django ORM
        v
    PostgreSQL Table

Example:

    LiturgicalDay model
        |
        v
    missal_liturgicalday table
```
# 6. PostgreSQL

PostgreSQL stores the application's persistent data.

Important database areas include:

Accounts
auth_user
accounts_user_profile
accounts_subscription
accounts_subscription_plan
Liturgical structure
missal_liturgicalseason
missal_weektitle
missal_daytitle
missal_liturgicalday
missal_liturgicaldaytype
Readings
missal_reading
missal_readingkind
missal_reading_sunday_cycles
missal_reading_weekday_cycles
Other liturgical content
missal_responsorialpsalm
missal_gospelacclamation
missal_introductoryrites
missal_specialsections

The complete database structure is documented separately in:

docs/03-database.md
# 7. Django Admin / CMS

Django Admin provides the content management interface.

Administrators can manage liturgical content through the browser instead of directly editing PostgreSQL.

The relationship is:

```text 
    Administrator
        |
        v
    Django Admin
        |
        v
    Django Models / ORM
        |
        v
    PostgreSQL
```
The mobile application does not use Django Admin directly.

Instead:
```text
    Administrator
        |
        v
    Django Admin
        |
        v
    PostgreSQL
        |
        v
    FastAPI
        |
        v
    React Native
```
This allows administrators to update content through the CMS and allows the mobile application to retrieve that content through the API.

# 8. Liturgical Reading Flow

The reading system is centered around LiturgicalDay.

Conceptually:
```text
    LiturgicalSeason
        |
        v
    WeekTitle
        |
        v
    DayTitle
        |
        v
    LiturgicalDay
        |
        +-------- Reading
        |
        +-------- Psalm
        |
        +-------- Gospel Acclamation
        |
        +-------- Introductory Rites
        |
        +-------- Special Sections
```
LiturgicalDay represents a specific liturgical day and connects the day with its associated content.

# 9. Reading API Flow

When the mobile application requests readings:

GET /api/v1/readings/today

the request enters FastAPI.

The backend then uses reading services and the Django ORM to locate the appropriate liturgical data.

Conceptually:
```text
    GET /readings/today
            |
            v
    FastAPI
            |
            v
    Reading Service
            |
            +------> External Calendar API
            |
            +------> Django ORM
                    |
                    v
                PostgreSQL
                    |
                    v
              LiturgicalDay
                    |
                    +--> Readings
                    +--> Psalm
                    +--> Gospel Acclamation
                    +--> Other content
            |
            v
    Formatted API Response
            |
            v
    React Native
```
# 10. External Calendar API

The backend can communicate with an external Catholic calendar service using HTTP.

This external service can provide calendar/liturgical context used by the reading system.

The backend therefore acts as an intermediary:
```text
    FastAPI
    |
    | HTTP request
    v
    External Catholic Calendar API
    |
    | Calendar information
    v
    FastAPI
```
The mobile application does not need to communicate directly with the external service.

# 11. Authentication Architecture

Authentication is handled through the FastAPI API layer.

The general flow is:
```text
    React Native
        |
        | POST /auth/register
        v
    FastAPI
        |
        v
    Django User Model
        |
        v
    PostgreSQL
```
After successful authentication, the backend returns authentication tokens.

For protected requests:
```text
    React Native
        |
        | Authorization: Bearer <access_token>
        v
    FastAPI
        |
        v
    Authentication / Dependencies
        |
        v
    Protected Endpoint
```
The exact authentication flow is documented in:

docs/06-authentication.md
# 12. Subscriptions

Subscription functionality follows a similar pattern:
```text
    React Native
        |
        v
    FastAPI Subscription Endpoint
        |
        v
    Django ORM
        |
        v
    PostgreSQL
```
Subscription information is stored in:

accounts_subscription
accounts_subscription_plan
# 13. Why FastAPI and Django Are Both Used

The project does not use FastAPI and Django for the same purpose.

FastAPI

Primarily responsible for:

REST API
Request/response handling
API validation
Authentication endpoints
Mobile application communication
Django

Primarily responsible for:

Models
ORM
Migrations
Database management
Django Admin
CMS functionality

This gives the project a separation between:
```text
API Layer
   +
Data / CMS Layer
```
# 14. Current Architecture Considerations

The current project already contains substantial backend functionality.

Development should therefore prioritize:

Understanding existing functionality.
Testing existing endpoints.
Identifying gaps.
Fixing issues.
Adding missing functionality.
Testing changes.

The project should avoid rewriting working components without a clear reason.

# 15. Current Known Issues

The following issues have been identified during initial development:

Django Admin static assets

Some Django Admin/Jazzmin/Nested Admin static assets currently return 404 responses.

This affects the appearance and potentially some functionality of the Admin interface.

This needs to be investigated separately from the API implementation.

Reading data availability

The reading API can respond successfully at the endpoint level, but some requested dates may not have corresponding reading records in the database.

For example:

GET /api/v1/readings/today

can return a 404 when matching readings are not available.

This should be distinguished from an API endpoint being unavailable.

# 16. Architecture Goal

The intended final flow is:
```text
                    React Native
                         |
                         v
                     FastAPI
                    /       \
                   /         \
                  v           v
          Django ORM       External
              |             Calendar
              v               API
          PostgreSQL
              ^
              |
        Django Admin
              ^
              |
        Administrator
```
The system should allow administrators to manage content through Django Admin while the React Native application consumes that content through the FastAPI API.
