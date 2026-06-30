# Vertex Fit Backend

Vertex Fit is an AI-powered, computer-vision-assisted bodybuilding assistant engineered to bridge the gap between traditional workout logging and automated personal coaching[cite: 2]. The platform targets athletes and lifters looking to optimize execution mechanics by transforming standard mobile video recordings into actionable, millisecond-accurate biomechanical feedback[cite: 2].

By pairing a robust, relational data layer with state-of-the-art Video Language Models (VLMs), Vertex Fit eliminates the guesswork from compound movements (like Squats) and isolation movements (like Bicep Curls), ensuring users maintain optimal form, track true performance metrics, and reduce injury risks[cite: 2].

## 🚀 Key Core Features & Capabilities

- **Automated Form Analysis (VLM Integration):** Users upload video recordings of their sets directly from their mobile devices[cite: 2]. The backend pipelines these assets to a specialized vision intelligence engine to evaluate range of motion, eccentric/concentric speed, and postural breakdowns[cite: 2].
- **Intelligent Metrics Tracking:** Moving beyond simple numerical tallies, the platform captures contextual session execution data, storing comprehensive feedback blocks alongside validated rep counts[cite: 2].
- **Granular Physical Profiling:** Tracks dynamic user biological data over time, adapting to changing fitness goals (Bulking, Cutting, Maintenance) while offering a framework for customized progression tracking[cite: 2].
- **Production-Ready SaaS Foundations:** Built with commercial scalability in mind, incorporating secure premium tiers and subscription state mapping directly via webhook-ready infrastructure (Paddle integration)[cite: 2].

## 📈 Project Status: Phase 3 Complete

The core architectural database layer, secure authentication services, and the cloud-integrated video ingestion pipeline are fully operational.

- **Phase 1: Core Django Setup & Relational Database** `[COMPLETE]`
- **Phase 2: Stateless Authentication & User Management** `[COMPLETE]`
- **Phase 3: Multipart Video Handling & AWS S3 Integration** `[COMPLETE]`
- **Phase 4: Async Vision Model (VLM) Pipeline** `[IN PROGRESS]`

---

## 🛠️ Tech Stack & Architecture

- **Framework:** Django 5.0 & Django REST Framework (DRF)[cite: 2]
- **Database:** PostgreSQL 18 (Relational Storage)[cite: 2]
- **Cloud Storage & SDKs:** AWS S3, Boto3, Botocore
- **Authentication:** SimpleJWT (JSON Web Tokens)
- **Environment:** Python Virtual Environment (`venv`) with decoupled `.env` configurations[cite: 2]

---

## 📐 System Modules & Architecture

### 1. Core Database & Schema (Phase 1)

- **`User` Model:** Custom authentication transitions from username-based logins to a modern **Email-as-Username** configuration[cite: 2].
- **`Profile` Model:** Maps one-to-one with the User table to track localized physical metrics (`height`, `target_weight`), goals, and monetization states (`is_premium`, `paddle_subscription_id`)[cite: 2].
- **`Exercise` Model:** A static lookup directory for baseline physical movements (e.g., Squat, Bicep Curl)[cite: 2].
- **`WorkoutSession` Model:** A transactional log recording individual sets, capturing `rep_count`, an S3 cloud destination `video_url`, and a `vlm_feedback` text block[cite: 2].

### 2. Stateless Authentication & User Management (Phase 2)

- **JWT Endpoint Hookup:** Integrated `SimpleJWT` token pairs (access and refresh tokens) to handle application login states seamlessly across mobile/browser endpoints without traditional session cookies.
- **Atomic Registration Pipeline:** Built a robust registration workflow utilizing Django database transactions, guaranteeing that both the `User` record and its corresponding `UserProfile` are created simultaneously or rolled back atomically upon error.
- **Auth Testing Suite:** Mock endpoints verified via Postman client testing for absolute security across token-restricted resources.

### 3. Multipart Video Ingestion & Cloud Streaming (Phase 3)

- **Boto3 & S3 Engine Optimization:** Configured a secure `S3Service` leveraging Signature V4 signing and explicit virtual host addressing styles to force clean regional communication routes.
- **In-Memory File Processing:** Replaced heavy physical server disk staging by processing incoming multi-megabyte mobile files via DRF's `MultiPartParser`, streaming data directly to AWS S3 buckets to reduce server footprint and eliminate disk I/O operations.
- **Inline Streaming Delivery:** Forced browser-native inline video rendering by explicitly setting `ContentType` headers to `video/mp4` and applying `inline` content dispositions during bucket transfer. Secured real-time asset playback via region-locked, short-expiry pre-signed URLs.

---

## 💻 Local Setup & Installation

1. **Clone the repository:**

   ````bash
   git clone [https://github.com/rakanHijazeen/Vertex_Fit.git](https://github.com/rakanHijazeen/Vertex_Fit.git)
   cd Vertex_Fit
   ```[cite: 2]

   ````

2. **Initialize and activate the virtual environment:**

   ````bash
   python -m venv venv
   # On Windows (Git Bash):
   source venv/Scripts/activate
   ```[cite: 2]

   ````

3. **Install dependencies:**

   ````bash
   pip install -r requirements.txt
   ```[cite: 2]

   ````

4. **Environment Variables:**
   Create a `.env` file in the root directory and configure your credentials:

   ````env
   # Core Config
   SECRET_KEY=your_django_secret_key
   DEBUG=True

   # Database Config
   DB_NAME=vertex_fit_db
   DB_USER=postgres
   DB_PASSWORD=your_master_password
   DB_HOST=127.0.0.1
   DB_PORT=5432

   # AWS S3 Config
   AWS_ACCESS_KEY_ID=your_aws_access_key
   AWS_SECRET_ACCESS_KEY=your_aws_secret_key
   AWS_STORAGE_BUCKET_NAME=your_bucket_name
   AWS_S3_REGION_NAME=your_bucket_region
   ```[cite: 2]

   ````

5. **Run Migrations:**
   ````bash
   python manage.py migrate
   ```[cite: 2]
   ````
