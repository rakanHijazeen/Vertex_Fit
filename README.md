# Vertex Fit

Vertex Fit is an AI-powered fitness coaching platform that combines Django, computer vision, and multimodal language models to help users train with better form, safer execution, and more immediate feedback. The project now spans both asynchronous workout analysis and a live real-time coaching experience driven by the browser, Django Channels, and Gemini.

The system is designed to turn a simple camera feed into a coaching loop that can guide posture, tempo, and rep execution while maintaining a strong foundation for future mobile and web delivery.

---

## ✅ What Has Been Achieved So Far

### 1. Core Backend and User Platform

- **2-Phase Registration Pipeline**: Split the signup workflow into a multi-step onboarding system. Phase 1 validates core credentials (email, password, and indexed unique username), while Phase 2 captures physical and biometric profile metrics using interactive, Tailwind-styled components featuring silent client-side timezone detection.
- **Unified Identifier Authentication**: Upgraded the login flow to support both email addresses and custom usernames interchangeably from a single generic input field, handling validation case-insensitively.
- Built a Django-based backend with modular app structure for authentication and workouts.
- Added profile management for body metrics, fitness goals, and premium-related fields.
- Created workout session persistence for exercise tracking and AI feedback history.
- Expanded the profile schema to support demographic tracking fields including tracking **Gender** to drive highly personalized baseline physiological coaching recommendations.
- Robust Hybrid Authentication: Implemented a secure, hybrid authentication system that reconciles Django session-based security (for template-rendered pages) with JWT-based authentication (for API/WebSocket workflows). This includes dynamic secure-cookie handling, server-side **@login_required** route protection, and seamless token persistence via silent refresh patterns.

### 2. Unified Video Upload and Cloud Storage Pipeline

- **Dual-Mode Session Processing**: Fully integrated support for tracking workout sets through two distinct user pipelines:
  - **Live AI Coaching**: Captures and analyzes interactive device camera clips along with exact real-time rep counts mapped directly from active frontend state-machine trackers.
  - **Retroactive Video Uploads**: Allows instant file drops of pre-recorded sets from an administrative dashboard, dynamically skipping live metrics math and scaling cleanly as a standalone video review tool.
- Integrated AWS S3 for secure, fast video persistence and expiring pre-signed playback URL streaming.

### 3. Context-Aware AI Workout Analysis Engine (VLM)

- **Dynamic Context Prompting**: Powered by `gemini-2.5-flash` using a dynamic system instruction builder that adapts its structural guidelines depending on the tracking method (Live Coach vs. Pre-recorded Review).
- **Persistent Global Localization**: Implemented client-side caching (`localStorage`) to synchronize localized report targets across pages. The backend extracts choices automatically to generate full markdown feedback reviews matching the selected language profile (e.g., Arabic, English) seamlessly without schema bloat.
- **Adaptive Frontend Rendering**: Uses Django template tags (`{% if %}`) within a unified layout page to show performance badges dynamically while automatically omitting redundant metric layouts (like a hardcoded '0 Reps' indicator) for pre-recorded media files.

### 4. Live AI Coach (Real-Time Coaching Prototype)

- Implemented a real-time websocket coaching pipeline using Django Channels and Daphne.
- Connected the browser webcam to a live Gemini Live session over WebSocket.
- Added browser-side camera capture, frame streaming, and audio playback for live coaching feedback.
- Added MediaPipe-based pose estimation so the app can track body landmarks, draw skeletal lines, and display active joint information in real time.
- Implemented exercise-aware rep counting logic that tracks movement through a dynamic anchor joint and records rep totals during live sessions.
- The live coach now receives rep-count context during Phase 2 so its coaching can reference the current completed reps, and it can respond in both English and Arabic.
- Built a two-phase coaching experience:
  - Phase 1: initialization and setup guidance
  - Phase 2: live frame-based coaching after user readiness is confirmed
- Added frontend state transitions for connecting, preparing, and entering live coaching mode.

### 5. Frontend Coaching UI

- Developed a unified Workout History Dashboard that allows users to review past training metrics, track active sessions, or directly upload pre-recorded videos for retroactive AI analysis.
- Added a live workout tracker page with camera preview, coaching status, mode indicators, and rep count display.
- Implemented workflow buttons for starting the camera, beginning the set, stopping the live session, and opening the post-session analysis view.
- Overlaid pose landmarks and skeletal connection lines on the video feed to support form tracking and visual feedback.
- Wired the UI to the websocket-based coaching backend.
- The final action button now routes the user to a dedicated analysis page that displays the recorded set video alongside the Gemini VLM coaching breakdown and performance summary.

### 6. Context-Aware Personal AI Chat Engine

