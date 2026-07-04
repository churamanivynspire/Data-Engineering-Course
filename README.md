# Data Engineering Course

A hands-on data engineering course covering the core tools and concepts used in modern data pipelines — from ingestion and storage to transformation and orchestration. Course material is added weekly.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- Python 3.10+
- Basic SQL knowledge

## Course Structure

| Week | Topic | Resources | Status |
|------|-------|-----------|--------|
| [Week 1](#week-1--data-engineering-and-basic-sql) | Data engineering and Basic SQL | | In progress |
| [Week 2](#week-2--string-functions-normalization--group-by) | String Functions, Normalization, GROUP BY | [Cheatsheet](https://bishalrijal.github.io/Data-Engineering-Course/Week2/week2_string_functions_cheatsheet.html) · [Normalization](https://bishalrijal.github.io/Data-Engineering-Course/Week2/normalization_exercise.html) · [GROUP BY](https://bishalrijal.github.io/Data-Engineering-Course/Week2/group_by_under_the_hood.html) | In progress |
| [Week 3](#week-3--python-for-data-pipelines) | Python for Data Pipelines | [Python Pre-read](https://bishalrijal.github.io/Data-Engineering-Course/Week3/week3_python_preread.html) | In progress |
| Week 4 | Data Structures & Loops | [Data Structures Pre-read](https://bishalrijal.github.io/Data-Engineering-Course/Week4/week4_data_structures_preread.html) | In progress |

---

## Week 1 — Data engineering and Basic SQL

### Files

| File | Description |
|------|-------------|
| `README.md` | Setup and run instructions for this week |
| `docker-compose.yml` | Launches a PostgreSQL 16 container with a persistent volume |
| `load.py` | Python script to create the `rides` table and load `rides.csv` via PostgreSQL COPY |
| `requirements.txt` | Python dependencies for this week |
| `rides.csv` | Sample ride-sharing dataset (ride fares, distances, statuses across Nepali cities) |

### Dataset Schema

`rides.csv` — ride-level records from a fictional ride-sharing service.

| Column | Type | Description |
|--------|------|-------------|
| `ride_id` | int | Unique ride identifier |
| `driver_name` | string | Driver full name |
| `rider_name` | string | Rider full name |
| `pickup_city` | string | City where the ride started |
| `dropoff_city` | string | City where the ride ended |
| `fare_amount` | float | Fare in NPR |
| `ride_distance_km` | float | Trip distance in kilometers |
| `ride_status` | string | `completed`, `cancelled`, or `no_show` |
| `requested_at` | timestamp | When the ride was requested |
| `completed_at` | timestamp | When the ride was completed (null if not completed) |
| `rating` | float | Rider rating out of 5 (null if not completed) |
| `payment_method` | string | `cash` or `card` |

### Getting Started

```bash
cd Week1

# 1. Start the PostgreSQL container
docker compose up -d

# 2. Install Python dependencies
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Edit the credentials at the top of load.py to match your database
#    DB_NAME, DB_USER, DB_PASSWORD

# 4. Load the dataset — creates the rides table and bulk-loads rides.csv
python load.py
```

You should see a row count and a status breakdown when it finishes:

```
Connected
Table created
Loading .../rides.csv...
Loaded 10,000 rows

Rides by status:
  completed      6012
  cancelled      2498
  no_show        1490
```

**5. Query the data in DBeaver or psql:**

```bash
docker exec -it course_postgres psql -U postgres -d ridedb
```

```sql
SELECT * FROM rides LIMIT 10;
```

**6. Stop the container when done:**

```bash
docker compose down
```

---

## Week 2 — String Functions, Normalization & GROUP BY

This week covers three interconnected topics: cleaning messy string data, understanding why table design matters, and seeing how the database executes aggregate queries under the hood.

### Topics

**String Functions** — PostgreSQL functions for cleaning dirty data: `LOWER`, `TRIM`, `REGEXP_REPLACE`, `SPLIT_PART`, `CONCAT`, and more. The cheatsheet shows each function with a real example from the rides dataset.

**Normalization (1NF → 2NF → 3NF)** — Start with one broken flat table that violates every normal form. Step through each fix and watch the schema get cleaner at each stage. Covers partial dependencies, transitive dependencies, and when to extract a new table.

**GROUP BY under the hood** — A step-by-step walkthrough of what PostgreSQL actually does when it executes a GROUP BY: reading rows from disk, hashing each row's key into an in-memory bucket, running aggregate functions once per bucket, then sorting the result with ORDER BY. Covers the HashAggregate vs GroupAggregate plan choice and why casing mismatches silently split one group into two.

### Interactive Resources

| Resource | Link | What it covers |
|----------|------|----------------|
| String Functions Cheatsheet | [Open](https://bishalrijal.github.io/Data-Engineering-Course/Week2/week2_string_functions_cheatsheet.html) | Every key string function with live rides examples |
| Normalization Exercise | [Open](https://bishalrijal.github.io/Data-Engineering-Course/Week2/normalization_exercise.html) | Fix a broken table through 1NF, 2NF, 3NF step by step |
| GROUP BY Walkthrough | [Open](https://bishalrijal.github.io/Data-Engineering-Course/Week2/group_by_under_the_hood.html) | How HashAggregate works internally, phase by phase |

### Files

| File | Description |
|------|-------------|
| `week2_string_functions_cheatsheet.html` | Interactive string functions reference |
| `normalization_exercise.html` | Step-by-step normalization walkthrough (1NF → 2NF → 3NF) |
| `group_by_under_the_hood.html` | Interactive GROUP BY internals walkthrough |
| `normalized_migration.sql` | Full schema for the normalized tables (`locations`, `drivers`, `passengers`, `payment_methods`, `trips`) |
| `migrations/` | Sequential migration files — DDL first, then data inserts from the `rides` table |
| `pipeline.py` | Runs all migration files in order to build and populate the normalized schema |
| `query_drivers.py` | Assignment file — students complete the DB connection, query, and formatted output |
| `.env.example` | Template for database credentials — copy to `.env` and fill in your values |
| `requirements.txt` | Python dependencies for this week |

### Getting Started

**Prerequisites:** Week 1's `load.py` must have been run first — `pipeline.py` reads from the `rides` table.

```bash
cd Week2

# 1. Install Python dependencies
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Set up your database credentials
cp .env.example .env
# Open .env and fill in DB_NAME, DB_USER, DB_PASSWORD

# 3. Run the migration pipeline
#    This creates the normalized tables and populates them from rides
python ../Week1/load.py 
python pipeline.py
```

You should see each migration file confirmed:

```
Starting migration pipeline...

Running: 20260626000001_create_locations.sql ... OK
Running: 20260626000002_create_drivers.sql ... OK
Running: 20260626000003_create_passengers.sql ... OK
Running: 20260626000004_create_payment_methods.sql ... OK
Running: 20260626000005_create_trips.sql ... OK
Running: 20260626000006_insert_drivers.sql ... OK
Running: 20260626000007_insert_passengers.sql ... OK
Running: 20260626000008_insert_locations.sql ... OK
Running: 20260626000009_insert_payment_methods.sql ... OK
Running: 20260626000010_insert_trips.sql ... OK

All migrations completed successfully.
```

**4. Verify in DBeaver or psql:**

```sql
SELECT * FROM trips LIMIT 10;
SELECT COUNT(*) FROM drivers;
```

### Key Concepts

**Why normalization matters for this dataset** — The `rides` table has `driver_name` stored as free text. If the same driver is entered as `"ramesh shrestha"` and `"Ramesh Shrestha"`, GROUP BY treats them as two separate drivers — because `hash('ramesh shrestha') ≠ hash('Ramesh Shrestha')`. Normalization fixes this by giving each driver a row in a `drivers` table with a numeric `driver_id` as the foreign key in `rides`.

**The normalization → GROUP BY connection** — Once the schema is normalized and `driver_name` lives in exactly one place, aggregate queries become reliable: GROUP BY on `driver_id` (an integer) is unambiguous, and any display name change only requires updating one row.

---

## Assignment Submission

Assignments are submitted via GitHub Pull Requests — the same workflow used by professional data engineering teams.

### Overall Structure

You maintain a fork of this repository. Each week, you add your SQL file to the correct `submissions/` folder and open a Pull Request. The instructor reviews inline and either requests changes or merges.

```
Instructor repo (upstream)
    └── you fork it → your own copy
        └── add your SQL file → open a Pull Request → instructor reviews
```

---

### One-Time Setup

Do this once at the start of the course.

**1. Fork this repo** — click the **Fork** button on the GitHub repo page.

**2. Clone your fork:**

```bash
git clone https://github.com/YOUR-USERNAME/Data-Engineering-Course
cd de-course-assignments
```

**3. Add the instructor repo as `upstream`** so you can pull new assignments each week:

```bash
git remote add upstream https://github.com/bishalrijal/Data-Engineering-Course
```

---

### Every Week — Submitting Your Work

```bash
# 1. Pull the latest instructions and files from the instructor
git pull upstream main

# 2. Add your SQL file to the correct submissions folder
# File must follow the naming convention: yourname_weekN_queries.sql
# Example: ram_sharma_week1_queries.sql

# 3. Stage and commit
git add week1/submissions/ram_sharma_week1_queries.sql
git commit -m "week1: add Ram Sharma queries"

# 4. Push to your fork
git push origin main

# 5. Open a Pull Request
# Go to your fork on GitHub → click "Contribute" → "Open Pull Request"
```

---

### Naming Convention

All submission files must follow this format:

```
yourname_weekN_queries.sql
```

Examples:
```
ram_sharma_week1_queries.sql
sita_rai_week2_queries.sql
```

Files that don't follow this convention will be returned without review.

---

### What Happens After You Submit

- The instructor leaves **inline comments** on specific lines in your PR — read them carefully.
- If changes are needed, the PR stays open. Fix the issues, push again, and the instructor will re-review.
- Once approved, your PR is merged and your submission is complete.

---

### PR Template

When you open a Pull Request, fill in the template:

```
Student name:
Week:
Queries completed: (e.g. Q1–Q5, Q7, Q8)
Stretch attempted: Yes / No

Notes for instructor:
(What was difficult, what you're unsure about)
```

---

### Why GitHub?

By the end of this course you will have a portfolio of real work in version control with instructor feedback inline — something you can show in a job interview. Every commit, every PR, and every review comment is timestamped and permanent.

---

## License

This repository is for educational purposes.
