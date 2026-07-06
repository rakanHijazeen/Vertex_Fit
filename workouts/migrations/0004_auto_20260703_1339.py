from django.db import migrations, models

def seed_master_exercise_matrix(apps, schema_editor):
    Exercise = apps.get_model('workouts', 'Exercise')
    
    # Standardizing all popular movements into our core tracking archetypes using Right-side nodes
    exercise_data = [
        # --- LOWER BODY (Hip Anchor: 24) ---
        {"name": "Squat", "anchor_joint": 24, "description": "Compound lower body movement focusing on quads, glutes, and hamstrings."},
        {"name": "Deadlift", "anchor_joint": 24, "description": "Posterior chain power movement tracking hip hinge displacement."},
        {"name": "Romanian Deadlift (RDL)", "anchor_joint": 24, "description": "Focused hamstring and glute eccentric loading."},
        {"name": "Leg Press", "anchor_joint": 24, "description": "Machine-based lower body press tracking hip/sled movement."},
        {"name": "Hip Thrust", "anchor_joint": 24, "description": "Glute isolation tracking pure vertical hip extension."},
        {"name": "Lunge", "anchor_joint": 24, "description": "Unilateral lower body tracking via dominant tracking hip side."},

        # --- UPPER BODY (Wrist Anchor: 16) ---
        {"name": "Bicep Curl", "anchor_joint": 16, "description": "Elbow flexion arm tracking via wrist path arc."},
        {"name": "Bench Press", "anchor_joint": 16, "description": "Horizontal pushing tracking bar velocity via wrist path."},
        {"name": "Overhead Press (OHP)", "anchor_joint": 16, "description": "Vertical shoulder pressing tracking complete arm lockout."},
        {"name": "Lateral Raise", "anchor_joint": 16, "description": "Shoulder abduction tracking wrist elevation arcs."},
        {"name": "Lat Pulldown", "anchor_joint": 16, "description": "Vertical pulling tracking downward vertical wrist travel."},
        {"name": "Cable Row", "anchor_joint": 16, "description": "Horizontal pulling tracking horizontal wrist displacement."},

        # --- CALISTHENICS / CORE (Shoulder Anchor: 12 / Wrist: 16) ---
        {"name": "Pull-Up", "anchor_joint": 12, "description": "Vertical body pulling tracking chest ascension relative to shoulder frame."},
        {"name": "Dip", "anchor_joint": 12, "description": "Tricep/chest calisthenic tracking shoulder height travel."},
        {"name": "Push-Up", "anchor_joint": 16, "description": "Horizontal body pressing tracking torso shifts relative to static hands."},
    ]
    
    for item in exercise_data:
        Exercise.objects.update_or_create(
            name=item["name"],
            defaults={
                "anchor_joint": item["anchor_joint"],
                "description": item["description"]
            }
        )

def rollback_master_matrix(apps, schema_editor):
    Exercise = apps.get_model('workouts', 'Exercise')
    # Clean rollback strategy if we ever migrate backwards
    Exercise.objects.all().delete()

class Migration(migrations.Migration):

    dependencies = [
        ('workouts', '0003_workoutsession_status'), # This matches your explicit initial step exactly
    ]

    operations = [
        # Step 1: Add the field structurally to PostgreSQL with a safe fallback default
        migrations.AddField(
            model_name='exercise',
            name='anchor_joint',
            field=models.IntegerField(default=24, help_text='MediaPipe keypoint node index tracking primary velocity shifts (e.g. 16=Wrist, 24=Hip)'),
        ),
        # Step 2: Automatically populate all the production exercise data rows
        migrations.RunPython(seed_master_exercise_matrix, rollback_master_matrix),
    ]