- **Deep Profile & Workout Ingestion**: Designed a data-compilation pipeline inside the chat service layer that dynamically pulls the user's active biometric profile (including the newly added **Gender** field, height, weight, and fitness goals) along with their **last 5 historical workout session reports** to feed directly into the Gemini system instructions.
- **Persistent Chat History & Session Caching**: Built a historical message recovery system using a dedicated REST API endpoint (`/api/workouts/chat/history/<thread_id>/`) paired with client-side `localStorage` caching to persist user thread IDs seamlessly across page refreshes.
- **Asynchronous Dual-Layer Communication**: Integrated WebSocket state machines to keep user chat workflows dynamic, real-time, and light on database threads.

---

## 🧱 Current Architecture

### Backend

- Django 5
- Django REST Framework
- Django Channels + Daphne for websocket support
- PostgreSQL for relational data storage
- Background task processing for async AI analysis

### AI / Vision

- Gemini multimodal models for workout analysis and live coaching
- MediaPipe-based pose tracking with landmark visualization and skeletal line drawing
- Exercise-aware dynamic rep counting using anchor joints and movement thresholds
- Structured prompts for biomechanical coaching and safety-oriented feedback
- Real-time frame streaming for live visual reasoning

### Storage and Media

- AWS S3 for workout video persistence
- Presigned URLs for secure media access
- Media handling prepared for future mobile-first delivery

---

## 🏗️ Main Modules

### Authentication

- Secure, unified authentication backend allowing users to sign in with either an exact case-insensitive username or email string.

- 2-Phase atomic onboarding pipeline separating credential tracking from deep profile physical data collection.

- Custom JWT token serializers that dynamically clear and remap input payloads matching SimpleJWT requirements.

- Decoupled runtime authentication backends declared within views to bypass premature application registry loading traps.

- Secure, hybrid Session/JWT persistence with dynamic cookie security management.

### Workouts

- Exercise registry and workout session data model
- Upload API for video-based workout submissions
- Playback and feedback APIs for session details
- Live tracker page for interactive coaching

### Live Coaching

- Websocket endpoint for live coaching sessions
- Browser camera + canvas frame streaming
- Gemini Live session orchestration with phase-based state handling
- Audio feedback playback for generated coaching responses

---

## 📊 Project Status

### Completed

- Core Django project scaffolding
- 2-Phase onboarding pipeline (Credential split from biometric/physical profiles)
- Single-input unified login identifier tracking (Email or Username)
- Workout session and exercise models
- S3 media upload pipeline
- VLM-based workout analysis pipeline
- Live websocket coach prototype with browser camera integration
- Real-time pose tracking with skeletal lines and landmark overlays
- Exercise-specific rep counting for live workout sessions
- Secure Auth Integration: Successfully transitioned to a unified authentication architecture, eliminating redirection loops, resolving CSRF/JWT conflicts, and implementing silent token refresh for persistent state across the platform.
- **Persistent, Context-Aware Conversational AI Chat**: Implemented a stateful personal chat engine featuring full historical message loading mechanics. The background pipeline dynamically injects user biometric parameters alongside their last 5 historical workout session reports directly into the LLM context for hyper-personalized coaching feedback.
- **Biometric Schema Expansion**: Added gender tracking attributes to the `Profile` authentication models, fully backed by active database schema migrations.

### In Progress / Active Focus

- Improving the reliability of Phase 2 coaching under live video input
- Reducing hallucinated coaching behavior when visual evidence is weak or blocked
- Strengthening prompt architecture and visual-grounding behavior for the live coach
- Tuning rep-count sensitivity and motion thresholds across exercises

---

## 🛠️ Tech Stack

- Python
- Django
- Django REST Framework
- Django Channels
- Daphne
- PostgreSQL
- boto3 / botocore
- Google Gemini APIs
- Tailwind-styled frontend templates and vanilla JavaScript

---

## ▶️ Local Setup

1. Clone the repository

   ```bash
   git clone https://github.com/rakanHijazeen/Vertex_Fit.git
   cd Vertex_Fit
   ```

2. Create and activate a virtual environment

   ```bash
   python -m venv venv
   source venv/Scripts/activate
   ```

3. Install dependencies

   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables
   Create a `.env` file with:

   ```env
   SECRET_KEY=your_secret_key
   DEBUG=True

   DB_NAME=vertex_fit_db
   DB_USER=postgres
   DB_PASSWORD=your_password
   DB_HOST=127.0.0.1
   DB_PORT=5432

   AWS_ACCESS_KEY_ID=your_aws_key
   AWS_SECRET_ACCESS_KEY=your_aws_secret
   AWS_STORAGE_BUCKET_NAME=your_bucket
   AWS_S3_REGION_NAME=your_region

   GEMINI_API_KEY=your_gemini_key
   ```

5. Run migrations

   ```bash
   python manage.py migrate
   ```

6. Start the app and background worker
   ```bash
   python manage.py runserver
   python manage.py process_tasks
   ```

---

## 🚀 Current Goal

The next milestone is to make the live coaching experience more dependable by tightening the visual grounding and reducing false-positive coaching during Phase 2. The system is already capable of connecting, streaming frames, and generating live responses, but the coaching logic still needs stronger safeguards to remain silent unless real visual evidence is present while continuing to improve rep-count accuracy across exercises.
