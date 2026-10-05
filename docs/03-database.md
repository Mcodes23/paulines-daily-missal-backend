# Database Documentation

## 1. Overview

Paulines Daily Missal uses **PostgreSQL** as its primary relational database.

Django models define the structure of the application's data, while Django ORM provides the interface between the Python backend and PostgreSQL.

The relationship is:

```text
Django Model
     |
     | Django ORM
     v
PostgreSQL Table
     |
     v
Stored Records
