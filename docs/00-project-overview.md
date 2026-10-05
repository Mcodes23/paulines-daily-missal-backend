# Paulines Daily Missal

## 1. Project Overview

Paulines Daily Missal is a mobile application for accessing Catholic liturgical content, including daily Mass readings, liturgical information, user accounts, and subscription features.

The project consists of:

- React Native mobile application
- FastAPI backend/API layer
- Django ORM and Django Admin
- PostgreSQL database
- External Catholic calendar integration

The backend is responsible for providing data and functionality to the mobile application while Django Admin acts as the content management interface for managing liturgical content.

---

## 2. Project Goal

The goal of the project is to provide a reliable mobile application through which users can:

- View daily Catholic readings
- Browse readings by date
- Browse the liturgical calendar
- Search readings
- Browse readings by liturgical season
- Create and manage an account
- Manage their profile
- Manage subscription-related features

The backend must provide the APIs and content management capabilities required by the mobile application.

---

## 3. Current Backend Architecture

The current backend uses a hybrid architecture:

```text
React Native Mobile App
          |
          v
       FastAPI
          |
          v
     Django ORM
          |
          v
      PostgreSQL
