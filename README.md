# Vertex Fit Backend

Vertex Fit is an AI-powered, computer-vision-assisted bodybuilding assistant engineered to bridge the gap between traditional workout logging and automated personal coaching. The platform targets athletes and lifters looking to optimize execution mechanics by transforming standard mobile video recordings into actionable, millisecond-accurate biomechanical feedback.

By pairing a robust, relational data layer with state-of-the-art Video Language Models (VLMs), Vertex Fit eliminates the guesswork from compound movements (like Squats) and isolation movements (like Bicep Curls), ensuring users maintain optimal form, track true performance metrics, and reduce injury risks.

## 🚀 Key Core Features & Capabilities

- **Automated Form Analysis (VLM Integration):** Users upload video recordings of their sets directly from their mobile devices. The backend pipelines these assets to a specialized vision intelligence engine to evaluate range of motion, eccentric/concentric speed, and postural breakdowns.
- **Intelligent Metrics Tracking:** Moving beyond simple numerical tallies, the platform captures contextual session execution data, storing comprehensive feedback blocks alongside validated rep counts.
- **Granular Physical Profiling:** Tracks dynamic user biological data over time, adapting to changing fitness goals (Bulking, Cutting, Maintenance) while offering a framework for customized progression tracking.
- **Production-Ready SaaS Foundations:** Built with commercial scalability in mind, incorporating secure premium tiers and subscription state mapping directly via webhook-ready infrastructure (Paddle integration).

## 🚀 Project Status: Phase 1 Complete

The underlying database schema and local development environment are fully initialized and functional.

---

## 🛠️ Tech Stack & Architecture

- **Framework:** Django 5.0 & Django REST Framework (DRF)
- **Database:** PostgreSQL 18 (Relational Storage)
- **Environment:** Python Virtual Environment (`venv`) with decoupled `.env` configurations

---

## 📐 System Schema (Phase 1 Database Architecture)

### 1. Authentication App

Extends Django's base `AbstractUser` model to transition from username-based logins to a modern **Email-as-Username** configuration.

- **`User` Model:** Custom authentication handles using unique email identifiers.
- **`Profile` Model:** One-to-One relationship with the User table. Tracks localized physical metrics (`height`, `target_weight`), fitness goals, and monetization states (`is_premium`, `paddle_subscription_id`).

### 2. Workouts App

Manages physical execution data structure and placeholder structures for AI system metrics.

- **`Exercise` Model:** A static repository lookup table for baseline tracking movements (e.g., Squat, Bicep Curl).
- **`WorkoutSession` Model:** A transactional log recording individual user sets, capturing `rep_count`, an S3 cloud destination `video_url`, and a `vlm_feedback` text block for future Video Language Model analysis integration.

---

## 💻 Local Setup & Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/rakanHijazeen/Vertex_Fit.git
   cd Vertex_Fit

   ```

2. **Initialize and activate the virtual environment:**

   ```bash
   python -m venv venv
   # On Windows (Git Bash):
   source venv/Scripts/activate

   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt

   ```

4. **Environment Variables: Create a .env file in the root directory and configure your local PostgreSQL credentials:**
   Code snippet

   DB_NAME=vertex_fit_db
   DB_USER=postgres
   DB_PASSWORD=your_master_password
   DB_HOST=127.0.0.1
   DB_PORT=5432
   SECRET_KEY=your_django_secret_key
   DEBUG=True

5. **Run Migrations:**
   ```bash
   python manage.py migrate
   ```
